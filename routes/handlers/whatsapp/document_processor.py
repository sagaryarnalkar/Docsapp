"""
WhatsApp Document Processor
-------------------------
This module handles processing documents from WhatsApp, including downloading,
storing in Google Drive, and processing with RAG.
"""

import json
import logging
import os
import time
import asyncio
import aiohttp
from config import (
    WHATSAPP_ACCESS_TOKEN,
    TEMP_DIR
)
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Global message tracking to prevent duplicates across instances
# Format: {document_id: {message_type: timestamp}}
GLOBAL_MESSAGE_TRACKING = {}

# Global tracking for document processing across instances
# This will be replaced by Redis in production
GLOBAL_DOCUMENT_TRACKING = {}
GLOBAL_TRACKING_LAST_CLEANUP = time.time()

# Define the error class here to avoid circular imports
class WhatsAppHandlerError(Exception):
    """
    Custom exception for WhatsApp handler errors that have already been 
    communicated to the user.
    
    This exception is used to signal that an error has occurred and has been
    properly handled (e.g., by sending an error message to the user), so the
    calling code doesn't need to send additional error messages.
    """
    pass

class DocumentProcessor:
    """
    Processes documents from WhatsApp.
    
    This class is responsible for:
    1. Downloading documents from WhatsApp
    2. Storing documents in Google Drive
    3. Processing documents with RAG
    4. Handling document replies for adding descriptions
    """
    
    def __init__(self, docs_app, message_sender, deduplication):
        """
        Initialize the document processor.
        
        Args:
            docs_app: The DocsApp instance for document operations
            message_sender: The MessageSender instance for sending responses
            deduplication: The DeduplicationManager for tracking processed documents
        """
        self.docs_app = docs_app
        self.message_sender = message_sender
        self.deduplication = deduplication
        
        # Track document processing states to prevent duplicate notifications
        self.document_states = {}
        
        # Clean up old global message tracking entries
        self._cleanup_global_tracking()
        
        # Try to import Redis deduplication manager
        try:
            from .redis_deduplication import RedisDeduplicationManager
            # Check if Redis URL is available
            if os.environ.get('REDIS_URL'):
                self.redis_deduplication = RedisDeduplicationManager()
                print("Using Redis for document deduplication")
            else:
                self.redis_deduplication = None
                print("Redis URL not available, using in-memory deduplication")
        except ImportError:
            self.redis_deduplication = None
            print("Redis deduplication not available, using in-memory deduplication")
        
    async def handle_document(self, from_number, document, message=None):
        """
        Process a document from WhatsApp.
        
        Args:
            from_number: The sender's phone number
            document: The document data from WhatsApp
            message: The full message object (optional)
            
        Returns:
            tuple: (response_message, status_code)
        """
        debug_info = []
        try:
            debug_info.append("=== Document Processing Started ===")
            debug_info.append(f"Document details: {json.dumps(document, indent=2) if document else 'None'}")

            # Handle replies to documents (for adding descriptions)
            if message and 'context' in message:
                return await self._handle_document_reply(from_number, message, debug_info)

            # If no document provided, return early
            if not document:
                return "No document to process", 200

            # Check for duplicate document processing
            doc_id = document.get('id')
            filename = document.get('filename', 'Unknown file')
            mime_type = document.get('mime_type', 'application/octet-stream')
            
            # Check global tracking first
            if self._is_duplicate_by_global_tracking(doc_id, "document_received"):
                logger.info(f"Skipping duplicate document processing for {doc_id} based on global tracking")
                return "Duplicate document processing prevented", 200
            
            # Mark as received in global tracking
            self._update_global_tracking(doc_id, "document_received")
            
            if self._get_deduplication().is_duplicate_document(from_number, doc_id):
                # Still send a confirmation message if we haven't sent one recently
                if not self._is_duplicate_by_global_tracking(doc_id, "already_processed_notification"):
                    await self.message_sender.send_message(
                        from_number, 
                        f"✅ Document '{filename}' was already processed. You can ask questions about it using:\n/ask <your question>"
                    )
                    self._update_global_tracking(doc_id, "already_processed_notification")
                    
                return "Duplicate document processing prevented", 200

            # Get document details
            debug_info.append(f"Doc ID: {doc_id}")
            debug_info.append(f"Filename: {filename}")
            debug_info.append(f"MIME Type: {mime_type}")

            # Get initial description from caption if provided
            description = "Document from WhatsApp"
            if message and message.get('caption'):
                description = message.get('caption')
                debug_info.append(f"Using caption as initial description: {description}")

            # Download and process the document
            return await self._download_and_process_document(
                from_number, doc_id, filename, mime_type, description, debug_info
            )

        except WhatsAppHandlerError:
            raise
        except Exception as e:
            error_msg = f"❌ Error processing document: {str(e)}"
            await self.message_sender.send_message(from_number, error_msg)
            raise WhatsAppHandlerError(str(e))
            
    async def _handle_document_reply(self, from_number, message, debug_info):
        """
        Handle a reply to a document (for adding descriptions).
        
        Args:
            from_number: The sender's phone number
            message: The message object
            debug_info: List for collecting debug information
            
        Returns:
            tuple: (response_message, status_code)
        """
        context = message.get('context', {})
        quoted_msg_id = context.get('id')
        debug_info.append(f"Found reply context. Quoted message ID: {quoted_msg_id}")

        if quoted_msg_id:
            description = message.get('text', {}).get('body', '')
            debug_info.append(f"Adding description from reply: {description}")
            
            # Check for duplicate description update
            if self._is_duplicate_by_global_tracking(quoted_msg_id, "description_update"):
                logger.info(f"Skipping duplicate description update for {quoted_msg_id}")
                return "Duplicate description update prevented", 200
                
            # Mark as description update in global tracking
            self._update_global_tracking(quoted_msg_id, "description_update")
            
            result = self.docs_app.update_document_description(from_number, quoted_msg_id, description)
            if result:
                await self.message_sender.send_message(
                    from_number, 
                    f"✅ Added description to document: {description}\n\n"
                    "You can keep adding more descriptions to make the document easier to find!"
                )
            else:
                await self.message_sender.send_message(
                    from_number, 
                    f"❌ Failed to update document description.\n\nDebug Info:\n" + "\n".join(debug_info)
                )
            return "Description updated", 200
        return "No quoted message ID found", 400
            
    async def _download_and_process_document(self, from_number, doc_id, filename, mime_type, description, debug_info):
        """
        Download a document from WhatsApp and process it.
        
        Args:
            from_number: The sender's phone number
            doc_id: The document ID
            filename: The document filename
            mime_type: The document MIME type
            description: The document description
            debug_info: List for collecting debug information
            
        Returns:
            tuple: (response_message, status_code)
        """
        # Check if we've already started downloading this document
        if self._is_duplicate_by_global_tracking(doc_id, "download_started"):
            logger.info(f"Skipping duplicate download for {doc_id}")
            return "Duplicate download prevented", 200
            
        # Mark as download started in global tracking
        self._update_global_tracking(doc_id, "download_started")
        
        # Get media URL first
        media_request_url = f"https://graph.facebook.com/{self.message_sender.api_version}/{doc_id}"
        headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Accept': '*/*'
        }

        debug_info.append(f"Media Request URL: {media_request_url}")
        debug_info.append(f"Using headers: {json.dumps(headers)}")

        # First get the media URL using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(media_request_url, headers=headers) as media_response:
                media_response_text = await media_response.text()
                debug_info.append(f"Media URL Request Status: {media_response.status}")
                debug_info.append(f"Media URL Response: {media_response_text}")

                if media_response.status == 200:
                    try:
                        media_data = json.loads(media_response_text)
                        download_url = media_data.get('url')
                        debug_info.append(f"Got download URL: {download_url}")

                        if download_url:
                            # Now download the actual file using aiohttp
                            async with session.get(download_url, headers=headers) as file_response:
                                debug_info.append(f"File Download Status: {file_response.status}")

                                if file_response.status == 200:
                                    file_content = await file_response.read()
                                    temp_path = os.path.join(TEMP_DIR, filename)
                                    with open(temp_path, 'wb') as f:
                                        f.write(file_content)

                                    debug_info.append(f"File saved to: {temp_path}")

                                    try:
                                        # Check if we've already stored this document
                                        if self._is_duplicate_by_global_tracking(doc_id, "document_stored"):
                                            logger.info(f"Skipping duplicate storage for {doc_id}")
                                            return "Duplicate storage prevented", 200
                                            
                                        # Store in Drive with description
                                        store_result = await self.docs_app.store_document(
                                            from_number, temp_path, description, filename
                                        )
                                        debug_info.append(f"Store document result: {store_result}")

                                        if not store_result:
                                            debug_info.append("Failed to store document")
                                            error_msg = "❌ Error storing document. Please try again later."
                                            await self.message_sender.send_message(from_number, error_msg)
                                            raise WhatsAppHandlerError("Failed to store document")

                                        debug_info.append("Document stored successfully")
                                        
                                        # Get the file ID for tracking
                                        file_id = store_result.get('file_id', 'unknown')
                                        
                                        # Mark as stored in global tracking
                                        self._update_global_tracking(doc_id, "document_stored")
                                        self._update_global_tracking(file_id, "document_stored")
                                        
                                        # Create a document state entry for this file
                                        doc_state_key = f"{from_number}:{file_id}"
                                        self.document_states[doc_state_key] = {
                                            "received": True,
                                            "stored": True,
                                            "processing_started": False,
                                            "processing_completed": False,
                                            "last_notification": int(time.time())
                                        }
                                        
                                        # Check if we've already sent a storage confirmation
                                        if not self._is_duplicate_by_global_tracking(doc_id, "storage_notification") and \
                                           not self._is_duplicate_by_global_tracking(file_id, "storage_notification"):
                                            # Send storage confirmation message
                                            folder_name = self.docs_app.folder_name
                                            immediate_response = (
                                                f"✅ Document '{filename}' stored successfully in your Google Drive folder '{folder_name}'!\n\n"
                                                f"Initial description: {description}\n\n"
                                                "You can reply to this message with additional descriptions "
                                                "to make the document easier to find later!"
                                            )
                                            
                                            await self.message_sender.send_message(from_number, immediate_response)
                                            
                                            # Mark storage notification as sent
                                            self._update_global_tracking(doc_id, "storage_notification")
                                            self._update_global_tracking(file_id, "storage_notification")
                                        
                                        # Process document with RAG in the background
                                        if file_id != 'unknown':
                                            await self._process_document_with_rag(
                                                from_number, 
                                                file_id,
                                                store_result.get('mime_type'),
                                                filename
                                            )
                                            
                                        return "Document stored successfully", 200
                                    finally:
                                        # Always clean up temp file
                                        try:
                                            if os.path.exists(temp_path):
                                                os.remove(temp_path)
                                                debug_info.append("Temp file cleaned up")
                                        except Exception as e:
                                            logger.error(f"Failed to clean up temp file: {str(e)}")
                                else:
                                    debug_info.append(f"File download failed: {await file_response.text()}")
                                    error_msg = "❌ Failed to download the document. Please try sending it again."
                                    await self.message_sender.send_message(from_number, error_msg)
                                    raise WhatsAppHandlerError("Failed to download document")
                        else:
                            debug_info.append("No download URL found in response")
                            error_msg = "❌ Could not access the document. Please try sending it again."
                            await self.message_sender.send_message(from_number, error_msg)
                            raise WhatsAppHandlerError("No download URL found")
                    except json.JSONDecodeError as e:
                        debug_info.append(f"Error parsing media response: {str(e)}")
                        error_msg = "❌ Error processing the document. Please try again later."
                        await self.message_sender.send_message(from_number, error_msg)
                        raise WhatsAppHandlerError(str(e))
                else:
                    debug_info.append(f"Media URL request failed: {media_response_text}")
                    error_msg = "❌ Could not access the document. Please try sending it again."
                    await self.message_sender.send_message(from_number, error_msg)
                    raise WhatsAppHandlerError("Media URL request failed")
                    
    async def _process_document_with_rag(self, from_number, file_id, mime_type, filename):
        """
        Process a document with RAG in the background.
        
        Args:
            from_number: The sender's phone number
            file_id: The Google Drive file ID
            mime_type: The document MIME type
            filename: The document filename
        """
        try:
            # Check if we've already started processing this document
            if self._is_duplicate_by_global_tracking(file_id, "processing_started"):
                logger.info(f"Skipping duplicate RAG processing for {file_id}")
                return
                
            # Create a document state key for tracking
            doc_state_key = f"{from_number}:{file_id}"
            
            # Check if this document is already being processed
            if self._get_deduplication().is_document_processing(from_number, file_id):
                # Only send a notification if we haven't already notified about processing
                if not self._is_duplicate_by_global_tracking(file_id, "processing_notification"):
                    await self.message_sender.send_message(
                        from_number, 
                        "🔄 Document is already being processed. I'll notify you when it's complete..."
                    )
                    self._update_global_tracking(file_id, "processing_notification")
                return
            
            # Mark as processing to avoid duplicate processing
            processing_key = self._get_deduplication().mark_document_processing(from_number, file_id)
            
            # Mark as processing started in global tracking
            self._update_global_tracking(file_id, "processing_started")
            
            # Initialize or update document state
            if doc_state_key not in self.document_states:
                self.document_states[doc_state_key] = {
                    "received": True,
                    "stored": True,
                    "processing_started": False,
                    "processing_completed": False,
                    "last_notification": 0
                }
            
            # Check if we need to send a processing notification
            if not self._is_duplicate_by_global_tracking(file_id, "processing_notification"):
                # Send processing started message
                await self.message_sender.send_message(
                    from_number, 
                    "🔄 Document processing started. I'll notify you when it's complete..."
                )
                # Mark processing notification as sent
                self._update_global_tracking(file_id, "processing_notification")
                
                # Update state
                if doc_state_key in self.document_states:
                    doc_state = self.document_states[doc_state_key]
                    doc_state["processing_started"] = True
                    doc_state["last_notification"] = int(time.time())
            
            # Create a task to process the document and notify when done
            async def process_and_notify():
                try:
                    print(f"Starting background RAG processing for document {file_id}")
                    
                    # IMPORTANT: Reset completion notification tracking to ensure we always send a completion notification
                    # This ensures the user always gets notified when processing completes
                    if file_id in GLOBAL_MESSAGE_TRACKING and "completion_notification" in GLOBAL_MESSAGE_TRACKING[file_id]:
                        del GLOBAL_MESSAGE_TRACKING[file_id]["completion_notification"]
                    
                    # Process the document
                    result = await self.docs_app.rag_processor.process_document_async(
                        file_id, 
                        mime_type,
                        from_number
                    )
                    
                    print(f"RAG processing completed for {file_id}. Result: {result}")
                    
                    # Mark as processing completed in global tracking
                    self._update_global_tracking(file_id, "processing_completed")
                    
                    # Always send a completion notification regardless of previous notifications
                    # This ensures the user is always informed when processing is done
                    if result and result.get("status") == "success":
                        print(f"Sending success notification for {file_id}")
                        await self.message_sender.send_message(
                            from_number, 
                            f"✅ Document '{filename}' has been processed successfully!\n\n"
                            f"You can now ask questions about it using:\n"
                            f"/ask <your question>"
                        )
                    else:
                        error = result.get("error", "Unknown error")
                        print(f"Sending completion with issues notification for {file_id}: {error}")
                        await self.message_sender.send_message(
                            from_number,
                            f"⚠️ Document processing completed with issues: {error}\n\n"
                            f"You can still try asking questions about it."
                        )
                    
                    # Mark completion notification as sent
                    self._update_global_tracking(file_id, "completion_notification")
                    
                    # Update state
                    if doc_state_key in self.document_states:
                        doc_state = self.document_states[doc_state_key]
                        doc_state["processing_completed"] = True
                        doc_state["last_notification"] = int(time.time())
                    
                    # Remove from processing documents
                    self._get_deduplication().mark_document_processed(processing_key)
                    
                    # Clean up old document states (older than 24 hours)
                    self._cleanup_document_states()
                    
                except Exception as e:
                    print(f"Error in process_and_notify: {str(e)}")
                    import traceback
                    print(f"Traceback:\n{traceback.format_exc()}")
                    
                    # Mark as processing error in global tracking
                    self._update_global_tracking(file_id, "processing_error")
                    
                    # Always send an error notification regardless of previous notifications
                    # This ensures the user is always informed of processing errors
                    print(f"Sending error notification for {file_id}")
                    await self.message_sender.send_message(
                        from_number, 
                        f"❌ There was an error processing your document: {str(e)}\n\n"
                        f"You can still try asking questions about it, but results may be limited."
                    )
                    
                    # Mark error notification as sent
                    self._update_global_tracking(file_id, "error_notification")
                    
                    # Update state
                    if doc_state_key in self.document_states:
                        doc_state = self.document_states[doc_state_key]
                        doc_state["processing_completed"] = True
                        doc_state["last_notification"] = int(time.time())
                    
                    # Remove from processing documents
                    self._get_deduplication().mark_document_processed(processing_key)
            
            # Fire and forget the processing task
            task = asyncio.create_task(process_and_notify())
            # Add a name to the task for better debugging
            task.set_name(f"rag_processing_{file_id}")
            
        except Exception as rag_err:
            print(f"Error starting RAG processing: {str(rag_err)}")
            import traceback
            print(f"RAG processing error traceback:\n{traceback.format_exc()}")
    
    def _cleanup_document_states(self):
        """Clean up old document states to prevent memory leaks."""
        current_time = int(time.time())
        cutoff_time = current_time - 86400  # 24 hours
        
        # Remove old document states
        self.document_states = {
            k: v for k, v in self.document_states.items() 
            if v.get("last_notification", 0) > cutoff_time
        }
        
        # Also clean up global tracking
        self._cleanup_global_tracking()
        
        print(f"Cleaned up document states. Remaining: {len(self.document_states)}")
    
    def _is_duplicate_by_global_tracking(self, doc_id, message_type):
        """
        Check if a message type for a document has already been sent.
        
        Args:
            doc_id: The document ID
            message_type: The type of message
            
        Returns:
            bool: True if this message type has already been sent for this document
        """
        if not doc_id or doc_id == 'unknown':
            return False
            
        return doc_id in GLOBAL_MESSAGE_TRACKING and message_type in GLOBAL_MESSAGE_TRACKING[doc_id]
    
    def _update_global_tracking(self, doc_id, message_type):
        """
        Update global tracking for a document and message type.
        
        Args:
            doc_id: The document ID
            message_type: The type of message
        """
        if not doc_id or doc_id == 'unknown':
            return
            
        if doc_id not in GLOBAL_MESSAGE_TRACKING:
            GLOBAL_MESSAGE_TRACKING[doc_id] = {}
            
        GLOBAL_MESSAGE_TRACKING[doc_id][message_type] = int(time.time())
        
        # Log the update
        logger.info(f"Updated global tracking for {doc_id}: {message_type}")
    
    def _cleanup_global_tracking(self):
        """Clean up old global tracking entries to prevent memory leaks."""
        global GLOBAL_MESSAGE_TRACKING
        
        current_time = int(time.time())
        cutoff_time = current_time - 86400  # 24 hours
        
        # Count before cleanup
        count_before = len(GLOBAL_MESSAGE_TRACKING)
        
        # Remove old entries
        for doc_id in list(GLOBAL_MESSAGE_TRACKING.keys()):
            # Remove old message types
            GLOBAL_MESSAGE_TRACKING[doc_id] = {
                k: v for k, v in GLOBAL_MESSAGE_TRACKING[doc_id].items()
                if v > cutoff_time
            }
            
            # Remove empty documents
            if not GLOBAL_MESSAGE_TRACKING[doc_id]:
                del GLOBAL_MESSAGE_TRACKING[doc_id]
        
        # Count after cleanup
        count_after = len(GLOBAL_MESSAGE_TRACKING)
        
        if count_before != count_after:
            logger.info(f"Cleaned up global tracking. Before: {count_before}, After: {count_after}") 
    
    def _get_deduplication(self):
        """Get the appropriate deduplication manager."""
        if self.redis_deduplication:
            return self.redis_deduplication
        return self.deduplication 