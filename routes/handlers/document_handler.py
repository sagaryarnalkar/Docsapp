import logging
import os
import json
from datetime import datetime
#from twilio.rest import Client
from config import (
    TEMP_DIR, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
)
from utils.text_extractor import extract_text
from models.docs_app import DocsApp

logger = logging.getLogger(__name__)

class DocumentHandler:
    def __init__(self, docs_app, user_documents):
        self.docs_app = docs_app
        self.user_documents = user_documents
        # Removed Twilio client initialization

    def list_documents(self, user_phone):
        """Handle list command"""
        try:
            logger.debug("Processing list command")
            document_list, documents = self.docs_app.list_documents(user_phone)
            if document_list:
                self.user_documents[user_phone] = documents
                response_text = "Your documents:\n\n" + "\n".join(document_list)
                response_text += "\n\nTo get a document, reply with the number (e.g., '2')"
                response_text += "\nTo delete a document, reply with 'delete <number>' (e.g., 'delete 2')"
                return response_text
            return "You don't have any stored documents."
        except Exception as e:
            logger.error(f"Error handling list command: {str(e)}")
            return "❌ Error retrieving document list. Please try again."

    def delete_document(self, user_phone, command):
        """Handle delete command"""
        try:
            index = int(command.split('delete ')[1]) - 1
            if user_phone in self.user_documents and 0 <= index < len(self.user_documents[user_phone]):
                doc_id = self.user_documents[user_phone][index][0]
                filename = self.user_documents[user_phone][index][2]
                if self.docs_app.delete_document(user_phone, doc_id):
                    return f"✅ Document '{filename}' deleted successfully!"
                return "❌ Failed to delete document. Please try again."
            return "❌ Invalid document number. Use 'list' to see your documents."
        except ValueError:
            return "❌ Invalid command. Use 'delete <number>' (e.g., 'delete 1')"
        except Exception as e:
            logger.error(f"Error in delete_document: {str(e)}")
            return "❌ An error occurred. Please try again."

    def handle_document_selection(self, user_phone, selection):
        """Handle document selection from list"""
        try:
            selection = int(selection)
            matches = self.user_documents[user_phone]

            if 1 <= selection <= len(matches):
                _, file_id, filename = matches[selection-1]
                file_data, content_type = self.docs_app.get_document(file_id, user_phone)

                if file_data:
                    # Create temporary file
                    temp_path = os.path.join(TEMP_DIR, filename)
                    logger.debug(f"Creating temporary file: {temp_path}")

                    with open(temp_path, 'wb') as f:
                        file_data.seek(0)
                        f.write(file_data.read())

                    # Send file through WhatsApp
                    media_url = f'https://sagary.pythonanywhere.com/temp/{filename}'
                    logger.debug(f"Sending media: {media_url}")

                    message = self.client.messages.create(
                        body=f"Here's your document: {filename}",
                        from_=TWILIO_WHATSAPP_NUMBER,
                        to=user_phone,
                        media_url=[media_url]
                    )

                    del self.user_documents[user_phone]
                    return "✅ Here's your document!"

                return "❌ Error retrieving the document. Please try again."
            return "❌ Invalid selection. Please try your search again."

        except Exception as e:
            logger.error(f"Error in handle_document_selection: {str(e)}")
            return "❌ An error occurred. Please try again."

    def find_document(self, user_phone, query):
        """Handle find command"""
        try:
            logger.debug(f"Processing find command with query: '{query}'")

            file_data, filename, content_type, multiple_matches = self.docs_app.retrieve_document(user_phone, query)

            if multiple_matches:
                descriptions, matches = multiple_matches
                self.user_documents[user_phone] = matches
                response_text = "I found multiple matching documents:\n\n"
                response_text += "\n".join(descriptions)
                response_text += "\n\nPlease reply with the number of the document you want."
                return response_text

            elif file_data:
                # Create temporary file
                temp_path = os.path.join(TEMP_DIR, filename)
                logger.debug(f"Creating temporary file: {temp_path}")

                with open(temp_path, 'wb') as f:
                    file_data.seek(0)
                    f.write(file_data.read())

                # Send file through WhatsApp
                media_url = f'https://sagary.pythonanywhere.com/temp/{filename}'

                message = self.client.messages.create(
                    body=f"Here's your document: {filename}",
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=user_phone,
                    media_url=[media_url]
                )
                return "✅ Here's your document!"

            return "❌ Sorry, I couldn't find any documents matching your description."

        except Exception as e:
            logger.error(f"Error in find_document: {str(e)}")
            return "❌ An error occurred while searching. Please try again."

    def handle_document(self, phone, document_id):
        """Handle document processing"""
        try:
            # Document handling logic
            return True
        except Exception as e:
            logger.error(f"Document error: {str(e)}")
            return False