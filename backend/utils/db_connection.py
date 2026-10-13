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
        pass
    
    def connect(self):
        """Establish database connection with graceful fallback"""
        if self._connected and self._client is not None:
            return self._db
            
        try:
            logger.info("Attempting to connect to MongoDB...")
            mongo_uri = getattr(Config, 'MONGO_URI', None) or "mongodb://localhost:27017/"
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
            
            db_name = getattr(Config, 'MONGO_DB_NAME', 'ai_examiner') or 'ai_examiner'
            self._db = self._client[db_name]
            self._connected = True
            logger.info(f"Successfully connected to MongoDB database: {db_name}")
            
            self._create_indexes()
            return self._db
            
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
            logger.info("⚠️  Using in-memory mongomock database.")
            self._create_indexes()
            return self._db
        except ImportError:
            raise RuntimeError("MongoDB is not reachable and mongomock is not installed.")

    def _create_indexes(self):
        """Create indexes for better query performance"""
        try:
            self._db.teachers.create_index("email", unique=True)
            self._db.students.create_index("email", unique=True)
            self._db.evaluations.create_index("student_id")
            self._db.evaluations.create_index("teacher_id")
            self._db.evaluations.create_index("created_at")
            self._db.evaluations.create_index([("created_at", -1)])
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating indexes: {e}")
    
    def get_db(self):
        if not self._connected or self._db is None:
            return self.connect()
        return self._db
    
    def get_collection(self, collection_name):
        db = self.get_db()
        return db[collection_name]
    
    def close(self):
        if self._client:
            self._client.close()
            logger.info("Database connection closed")


# Global database instance
db_connection = DatabaseConnection()

def get_database():
    return db_connection.get_db()

db = None
try:
    db = db_connection.connect()
except Exception as e:
    logger.warning(f"Database not connected at startup: {e}")
