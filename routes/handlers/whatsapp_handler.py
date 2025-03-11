# routes/handlers/whatsapp_handler.py
import requests
import json
import logging
import os
import time
from .auth_handler import AuthHandler
from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_API_VERSION,
    TEMP_DIR,
    GOOGLE_CLOUD_PROJECT,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_APPLICATION_CREDENTIALS
)
import aiohttp

logger = logging.getLogger(__name__)

class WhatsAppHandlerError(Exception):
    """Custom exception for WhatsApp handler errors that have already been communicated to the user."""
    pass

class WhatsAppHandler:
    def __init__(self, docs_app, pending_descriptions, user_state):
        self.docs_app = docs_app
        self.pending_descriptions = pending_descriptions
        self.user_state = user_state
        self.api_version = WHATSAPP_API_VERSION
        self.phone_number_id = WHATSAPP_PHONE_NUMBER_ID
        self.access_token = WHATSAPP_ACCESS_TOKEN
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        self.auth_handler = AuthHandler(self.user_state)
        self.rag_processor = docs_app.rag_processor if docs_app else None
        self.rag_available = self.rag_processor is not None and hasattr(self.rag_processor, 'is_available') and self.rag_processor.is_available
        self.sent_messages = {}  # Track sent messages
        self.processed_documents = {}  # Track processed documents to prevent duplicates

    async def send_message(self, to_number, message):
        """Send WhatsApp message using Meta API"""
        try:
            # Generate a unique key for this message
            message_key = f"{to_number}:{message}"
            current_time = int(time.time())
            
            # Clean up old sent messages (older than 1 hour)
            cutoff_time = current_time - 3600
            self.sent_messages = {k:v for k,v in self.sent_messages.items() if v > cutoff_time}
            
            # Check if we've sent this exact message recently (within 60 seconds)
            if message_key in self.sent_messages:
                time_since_sent = current_time - self.sent_messages[message_key]
                if time_since_sent < 60:  # Increased from 30 to 60 seconds
                    print(f"Skipping duplicate message to {to_number}: {message[:50]}... (sent {time_since_sent}s ago)")
                    return True
                else:
                    print(f"Message was sent before, but {time_since_sent}s ago, so sending again")
            
            # For document confirmations, use a more aggressive deduplication
            if "Document" in message and "stored successfully" in message:
                # Create a simplified key that ignores the exact filename
                simplified_key = f"{to_number}:document_stored"
                if simplified_key in self.sent_messages:
                    time_since_sent = current_time - self.sent_messages[simplified_key]
                    if time_since_sent < 300:  # 5 minutes for document confirmations
                        print(f"Skipping duplicate document confirmation to {to_number} (sent {time_since_sent}s ago)")
                        return True
                # Store both the exact message and the simplified version
                self.sent_messages[simplified_key] = current_time
            
            url = f'https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages'
            
            headers = {
                'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'to': to_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            print(f"\nSending message to {to_number}:")
            print(f"URL: {url}")
            print(f"Data: {json.dumps(data, indent=2)}")
            
            # Use aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response_text = await response.text()
                    print(f"Response Status: {response.status}")
                    print(f"Response Body: {response_text}")
                    
                    if response.status == 400:
                        error_data = json.loads(response_text)
                        error_message = error_data.get('error', {}).get('message', '')
                        if 'access token' in error_message.lower():
                            print("WhatsApp access token error detected")
                            logger.error(f"WhatsApp API Error: {error_message}")
                            return False
                    
                    if response.status == 200:
                        # Mark message as sent
                        self.sent_messages[message_key] = current_time
                    
                    return response.status == 200
            
        except Exception as e:
            print(f"Error sending WhatsApp message: {str(e)}")
            import traceback
            print(f"Send Message Traceback: {traceback.format_exc()}")
            return False

    async def handle_incoming_message(self, data):
        """Handle incoming WhatsApp message"""
        try:
            print(f"\n{'='*50}")
            print("WHATSAPP MESSAGE PROCESSING START")
            print(f"{'='*50}")
            print(f"Raw Data: {json.dumps(data, indent=2)}")

            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})

            # Check if this is a status update
            if 'statuses' in value:
                print("Status update received - ignoring")
                return "Status update processed", 200

            # Extract message data
            messages = value.get('messages', [])
            if not messages:
                print("No messages found in payload")
                return "No messages to process", 200

            message = messages[0]
            message_id = message.get('id')
            from_number = message.get('from')
            
            # Create a more robust message key that includes the from_number
            message_key = f"{from_number}:{message_id}"
            
            # Check for duplicate message processing
            current_time = int(time.time())
            
            # Clean up old processed messages (older than 10 minutes)
            cutoff_time = current_time - 600  # 10 minutes
            self.processed_documents = {k:v for k,v in self.processed_documents.items() if v > cutoff_time}
            
            # Check both the combined key and the message_id for backward compatibility
            if message_key in self.processed_documents or message_id in self.processed_documents:
                time_since_processed = current_time - (self.processed_documents.get(message_key) or self.processed_documents.get(message_id))
                print(f"Skipping duplicate message processing for message ID {message_id} from {from_number} (processed {time_since_processed}s ago)")
                return "Duplicate message processing prevented", 200
            
            # Mark this message as being processed with both keys
            self.processed_documents[message_key] = current_time
            self.processed_documents[message_id] = current_time
            print(f"Processing new message {message_id} from {from_number}")

            print(f"\n=== Message Details ===")
            print(f"From: {from_number}")

            # Check authentication status first for any message
            is_authorized = self.user_state.is_authorized(from_number)
            print(f"User authorization status: {is_authorized}")

            if not is_authorized:
                print("\n=== Starting OAuth Flow ===")
                auth_url = self.auth_handler.handle_authorization(from_number)
                print(f"Generated Auth URL: {auth_url}")

                if auth_url.startswith('http'):
                    message = (
                        "🔐 *Authorization Required*\n\n"
                        "To use this bot and manage your documents, I need access to your Google Drive.\n\n"
                        "Please click the link below to authorize:\n\n"
                        f"{auth_url}\n\n"
                        "After authorizing, you can start using the bot!"
                    )
                    print("\n=== Sending Auth Message ===")
                    print(f"Message: {message}")
                    
                    send_result = await self.send_message(from_number, message)
                    if not send_result:
                        print("Failed to send authorization message - WhatsApp token may be invalid")
                        return "WhatsApp token error", 500
                    print(f"Successfully sent authorization URL to {from_number}")
                else:
                    error_msg = "❌ Error getting authorization URL. Please try again later."
                    await self.send_message(from_number, error_msg)
                    print(f"Error with auth URL: {auth_url}")
                return "Authorization needed", 200

            # Now process the message since user is authorized
            message_type = message.get('type')

            # Handle all file types (document, image, video, audio)
            if message_type in ['document', 'image', 'video', 'audio']:
                print(f"Processing {message_type} message...")
                # Get the media object based on type
                media_obj = message.get(message_type, {})
                if not media_obj:
                    print(f"No {message_type} object found in message")
                    return f"No {message_type} found", 400
                
                # For images and other media that might not have filename
                if message_type != 'document':
                    extension = {
                        'image': '.jpg',
                        'video': '.mp4',
                        'audio': '.mp3'
                    }.get(message_type, '')
                    media_obj['filename'] = f"{message_type}_{int(time.time())}{extension}"
                
                result = await self.handle_document(from_number, media_obj, message)
                print(f"{message_type.capitalize()} processing result: {result}")
                return result
                
            # Handle text messages and document replies
            elif message_type == 'text':
                # Check if this is a reply to a document (for adding descriptions)
                if 'context' in message:
                    print("Processing document reply...")
                    result = await self.handle_document(from_number, None, message)
                    print(f"Document reply result: {result}")
                    return result
                # Handle regular text commands
                else:
                    print(f"Processing text message: {message.get('text', {}).get('body', '')}")
                    result = await self.handle_text_command(from_number, message.get('text', {}).get('body', ''))
                    print(f"Text processing result: {result}")
                    return result
            else:
                print(f"Unsupported message type: {message_type}")
                await self.send_message(from_number, "Sorry, I don't understand this type of message. You can send me documents, images, videos, audio files, or text commands.")
                raise WhatsAppHandlerError("Unsupported message type")

        except WhatsAppHandlerError:
            raise
        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            await self.send_message(from_number, "❌ Sorry, there was an error processing your request. Please try again later.")
            raise WhatsAppHandlerError(str(e))

    async def handle_document(self, from_number, document, message=None):
        """Handle incoming document"""
        debug_info = []
        try:
            debug_info.append("=== Document Processing Started ===")
            debug_info.append(f"Document details: {json.dumps(document, indent=2)}")

            # Check for duplicate document processing
            doc_id = document.get('id') if document else None
            current_time = int(time.time())
            
            # Clean up old processed documents (older than 10 minutes)
            cutoff_time = current_time - 600  # 10 minutes
            self.processed_documents = {k:v for k,v in self.processed_documents.items() if v > cutoff_time}
            
            # Check if we've processed this document recently
            if doc_id and doc_id in self.processed_documents:
                time_since_processed = current_time - self.processed_documents[doc_id]
                print(f"Skipping duplicate document processing for {doc_id} (processed {time_since_processed}s ago)")
                return "Duplicate document processing prevented", 200
                
            # Create a unique key for this document and user
            doc_user_key = f"{from_number}:{doc_id}"
            if doc_user_key in self.processed_documents:
                time_since_processed = current_time - self.processed_documents[doc_user_key]
                print(f"Skipping duplicate document processing for user {from_number} and doc {doc_id} (processed {time_since_processed}s ago)")
                return "Duplicate document processing prevented", 200
                
            # Mark this document as being processed for this user
            self.processed_documents[doc_user_key] = current_time
            self.processed_documents[doc_id] = current_time

            # Handle replies to documents (for adding descriptions)
            if message and 'context' in message:
                context = message.get('context', {})
                quoted_msg_id = context.get('id')
                debug_info.append(f"Found reply context. Quoted message ID: {quoted_msg_id}")

                if quoted_msg_id:
                    description = message.get('text', {}).get('body', '')
                    debug_info.append(f"Adding description from reply: {description}")
                    result = self.docs_app.update_document_description(from_number, quoted_msg_id, description)
                    if result:
                        await self.send_message(from_number, f"✅ Added description to document: {description}\n\n" +
                            "You can keep adding more descriptions to make the document easier to find!")
                    else:
                        await self.send_message(from_number, f"❌ Failed to update document description.\n\nDebug Info:\n" + "\n".join(debug_info))
                    return "Description updated", 200

            # First check if user is authorized
            print(f"=== Starting Authorization Check for {from_number} ===")
            is_authorized = self.user_state.is_authorized(from_number)
            debug_info.append(f"User authorization status: {is_authorized}")

            if not is_authorized:
                print("User not authorized - getting auth URL")
                auth_response = self.auth_handler.handle_authorization(from_number)
                debug_info.append(f"Auth Response: {auth_response}")

                import re
                url_match = re.search(r'(https://accounts\.google\.com/[^\s]+)', auth_response)
                if url_match:
                    auth_url = url_match.group(1)
                    message = (
                        "🔐 *Authorization Required*\n\n"
                        "To store and manage your documents, I need access to your Google Drive.\n\n"
                        "Please click the link below to authorize:\n\n"
                        f"{auth_url}\n\n"
                        "After authorizing, send your document again!"
                    )
                    send_result = await self.send_message(from_number, message)
                    if not send_result:
                        print("Failed to send authorization message - WhatsApp token may be invalid")
                        return "WhatsApp token error", 500
                    print(f"Sent authorization URL to {from_number}")
                else:
                    error_msg = "❌ Error getting authorization URL. Please try again later."
                    await self.send_message(from_number, error_msg)
                    print(f"Could not extract auth URL from response: {auth_response}")
                return "Authorization needed", 200

            # If this is a reply or no document provided, return early
            if not document:
                return "No document to process", 200

            # Get document details
            doc_id = document.get('id')
            filename = document.get('filename', 'unnamed_document')
            mime_type = document.get('mime_type')
            debug_info.append(f"Doc ID: {doc_id}")
            debug_info.append(f"Filename: {filename}")
            debug_info.append(f"MIME Type: {mime_type}")

            # Get initial description from caption if provided
            description = "Document from WhatsApp"
            if message and message.get('caption'):
                description = message.get('caption')
                debug_info.append(f"Using caption as initial description: {description}")

            # Get media URL first
            media_request_url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{doc_id}"
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
                                            store_result = await self.docs_app.store_document(from_number, temp_path, description, filename)
                                            debug_info.append(f"Store document result: {store_result}")

                                            if not store_result:
                                                debug_info.append("Failed to store document")
                                                error_msg = "❌ Error storing document. Please try again later."
                                                await self.send_message(from_number, error_msg)
                                                raise WhatsAppHandlerError("Failed to store document")

                                            debug_info.append("Document stored successfully")
                                            
                                            # Mark this document as processed to prevent duplicates
                                            if doc_id:
                                                self.processed_documents[doc_id] = int(time.time())
                                                doc_user_key = f"{from_number}:{doc_id}"
                                                self.processed_documents[doc_user_key] = int(time.time())
                                                print(f"Marked document {doc_id} as processed for user {from_number}")
                                            
                                            # Create a unique confirmation key for this document
                                            confirmation_key = f"confirmation:{from_number}:{store_result.get('file_id', 'unknown')}"
                                            if confirmation_key in self.sent_messages:
                                                print(f"Skipping duplicate confirmation for {store_result.get('file_id')} - already sent")
                                            else:
                                                # First send immediate confirmation of storage
                                                folder_name = self.docs_app.folder_name
                                                immediate_response = (
                                                    f"✅ Document '{filename}' stored successfully in your Google Drive folder '{folder_name}'!\n\n"
                                                    f"Initial description: {description}\n\n"
                                                    "You can reply to this message with additional descriptions "
                                                    "to make the document easier to find later!"
                                                )
                                                
                                                await self.send_message(from_number, immediate_response)
                                                # Mark this confirmation as sent
                                                self.sent_messages[confirmation_key] = int(time.time())
                                            
                                            # Process document with RAG in the background
                                            if store_result.get('file_id'):
                                                try:
                                                    # Use the docs_app.rag_processor directly
                                                    if self.docs_app and hasattr(self.docs_app, 'rag_processor') and self.docs_app.rag_processor:
                                                        # Track processing to avoid duplicates
                                                        processing_key = f"rag_processing:{store_result.get('file_id')}"
                                                        if processing_key not in self.sent_messages:
                                                            # Create a unique processing notification key
                                                            processing_notification_key = f"processing_notification:{from_number}:{store_result.get('file_id')}"
                                                            
                                                            if processing_notification_key in self.sent_messages:
                                                                print(f"Skipping duplicate processing notification for {store_result.get('file_id')} - already sent")
                                                            else:
                                                                # Send processing started message
                                                                await self.send_message(from_number, "🔄 Document processing started. I'll notify you when it's complete...")
                                                                # Mark this notification as sent
                                                                self.sent_messages[processing_notification_key] = int(time.time())
                                                            
                                                            # Create a task to process the document and notify when done
                                                            async def process_and_notify():
                                                                try:
                                                                    print(f"Starting background RAG processing for document {store_result.get('file_id')}")
                                                                    result = await self.docs_app.rag_processor.process_document_async(
                                                                        store_result.get('file_id'), 
                                                                        store_result.get('mime_type'),
                                                                        from_number
                                                                    )
                                                                    
                                                                    # Create a unique completion notification key
                                                                    completion_notification_key = f"completion_notification:{from_number}:{store_result.get('file_id')}"
                                                                    
                                                                    if completion_notification_key not in self.sent_messages:
                                                                        # Notify user of completion
                                                                        if result and result.get("status") == "success":
                                                                            await self.send_message(from_number, 
                                                                                f"✅ Document '{filename}' has been processed successfully!\n\n"
                                                                                f"You can now ask questions about it using:\n"
                                                                                f"/ask <your question>"
                                                                            )
                                                                        else:
                                                                            error = result.get("error", "Unknown error")
                                                                            await self.send_message(from_number,
                                                                                f"⚠️ Document processing completed with issues: {error}\n\n"
                                                                                f"You can still try asking questions about it."
                                                                            )
                                                                        # Mark completion notification as sent
                                                                        self.sent_messages[completion_notification_key] = int(time.time())
                                                                except Exception as e:
                                                                    print(f"Error in process_and_notify: {str(e)}")
                                                                    import traceback
                                                                    print(f"Traceback:\n{traceback.format_exc()}")
                                                                    
                                                                    # Only send error message if we haven't sent one for this document
                                                                    error_notification_key = f"error_notification:{from_number}:{store_result.get('file_id')}"
                                                                    if error_notification_key not in self.sent_messages:
                                                                        await self.send_message(from_number, 
                                                                            f"❌ There was an error processing your document: {str(e)}\n\n"
                                                                            f"You can still try asking questions about it, but results may be limited."
                                                                        )
                                                                        self.sent_messages[error_notification_key] = int(time.time())
                                                            
                                                            # Fire and forget the processing task
                                                            import asyncio
                                                            asyncio.create_task(process_and_notify())
                                                            
                                                            # Mark as processing to avoid duplicate processing
                                                            self.sent_messages[processing_key] = int(time.time())
                                                except Exception as rag_err:
                                                    print(f"Error starting RAG processing: {str(rag_err)}")
                                                    import traceback
                                                    print(f"RAG processing error traceback:\n{traceback.format_exc()}")
                                            
                                        finally:
                                            # Always clean up temp file
                                            try:
                                                if os.path.exists(temp_path):
                                                    os.remove(temp_path)
                                                    debug_info.append("Temp file cleaned up")
                                            except Exception as e:
                                                logger.error(f"Failed to clean up temp file: {str(e)}")
                                            
                                        return "Document stored successfully", 200
                                    else:
                                        debug_info.append(f"File download failed: {await file_response.text()}")
                                        error_msg = "❌ Failed to download the document. Please try sending it again."
                                        await self.send_message(from_number, error_msg)
                                        raise WhatsAppHandlerError("Failed to download document")
                            else:
                                debug_info.append("No download URL found in response")
                                error_msg = "❌ Could not access the document. Please try sending it again."
                                await self.send_message(from_number, error_msg)
                                raise WhatsAppHandlerError("No download URL found")
                        except json.JSONDecodeError as e:
                            debug_info.append(f"Error parsing media response: {str(e)}")
                            error_msg = "❌ Error processing the document. Please try again later."
                            await self.send_message(from_number, error_msg)
                            raise WhatsAppHandlerError(str(e))
                    else:
                        debug_info.append(f"Media URL request failed: {media_response_text}")
                        error_msg = "❌ Could not access the document. Please try sending it again."
                        await self.send_message(from_number, error_msg)
                        raise WhatsAppHandlerError("Media URL request failed")

        except WhatsAppHandlerError:
            raise
        except Exception as e:
            error_msg = f"❌ Error processing document: {str(e)}"
            await self.send_message(from_number, error_msg)
            raise WhatsAppHandlerError(str(e))

    async def handle_text_command(self, from_number, text):
        """Handle text commands"""
        try:
            # Log the command
            print(f"\n=== Processing Text Command ===")
            print(f"Command: {text}")
            print(f"From: {from_number}")

            # Normalize the command
            command = text.lower().strip()

            # Process different commands
            if command == 'help':
                help_message = """🤖 Available commands:
- Send any file to store it (documents, images, videos, audio)
- Add descriptions by replying to a stored file
- 'list' to see your stored files
- 'find <text>' to search your files
- '/ask <question>' to ask questions about your documents (Beta)
- 'help' to see this message

📎 Supported file types:
• Documents (PDF, Word, Excel, PowerPoint, etc.)
• Images (JPG, PNG, etc.)
• Videos (MP4, etc.)
• Audio files (MP3, etc.)"""
                await self.send_message(from_number, help_message)
                return "Help message sent", 200

            elif command == 'list':
                print("Processing list command...")
                # Use docs_app to list documents
                document_list, _ = self.docs_app.list_documents(from_number)
                if document_list:
                    message = "Your documents:\n\n" + "\n".join(document_list)
                else:
                    message = "You don't have any stored documents."
                await self.send_message(from_number, message)
                return "List command processed", 200

            elif command.startswith('find '):
                print("Processing find command...")
                query = command[5:].strip()
                # Use docs_app to retrieve document
                result = self.docs_app.retrieve_document(from_number, query)
                if result:
                    await self.send_message(from_number, "Found matching documents!")
                else:
                    await self.send_message(from_number, "No documents found matching your query.")
                return "Find command processed", 200

            elif command.startswith('/ask '):
                print("Processing ask command...")
                question = command[5:].strip()
                await self.send_message(from_number, "🔄 Processing your question... This might take a moment.")
                
                # Use the docs_app to process the question
                result = await self.docs_app.ask_question(from_number, question)
                
                if result["status"] == "success" and result.get("answers"):
                    # Format answers from all relevant documents
                    response_parts = ["📝 Here are the answers from your documents:\n"]
                    
                    for idx, answer in enumerate(result["answers"], 1):
                        # Format the answer section
                        response_parts.append(f"📄 Document {idx}: {answer['document']}")
                        response_parts.append(f"Answer: {answer['answer']}")
                        
                        # Add source information if available
                        if answer.get('sources'):
                            source_info = []
                            for source in answer['sources']:
                                metadata = source.get('metadata', {})
                                if metadata.get('page_number'):
                                    source_info.append(f"Page {metadata['page_number']}")
                                if metadata.get('section'):
                                    source_info.append(metadata['section'])
                            if source_info:
                                response_parts.append(f"Source: {', '.join(source_info)}")
                        
                        response_parts.append("")  # Add blank line between answers
                    
                    # Add a note about confidence if available
                    if any(a.get('confidence') for a in result["answers"]):
                        response_parts.append("\nℹ️ Note: Answers are provided based on the relevant content found in your documents.")
                    
                    message = "\n".join(response_parts)
                    await self.send_message(from_number, message)
                    return "Question processed", 200
                else:
                    await self.send_message(from_number, result.get("message", "No relevant information found in your documents."))
                    return "Question processed", 500

            else:
                print(f"Unknown command: {command}")
                await self.send_message(from_number, "I don't understand that command. Type 'help' to see available commands.")
                return "Unknown command", 200

        except Exception as e:
            error_msg = "❌ Error processing command. Please try again."
            await self.send_message(from_number, error_msg)
            raise WhatsAppHandlerError(str(e))