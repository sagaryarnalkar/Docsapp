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
        self.debug_mode = True  # Enable debug mode for detailed logging
        
        # Try to connect to Redis
        self._connect_to_redis()
        
        # If Redis connection failed, use in-memory fallback
        if self.redis is None:
            logger.warning("Redis connection failed, using in-memory fallback")
            self.fallback = DeduplicationManager()
        else:
            # Log Redis connection details
            logger.info(f"[DEBUG] Connected to Redis at {self.redis_url}")
            try:
                info = self.redis.info()
                logger.info(f"[DEBUG] Redis version: {info.get('redis_version')}")
                logger.info(f"[DEBUG] Redis memory used: {info.get('used_memory_human')}")
                logger.info(f"[DEBUG] Redis connected clients: {info.get('connected_clients')}")
            except Exception as e:
                logger.error(f"[DEBUG] Error getting Redis info: {str(e)}")
    
    def _connect_to_redis(self):
        """Attempt to connect to Redis"""
        if not self.redis_url:
            logger.warning("No Redis URL provided, using in-memory fallback")
            return
            
        try:
            # Parse Redis URL to extract connection details
            if self.redis_url.startswith('redis://'):
                # Standard Redis URL
                logger.info(f"[DEBUG] Connecting to Redis with URL: {self.redis_url}")
                self.redis = redis.Redis.from_url(
                    self.redis_url,
                    socket_timeout=2,
                    socket_connect_timeout=2,
                    retry_on_timeout=True,
                    decode_responses=True  # Automatically decode responses to strings
                )
            else:
                # Handle other formats or direct connection details
                logger.info(f"[DEBUG] Connecting to Redis with host/port configuration")
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
            logger.info("[DEBUG] Successfully connected to Redis")
        except Exception as e:
            logger.error(f"[DEBUG] Failed to connect to Redis: {str(e)}")
            self.redis = None
    
    def is_duplicate_message(self, from_number, message_id, message_type=None):
        """
        Check if a message is a duplicate.
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            message_type: Optional type of message (e.g., "list_command")
            
        Returns:
            bool: True if the message is a duplicate, False otherwise
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            result = self.fallback.is_duplicate_message(from_number, message_id)
            print(f"[DEBUG] Using fallback deduplication for message {message_id}: {result}")
            return result
            
        # Create a more robust message key that includes the from_number
        message_key = f"{from_number}:{message_id}"
        current_time = int(time.time())
        
        # Debug logging
        print(f"\n==================================================")
        print(f"[DEBUG] DEDUPLICATION CHECK - Message ID: {message_id}")
        print(f"[DEBUG] From: {from_number}")
        print(f"[DEBUG] Key: {message_key}")
        print(f"[DEBUG] Message Type: {message_type}")
        print(f"==================================================")
        
        # Special handling for command responses - NEVER deduplicate these
        if message_type in ["list_command", "help_command", "find_command", "ask_command"]:
            print(f"[DEBUG] Message is a {message_type} response - BYPASSING DEDUPLICATION")
            # Still track it for debugging purposes
            self.redis.set(f"cmd:{message_key}", current_time, ex=600)
            return False
        
        # Check both the combined key and the message_id for backward compatibility
        combined_key_exists = self.redis.exists(f"msg:{message_key}")
        message_id_exists = self.redis.exists(f"msg:{message_id}")
        
        # Debug logging for key existence
        if combined_key_exists:
            timestamp = int(self.redis.get(f"msg:{message_key}") or 0)
            time_since_processed = current_time - timestamp
            print(f"[DEBUG] Combined key exists: msg:{message_key}, processed {time_since_processed}s ago")
        
        if message_id_exists:
            timestamp = int(self.redis.get(f"msg:{message_id}") or 0)
            time_since_processed = current_time - timestamp
            print(f"[DEBUG] Message ID key exists: msg:{message_id}, processed {time_since_processed}s ago")
        
        if combined_key_exists or message_id_exists:
            # Get the timestamp when the message was processed
            timestamp = None
            if combined_key_exists:
                timestamp = int(self.redis.get(f"msg:{message_key}") or 0)
            elif message_id_exists:
                timestamp = int(self.redis.get(f"msg:{message_id}") or 0)
                
            time_since_processed = current_time - timestamp
            print(f"[DEBUG] DUPLICATE DETECTED: Message ID {message_id} from {from_number} (processed {time_since_processed}s ago)")
            return True
        
        # Mark this message as being processed with both keys
        # Set expiration to 10 minutes (600 seconds)
        self.redis.set(f"msg:{message_key}", current_time, ex=600)
        self.redis.set(f"msg:{message_id}", current_time, ex=600)
        print(f"[DEBUG] NEW MESSAGE: Processing message {message_id} from {from_number}")
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
            result = self.fallback.is_duplicate_document(from_number, doc_id)
            logger.info(f"[DEBUG] Using fallback deduplication for document {doc_id}: {result}")
            return result
            
        if not doc_id:
            logger.info("[DEBUG] No document ID provided, not a duplicate")
            return False
            
        current_time = int(time.time())
        
        # Create a unique key for this document and user
        doc_user_key = f"{from_number}:{doc_id}"
        
        # Debug logging
        logger.info(f"[DEBUG] Checking if document is duplicate - Key: {doc_user_key}")
        
        # Check if we've processed this document recently
        doc_user_exists = self.redis.exists(f"doc:{doc_user_key}")
        doc_exists = self.redis.exists(f"doc:{doc_id}")
        
        # Debug logging for key existence
        if doc_user_exists:
            timestamp = int(self.redis.get(f"doc:{doc_user_key}") or 0)
            time_since_processed = current_time - timestamp
            logger.info(f"[DEBUG] Document user key exists: doc:{doc_user_key}, processed {time_since_processed}s ago")
        
        if doc_exists:
            timestamp = int(self.redis.get(f"doc:{doc_id}") or 0)
            time_since_processed = current_time - timestamp
            logger.info(f"[DEBUG] Document ID key exists: doc:{doc_id}, processed {time_since_processed}s ago")
        
        if doc_user_exists or doc_exists:
            # Get the timestamp when the document was processed
            timestamp = None
            if doc_user_exists:
                timestamp = int(self.redis.get(f"doc:{doc_user_key}") or 0)
            elif doc_exists:
                timestamp = int(self.redis.get(f"doc:{doc_id}") or 0)
                
            time_since_processed = current_time - timestamp
            logger.info(f"[DEBUG] Skipping duplicate document processing for {doc_id} "
                      f"(processed {time_since_processed}s ago)")
            return True
            
        # Mark this document as being processed for this user
        # Set expiration to 30 minutes (1800 seconds)
        self.redis.set(f"doc:{doc_user_key}", current_time, ex=1800)
        self.redis.set(f"doc:{doc_id}", current_time, ex=1800)
        logger.info(f"[DEBUG] Processing new document {doc_id} for {from_number}")
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
            result = self.fallback.is_document_processing(from_number, file_id)
            logger.info(f"[DEBUG] Using fallback for document processing check {file_id}: {result}")
            return result
            
        if not file_id:
            logger.info("[DEBUG] No file ID provided, not being processed")
            return False
            
        # Create a unique key for tracking this document processing
        processing_key = f"processing:{from_number}:{file_id}"
        
        # Debug logging
        logger.info(f"[DEBUG] Checking if document is being processed - Key: {processing_key}")
        
        # Check if this document is already being processed
        if self.redis.exists(processing_key):
            timestamp = int(self.redis.get(processing_key) or 0)
            current_time = int(time.time())
            time_since_started = current_time - timestamp
            logger.info(f"[DEBUG] Document {file_id} is already being processed "
                      f"(started {time_since_started}s ago)")
            return True
            
        logger.info(f"[DEBUG] Document {file_id} is not currently being processed")
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
            result = self.fallback.mark_document_processing(from_number, file_id)
            logger.info(f"[DEBUG] Using fallback to mark document as processing {file_id}")
            return result
            
        # Create a unique key for tracking this document processing
        processing_key = f"processing:{from_number}:{file_id}"
        current_time = int(time.time())
        
        # Mark this document as being processed
        # Set expiration to 30 minutes (1800 seconds)
        self.redis.set(processing_key, current_time, ex=1800)
        logger.info(f"[DEBUG] Marked document {file_id} as being processed with key {processing_key}")
        
        return processing_key
        
    def mark_document_processed(self, processing_key):
        """
        Mark a document as processed (no longer being processed).
        
        Args:
            processing_key: The processing key for this document
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            self.fallback.mark_document_processed(processing_key)
            logger.info(f"[DEBUG] Using fallback to mark document as processed {processing_key}")
            return
            
        # Delete the processing key
        self.redis.delete(processing_key)
        logger.info(f"[DEBUG] Marked document as processed by deleting key {processing_key}")
        
    def track_message_type(self, doc_id, message_type, from_number=None):
        """
        Track a message type for a document to prevent duplicate notifications.
        
        Args:
            doc_id: The document ID
            message_type: The type of message (e.g., 'stored', 'processing', 'completed')
            from_number: The sender's phone number (optional)
            
        Returns:
            bool: True if this is a new message type for this document, False if it's a duplicate
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            logger.info(f"[DEBUG] Using fallback for message type tracking {doc_id}:{message_type}")
            # Fallback doesn't implement this method, so always return True
            return True
            
        if not doc_id or not message_type:
            logger.info("[DEBUG] Missing doc_id or message_type for tracking")
            return True
            
        current_time = int(time.time())
        
        # Create a unique key for this document and message type
        if from_number:
            tracking_key = f"track:{from_number}:{doc_id}:{message_type}"
        else:
            tracking_key = f"track:{doc_id}:{message_type}"
            
        # Debug logging
        logger.info(f"[DEBUG] Checking message type tracking - Key: {tracking_key}")
        
        # Check if we've sent this type of message for this document recently
        if self.redis.exists(tracking_key):
            timestamp = int(self.redis.get(tracking_key) or 0)
            time_since_sent = current_time - timestamp
            
            # Different expiration times for different message types
            if message_type == 'stored':
                # Storage confirmations expire after 5 minutes
                if time_since_sent < 300:
                    logger.info(f"[DEBUG] Skipping duplicate 'stored' message for {doc_id} "
                              f"(sent {time_since_sent}s ago)")
                    return False
            elif message_type == 'processing':
                # Processing notifications expire after 10 minutes
                if time_since_sent < 600:
                    logger.info(f"[DEBUG] Skipping duplicate 'processing' message for {doc_id} "
                              f"(sent {time_since_sent}s ago)")
                    return False
            elif message_type == 'completed' or message_type == 'error':
                # Completion and error notifications expire after 1 hour
                if time_since_sent < 3600:
                    logger.info(f"[DEBUG] Skipping duplicate '{message_type}' message for {doc_id} "
                              f"(sent {time_since_sent}s ago)")
                    return False
            else:
                # Other message types expire after 5 minutes
                if time_since_sent < 300:
                    logger.info(f"[DEBUG] Skipping duplicate '{message_type}' message for {doc_id} "
                              f"(sent {time_since_sent}s ago)")
                    return False
                    
        # Set expiration based on message type
        if message_type == 'stored':
            # Storage confirmations expire after 5 minutes
            self.redis.set(tracking_key, current_time, ex=300)
        elif message_type == 'processing':
            # Processing notifications expire after 10 minutes
            self.redis.set(tracking_key, current_time, ex=600)
        elif message_type == 'completed' or message_type == 'error':
            # Completion and error notifications expire after 1 hour
            self.redis.set(tracking_key, current_time, ex=3600)
        else:
            # Other message types expire after 5 minutes
            self.redis.set(tracking_key, current_time, ex=300)
            
        logger.info(f"[DEBUG] Tracking new '{message_type}' message for {doc_id}")
        return True
        
    def reset_message_tracking(self, doc_id, message_type, from_number=None):
        """
        Reset message tracking for a document and message type.
        
        Args:
            doc_id: The document ID
            message_type: The type of message
            from_number: The sender's phone number (optional)
        """
        # Use fallback if Redis is not available
        if self.redis is None:
            logger.info(f"[DEBUG] Using fallback for reset message tracking {doc_id}:{message_type}")
            # Fallback doesn't implement this method
            return
            
        if not doc_id or not message_type:
            return
            
        # Create a unique key for this document and message type
        if from_number:
            tracking_key = f"track:{from_number}:{doc_id}:{message_type}"
        else:
            tracking_key = f"track:{doc_id}:{message_type}"
            
        # Delete the tracking key
        self.redis.delete(tracking_key)
        logger.info(f"[DEBUG] Reset message tracking for {doc_id}:{message_type}")
        
    def cleanup(self):
        """Clean up old tracking data to prevent memory leaks"""
        # Use fallback if Redis is not available
        if self.redis is None:
            self.fallback.cleanup()
            return
            
        # Only clean up once per hour
        current_time = time.time()
        if current_time - self.last_cleanup_time < 3600:
            return
            
        self.last_cleanup_time = current_time
        logger.info("[DEBUG] Running Redis deduplication cleanup")
        
        # We don't need to manually clean up Redis keys since they have expiration times
        # This method is kept for compatibility with the in-memory fallback 