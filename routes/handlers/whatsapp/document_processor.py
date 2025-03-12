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

logger = logging.getLogger(__name__)

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
            
            if self.deduplication.is_duplicate_document(from_number, doc_id):
                # Still send a confirmation message if we haven't sent one recently
                confirmation_key = f"confirmation:{from_number}:{doc_id}"
                if confirmation_key not in self.message_sender.sent_messages:
                    await self.message_sender.send_message(
                        from_number, 
                        f"✅ Document '{filename}' was already processed. You can ask questions about it using:\n/ask <your question>"
                    )
                    self.message_sender.sent_messages[confirmation_key] = int(time.time())
                    
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
                                        
                                        # Create a document state entry for this file
                                        doc_state_key = f"{from_number}:{file_id}"
                                        self.document_states[doc_state_key] = {
                                            "received": True,
                                            "stored": True,
                                            "processing_started": False,
                                            "processing_completed": False,
                                            "last_notification": int(time.time())
                                        }
                                        
                                        # Send storage confirmation message
                                        folder_name = self.docs_app.folder_name
                                        immediate_response = (
                                            f"✅ Document '{filename}' stored successfully in your Google Drive folder '{folder_name}'!\n\n"
                                            f"Initial description: {description}\n\n"
                                            "You can reply to this message with additional descriptions "
                                            "to make the document easier to find later!"
                                        )
                                        
                                        await self.message_sender.send_message(from_number, immediate_response)
                                        
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
            # Create a document state key for tracking
            doc_state_key = f"{from_number}:{file_id}"
            
            # Check if this document is already being processed
            if self.deduplication.is_document_processing(from_number, file_id):
                # Only send a notification if we haven't already notified about processing
                if doc_state_key in self.document_states:
                    doc_state = self.document_states[doc_state_key]
                    if not doc_state.get("processing_started", False):
                        await self.message_sender.send_message(
                            from_number, 
                            "🔄 Document is already being processed. I'll notify you when it's complete..."
                        )
                        doc_state["processing_started"] = True
                        doc_state["last_notification"] = int(time.time())
                return
            
            # Mark as processing to avoid duplicate processing
            processing_key = self.deduplication.mark_document_processing(from_number, file_id)
            
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
            doc_state = self.document_states[doc_state_key]
            current_time = int(time.time())
            
            # Only send processing notification if we haven't already
            if not doc_state.get("processing_started", False):
                # Send processing started message
                await self.message_sender.send_message(
                    from_number, 
                    "🔄 Document processing started. I'll notify you when it's complete..."
                )
                # Update state
                doc_state["processing_started"] = True
                doc_state["last_notification"] = current_time
            
            # Create a task to process the document and notify when done
            async def process_and_notify():
                try:
                    print(f"Starting background RAG processing for document {file_id}")
                    result = await self.docs_app.rag_processor.process_document_async(
                        file_id, 
                        mime_type,
                        from_number
                    )
                    
                    # Update document state
                    if doc_state_key in self.document_states:
                        doc_state = self.document_states[doc_state_key]
                        
                        # Only send completion notification if we haven't already
                        if not doc_state.get("processing_completed", False):
                            # Notify user of completion
                            if result and result.get("status") == "success":
                                await self.message_sender.send_message(
                                    from_number, 
                                    f"✅ Document '{filename}' has been processed successfully!\n\n"
                                    f"You can now ask questions about it using:\n"
                                    f"/ask <your question>"
                                )
                            else:
                                error = result.get("error", "Unknown error")
                                await self.message_sender.send_message(
                                    from_number,
                                    f"⚠️ Document processing completed with issues: {error}\n\n"
                                    f"You can still try asking questions about it."
                                )
                            
                            # Update state
                            doc_state["processing_completed"] = True
                            doc_state["last_notification"] = int(time.time())
                    
                    # Remove from processing documents
                    self.deduplication.mark_document_processed(processing_key)
                    
                    # Clean up old document states (older than 24 hours)
                    self._cleanup_document_states()
                    
                except Exception as e:
                    print(f"Error in process_and_notify: {str(e)}")
                    import traceback
                    print(f"Traceback:\n{traceback.format_exc()}")
                    
                    # Update document state
                    if doc_state_key in self.document_states:
                        doc_state = self.document_states[doc_state_key]
                        
                        # Only send error notification if we haven't already sent a completion notification
                        if not doc_state.get("processing_completed", False):
                            await self.message_sender.send_message(
                                from_number, 
                                f"❌ There was an error processing your document: {str(e)}\n\n"
                                f"You can still try asking questions about it, but results may be limited."
                            )
                            
                            # Update state
                            doc_state["processing_completed"] = True
                            doc_state["last_notification"] = int(time.time())
                    
                    # Remove from processing documents
                    self.deduplication.mark_document_processed(processing_key)
            
            # Fire and forget the processing task
            asyncio.create_task(process_and_notify())
            
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
        
        print(f"Cleaned up document states. Remaining: {len(self.document_states)}") 