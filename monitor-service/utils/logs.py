import logging
from logging.handlers import RotatingFileHandler
import os

LOG_FILE_NAME = "system.log"

def InitializeLogging(name="AirspaceMonitor", log_path="", max_mb=50, backup_count=2):
    """
    Sets up a rolling logger that caps at max_mb and keeps backup_count old files.
    """
    log_path = os.path.join(log_path, LOG_FILE_NAME)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid adding multiple handlers.
    if not logger.handlers:
        
        # Convert megabytes to bytes
        max_bytes = max_mb * 1024 * 1024 
        
        file_handler = RotatingFileHandler(
            log_path, 
            maxBytes=max_bytes, 
            backupCount=backup_count
        )
        
        # Format the log output.
        # Prints the time, log level, log name, and message.
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

def GetLogger(childName: str):
    """
    Creates a child logger that inherits the file and console handlers 
    from the base 'AirspaceMonitor' logger.
    
    Usage: logger = GetLogger("FlightAware")
    """
    return logging.getLogger(f"AirspaceMonitor.{childName}")