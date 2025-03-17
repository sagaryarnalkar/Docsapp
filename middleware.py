"""
Middleware Module
----------------
This module contains middleware functions for the Flask application.
"""

from flask import request, g
import time
import os
import traceback
from utils.logger import get_logger

# Set up logger
logger = get_logger(__name__)

def setup_middleware(app):
    """
    Set up middleware for the Flask application.
    
    Args:
        app: The Flask application
    """
    
    @app.before_request
    def before_request():
        """
        Middleware executed before each request.
        Sets up request timing and logging.
        """
        g.start_time = time.time()
        
        # Log request details
        if request.path != '/health':  # Skip logging for health checks
            logger.info(f"Request: {request.method} {request.path}")
            if request.json:
                logger.debug(f"Request JSON: {request.json}")
    
    @app.after_request
    def after_request(response):
        """
        Middleware executed after each request.
        Logs response timing and status.
        
        Args:
            response: The Flask response object
            
        Returns:
            The response object
        """
        if hasattr(g, 'start_time'):
            elapsed_time = time.time() - g.start_time
            
            # Log response details
            if request.path != '/health':  # Skip logging for health checks
                logger.info(f"Response: {request.method} {request.path} - Status: {response.status_code} - Time: {elapsed_time:.4f}s")
        
        return response

    @app.errorhandler(Exception)
    def handle_exception(e):
        """
        Global exception handler.
        Logs exceptions and returns an appropriate response.
        
        Args:
            e: The exception that was raised
            
        Returns:
            Error response
        """
        # Log the exception
        logger.error(f"Unhandled exception: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return error response
        return {
            "error": "Internal server error",
            "message": str(e) if os.getenv("FLASK_ENV") == "development" else "An unexpected error occurred"
        }, 500 