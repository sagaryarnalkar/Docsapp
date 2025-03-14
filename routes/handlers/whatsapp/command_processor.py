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
            
            # Detect command intent from natural language
            command_intent = self._detect_command_intent(command)
            if command_intent:
                print(f"Detected command intent: {command_intent}")
                command = command_intent
            
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
                help_message = (
                    "I don't understand that command. Here are some things you can say:\n\n"
                    "• 'list' or 'show my documents' - See your stored files\n"
                    "• 'find [text]' - Search for specific documents\n"
                    "• '/ask [question]' - Ask questions about your documents\n"
                    "• 'help' - See all available commands\n\n"
                    "You can also just send me any document to store it!"
                )
                await self.message_sender.send_message(from_number, help_message)
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

    def _detect_command_intent(self, text):
        """
        Detect command intent from natural language.
        
        Args:
            text: The user's message
            
        Returns:
            str: The detected command, or None if no command was detected
        """
        # Normalize text for better matching
        normalized_text = text.lower().strip()
        
        # Print debug info
        print(f"Detecting intent for: '{normalized_text}'")
        
        # List command phrases
        list_phrases = [
            'show me my files', 'show my files', 'show my documents', 
            'list my files', 'list my documents', 'show documents',
            'what files do i have', 'what documents do i have',
            'view my files', 'view my documents', 'display my files',
            'show all my files', 'show all documents', 'get my files',
            'see my files', 'see my documents', 'show me a list of my documents',
            'show me my documents', 'list of my documents', 'list of documents',
            'what documents have i stored', 'what documents have i saved',
            'what have i stored', 'show me what i have'
        ]
        
        # Help command phrases
        help_phrases = [
            'what can you do', 'how does this work', 'how to use',
            'show me help', 'need help', 'instructions', 'guide me',
            'how do i', 'what commands', 'available commands',
            'help me', 'i need help', 'show help'
        ]
        
        # Find command phrases
        find_prefixes = [
            'find', 'search for', 'look for', 'search', 'locate',
            'get me', 'find me', 'search my files for', 'find documents about',
            'search documents for', 'find files about', 'look up'
        ]
        
        # Ask command phrases
        ask_prefixes = [
            'ask', 'tell me', 'what is', 'who is', 'when is',
            'where is', 'why is', 'how is', 'can you tell me',
            'i want to know', 'explain', 'describe'
        ]
        
        # Check for exact matches first
        if normalized_text == 'list':
            print("Detected exact match for 'list' command")
            return 'list'
        elif normalized_text == 'help':
            print("Detected exact match for 'help' command")
            return 'help'
        
        # Check for list command
        for phrase in list_phrases:
            if phrase in normalized_text:
                print(f"Detected list intent from phrase: '{phrase}'")
                return 'list'
        
        # Check for help command
        for phrase in help_phrases:
            if phrase in normalized_text:
                print(f"Detected help intent from phrase: '{phrase}'")
                return 'help'
        
        # Check for find command
        for prefix in find_prefixes:
            if normalized_text.startswith(prefix + ' '):
                query = normalized_text[len(prefix) + 1:].strip()
                if query:  # Only if there's something to search for
                    print(f"Detected find intent with query: '{query}'")
                    return f'find {query}'
        
        # Check for ask command
        for prefix in ask_prefixes:
            if normalized_text.startswith(prefix + ' '):
                question = normalized_text[len(prefix) + 1:].strip()
                if question:  # Only if there's a question
                    print(f"Detected ask intent with question: '{question}'")
                    return f'/ask {question}'
        
        # No command intent detected
        print("No intent detected")
        return None 