"""
Logging Configuration
-------------------
This module provides logging configuration for the DocsApp application.
It sets up logging to both file and stdout with immediate flush.
"""

import os
import sys
import logging
from datetime import datetime
from config import BASE_DIR, LOG_DIR

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Set up file logging
log_file = os.path.join(LOG_DIR, 'docsapp.log')

class UnbufferedLogger:
    """
    A logger that ensures all output is immediately flushed to the stream.
    This is useful for debugging in production environments where buffering
    might delay log output.
    """
    def __init__(self, stream):
        """
        Initialize the unbuffered logger with a stream.
        
        Args:
            stream: The stream to write to (e.g., sys.stdout)
        """
        self.stream = stream
        
    def write(self, data):
        """
        Write data to the stream and flush immediately.
        
        Args:
            data: The data to write
        """
        self.stream.write(data)
        self.stream.flush()
        
    def writelines(self, datas):
        """
        Write multiple lines to the stream and flush immediately.
        
        Args:
            datas: The lines to write
        """
        self.stream.writelines(datas)
        self.stream.flush()
        
    def __getattr__(self, attr):
        """
        Delegate attribute access to the underlying stream.
        
        Args:
            attr: The attribute name
            
        Returns:
            The attribute from the underlying stream
        """
        return getattr(self.stream, attr)

def setup_logging(app_version):
    """
    Set up logging for the application.
    
    Args:
        app_version: The application version string
        
    Returns:
        logger: The configured logger
    """
    # Configure logging to both file and stdout
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(UnbufferedLogger(sys.stdout))
        ]
    )
    
    # Get the root logger
    logger = logging.getLogger()
    
    # Log application startup
    logger.info("="*50)
    logger.info(f"STARTING DOCSAPP SERVER VERSION {app_version}")
    logger.info(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*50)
    
    # Add direct stdout logging for critical debug info
    print("=== Application Starting ===")
    print(f"Log file location: {log_file}")
    print(f"Application version: {app_version}")
    
    return logger

def log_debug(message):
    """
    Log a debug message with timestamp.
    
    Args:
        message: The message to log
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[DEBUG {timestamp}] {message}") 