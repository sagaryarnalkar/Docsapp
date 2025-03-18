"""
Startup Checks
------------
This module provides functions to check the health of external services
during application startup, such as database and Redis connections.
"""

import os
import logging
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from models.database import get_session, get_database_url, migrate_sqlite_to_postgres

logger = logging.getLogger(__name__)

def check_database_connection():
    """
    Check the database connection and attempt migration if needed.
    
    Returns:
        bool: True if the connection is successful, False otherwise
    """
    print("\n=== Checking Database Connection ===")
    database_url = get_database_url()
    print(f"Database URL: {database_url.split('@')[1] if '@' in database_url else database_url}")
    
    try:
        # Test database connection
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        print("✅ Database connection successful")
        
        # Try to run migration if needed
        try:
            migrate_sqlite_to_postgres()
        except Exception as e:
            print(f"⚠️ Migration attempt failed: {str(e)}")
            logger.warning(f"Migration attempt failed: {str(e)}")
        
        return True
    except OperationalError as e:
        print(f"❌ Database connection failed: {str(e)}")
        logger.error(f"Database connection failed: {str(e)}")
        print("Application will continue with fallback to SQLite if available")
        return False
    except Exception as e:
        print(f"❌ Unexpected database error: {str(e)}")
        logger.error(f"Unexpected database error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return False

def check_redis_connection():
    """
    Check the Redis connection.
    
    Returns:
        bool: True if the connection is successful, False otherwise
    """
    print("\n=== Checking Redis Connection ===")
    redis_url = os.environ.get('REDIS_URL')
    
    if not redis_url:
        print("⚠️ No Redis URL provided, will use in-memory deduplication")
        logger.warning("No Redis URL provided, will use in-memory deduplication")
        return False
    
    try:
        import redis
        redis_client = redis.Redis.from_url(
            redis_url,
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=True
        )
        redis_client.ping()
        print(f"✅ Redis connection successful: {redis_url.split('@')[1] if '@' in redis_url else 'redis://localhost'}")
        logger.info("Redis connection successful")
        return True
    except ImportError:
        print("⚠️ Redis package not installed, will use in-memory deduplication")
        logger.warning("Redis package not installed, will use in-memory deduplication")
        return False
    except Exception as e:
        print(f"❌ Redis connection failed: {str(e)}")
        logger.error(f"Redis connection failed: {str(e)}")
        print("Application will continue with in-memory deduplication")
        return False

def run_startup_checks():
    """
    Run all startup checks.
    
    Returns:
        dict: A dictionary with the results of each check
    """
    results = {
        'database': check_database_connection(),
        'redis': check_redis_connection()
    }
    
    # Log overall status
    if all(results.values()):
        logger.info("All startup checks passed")
    else:
        logger.warning("Some startup checks failed, but application will continue with fallbacks")
        
    return results 