# routes/handlers/whatsapp_handler.py
import requests
import json
import logging
import os
from .auth_handler import AuthHandler
from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_API_VERSION,
    TEMP_DIR
)
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

    async def send_message(self, to_number, message):
        """Send WhatsApp message using Meta API"""
        try:
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
                    
                    return response.status == 200
            
        except Exception as e:
            print(f"Error sending WhatsApp message: {str(e)}")
            import traceback
            print(f"Send Message Traceback: {traceback.format_exc()}")
            return False

    async def handle_incoming_message(self, data):
        """Handle incoming WhatsApp message"""
        try:
            print("\n=== Processing WhatsApp Message ===")
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
            message_type = message.get('type')
            from_number = message.get('from')

            print(f"\nMessage Details:")
            print(f"Type: {message_type}")
            print(f"From: {from_number}")

            # Handle document messages with caption
            if message_type == 'document':
                print("Processing document message...")
                result = await self.handle_document(from_number, message.get('document', {}), message)
                print(f"Document processing result: {result}")
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
                await self.send_message(from_number, "Sorry, I can only process text messages and documents at the moment.")
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

                                        # Store in Drive with description
                                        store_result = await self.docs_app.store_document(from_number, temp_path, description, filename)
                                        debug_info.append(f"Store document result: {store_result}")

                                        if store_result:
                                            debug_info.append("Document stored successfully")
                                            response_message = (
                                                f"✅ Document '{filename}' stored successfully!\n\n"
                                                f"Initial description: {description}\n\n"
                                                "You can reply to this message with additional descriptions "
                                                "to make the document easier to find later!"
                                            )
                                            
                                            # Try RAG processing in the background
                                            try:
                                                rag_result = await self.rag_handler.process_document_async(store_result.get('file_id'), mime_type)
                                                if rag_result:
                                                    response_message += "\n\nℹ️ Document is being processed for Q&A functionality."
                                            except Exception as e:
                                                logger.error(f"RAG processing failed but document was stored: {str(e)}")
                                            
                                            await self.send_message(from_number, response_message)
                                            return "Document stored successfully", 200
                                        else:
                                            debug_info.append("Failed to store document")
                                            error_msg = "❌ Error storing document. Please try again later."
                                            await self.send_message(from_number, error_msg)
                                            raise WhatsAppHandlerError("Failed to store document")

                                        if os.path.exists(temp_path):
                                            os.remove(temp_path)
                                            debug_info.append("Temp file cleaned up")
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
- Send any document to store it
- Add descriptions by replying to a document
- 'list' to see your documents
- 'find <text>' to search documents
- '/ask <question>' to ask questions about your documents (Beta)
- 'help' to see this message"""
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