"""
WhatsApp Command Processor
------------------------
This module handles processing text commands from WhatsApp users.
"""

import logging
import asyncio
from .document_processor import WhatsAppHandlerError
from models.intent_classifier import IntentClassifier
from models.response_generator import ResponseGenerator
import time
import hashlib
import uuid

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
        
        # Initialize the intent classifier and response generator
        self.intent_classifier = IntentClassifier()
        self.response_generator = ResponseGenerator()
        
        # Track context for better responses
        self.user_context = {}
        
        logger.info("[DEBUG] CommandProcessor initialized")
        
    async def handle_command(self, from_number, text):
        """
        Process a command from a user.
        
        Args:
            from_number: The user's phone number
            text: The command text
            
        Returns:
            A tuple of (success, message)
        """
        try:
            # Add timestamp to log for tracking
            timestamp = int(time.time())
            command_hash = hashlib.md5(f"{from_number}:{text}:{timestamp}".encode()).hexdigest()[:8]
            
            print(f"\n==================================================")
            print(f"[DEBUG] COMMAND PROCESSING START - {command_hash}")
            print(f"[DEBUG] From: {from_number}")
            print(f"[DEBUG] Text: '{text}'")
            print(f"[DEBUG] Time: {timestamp}")
            print(f"==================================================")
            
            # Normalize text
            text = text.strip().lower()
            
            # Check for help command
            if text == 'help':
                print(f"[DEBUG] {command_hash} - Detected HELP command")
                return await self._handle_help_command(from_number)
                
            # Check for list command
            if text == 'list':
                print(f"[DEBUG] {command_hash} - Detected LIST command")
                return await self._handle_list_command(from_number)
                
            # Check for find command
            if text.startswith('find '):
                print(f"[DEBUG] {command_hash} - Detected FIND command")
                query = text[5:].strip()
                print(f"[DEBUG] {command_hash} - Find query: '{query}'")
                return await self._handle_find_command(from_number, query)
                
            # Check for ask command
            if text.startswith('/ask '):
                print(f"[DEBUG] {command_hash} - Detected ASK command")
                question = text[5:].strip()
                print(f"[DEBUG] {command_hash} - Question: '{question}'")
                return await self._handle_ask_command(from_number, question)
                
            # Try to detect command intent
            command_intent = self._detect_command_intent(text)
            print(f"[DEBUG] {command_hash} - Command intent detection result: {command_intent}")
            
            if command_intent == 'help':
                print(f"[DEBUG] {command_hash} - Executing HELP command via intent detection")
                return await self._handle_help_command(from_number)
                
            elif command_intent == 'list':
                print(f"[DEBUG] {command_hash} - Executing LIST command via intent detection")
                return await self._handle_list_command(from_number)
                
            elif command_intent.startswith('find:'):
                query = command_intent[5:].strip()
                print(f"[DEBUG] {command_hash} - Executing FIND command via intent detection")
                print(f"[DEBUG] {command_hash} - Find query: '{query}'")
                return await self._handle_find_command(from_number, query)
                
            elif command_intent.startswith('ask:'):
                question = command_intent[4:].strip()
                print(f"[DEBUG] {command_hash} - Executing ASK command via intent detection")
                print(f"[DEBUG] {command_hash} - Question: '{question}'")
                return await self._handle_ask_command(from_number, question)
            
            # No command detected
            print(f"[DEBUG] {command_hash} - No command detected in text: '{text}'")
            return False, "I'm not sure what you're asking. Try 'help' to see available commands."
            
        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            print(f"[ERROR] Command processing error {error_id}: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback {error_id}: {traceback.format_exc()}")
            return False, f"❌ Sorry, an error occurred while processing your command. (Error ID: {error_id})"
            
    async def _handle_help_command(self, from_number):
        """
        Handle the 'help' command.
        
        Args:
            from_number: The sender's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing help command for {from_number}")
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
        logger.info(f"[DEBUG] Sending help message to {from_number}")
        send_result = await self.message_sender.send_message(from_number, help_message)
        logger.info(f"[DEBUG] Help message send result: {send_result}")
        return "Help message sent", 200
        
    async def _handle_list_command(self, from_number):
        """Handle list command"""
        try:
            command_hash = hashlib.md5(f"{from_number}:list:{int(time.time())}".encode()).hexdigest()[:8]
            print(f"[DEBUG] {command_hash} - Executing LIST command for {from_number}")
            
            # Check if user is authorized
            if not self.docs_app._get_user_credentials(from_number):
                print(f"[DEBUG] {command_hash} - User {from_number} is not authorized")
                return False, "You need to log in first. Send 'login' to get started."
            
            # Get document list
            print(f"[DEBUG] {command_hash} - Getting document list for {from_number}")
            document_list, documents = self.docs_app.list_documents(from_number)
            
            if document_list:
                print(f"[DEBUG] {command_hash} - Found {len(document_list)} documents")
                # Add timestamp to make message unique
                timestamp = int(time.time())
                response_text = f"Your documents (as of {timestamp}):\n\n" + "\n".join(document_list)
                response_text += "\n\nTo get a document, reply with the number (e.g., '2')"
                response_text += "\nTo delete a document, reply with 'delete <number>' (e.g., 'delete 2')"
                
                # Send the message with special handling - try up to 3 times
                print(f"[DEBUG] {command_hash} - Sending LIST response with {len(document_list)} documents")
                
                # Try sending the message up to 3 times
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    print(f"[DEBUG] {command_hash} - Send attempt {attempt}/{max_retries}")
                    success = await self.message_sender.send_message(
                        from_number, 
                        response_text,
                        message_type="list_command",
                        bypass_deduplication=True
                    )
                    
                    if success:
                        print(f"[DEBUG] {command_hash} - LIST response sent successfully on attempt {attempt}")
                        return True, "Document list sent"
                    else:
                        print(f"[DEBUG] {command_hash} - Failed to send LIST response on attempt {attempt}")
                        if attempt < max_retries:
                            # Wait a bit before retrying
                            await asyncio.sleep(1)
                
                # If we get here, all attempts failed
                print(f"[DEBUG] {command_hash} - All {max_retries} send attempts failed")
                return False, "Failed to send document list after multiple attempts"
            else:
                print(f"[DEBUG] {command_hash} - No documents found for {from_number}")
                # Add timestamp to make message unique
                timestamp = int(time.time())
                response_text = f"You don't have any stored documents. (Check: {timestamp})"
                
                # Try sending the message up to 3 times
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    print(f"[DEBUG] {command_hash} - Send attempt {attempt}/{max_retries}")
                    success = await self.message_sender.send_message(
                        from_number, 
                        response_text,
                        message_type="list_command",
                        bypass_deduplication=True
                    )
                    
                    if success:
                        print(f"[DEBUG] {command_hash} - Empty LIST response sent successfully on attempt {attempt}")
                        return True, "Empty document list sent"
                    else:
                        print(f"[DEBUG] {command_hash} - Failed to send empty LIST response on attempt {attempt}")
                        if attempt < max_retries:
                            # Wait a bit before retrying
                            await asyncio.sleep(1)
                
                # If we get here, all attempts failed
                print(f"[DEBUG] {command_hash} - All {max_retries} send attempts failed")
                return False, "Failed to send document list after multiple attempts"
                
        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            print(f"[ERROR] List command error {error_id}: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback {error_id}: {traceback.format_exc()}")
            return False, f"❌ An error occurred while listing your documents. (Error ID: {error_id})"
        
    async def _handle_find_command(self, from_number, query):
        """
        Handle the 'find' command.
        
        Args:
            from_number: The sender's phone number
            query: The search query
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing find command for {from_number} with query: '{query}'")
        # Use docs_app to retrieve document
        try:
            result = self.docs_app.retrieve_document(from_number, query)
            
            if result:
                logger.info(f"[DEBUG] Found matching document for query '{query}'")
                message = "Found matching documents!"
            else:
                logger.info(f"[DEBUG] No documents found for query '{query}'")
                message = "No documents found matching your query."
                
            logger.info(f"[DEBUG] Sending find command response to {from_number}")
            send_result = await self.message_sender.send_message(from_number, message)
            logger.info(f"[DEBUG] Find command response send result: {send_result}")
            
            return "Find command processed", 200
        except Exception as e:
            logger.error(f"[DEBUG] Error in _handle_find_command: {str(e)}", exc_info=True)
            error_msg = "❌ Error searching for documents. Please try again."
            await self.message_sender.send_message(from_number, error_msg)
            return "Find command error", 500
        
    async def _handle_ask_command(self, from_number, question):
        """
        Handle the '/ask' command.
        
        Args:
            from_number: The sender's phone number
            question: The question to ask
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing ask command for {from_number} with question: '{question}'")
        
        try:
            # Send processing message
            processing_msg = "🔄 Processing your question... This might take a moment."
            logger.info(f"[DEBUG] Sending processing message to {from_number}")
            await self.message_sender.send_message(from_number, processing_msg)
            
            # Use the docs_app to process the question
            logger.info(f"[DEBUG] Calling docs_app.ask_question with question: '{question}'")
            result = await self.docs_app.ask_question(from_number, question)
            logger.info(f"[DEBUG] ask_question result status: {result.get('status')}")
            
            if result["status"] == "success" and result.get("answers"):
                # Format answers from all relevant documents
                logger.info(f"[DEBUG] Found {len(result['answers'])} answers")
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
                logger.info(f"[DEBUG] Sending ask command response to {from_number} with {len(result['answers'])} answers")
            else:
                message = result.get("message", "No relevant information found in your documents.")
                logger.info(f"[DEBUG] Sending ask command error response to {from_number}: {message}")
            
            # Force this message to be sent by adding a timestamp
            import time
            timestamp = int(time.time())
            message = f"{message}\n\nTimestamp: {timestamp}"
            
            send_result = await self.message_sender.send_message(from_number, message)
            logger.info(f"[DEBUG] Ask command response send result: {send_result}")
            
            if result["status"] == "success":
                return "Question processed", 200
            else:
                return "Question processed", 500
        except Exception as e:
            logger.error(f"[DEBUG] Error in _handle_ask_command: {str(e)}", exc_info=True)
            error_msg = "❌ Error processing your question. Please try again."
            await self.message_sender.send_message(from_number, error_msg)
            return "Ask command error", 500

    def _detect_command_intent(self, text):
        """
        Detect command intent from natural language.
        
        Args:
            text: The user's message
            
        Returns:
            str: The detected command intent, or None if no intent was detected
        """
        logger.info(f"[DEBUG] Detecting intent for: '{text}'")
        
        # Exact matches
        if text == 'help':
            logger.info("[DEBUG] Detected exact match for 'help' command")
            return 'help'
        elif text == 'list' or text == 'show documents' or text == 'show my documents':
            logger.info("[DEBUG] Detected exact match for 'list' command")
            return 'list'
            
        # Prefix matches
        if text.startswith('find '):
            logger.info("[DEBUG] Detected 'find' command")
            return text  # Return the full command with the search query
        elif text.startswith('/ask '):
            logger.info("[DEBUG] Detected '/ask' command")
            return text  # Return the full command with the question
        elif text.startswith('delete '):
            logger.info("[DEBUG] Detected 'delete' command")
            return text  # Return the full command with the document ID
            
        # Natural language matches
        help_phrases = ['help me', 'what can you do', 'how does this work', 'commands', 'instructions']
        list_phrases = ['show me', 'list', 'documents', 'files', 'what do i have']
        find_phrases = ['find', 'search', 'look for', 'where is']
        ask_phrases = ['ask', 'question', 'tell me about', 'what is', 'how to']
        
        # Check for help intent
        if any(phrase in text for phrase in help_phrases):
            logger.info("[DEBUG] Detected natural language 'help' command")
            return 'help'
            
        # Check for list intent
        if any(phrase in text for phrase in list_phrases):
            logger.info("[DEBUG] Detected natural language 'list' command")
            return 'list'
            
        # Check for find intent with query
        for phrase in find_phrases:
            if phrase in text:
                # Extract the query after the phrase
                query_start = text.find(phrase) + len(phrase)
                query = text[query_start:].strip()
                if query:
                    logger.info(f"[DEBUG] Detected natural language 'find' command with query: '{query}'")
                    return f'find {query}'
                    
        # Check for ask intent with question
        for phrase in ask_phrases:
            if phrase in text:
                # Extract the question after the phrase
                question_start = text.find(phrase) + len(phrase)
                question = text[question_start:].strip()
                if question:
                    logger.info(f"[DEBUG] Detected natural language 'ask' command with question: '{question}'")
                    return f'/ask {question}'
                    
        logger.info("[DEBUG] No command intent detected")
        return None 