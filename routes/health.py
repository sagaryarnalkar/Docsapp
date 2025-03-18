"""
Health Routes
-----------
This module provides health check and monitoring endpoints for the DocsApp application.
These endpoints are used by monitoring systems to check the health of the application.
"""

import os
import logging
import platform
from datetime import datetime
from flask import Blueprint, jsonify, current_app
from models.database import get_session
from sqlalchemy import text

# Create a blueprint for health routes
health_bp = Blueprint('health', __name__)

logger = logging.getLogger(__name__)

@health_bp.route('/health')
def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON response with health status
    """
    return jsonify({
        "status": "healthy",
        "version": current_app.config.get('VERSION', 'unknown'),
        "timestamp": datetime.now().isoformat()
    }), 200

@health_bp.route('/health/detailed')
def detailed_health_check():
    """
    Detailed health check endpoint.
    
    Returns:
        JSON response with detailed health information
    """
    # Check database connection
    db_status = "healthy"
    db_error = None
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
    except Exception as e:
        db_status = "unhealthy"
        db_error = str(e)
        logger.error(f"Database health check failed: {str(e)}")
    
    # Check Redis connection if available
    redis_status = "not_configured"
    redis_error = None
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        try:
            import redis
            redis_client = redis.Redis.from_url(
                redis_url,
                socket_timeout=2,
                socket_connect_timeout=2,
                decode_responses=True
            )
            redis_client.ping()
            redis_status = "healthy"
        except Exception as e:
            redis_status = "unhealthy"
            redis_error = str(e)
            logger.error(f"Redis health check failed: {str(e)}")
    
    # Get system information
    system_info = {
        "os": platform.system(),
        "python_version": platform.python_version(),
        "hostname": platform.node()
    }
    
    return jsonify({
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": current_app.config.get('VERSION', 'unknown'),
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": {
                "status": db_status,
                "error": db_error
            },
            "redis": {
                "status": redis_status,
                "error": redis_error
            }
        },
        "system": system_info
    }), 200

def register_health_routes(app):
    """
    Register health routes with the Flask application.
    
    Args:
        app: The Flask application
    """
    app.register_blueprint(health_bp) 