import os
from waitress import serve
from app import app
from utils.logger_setup import LoggerSetup

if __name__ == '__main__':
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # We can setup logger here again just in case, but app.py already does it
    logger = LoggerSetup.setup_app_logger()
    logger.info("Starting Waitress production server...")
    
    # Run the application with waitress instead of Werkzeug
    # threads=16 allows Waitress to handle many concurrent API calls
    # max_request_body_size=1073741824 explicitly allows up to 1GB uploads
    serve(app, host='0.0.0.0', port=5000, threads=16, max_request_body_size=1073741824)
