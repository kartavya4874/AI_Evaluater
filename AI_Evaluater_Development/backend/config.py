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
    # ── vLLM / OpenAI-compatible backend (primary) ──────────────────────────
    VLLM_BASE_URL = os.getenv('VLLM_BASE_URL', 'http://localhost:8000/v1')
    VLLM_MODEL    = os.getenv('VLLM_MODEL', 'google/gemma-4-31B-it')
    VLLM_API_KEY  = os.getenv('VLLM_API_KEY', 'EMPTY')

    # ── Legacy Gemini / DeepSeek keys (kept for backwards-compat, unused) ────
    _keys_str = os.getenv('GEMINI_API_KEYS', os.getenv('GEMINI_API_KEY', ''))
    GEMINI_API_KEYS = [k.strip() for k in _keys_str.split(',')] if _keys_str else []
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')

    # ── File uploads ─────────────────────────────────────────────────────────
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 1024 * 1024 * 1024))  # 1 GB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URI    = os.getenv('MONGO_URI')
    MONGO_DB_NAME = os.getenv('MONGO_DB_NAME', 'ai_examiner')

    # ── Batch processing ──────────────────────────────────────────────────────
    BATCH_PROCESSING_MAX_WORKERS = int(os.getenv('BATCH_PROCESSING_MAX_WORKERS', '3'))
    BATCH_PROCESSING_TIMEOUT     = int(os.getenv('BATCH_PROCESSING_TIMEOUT', '3600'))
    CONFIG_FILE_NAME = 'config.json'

    # ── Authentication ────────────────────────────────────────────────────────
    JWT_SECRET_KEY  = os.getenv('JWT_SECRET_KEY', 'ai-examiner-secret-key-change-in-production')
    ADMIN_EMAIL     = os.getenv('ADMIN_EMAIL', 'admin@aiexaminer.com')
    ADMIN_PASSWORD  = os.getenv('ADMIN_PASSWORD', 'admin123')

    # ── Batch upload ──────────────────────────────────────────────────────────
    BATCH_UPLOAD_FOLDER = os.getenv('BATCH_UPLOAD_FOLDER', 'batch_uploads')

    @staticmethod
    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
