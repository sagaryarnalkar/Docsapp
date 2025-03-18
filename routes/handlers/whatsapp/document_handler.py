"""
WhatsApp Document Handler
------------------------
This module handles document messages from WhatsApp and processes them.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Tuple, Union

from models import DocsApp
from services.whatsapp import WhatsAppMessageSender
from .document import DocumentProcessor

logger = logging.getLogger(__name__)

class WhatsAppDocumentHandler:
    """
    Handles document messages from WhatsApp.
    
    This class is responsible for:
    1. Receiving document messages from the WhatsApp API
    2. Processing documents using the DocumentProcessor
    3. Coordinating responses to the user
    """
    
    def __init__(self, docs_app: DocsApp, message_sender: Optional[WhatsAppMessageSender] = None):
        """
        Initialize the document handler.
        
        Args:
            docs_app: DocsApp instance for document storage and RAG
            message_sender: WhatsApp message sender for user communication
        """
        self.docs_app = docs_app
        self.message_sender = message_sender or WhatsAppMessageSender()
        
        # Create the document processor
        self.document_processor = DocumentProcessor(docs_app, self.message_sender)
        
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a document message from WhatsApp.
        
        Args:
            message: Message data from WhatsApp
            
        Returns:
            Dict: Status information
        """
        try:
            from_number = self._extract_phone_number(message)
            
            # Extract document data
            document = self._extract_document(message)
            if not document:
                return {
                    'status': 'error',
                    'error': 'No document found in message'
                }
            
            # Process the document
            result = await self.document_processor.handle_document(from_number, document, message)
            return result
            
        except Exception as e:
            logger.error(f"Error handling document message: {str(e)}", exc_info=True)
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
        # Check various locations where the phone number might be
        from_number = None
        
        # Try to get from contacts
        contacts = message.get('contacts', [])
        if contacts and len(contacts) > 0:
            from_number = contacts[0].get('wa_id')
        
        # Try to get from metadata
        if not from_number and 'metadata' in message:
            from_number = message['metadata'].get('display_phone_number') or message['metadata'].get('phone_number_id')
        
        # Try to get from "from" field
        if not from_number and 'from' in message:
            from_number = message['from']
        
        if not from_number:
            raise ValueError("Could not extract phone number from message")
        
        return from_number
    
    def _extract_document(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract document data from the message.
        
        Args:
            message: Message data from WhatsApp
            
        Returns:
            Optional[Dict[str, Any]]: Document data or None if not found
        """
        # First look for document in standard location
        if 'document' in message:
            return message['document']
        
        # Try WhatsApp Cloud API format
        if 'messages' in message and len(message['messages']) > 0:
            msg = message['messages'][0]
            if 'document' in msg:
                return msg['document']
        
        # Look in other potential locations
        for key in ['attachments', 'media']:
            if key in message and message[key]:
                attachments = message[key]
                if isinstance(attachments, list) and len(attachments) > 0:
                    attachment = attachments[0]
                    if isinstance(attachment, dict) and 'type' in attachment and attachment['type'] == 'document':
                        return attachment
        
        return None 