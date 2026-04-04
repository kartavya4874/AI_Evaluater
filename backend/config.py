import os
from dotenv import load_dotenv

# Load environment variables from .env file (only if it exists)
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    # In production, environment variables should be set directly
    load_dotenv()

class Config:
    # Read comma separated list of keys (fallback to single key if that's what's currently there)
    _keys_str = os.getenv('GEMINI_API_KEYS', os.getenv('GEMINI_API_KEY', ''))
    GEMINI_API_KEYS = [k.strip() for k in _keys_str.split(',')] if _keys_str else []
    
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 16 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
    
    # MongoDB Configuration
    MONGO_URI = os.getenv('MONGO_URI')
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'ai_examiner')  
    
    # Batch processing configuration
    BATCH_PROCESSING_MAX_WORKERS = int(os.getenv('BATCH_PROCESSING_MAX_WORKERS', '3'))
    BATCH_PROCESSING_TIMEOUT = int(os.getenv('BATCH_PROCESSING_TIMEOUT', '3600'))  # seconds
    CONFIG_FILE_NAME = 'config.json'
    
    @staticmethod
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
