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
from models.rag_processor import RAGProcessor
from .rag_handler import RAGHandler
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
        self.base_url = f'https://graph.facebook.com/{WHATSAPP_API_VERSION}'
        self.headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        self.auth_handler = AuthHandler(self.user_state)
        self.rag_handler = RAGHandler(self.docs_app)
        self.sent_messages = {}  # Track sent messages
        
        # Initialize RAG processor
        try:
            self.rag_processor = RAGProcessor(
                project_id=GOOGLE_CLOUD_PROJECT,
                location=GOOGLE_CLOUD_LOCATION,
                credentials_path=GOOGLE_APPLICATION_CREDENTIALS
            )
            self.rag_available = hasattr(self.rag_processor, 'language_model')
            logger.info("RAG processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG processor: {str(e)}")
            self.rag_available = False
            self.rag_processor = None

    async def send_message(self, to_number, message):
        """Send WhatsApp message using Meta API"""
        try:
            # Generate a unique key for this message
            message_key = f"{to_number}:{message}"
            current_time = int(time.time())
            
            # Clean up old sent messages (older than 1 hour)
            cutoff_time = current_time - 3600
            self.sent_messages = {k:v for k,v in self.sent_messages.items() if v > cutoff_time}
            
            # Check if we've sent this exact message recently
            if message_key in self.sent_messages:
                print(f"Skipping duplicate message to {to_number}: {message[:50]}...")
                return True
            
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

            messages = value.get('messages', [])
            if not messages:
                print("No messages in payload")
                return "No messages found", 200

            message = messages[0]
            from_number = message.get('from')

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
                                            response_message = (
                                                f"✅ Document '{filename}' stored successfully!\n\n"
                                                f"Initial description: {description}\n\n"
                                                "You can reply to this message with additional descriptions "
                                                "to make the document easier to find later!"
                                            )
                                            
                                            # Try RAG processing in the background, but don't wait for it
                                            try:
                                                # Fire and forget RAG processing
                                                import asyncio
                                                asyncio.create_task(self.rag_handler.process_document_async(
                                                    store_result.get('file_id'), 
                                                    store_result.get('mime_type'),
                                                    from_number  # Pass the user's phone number
                                                ))
                                                response_message += "\n\nℹ️ Document is being processed for Q&A functionality in the background."
                                            except Exception as e:
                                                logger.error(f"RAG processing setup failed but document was stored: {str(e)}")
                                                # Don't affect the user response if RAG fails
                                            
                                            await self.send_message(from_number, response_message)
                                            
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
                
                # Use the RAG handler which safely handles failures
                success, message = await self.rag_handler.handle_question(from_number, question)
                await self.send_message(from_number, message)
                return "Question processed", 200 if success else 500

            else:
                print(f"Unknown command: {command}")
                await self.send_message(from_number, "I don't understand that command. Type 'help' to see available commands.")
                return "Unknown command", 200

        except Exception as e:
            error_msg = "❌ Error processing command. Please try again."
            await self.send_message(from_number, error_msg)
            raise WhatsAppHandlerError(str(e))