from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from config import Config
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    _instance = None
    _client = None
    _db = None
    _connected = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Don't auto-connect on initialization
        pass
    
    def connect(self):
        """Establish database connection with proper error handling"""
        if self._connected and self._client is not None:
            return self._db
            
        try:
            logger.info("Attempting to connect to MongoDB...")
            
            # Validate MONGO_URI
            if not Config.MONGO_URI:
                raise ValueError("MONGO_URI not found in environment variables")
            
            mongo_uri = Config.MONGO_URI
            logger.info(f"Using MongoDB URI: {mongo_uri[:50]}...")
            
            # Use TLS/certifi only for remote Atlas connections
            is_remote = mongo_uri.startswith('mongodb+srv') or 'mongodb.net' in mongo_uri
            
            client_kwargs = {
                'serverSelectionTimeoutMS': 3000,
                'connectTimeoutMS': 5000,
            }
            if is_remote:
                import certifi as _certifi
                client_kwargs['tlsCAFile'] = _certifi.where()
            
            self._client = MongoClient(mongo_uri, **client_kwargs)
            
            # Test connection
            self._client.admin.command('ping')
            
            # Get database name from config or URI
            db_name = getattr(Config, 'MONGO_DB_NAME', None)
            if not db_name:
                db_name = Config.MONGO_URI.split('/')[-1].split('?')[0]
            if not db_name:
                db_name = 'ai_examiner'
            
            self._db = self._client[db_name]
            self._connected = True
            logger.info(f"Successfully connected to MongoDB database: {db_name}")
            
            # Create indexes
            self._create_indexes()
            
            return self._db
            
        except OperationFailure as e:
            logger.error(f"MongoDB Authentication Failed: {e}")
            raise Exception(f"Database authentication failed: {e}")
            
        except (ConnectionFailure, Exception) as e:
            logger.warning(f"MongoDB not reachable ({e}). Falling back to in-memory mongomock.")
            return self._connect_mongomock()

    def _connect_mongomock(self):
        """Use mongomock as an in-memory fallback when real MongoDB is unavailable."""
        try:
            import mongomock
            self._client = mongomock.MongoClient()
            db_name = getattr(Config, 'MONGO_DB_NAME', 'ai_examiner') or 'ai_examiner'
            self._db = self._client[db_name]
            self._connected = True
            logger.info(
                f"⚠️  Using in-memory mongomock (data will NOT persist across restarts). "
                f"Start a real MongoDB at {getattr(Config, 'MONGO_URI', 'mongodb://localhost:27017/')} for persistence."
            )
            self._create_indexes()
            return self._db
        except ImportError:
            raise RuntimeError(
                "MongoDB is not reachable and mongomock is not installed. "
                "Either start MongoDB or install mongomock: pip install mongomock"
            )

    def _create_indexes(self):
        """Create indexes for better query performance"""
        try:
            # Teachers collection indexes
            self._db.teachers.create_index("email", unique=True)
            
            # Students collection indexes
            self._db.students.create_index("email", unique=True)
            
            # Evaluations collection indexes
            self._db.evaluations.create_index("student_id")
            self._db.evaluations.create_index("teacher_id")
            self._db.evaluations.create_index("created_at")
            self._db.evaluations.create_index([("created_at", -1)])
            
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
    
    def get_db(self):
        """Get database instance, connecting if necessary"""
        if not self._connected or self._db is None:
            return self.connect()
        return self._db
    
    def get_collection(self, collection_name):
        """Get specific collection"""
        db = self.get_db()
        return db[collection_name]
    
    def close(self):
        """Close database connection"""
        if self._client:
            self._client.close()
            logger.info("Database connection closed")


# Global database instance (lazy initialization)
db_connection = DatabaseConnection()

# Lazy database accessor
def get_database():
    """Get database instance with lazy connection"""
    return db_connection.get_db()

# For backward compatibility — connect at import time with graceful fallback
db = None

try:
    db = db_connection.connect()
except Exception as e:
    logger.warning(f"Database not connected at startup: {e}")
    logger.warning("Database will be connected on first use")
