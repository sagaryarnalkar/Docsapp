import logging
import os
import json
from datetime import datetime
from config import TEMP_DIR
from models.docs_app import DocsApp

logger = logging.getLogger(__name__)

class DocumentHandler:
    def __init__(self, docs_app, user_documents):
        self.docs_app = docs_app
        self.user_documents = user_documents

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

                    # Return file path and name for the web interface to handle
                    return {
                        'status': 'success',
                        'file_path': temp_path,
                        'filename': filename,
                        'content_type': content_type
                    }

                return {
                    'status': 'error',
                    'message': "Error retrieving the document. Please try again."
                }
            return {
                'status': 'error',
                'message': "Invalid selection. Please try your search again."
            }

        except Exception as e:
            logger.error(f"Error in handle_document_selection: {str(e)}")
            return {
                'status': 'error',
                'message': "An error occurred. Please try again."
            }

    def find_document(self, user_phone, query):
        """Handle find command"""
        try:
            logger.debug(f"Processing find command with query: '{query}'")

            result = self.docs_app.retrieve_document(user_phone, query)

            if not result:
                return {
                    'status': 'error',
                    'message': "Sorry, I couldn't find any documents matching your description."
                }

            # Return the document information for the web interface to handle
            return {
                'status': 'success',
                'file': result
            }

        except Exception as e:
            logger.error(f"Error in find_document: {str(e)}")
            return {
                'status': 'error',
                'message': "An error occurred while searching. Please try again."
            }

    def handle_document(self, phone, document_id):
        """Handle document processing"""
        try:
            # Document handling logic
            return True
        except Exception as e:
            logger.error(f"Document error: {str(e)}")
            return False 