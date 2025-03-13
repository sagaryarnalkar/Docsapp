"""
WhatsApp Redis Deduplication Manager
----------------------------------
This module handles deduplication of WhatsApp messages and document processing
using Redis for persistent storage across application restarts and multiple instances.
"""

import time
import logging
import json
import os
from datetime import datetime, timedelta
import redis
from .deduplication import DeduplicationManager

logger = logging.getLogger(__name__)

class RedisDeduplicationManager:
    """
    Manages deduplication of messages and document processing using Redis.
    
    This class is responsible for:
    1. Tracking processed messages to prevent duplicate processing
    2. Tracking processed documents to prevent duplicate processing
    3. Tracking documents currently being processed
    4. Cleaning up old tracking data to prevent memory leaks
    
    All data is stored in Redis for persistence across application restarts
    and to support multiple application instances.
    """
    
    def __init__(self, redis_url=None):
        """
        Initialize the Redis deduplication manager.
        
        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL environment variable)
        """
        self.redis_url = redis_url or os.environ.get('REDIS_URL')
        self.redis = None
        self.fallback = None
        self.last_cleanup_time = time.time()
        
        # Try to connect to Redis
        self._connect_to_redis()
        
        # If Redis connection failed, use in-memory fallback
        if self.redis is None:
            logger.warning("Redis connection failed, using in-memory fallback")
            self.fallback = DeduplicationManager()
    
    def _connect_to_redis(self):
        """Attempt to connect to Redis"""
        if not self.redis_url:
            logger.warning("No Redis URL provided, using in-memory fallback")
            return
            
        try:
            # Parse Redis URL to extract connection details
            if self.redis_url.startswith('redis://'):
                # Standard Redis URL
                self.redis = redis.Redis.from_url(
                    self.redis_url,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                    retry_on_timeout=True,
                    decode_responses=True  # Automatically decode responses to strings
                )
            else:
                # Handle other formats or direct connection details
                self.redis = redis.Redis(
                    host=os.environ.get('REDIS_HOST', 'localhost'),
                    port=int(os.environ.get('REDIS_PORT', 6379)),
                    password=os.environ.get('REDIS_PASSWORD', None),
                    socket_timeout=2,
                    socket_connect_timeout=2,
                    retry_on_timeout=True,
                    decode_responses=True
                )
                
            # Test connection
            self.redis.ping()
            logger.info("Successfully connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            self.redis = None
    
    def is_duplicate_message(self, from_number, message_id):
        """
        Check if a message is a duplicate.
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            
        Returns:
            bool: True if the message is a duplicate, False otherwise
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            return self.fallback.is_duplicate_message(from_number, message_id)
            
        # Create a more robust message key that includes the from_number
        message_key = f"{from_number}:{message_id}"
        current_time = int(time.time())
        
        # Check both the combined key and the message_id for backward compatibility
        combined_key_exists = self.redis.exists(f"msg:{message_key}")
        message_id_exists = self.redis.exists(f"msg:{message_id}")
        
        if combined_key_exists or message_id_exists:
            # Get the timestamp when the message was processed
            timestamp = None
            if combined_key_exists:
                timestamp = int(self.redis.get(f"msg:{message_key}") or 0)
            elif message_id_exists:
                timestamp = int(self.redis.get(f"msg:{message_id}") or 0)
                
            time_since_processed = current_time - timestamp
            logger.info(f"Skipping duplicate message processing for message ID {message_id} "
                      f"from {from_number} (processed {time_since_processed}s ago)")
            return True
        
        # Mark this message as being processed with both keys
        # Set expiration to 10 minutes (600 seconds)
        self.redis.set(f"msg:{message_key}", current_time, ex=600)
        self.redis.set(f"msg:{message_id}", current_time, ex=600)
        logger.info(f"Processing new message {message_id} from {from_number}")
        return False
        
    def is_duplicate_document(self, from_number, doc_id):
        """
        Check if a document is a duplicate.
        
        Args:
            from_number: The sender's phone number
            doc_id: The document ID
            
        Returns:
            bool: True if the document is a duplicate, False otherwise
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            return self.fallback.is_duplicate_document(from_number, doc_id)
            
        if not doc_id:
            return False
            
        current_time = int(time.time())
        
        # Create a unique key for this document and user
        doc_user_key = f"{from_number}:{doc_id}"
        
        # Check if we've processed this document recently
        doc_user_exists = self.redis.exists(f"doc:{doc_user_key}")
        doc_exists = self.redis.exists(f"doc:{doc_id}")
        
        if doc_user_exists or doc_exists:
            # Get the timestamp when the document was processed
            timestamp = None
            if doc_user_exists:
                timestamp = int(self.redis.get(f"doc:{doc_user_key}") or 0)
            elif doc_exists:
                timestamp = int(self.redis.get(f"doc:{doc_id}") or 0)
                
            time_since_processed = current_time - timestamp
            logger.info(f"Skipping duplicate document processing for {doc_id} "
                      f"(processed {time_since_processed}s ago)")
            return True
            
        # Mark this document as being processed for this user
        # Set expiration to 30 minutes (1800 seconds)
        self.redis.set(f"doc:{doc_user_key}", current_time, ex=1800)
        self.redis.set(f"doc:{doc_id}", current_time, ex=1800)
        return False
        
    def is_document_processing(self, from_number, file_id):
        """
        Check if a document is currently being processed.
        
        Args:
            from_number: The sender's phone number
            file_id: The file ID
            
        Returns:
            bool: True if the document is currently being processed, False otherwise
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            return self.fallback.is_document_processing(from_number, file_id)
            
        if not file_id:
            return False
            
        # Create a unique key for tracking this document processing
        processing_key = f"processing:{from_number}:{file_id}"
        
        # Check if this document is already being processed
        if self.redis.exists(processing_key):
            timestamp = int(self.redis.get(processing_key) or 0)
            time_since_started = int(time.time()) - timestamp
            logger.info(f"Document {file_id} is already being processed "
                      f"(started {time_since_started}s ago)")
            return True
            
        return False
        
    def mark_document_processing(self, from_number, file_id):
        """
        Mark a document as currently being processed.
        
        Args:
            from_number: The sender's phone number
            file_id: The file ID
            
        Returns:
            str: The processing key for this document
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            return self.fallback.mark_document_processing(from_number, file_id)
            
        if not file_id:
            return None
            
        # Create a unique key for tracking this document processing
        processing_key = f"processing:{from_number}:{file_id}"
        
        # Mark as processing to avoid duplicate processing
        # Set expiration to 2 hours (7200 seconds)
        self.redis.set(processing_key, int(time.time()), ex=7200)
        return processing_key
        
    def mark_document_processed(self, processing_key):
        """
        Mark a document as processed (no longer being processed).
        
        Args:
            processing_key: The processing key for this document
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            return self.fallback.mark_document_processed(processing_key)
            
        if processing_key and self.redis.exists(processing_key):
            self.redis.delete(processing_key)
            
    def track_message_type(self, doc_id, message_type, from_number=None):
        """
        Track a message type for a document to prevent duplicate notifications.
        
        Args:
            doc_id: The document ID
            message_type: The type of message (e.g., 'stored', 'processing_started')
            from_number: The sender's phone number (optional)
            
        Returns:
            bool: True if this message type was already tracked, False otherwise
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            if hasattr(self.fallback, '_is_duplicate_by_global_tracking'):
                return self.fallback._is_duplicate_by_global_tracking(doc_id, message_type)
            return False
            
        if not doc_id:
            return False
            
        # Create a unique key for this document and message type
        tracking_key = f"track:{doc_id}:{message_type}"
        if from_number:
            tracking_key = f"track:{from_number}:{doc_id}:{message_type}"
            
        # Check if this message type has already been tracked
        if self.redis.exists(tracking_key):
            timestamp = int(self.redis.get(tracking_key) or 0)
            time_since_tracked = int(time.time()) - timestamp
            logger.info(f"Message type '{message_type}' for document {doc_id} "
                      f"already tracked {time_since_tracked}s ago")
            return True
            
        # Mark this message type as tracked
        # Set expiration based on message type
        expiration = 600  # Default: 10 minutes
        if message_type == 'stored':
            expiration = 1800  # 30 minutes
        elif message_type == 'processing_started':
            expiration = 3600  # 1 hour
        elif message_type == 'processing_completed':
            expiration = 86400  # 24 hours
            
        self.redis.set(tracking_key, int(time.time()), ex=expiration)
        return False
        
    def reset_message_tracking(self, doc_id, message_type, from_number=None):
        """
        Reset tracking for a specific message type.
        
        Args:
            doc_id: The document ID
            message_type: The type of message to reset
            from_number: The sender's phone number (optional)
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            return
            
        # Create a unique key for this document and message type
        tracking_key = f"track:{doc_id}:{message_type}"
        if from_number:
            tracking_key = f"track:{from_number}:{doc_id}:{message_type}"
            
        # Delete the tracking key
        self.redis.delete(tracking_key)
        
    def cleanup(self):
        """
        Clean up old tracking data to prevent memory leaks.
        
        This method doesn't need to do much with Redis since we use expiration.
        """
        # Redis handles expiration automatically, so we don't need to do much here
        # This method is mainly for compatibility with the in-memory implementation
        
        # Use fallback if Redis is not available
        if self.redis is None:
            return self.fallback.cleanup()
            
        # Only log periodically to avoid excessive logging
        current_time = time.time()
        if current_time - self.last_cleanup_time < 3600:  # 1 hour
            return
            
        logger.info("Redis deduplication manager performing periodic health check")
        try:
            # Just ping Redis to make sure it's still available
            self.redis.ping()
            logger.info("Redis connection is healthy")
        except Exception as e:
            logger.error(f"Redis connection error during cleanup: {str(e)}")
            # Try to reconnect
            self._connect_to_redis()
            
        self.last_cleanup_time = current_time 