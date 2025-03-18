"""
WhatsApp Document Tracking
-------------------------
This module handles tracking document states across instances.
"""

import time
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class DocumentTracker:
    """
    Tracks document processing state.
    
    This class is responsible for:
    1. Tracking document processing across instances
    2. Preventing duplicate processing
    3. Cleaning up stale tracking information
    """
    
    # Class-level tracking to share across instances
    # Format: {document_id: {message_type: timestamp}}
    _global_message_tracking = {}
    
    # Global tracking for document processing across instances
    # This will be replaced by Redis in production
    _global_document_tracking = {}
    _global_tracking_last_cleanup = time.time()
    
    # Cleanup interval (seconds)
    CLEANUP_INTERVAL = 3600  # 1 hour
    
    # Time after which tracking entries are considered stale (seconds)
    STALE_THRESHOLD = 86400  # 24 hours
    
    def __init__(self, deduplication_service=None):
        """
        Initialize the document tracker.
        
        Args:
            deduplication_service: Optional service for message deduplication
        """
        self.deduplication_service = deduplication_service
    
    def is_duplicate(self, doc_id: str, message_type: str) -> bool:
        """
        Check if this is a duplicate document message.
        
        Args:
            doc_id: Document ID
            message_type: Type of message (e.g., 'processing', 'completed')
            
        Returns:
            bool: True if duplicate, False otherwise
        """
        self._cleanup_if_needed()
        
        # Use deduplication service if available
        if self.deduplication_service:
            tracking_key = f"doc_{doc_id}_{message_type}"
            return self.deduplication_service.is_duplicate(tracking_key)
            
        # Otherwise use in-memory tracking
        return self._is_duplicate_by_global_tracking(doc_id, message_type)
    
    def _is_duplicate_by_global_tracking(self, doc_id: str, message_type: str) -> bool:
        """Check if duplicate using in-memory global tracking."""
        if doc_id in self._global_message_tracking:
            if message_type in self._global_message_tracking[doc_id]:
                # Message was seen before
                timestamp = self._global_message_tracking[doc_id][message_type]
                age = time.time() - timestamp
                
                # If seen within the last 10 minutes, consider it a duplicate
                if age < 600:  # 10 minutes
                    logger.info(f"Duplicate document message detected: {doc_id} {message_type}")
                    return True
        
        # Not a duplicate or too old to care
        return False
    
    def update_tracking(self, doc_id: str, message_type: str) -> None:
        """
        Update tracking for a document message.
        
        Args:
            doc_id: Document ID
            message_type: Type of message
        """
        self._cleanup_if_needed()
        
        # Use deduplication service if available
        if self.deduplication_service:
            tracking_key = f"doc_{doc_id}_{message_type}"
            self.deduplication_service.mark_as_processed(tracking_key)
            
        # Also update in-memory tracking
        self._update_global_tracking(doc_id, message_type)
    
    def _update_global_tracking(self, doc_id: str, message_type: str) -> None:
        """Update in-memory global tracking."""
        if doc_id not in self._global_message_tracking:
            self._global_message_tracking[doc_id] = {}
            
        self._global_message_tracking[doc_id][message_type] = time.time()
    
    def _cleanup_if_needed(self) -> None:
        """Clean up stale tracking entries if needed."""
        current_time = time.time()
        if current_time - self._global_tracking_last_cleanup > self.CLEANUP_INTERVAL:
            self._cleanup_global_tracking()
            self._global_tracking_last_cleanup = current_time
    
    def _cleanup_global_tracking(self) -> None:
        """Clean up stale entries in global tracking."""
        current_time = time.time()
        stale_threshold = current_time - self.STALE_THRESHOLD
        
        # Clean up message tracking
        docs_to_remove = []
        for doc_id, message_types in self._global_message_tracking.items():
            types_to_remove = []
            for message_type, timestamp in message_types.items():
                if timestamp < stale_threshold:
                    types_to_remove.append(message_type)
                    
            # Remove stale message types
            for message_type in types_to_remove:
                del message_types[message_type]
                
            # If no message types left, mark document for removal
            if not message_types:
                docs_to_remove.append(doc_id)
                
        # Remove empty documents
        for doc_id in docs_to_remove:
            del self._global_message_tracking[doc_id]
            
        # Also clean up document tracking
        doc_ids_to_remove = []
        for doc_id, state in self._global_document_tracking.items():
            if state.get('timestamp', 0) < stale_threshold:
                doc_ids_to_remove.append(doc_id)
                
        # Remove stale document states
        for doc_id in doc_ids_to_remove:
            del self._global_document_tracking[doc_id]
            
        logger.info(f"Cleaned up tracking: removed {len(docs_to_remove)} messages and {len(doc_ids_to_remove)} documents")
        
    def get_document_state(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current state of document processing.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Dict or None: Document state if found, None otherwise
        """
        return self._global_document_tracking.get(doc_id)
        
    def set_document_state(self, doc_id: str, state: Dict[str, Any]) -> None:
        """
        Set the state of document processing.
        
        Args:
            doc_id: Document ID
            state: Document state
        """
        # Add timestamp for cleanup
        state['timestamp'] = time.time()
        self._global_document_tracking[doc_id] = state 