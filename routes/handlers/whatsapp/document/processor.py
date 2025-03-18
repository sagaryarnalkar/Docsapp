"""
WhatsApp Document Processor
-------------------------
This module coordinates the processing of documents from WhatsApp.
"""

import logging
import os
import json
import asyncio
import time
from typing import Dict, Any, Optional, Tuple

from models import DocsApp
from .downloader import DocumentDownloader
from .tracking import DocumentTracker
from .errors import WhatsAppDocumentError, DocumentDownloadError, DocumentStorageError, DocumentProcessingError

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """
    Processes documents from WhatsApp.
    
    This class coordinates:
    1. Downloading documents from WhatsApp
    2. Storing documents in Google Drive
    3. Processing documents with RAG
    4. Tracking document states
    5. Sending status messages to users
    """
    
    def __init__(self, docs_app, message_sender, deduplication_service=None):
        """
        Initialize the document processor.
        
        Args:
            docs_app: DocsApp instance for document storage and RAG
            message_sender: WhatsApp message sender for user communication
            deduplication_service: Optional service for message deduplication
        """
        self.docs_app = docs_app
        self.message_sender = message_sender
        
        # Create components
        self.downloader = DocumentDownloader()
        self.tracker = DocumentTracker(deduplication_service)
    
    async def handle_document(self, from_number: str, document: Dict[str, Any], message: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Handle a document message from WhatsApp.
        
        Args:
            from_number: User's phone number
            document: Document data from WhatsApp
            message: Original message data (optional)
            
        Returns:
            Dict: Status information
        """
        try:
            # Extract document information
            doc_id = document.get('id')
            filename = document.get('filename', 'unknown_file')
            mime_type = document.get('mime_type', 'application/octet-stream')
            
            # Check if this is a duplicate message
            if self.tracker.is_duplicate(doc_id, 'received'):
                logger.info(f"Skipping duplicate document: {doc_id}")
                return {
                    'status': 'skipped',
                    'reason': 'duplicate'
                }
            
            # Mark as received to prevent duplicates
            self.tracker.update_tracking(doc_id, 'received')
            
            # Generate debug info for logging
            debug_info = {
                'doc_id': doc_id,
                'filename': filename,
                'mime_type': mime_type,
                'timestamp': time.time()
            }
            
            # Check if this is a reply to a message (has context)
            if message and message.get('context'):
                logger.info(f"Document is a reply to a message")
                return await self._handle_document_reply(from_number, message, debug_info)
            
            # Handle as a new document upload with no description
            return await self._process_document(from_number, doc_id, filename, mime_type, None, debug_info)
            
        except WhatsAppDocumentError as e:
            # Error already handled
            logger.info(f"Document error (already handled): {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }
        except Exception as e:
            # Unexpected error
            logger.error(f"Unexpected error handling document: {str(e)}", exc_info=True)
            await self._send_error_message(from_number, "Sorry, I couldn't process your document due to an unexpected error.")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _handle_document_reply(self, from_number: str, message: Dict[str, Any], debug_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a document that is a reply to a previous message.
        Use the replied-to message as the document description.
        
        Args:
            from_number: User's phone number
            message: Original message data
            debug_info: Debug information
            
        Returns:
            Dict: Status information
        """
        try:
            # Extract document information from debug info
            doc_id = debug_info.get('doc_id')
            filename = debug_info.get('filename')
            mime_type = debug_info.get('mime_type')
            
            # Try to get the message being replied to
            context = message.get('context', {})
            context_id = context.get('id')
            
            if not context_id:
                logger.warning(f"Missing context ID in replied-to message")
                # Process without description
                return await self._process_document(from_number, doc_id, filename, mime_type, None, debug_info)
            
            # Use the context ID to get the original message
            # In a real implementation, we would fetch the message text from the WhatsApp API
            # For now, we'll use a placeholder
            description = f"Document uploaded in reply to message {context_id}"
            
            return await self._process_document(from_number, doc_id, filename, mime_type, description, debug_info)
            
        except Exception as e:
            logger.error(f"Error handling document reply: {str(e)}", exc_info=True)
            await self._send_error_message(from_number, "Sorry, I couldn't process your document reply.")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def _process_document(self, from_number: str, doc_id: str, filename: str, mime_type: str, description: Optional[str], debug_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a document from WhatsApp.
        
        Args:
            from_number: User's phone number
            doc_id: Document ID
            filename: Document filename
            mime_type: Document MIME type
            description: Document description (optional)
            debug_info: Debug information
            
        Returns:
            Dict: Status information
        """
        # Create a processing key for tracking
        processing_key = f"{doc_id}_{int(time.time())}"
        
        # Track the document state
        self.tracker.set_document_state(doc_id, {
            'status': 'processing',
            'processing_key': processing_key,
            'filename': filename,
            'mime_type': mime_type,
            'from_number': from_number,
            'timestamp': time.time()
        })
        
        # Send an acknowledgment message
        await self._send_processing_message(from_number, filename)
        
        # Start processing in the background
        asyncio.create_task(
            self._process_document_async(
                from_number, doc_id, filename, mime_type, description, 
                debug_info, processing_key
            )
        )
        
        return {
            'status': 'processing',
            'processing_key': processing_key
        }
    
    async def _process_document_async(self, from_number: str, doc_id: str, filename: str, mime_type: str, description: Optional[str], debug_info: Dict[str, Any], processing_key: str) -> None:
        """
        Process a document asynchronously.
        
        Args:
            from_number: User's phone number
            doc_id: Document ID
            filename: Document filename
            mime_type: Document MIME type
            description: Document description (optional)
            debug_info: Debug information
            processing_key: Processing key for tracking
        """
        try:
            # Download the document
            logger.info(f"Downloading document: {doc_id}")
            file_path = await self.downloader.download_document(doc_id, filename)
            
            # Store in Google Drive and process with RAG
            logger.info(f"Storing document in Drive: {filename}")
            result = await self.docs_app.store_document(
                from_number, file_path, description or f"Document uploaded via WhatsApp", filename
            )
            
            if not result or isinstance(result, bool) and not result:
                raise DocumentStorageError("Failed to store document in Google Drive")
            
            # Clean up the temporary file
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {file_path}: {str(e)}")
            
            # Update tracking
            self.tracker.set_document_state(doc_id, {
                'status': 'stored',
                'processing_key': processing_key,
                'filename': filename,
                'file_id': result.get('file_id') if isinstance(result, dict) else None,
                'from_number': from_number,
                'timestamp': time.time()
            })
            
            # Send success message
            await self._send_success_message(from_number, filename)
            
            # Mark as completed to prevent duplicates
            self.tracker.update_tracking(doc_id, 'completed')
            
        except DocumentDownloadError as e:
            logger.error(f"Error downloading document: {str(e)}")
            await self._send_error_message(from_number, f"Sorry, I couldn't download your document. {str(e)}")
            
        except DocumentStorageError as e:
            logger.error(f"Error storing document: {str(e)}")
            await self._send_error_message(from_number, f"Sorry, I couldn't store your document. {str(e)}")
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}", exc_info=True)
            await self._send_error_message(from_number, f"Sorry, I couldn't process your document due to an internal error.")
    
    async def _send_processing_message(self, to_number: str, filename: str) -> None:
        """Send a message indicating document is being processed."""
        try:
            await self.message_sender.send_text_message(
                to_number,
                f"📄 Processing your document: {filename}...\n\nThis may take a moment."
            )
        except Exception as e:
            logger.error(f"Error sending processing message: {str(e)}")
    
    async def _send_success_message(self, to_number: str, filename: str) -> None:
        """Send a message indicating document was processed successfully."""
        try:
            await self.message_sender.send_text_message(
                to_number,
                f"✅ Your document has been uploaded successfully!\n\n" +
                f"📄 {filename}\n\n" +
                "You can now ask questions about it using the 'ask' command."
            )
        except Exception as e:
            logger.error(f"Error sending success message: {str(e)}")
    
    async def _send_error_message(self, to_number: str, message: str) -> None:
        """Send an error message to the user."""
        try:
            await self.message_sender.send_text_message(
                to_number,
                f"❌ {message}"
            )
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}") 