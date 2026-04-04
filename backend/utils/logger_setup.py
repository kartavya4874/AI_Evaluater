import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

class LoggerSetup:
    @staticmethod
    def setup_app_logger(log_dir="logs"):
        """Setup application-wide logging with both console and rotating file handlers."""
        os.makedirs(log_dir, exist_ok=True)
        
        # Get the root logger
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        
        # Remove any existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 1. Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # 2. File Handler (Rotates daily at midnight, keeps 30 days of logs)
        log_file_path = os.path.join(log_dir, 'ai_examiner.log')
        file_handler = TimedRotatingFileHandler(
            log_file_path, 
            when="midnight", 
            interval=1, 
            backupCount=30,
            encoding='utf-8'
        )
        # Suffix the rotated files with the date
        file_handler.suffix = "%Y-%m-%d"
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        logging.info("Logger initialized. Persistent audit logs are enabled.")
        return logger
