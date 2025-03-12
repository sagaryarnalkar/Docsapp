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
        
    def is_duplicate_message(self, from_number, message_id):
        """
        Check if a message is a duplicate.
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            
        Returns:
            bool: True if the message is a duplicate, False otherwise
        """
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
            
        # Create a unique key for tracking this document processing
        processing_key = f"processing:{from_number}:{file_id}"
        
        # Check if this document is already being processed
        if processing_key in self.processing_documents:
            time_since_started = int(time.time()) - self.processing_documents[processing_key]
            print(f"Document {file_id} is already being processed "
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
        if not file_id:
            return None
            
        # Create a unique key for tracking this document processing
        processing_key = f"processing:{from_number}:{file_id}"
        
        # Mark as processing to avoid duplicate processing
        self.processing_documents[processing_key] = int(time.time())
        return processing_key
        
    def mark_document_processed(self, processing_key):
        """
        Mark a document as processed (no longer being processed).
        
        Args:
            processing_key: The processing key for this document
        """
        if processing_key and processing_key in self.processing_documents:
            del self.processing_documents[processing_key]
            
    def cleanup(self):
        """
        Clean up old tracking data to prevent memory leaks.
        
        This method should be called periodically to remove old entries
        from the tracking dictionaries.
        """
        current_time = time.time()
        # Only clean up every 5 minutes to avoid excessive processing
        if current_time - self.last_cleanup_time < 300:  # 5 minutes
            return
            
        # Clean up old processed documents (older than 30 minutes)
        cutoff_time = current_time - 1800  # 30 minutes
        self.processed_messages = {k:v for k,v in self.processed_messages.items() if v > cutoff_time}
        self.processed_documents = {k:v for k,v in self.processed_documents.items() if v > cutoff_time}
        
        # Clean up very old processing documents (older than 2 hours)
        # This is a safety measure in case a document gets stuck in processing
        processing_cutoff_time = current_time - 7200  # 2 hours
        self.processing_documents = {k:v for k,v in self.processing_documents.items() if v > processing_cutoff_time}
        
        self.last_cleanup_time = current_time
        print(f"Cleaned up tracking dictionaries. Remaining items: "
              f"processed_messages={len(self.processed_messages)}, "
              f"processed_documents={len(self.processed_documents)}, "
              f"processing_documents={len(self.processing_documents)}") 