"""
WhatsApp Message Deduplication Helper
------------------------------------
This module provides helper functions for working with the WhatsApp message
deduplication system, particularly for debugging purposes.
"""

import os
import redis
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

def get_redis_client():
    """
    Get a Redis client instance from the REDIS_URL environment variable.
    
    Returns:
        redis.Redis: A Redis client instance, or None if Redis is not configured
    """
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url:
        logger.warning("No REDIS_URL found in environment variables")
        return None
        
    try:
        redis_client = redis.Redis.from_url(
            redis_url,
            socket_timeout=2,
            socket_connect_timeout=2,
            decode_responses=True
        )
        # Test connection
        redis_client.ping()
        return redis_client
    except Exception as e:
        logger.error(f"Error connecting to Redis: {str(e)}")
        return None

def is_duplicate_message(message_id, from_number, message_type=None):
    """
    Check if a message is a duplicate by directly querying Redis.
    
    Args:
        message_id: The WhatsApp message ID
        from_number: The sender's phone number
        message_type: Optional type of message (e.g., "list_command")
        
    Returns:
        bool: True if the message is a duplicate, False otherwise
        dict: Additional information about the check
    """
    # TEMPORARY FIX: Disable deduplication for ALL messages
    logger.info(f"TEMPORARY FIX: DEDUPLICATION DISABLED FOR ALL MESSAGES IN MESSAGE_DEDUPLICATION")
    return False, {"reason": "Deduplication temporarily disabled"}
    
    # The code below is temporarily disabled
    """
    redis_client = get_redis_client()
    if not redis_client:
        logger.warning("Redis not available for deduplication check")
        return False, {"error": "Redis not available"}
    
    # Create a more robust message key that includes the from_number
    message_key = f"{from_number}:{message_id}"
    current_time = int(time.time())
    
    # Debug logging
    logger.info(f"DEDUPLICATION CHECK - Message ID: {message_id}")
    logger.info(f"From: {from_number}")
    logger.info(f"Key: {message_key}")
    logger.info(f"Message Type: {message_type}")
    
    # Special handling for command responses - NEVER deduplicate these
    if message_type in ["list_command", "help_command", "find_command", "ask_command"]:
        logger.info(f"Message is a {message_type} response - BYPASSING DEDUPLICATION")
        # Still track it for debugging purposes
        redis_client.set(f"whatsapp:cmd:{message_key}", current_time, ex=600)
        return False, {"reason": f"Command response ({message_type}) bypass"}
    
    # Check both the combined key and the message_id for backward compatibility
    combined_key = f"whatsapp:msg:{message_key}"
    message_id_key = f"whatsapp:msg:{message_id}"
    
    combined_key_exists = redis_client.exists(combined_key)
    message_id_exists = redis_client.exists(message_id_key)
    
    result = {
        "combined_key": combined_key,
        "message_id_key": message_id_key,
        "combined_key_exists": combined_key_exists,
        "message_id_exists": message_id_exists,
        "timestamp": current_time,
        "check_time": datetime.now().isoformat()
    }
    
    # Debug logging for key existence
    if combined_key_exists:
        timestamp = int(redis_client.get(combined_key) or 0)
        time_since_processed = current_time - timestamp
        logger.info(f"Combined key exists: {combined_key}, processed {time_since_processed}s ago")
        result["combined_key_timestamp"] = timestamp
        result["combined_key_age"] = time_since_processed
    
    if message_id_exists:
        timestamp = int(redis_client.get(message_id_key) or 0)
        time_since_processed = current_time - timestamp
        logger.info(f"Message ID key exists: {message_id_key}, processed {time_since_processed}s ago")
        result["message_id_timestamp"] = timestamp
        result["message_id_age"] = time_since_processed
    
    if combined_key_exists or message_id_exists:
        # Get the timestamp when the message was processed
        timestamp = None
        if combined_key_exists:
            timestamp = int(redis_client.get(combined_key) or 0)
        elif message_id_exists:
            timestamp = int(redis_client.get(message_id_key) or 0)
            
        time_since_processed = current_time - timestamp
        logger.info(f"DUPLICATE DETECTED: Message ID {message_id} from {from_number} (processed {time_since_processed}s ago)")
        result["is_duplicate"] = True
        result["reason"] = f"Message processed {time_since_processed}s ago"
        return True, result
    
    # Mark this message as being processed with both keys
    # Set expiration to 10 minutes (600 seconds)
    redis_client.set(combined_key, current_time, ex=600)
    redis_client.set(message_id_key, current_time, ex=600)
    """
    
    return False, {"reason": "New message"} 