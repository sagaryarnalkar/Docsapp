import logging
from utils.response_builder import ResponseBuilder

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, media_handler, document_handler):
        self.media_handler = media_handler
        self.document_handler = document_handler

    def handle_command(self, command, user_phone, request_values=None):
        """Route and handle different commands"""
        try:
            if command == 'help':
                return ResponseBuilder.get_help_message()
                
            elif command == 'list':
                return self.document_handler.list_documents(user_phone)
                
            elif command.startswith('find '):
                query = command[5:].strip()
                return self.document_handler.find_document(user_phone, query)
                
            elif command.startswith('delete '):
                return self.document_handler.delete_document(user_phone, command)
                
            elif command.isdigit():
                return self.document_handler.handle_document_selection(user_phone, command)
                
            else:
                return ResponseBuilder.get_welcome_message()
                
        except Exception as e:
            logger.error(f"Error handling command '{command}': {str(e)}")
            return "❌ An error occurred. Please try again."