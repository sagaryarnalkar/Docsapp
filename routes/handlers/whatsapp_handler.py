# routes/handlers/whatsapp_handler.py
import requests
import json
import logging
import os
from models.user_state import UserState  # Add this import
from routes.handlers import AuthHandler  # Add this import
from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_API_VERSION,
    TEMP_DIR
)

logger = logging.getLogger(__name__)

class WhatsAppHandler:
    def __init__(self, docs_app_instance, pending_descriptions, user_state):  # Add user_state parameter
        self.docs_app = docs_app_instance
        self.pending_descriptions = pending_descriptions
        self.base_url = f'https://graph.facebook.com/{WHATSAPP_API_VERSION}'
        self.headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        self.user_state = user_state  # Store passed user_state
        self.auth_handler = AuthHandler(self.user_state)

    def send_text_message(self, to_phone, message):
        """Send a regular text message"""
        try:
            url = f'{self.base_url}/{WHATSAPP_PHONE_NUMBER_ID}/messages'

            print("\n=== Sending WhatsApp Message ===")
            print(f"URL: {url}")
            print(f"Headers: {self.headers}")

            data = {
                'messaging_product': 'whatsapp',
                'to': to_phone,
                'type': 'text',
                'text': {'body': message}
            }
            print(f"Request Data: {json.dumps(data, indent=2)}")

            response = requests.post(url, headers=self.headers, json=data)
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text}")

            return response.status_code == 200

        except Exception as e:
            print(f"Error sending text message: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

    def handle_incoming_message(self, data):
        """Handle incoming WhatsApp message"""
        try:
            print("\n=== Processing WhatsApp Message ===")
            print(f"Raw Data: {json.dumps(data)}")

            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})

            # If there are messages, log them
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

            if message_type == 'document':
                return self.handle_document(from_number, message.get('document', {}))
            elif message_type == 'text':
                return self.handle_text_command(from_number, message.get('text', {}).get('body', ''))
            else:
                print(f"Unsupported message type: {message_type}")
                self.send_text_message(
                    from_number,
                    "Sorry, I can only process text messages and documents at the moment."
                )
                return "Unsupported message type", 200

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return "Error processing message", 500

    def handle_document(self, from_number, document):
        """Handle incoming document"""
        debug_info = []
        try:
            debug_info.append("=== Document Processing Started ===")
            debug_info.append(f"Document details: {json.dumps(document, indent=2)}")

            # First check if user is authorized
            is_authorized = self.user_state.is_authorized(from_number)
            debug_info.append(f"User authorization status: {is_authorized}")

            if not is_authorized:
                auth_response = self.auth_handler.handle_authorization(from_number)
                debug_info.append(f"Auth Response: {auth_response}")

                import re
                url_match = re.search(r'(https://accounts\.google\.com/[^\s]+)', auth_response)
                if url_match:
                    auth_url = url_match.group(1)
                    full_message = f"Please authorize Google Drive access:\n\n{auth_url}\n\nDebug Info:\n" + "\n".join(debug_info)
                    self.send_text_message(from_number, full_message)
                else:
                    debug_info.append("Could not extract auth URL")
                    self.send_text_message(
                        from_number,
                        "Error getting auth URL. Debug Info:\n" + "\n".join(debug_info)
                    )
                return "Authorization needed", 200

            # Get document details
            doc_id = document.get('id')
            filename = document.get('filename', 'unnamed_document')
            mime_type = document.get('mime_type')
            debug_info.append(f"Doc ID: {doc_id}")
            debug_info.append(f"Filename: {filename}")
            debug_info.append(f"MIME Type: {mime_type}")

            # Get media URL first
            media_request_url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{doc_id}"
            headers = {
                'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
                'Accept': '*/*'
            }

            debug_info.append(f"Media Request URL: {media_request_url}")
            debug_info.append(f"Using headers: {json.dumps(headers)}")

            # First get the media URL
            media_response = requests.get(media_request_url, headers=headers)
            debug_info.append(f"Media URL Request Status: {media_response.status_code}")
            debug_info.append(f"Media URL Response: {media_response.text}")

            if media_response.status_code == 200:
                try:
                    media_data = media_response.json()
                    download_url = media_data.get('url')
                    debug_info.append(f"Got download URL: {download_url}")

                    if download_url:
                        # Now download the actual file
                        file_response = requests.get(download_url, headers=headers)
                        debug_info.append(f"File Download Status: {file_response.status_code}")

                        if file_response.status_code == 200:
                            temp_path = os.path.join(TEMP_DIR, filename)
                            with open(temp_path, 'wb') as f:
                                f.write(file_response.content)

                            debug_info.append(f"File saved to: {temp_path}")

                            # Store in Drive
                            store_result = self.docs_app.store_document(from_number, temp_path, "Document from WhatsApp", filename)
                            debug_info.append(f"Store document result: {store_result}")

                            if store_result:
                                debug_info.append("Document stored successfully")
                                self.send_text_message(
                                    from_number,
                                    f"✅ Document '{filename}' stored successfully!\n\nDebug Info:\n" + "\n".join(debug_info)
                                )
                            else:
                                debug_info.append("Failed to store document")
                                self.send_text_message(
                                    from_number,
                                    f"❌ Error storing document. Debug Info:\n" + "\n".join(debug_info)
                                )

                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                                debug_info.append("Temp file cleaned up")
                        else:
                            debug_info.append(f"File download failed: {file_response.text}")
                            self.send_text_message(
                                from_number,
                                f"❌ File download failed. Debug Info:\n" + "\n".join(debug_info)
                            )
                    else:
                        debug_info.append("No download URL found in response")
                        self.send_text_message(
                            from_number,
                            f"❌ No download URL found. Debug Info:\n" + "\n".join(debug_info)
                        )
                except json.JSONDecodeError as e:
                    debug_info.append(f"Error parsing media response: {str(e)}")
                    self.send_text_message(
                        from_number,
                        f"❌ Error parsing media response. Debug Info:\n" + "\n".join(debug_info)
                    )
            else:
                debug_info.append(f"Media URL request failed: {media_response.text}")
                self.send_text_message(
                    from_number,
                    f"❌ Media URL request failed. Debug Info:\n" + "\n".join(debug_info)
                )

            return "Document processed", 200

        except Exception as e:
            debug_info.append(f"Error: {str(e)}")
            import traceback
            debug_info.append(f"Traceback: {traceback.format_exc()}")
            self.send_text_message(
                from_number,
                f"❌ Error processing document. Debug Info:\n" + "\n".join(debug_info)
            )
            return "Error processing document", 500

    def handle_text_command(self, from_number, text):
        """Handle text commands"""
        try:
            # Log the command
            print(f"Processing command: {text} from {from_number}")

            # Normalize the command
            command = text.lower().strip()

            # Process different commands
            if command == 'help':
                help_message = """🤖 Available commands:
- Send any document to store it
- 'list' to see your documents
- 'find <text>' to search documents
- 'help' to see this message"""
                self.send_text_message(from_number, help_message)

            elif command == 'list':
                # Use your existing docs_app to list documents
                document_list, _ = self.docs_app.list_documents(from_number)
                if document_list:
                    message = "Your documents:\n\n" + "\n".join(document_list)
                else:
                    message = "You don't have any stored documents."
                self.send_text_message(from_number, message)

            elif command.startswith('find '):
                query = command[5:].strip()
                # Use your existing retrieve_document method
                result = self.docs_app.retrieve_document(from_number, query)
                # Handle the result and send appropriate message
                if result:
                    self.send_text_message(from_number, "Found matching documents!")
                else:
                    self.send_text_message(from_number, "No documents found matching your query.")

            else:
                self.send_text_message(
                    from_number,
                    "I didn't understand that command. Type 'help' to see available commands."
                )

            return "Command processed", 200

        except Exception as e:
            print(f"Error handling command: {str(e)}")
            return "Error processing command", 500