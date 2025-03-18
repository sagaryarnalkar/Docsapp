"""
WhatsApp Document Processor
-------------------------
This module integrates the document processing system with Flask.
"""

import logging
import os
import json
import asyncio
import time
from typing import Dict, Any, Optional, Tuple, Union

from models.docs_app import DocsApp
from .document import DocumentProcessor, DocumentDownloader, DocumentTracker
from .document.errors import WhatsAppDocumentError

logger = logging.getLogger(__name__)

class WhatsAppHandlerError(Exception):
    """
    Exception raised when there's an error in WhatsApp message handling.
    
    This exception is used to signal that an error has already been
    handled appropriately, and the caller can safely catch and ignore it.
    """
    pass

class WhatsAppDocumentProcessor:
    """
    Processes WhatsApp documents and integrates with Flask.
    
    This class wraps the underlying document processing system
    and provides Flask-compatible methods.
    """
    
    def __init__(self, docs_app: DocsApp, message_sender=None, deduplication_service=None):
        """
        Initialize the WhatsApp document processor.
        
        Args:
            docs_app: DocsApp instance for processing documents
            message_sender: Optional message sender (defaults to internal implementation)
            deduplication_service: Optional service for message deduplication
        """
        self.docs_app = docs_app
        
        # Create a default message sender if not provided
        if message_sender is None:
            from .message_sender import WhatsAppMessageSender
            message_sender = WhatsAppMessageSender()
        
        self.message_sender = message_sender
        self.deduplication_service = deduplication_service
        
        # Create core components
        self.document_processor = DocumentProcessor(docs_app, message_sender, deduplication_service)
        self.downloader = DocumentDownloader()
        self.tracker = DocumentTracker(deduplication_service)
    
    async def handle_document(self, from_number: str, document: Dict[str, Any], message: Optional[Dict[str, Any]] = None) -> Tuple[str, int]:
        """
        Handle a document from WhatsApp.
        This method provides compatibility with the old WhatsApp handler interface.
        
        Args:
            from_number: User's phone number
            document: Document data from WhatsApp
            message: Full message data (optional)
            
        Returns:
            Tuple[str, int]: (response_message, status_code)
            
        Raises:
            WhatsAppHandlerError: If an error occurs during processing
        """
        try:
            if document is None and message:
                # This is a document message where we need to extract the document
                document = self._extract_document(message)
                if not document:
                    return "No document found in message", 400
            
            # Process the document using our new document processor
            result = await self.document_processor.handle_document(from_number, document, message)
            
            # Return a suitable response
            if result.get('status') == 'error':
                return f"Error processing document: {result.get('error', 'Unknown error')}", 400
            
            return f"Document processing started: {result.get('processing_key', 'unknown')}", 200
            
        except WhatsAppDocumentError as e:
            logger.error(f"WhatsApp document error: {str(e)}")
            return f"Error processing document: {str(e)}", 400
            
        except Exception as e:
            logger.error(f"Unexpected error processing document: {str(e)}", exc_info=True)
            raise WhatsAppHandlerError(f"Error processing document: {str(e)}")
    
    async def process_document_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a document message from WhatsApp.
        
        Args:
            message: Message data from WhatsApp
            
        Returns:
            Dict: Status information
        """
        try:
            # Extract phone number
            from_number = self._extract_phone_number(message)
            
            # Extract document data
            document = self._extract_document(message)
            if not document:
                logger.warning("No document found in message")
                return {
                    'status': 'error',
                    'error': 'No document found in message'
                }
            
            # Process the document
            result = await self.document_processor.handle_document(from_number, document, message)
            return result
            
        except Exception as e:
            logger.error(f"Error processing document message: {str(e)}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _extract_phone_number(self, message: Dict[str, Any]) -> str:
        """
        Extract the sender's phone number from the message.
        
        Args:
            message: Message data from WhatsApp
            
        Returns:
            str: Phone number
            
        Raises:
            ValueError: If phone number cannot be extracted
        """
        # Check for contacts array
        contacts = message.get('contacts', [])
        if contacts and len(contacts) > 0:
            wa_id = contacts[0].get('wa_id')
            if wa_id:
                return wa_id
        
        # Look for "from" field directly in message
        if 'from' in message:
            return message['from']
        
        # Look in WhatsApp Cloud API format
        if 'messages' in message and len(message['messages']) > 0:
            msg = message['messages'][0]
            if 'from' in msg:
                return msg['from']
        
        # Try metadata
        metadata = message.get('metadata', {})
        phone = metadata.get('display_phone_number') or metadata.get('phone_number_id')
        if phone:
            return phone
        
        # If we got here, we couldn't find a phone number
        raise ValueError("Could not extract phone number from message")
    
    def _extract_document(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract document data from the message.
        
        Args:
            message: Message data from WhatsApp
            
        Returns:
            Optional[Dict[str, Any]]: Document data or None if not found
        """
        # Direct check
        if 'document' in message:
            return message['document']
        
        # Check WhatsApp Cloud API format
        if 'messages' in message and len(message['messages']) > 0:
            msg = message['messages'][0]
            if 'document' in msg:
                return msg['document']
        
        # Check in value section
        if 'value' in message and 'messages' in message['value'] and len(message['value']['messages']) > 0:
            msg = message['value']['messages'][0]
            if 'document' in msg:
                return msg['document']
        
        # Look in other potential locations
        for key in ['attachments', 'media']:
            if key in message and message[key]:
                attachments = message[key]
                if isinstance(attachments, list) and len(attachments) > 0:
                    attachment = attachments[0]
                    if isinstance(attachment, dict) and attachment.get('type') == 'document':
                        return attachment
        
        return None 