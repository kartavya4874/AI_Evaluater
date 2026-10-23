import os
from dotenv import load_dotenv

# Load environment variables from .env file (only if it exists)
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    # In production, environment variables should be set directly
    load_dotenv()

def positive_int(name, default):
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be a positive integer') from None
    if value <= 0:
        raise ValueError(f'{name} must be a positive integer')
    return value


class Config:
    APP_ENV = os.getenv('APP_ENV', 'development')
    # Read comma separated list of keys (fallback to single key if that's what's currently there)
    _keys_str = os.getenv('GEMINI_API_KEYS', os.getenv('GEMINI_API_KEY', ''))
    GEMINI_API_KEYS = [k.strip() for k in _keys_str.split(',')] if _keys_str else []
    
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 1024 * 1024 * 1024)) # 1 GB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
    
    # MongoDB Configuration
    MONGO_URI = os.getenv('MONGO_URI')
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'ai_examiner')  
    MONGO_SERVER_SELECTION_TIMEOUT_MS = positive_int('MONGO_SERVER_SELECTION_TIMEOUT_MS', 3000)
    MONGO_CONNECT_TIMEOUT_MS = positive_int('MONGO_CONNECT_TIMEOUT_MS', 5000)
    MONGO_SOCKET_TIMEOUT_MS = positive_int('MONGO_SOCKET_TIMEOUT_MS', 30000)
    MONGO_WAIT_QUEUE_TIMEOUT_MS = positive_int('MONGO_WAIT_QUEUE_TIMEOUT_MS', 10000)
    VLLM_TIMEOUT_SECONDS = positive_int('VLLM_TIMEOUT_SECONDS', 600)
    VLLM_CONNECT_TIMEOUT_SECONDS = positive_int('VLLM_CONNECT_TIMEOUT_SECONDS', 60)
    VLLM_TOKENIZE_TIMEOUT_SECONDS = positive_int('VLLM_TOKENIZE_TIMEOUT_SECONDS', 30)
    VLLM_REQUEST_ATTEMPTS = positive_int('VLLM_REQUEST_ATTEMPTS', 2)
    VLLM_RETRY_MIN_SECONDS = positive_int('VLLM_RETRY_MIN_SECONDS', 3)
    VLLM_RETRY_MAX_SECONDS = positive_int('VLLM_RETRY_MAX_SECONDS', 15)
    WORKER_RECOVERY_SECONDS = positive_int('WORKER_RECOVERY_SECONDS', 5)
    if VLLM_RETRY_MAX_SECONDS < VLLM_RETRY_MIN_SECONDS:
        raise ValueError('VLLM_RETRY_MAX_SECONDS must be at least VLLM_RETRY_MIN_SECONDS')
    
    # Batch processing configuration
    BATCH_PROCESSING_MAX_WORKERS = int(os.getenv('BATCH_PROCESSING_MAX_WORKERS', '3'))
    VLLM_MAX_CONCURRENT_REQUESTS = int(os.getenv('VLLM_MAX_CONCURRENT_REQUESTS', str(BATCH_PROCESSING_MAX_WORKERS)))
    if not 1 <= BATCH_PROCESSING_MAX_WORKERS <= 5 or not 1 <= VLLM_MAX_CONCURRENT_REQUESTS <= 5:
        raise ValueError('Evaluation and AI concurrency must be between 1 and 5')
    BATCH_PROCESSING_TIMEOUT = int(os.getenv('BATCH_PROCESSING_TIMEOUT', '3600'))  # seconds
    CONFIG_FILE_NAME = 'config.json'
    
    # Authentication
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'ai-examiner-secret-key-change-in-production')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@aiexaminer.com')
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123')
    if APP_ENV == 'production' and (len(JWT_SECRET_KEY) < 32 or
            JWT_SECRET_KEY == 'ai-examiner-secret-key-change-in-production' or not GOOGLE_CLIENT_ID):
        raise ValueError('Production requires a strong JWT_SECRET_KEY and GOOGLE_CLIENT_ID')
    
    # Batch upload folder (for folder uploads from browser)
    BATCH_UPLOAD_FOLDER = os.getenv('BATCH_UPLOAD_FOLDER', 'batch_uploads')
    
    @staticmethod
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
