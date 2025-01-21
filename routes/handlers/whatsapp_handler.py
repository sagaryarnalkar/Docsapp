# routes/handlers/whatsapp_handler.py
import requests
import json
import logging
import os
from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_API_VERSION,
    TEMP_DIR
)

logger = logging.getLogger(__name__)

class WhatsAppHandler:
    def __init__(self, docs_app_instance, pending_descriptions):
        self.docs_app = docs_app_instance
        self.pending_descriptions = pending_descriptions
        self.base_url = f'https://graph.facebook.com/{WHATSAPP_API_VERSION}'
        self.headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        self.user_state = UserState()
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
        try:
            print(f"\nDocument Details:")
            print(f"Document: {json.dumps(document, indent=2)}")

            # First check if user is authorized
            if not self.user_state.is_authorized(from_number):
                auth_url = self.auth_handler.handle_authorization(from_number)
                self.send_text_message(
                    from_number,
                    "Please authorize access to Google Drive first using this link. After authorizing, send your document again."
                )
                return "Authorization needed", 200

            # Get document details
            doc_id = document.get('id')
            filename = document.get('filename', 'unnamed_document')
            mime_type = document.get('mime_type')

            # Download document
            download_url = f"{self.base_url}/{doc_id}"
            download_headers = {
                'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            }

            print(f"\nDownloading document from: {download_url}")
            response = requests.get(download_url, headers=download_headers)

            if response.status_code == 200:
                # Save document temporarily
                temp_path = os.path.join(TEMP_DIR, filename)
                with open(temp_path, 'wb') as f:
                    f.write(response.content)

                print(f"Document saved to: {temp_path}")

                # Store in Drive using existing functionality
                if self.docs_app.store_document(from_number, temp_path, "Document from WhatsApp", filename):
                    print("Document stored successfully")
                    self.send_text_message(
                        from_number,
                        f"✅ Document '{filename}' stored successfully! You can reply with a description to help find it later."
                    )
                else:
                    print("Failed to store document")
                    self.send_text_message(
                        from_number,
                        "❌ Sorry, there was an error storing your document. Please try again."
                    )

                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            else:
                print(f"Failed to download document: {response.text}")
                self.send_text_message(
                    from_number,
                    "❌ Sorry, I couldn't download your document. Please try again."
                )

            return "Document processed", 200

        except Exception as e:
            print(f"Error handling document: {str(e)}")
            import traceback
            print(traceback.format_exc())
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