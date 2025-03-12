"""
WhatsApp Command Processor
------------------------
This module handles processing text commands from WhatsApp users.
"""

import logging
from .document_processor import WhatsAppHandlerError

logger = logging.getLogger(__name__)

class CommandProcessor:
    """
    Processes text commands from WhatsApp users.
    
    This class is responsible for:
    1. Parsing and routing text commands
    2. Handling help, list, find, and ask commands
    3. Delegating to the appropriate services
    """
    
    def __init__(self, docs_app, message_sender):
        """
        Initialize the command processor.
        
        Args:
            docs_app: The DocsApp instance for document operations
            message_sender: The MessageSender instance for sending responses
        """
        self.docs_app = docs_app
        self.message_sender = message_sender
        
    async def handle_command(self, from_number, text):
        """
        Process a text command from a user.
        
        Args:
            from_number: The sender's phone number
            text: The command text
            
        Returns:
            tuple: (response_message, status_code)
        """
        try:
            # Log the command
            print(f"\n=== Processing Text Command ===")
            print(f"Command: {text}")
            print(f"From: {from_number}")

            # Normalize the command
            command = text.lower().strip()

            # Process different commands
            if command == 'help':
                return await self._handle_help_command(from_number)
            elif command == 'list':
                return await self._handle_list_command(from_number)
            elif command.startswith('find '):
                return await self._handle_find_command(from_number, command[5:].strip())
            elif command.startswith('/ask '):
                return await self._handle_ask_command(from_number, command[5:].strip())
            else:
                print(f"Unknown command: {command}")
                await self.message_sender.send_message(
                    from_number, 
                    "I don't understand that command. Type 'help' to see available commands."
                )
                return "Unknown command", 200

        except Exception as e:
            error_msg = "❌ Error processing command. Please try again."
            await self.message_sender.send_message(from_number, error_msg)
            raise WhatsAppHandlerError(str(e))
            
    async def _handle_help_command(self, from_number):
        """
        Handle the 'help' command.
        
        Args:
            from_number: The sender's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
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
        await self.message_sender.send_message(from_number, help_message)
        return "Help message sent", 200
        
    async def _handle_list_command(self, from_number):
        """
        Handle the 'list' command.
        
        Args:
            from_number: The sender's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
        print("Processing list command...")
        # Use docs_app to list documents
        document_list, _ = self.docs_app.list_documents(from_number)
        if document_list:
            message = "Your documents:\n\n" + "\n".join(document_list)
        else:
            message = "You don't have any stored documents."
        await self.message_sender.send_message(from_number, message)
        return "List command processed", 200
        
    async def _handle_find_command(self, from_number, query):
        """
        Handle the 'find' command.
        
        Args:
            from_number: The sender's phone number
            query: The search query
            
        Returns:
            tuple: (response_message, status_code)
        """
        print("Processing find command...")
        # Use docs_app to retrieve document
        result = self.docs_app.retrieve_document(from_number, query)
        if result:
            await self.message_sender.send_message(from_number, "Found matching documents!")
        else:
            await self.message_sender.send_message(from_number, "No documents found matching your query.")
        return "Find command processed", 200
        
    async def _handle_ask_command(self, from_number, question):
        """
        Handle the '/ask' command.
        
        Args:
            from_number: The sender's phone number
            question: The question to ask
            
        Returns:
            tuple: (response_message, status_code)
        """
        print("Processing ask command...")
        await self.message_sender.send_message(from_number, "🔄 Processing your question... This might take a moment.")
        
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
            await self.message_sender.send_message(from_number, message)
            return "Question processed", 200
        else:
            await self.message_sender.send_message(
                from_number, 
                result.get("message", "No relevant information found in your documents.")
            )
            return "Question processed", 500 