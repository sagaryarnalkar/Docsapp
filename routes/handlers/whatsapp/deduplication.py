"""
WhatsApp Deduplication Manager
----------------------------
This module handles deduplication of WhatsApp messages and document processing
to prevent the same message or document from being processed multiple times.
"""

import time
import logging

logger = logging.getLogger(__name__)

class DeduplicationManager:
    """
    Manages deduplication of messages and document processing.
    
    This class is responsible for:
    1. Tracking processed messages to prevent duplicate processing
    2. Tracking processed documents to prevent duplicate processing
    3. Tracking documents currently being processed
    4. Cleaning up old tracking data to prevent memory leaks
    """
    
    def __init__(self):
        """Initialize the deduplication manager."""
        self.processed_messages = {}  # Track processed messages
        self.processed_documents = {}  # Track processed documents
        self.processing_documents = {}  # Track documents currently being processed
        self.last_cleanup_time = time.time()  # Track last cleanup time
        
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
        # NEVER deduplicate outgoing messages (command responses)
        # This ensures all outgoing messages are always sent
        if message_type is not None:
            print(f"[DEBUG] Message is a {message_type} - BYPASSING DEDUPLICATION FOR OUTGOING MESSAGE")
            return False
            
        # Create a more robust message key that includes the from_number
        message_key = f"{from_number}:{message_id}"
        current_time = int(time.time())
        
        # Check both the combined key and the message_id for backward compatibility
        if message_key in self.processed_messages or message_id in self.processed_messages:
            time_since_processed = current_time - (
                self.processed_messages.get(message_key) or 
                self.processed_messages.get(message_id)
            )
            print(f"Skipping duplicate message processing for message ID {message_id} "
                  f"from {from_number} (processed {time_since_processed}s ago)")
            return True
        
        # Mark this message as being processed with both keys
        self.processed_messages[message_key] = current_time
        self.processed_messages[message_id] = current_time
        print(f"Processing new message {message_id} from {from_number}")
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
        if not doc_id:
            return False
            
        current_time = int(time.time())
        
        # Create a unique key for this document and user
        doc_user_key = f"{from_number}:{doc_id}"
        
        # Check if we've processed this document recently
        if doc_id in self.processed_documents or doc_user_key in self.processed_documents:
            time_since_processed = current_time - (
                self.processed_documents.get(doc_user_key) or 
                self.processed_documents.get(doc_id)
            )
            print(f"Skipping duplicate document processing for {doc_id} "
                  f"(processed {time_since_processed}s ago)")
            return True
            
        # Mark this document as being processed for this user
        self.processed_documents[doc_user_key] = current_time
        self.processed_documents[doc_id] = current_time
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
        if not file_id:
            return False
            
        # Create a unique key for this document and user
        processing_key = f"{from_number}:{file_id}"
        
        # Check if this document is currently being processed
        return processing_key in self.processing_documents
        
    def mark_document_processing(self, from_number, file_id):
        """
        Mark a document as currently being processed.
        
        Args:
            from_number: The sender's phone number
            file_id: The file ID
            
        Returns:
            str: The processing key for this document
        """
        if not file_id:
            return None
            
        current_time = int(time.time())
        
        # Create a unique key for this document and user
        processing_key = f"{from_number}:{file_id}"
        
        # Mark this document as being processed
        self.processing_documents[processing_key] = current_time
        
        return processing_key
        
    def mark_document_processed(self, processing_key):
        """
        Mark a document as processed (no longer being processed).
        
        Args:
            processing_key: The processing key for this document
        """
        if processing_key in self.processing_documents:
            del self.processing_documents[processing_key]
            
    def cleanup(self):
        """Clean up old tracking data to prevent memory leaks."""
        current_time = int(time.time())
        
        # Only clean up every hour
        if current_time - self.last_cleanup_time < 3600:
            return
            
        self.last_cleanup_time = current_time
        
        # Clean up processed messages older than 10 minutes
        cutoff_time = current_time - 600
        self.processed_messages = {
            k: v for k, v in self.processed_messages.items()
            if v > cutoff_time
        }
        
        # Clean up processed documents older than 1 day
        cutoff_time = current_time - 86400
        self.processed_documents = {
            k: v for k, v in self.processed_documents.items()
            if v > cutoff_time
        }
        
        # Clean up processing documents older than 1 hour
        cutoff_time = current_time - 3600
        self.processing_documents = {
            k: v for k, v in self.processing_documents.items()
            if v > cutoff_time
        }
        
        logger.info(f"Cleaned up deduplication tracking data. "
                   f"Messages: {len(self.processed_messages)}, "
                   f"Documents: {len(self.processed_documents)}, "
                   f"Processing: {len(self.processing_documents)}") 