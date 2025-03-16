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
        command_id = hashlib.md5(f"help:{from_number}:{int(time.time())}".encode()).hexdigest()[:8]
        print(f"[DEBUG] Help command ID: {command_id}")
        
        try:
            # Create help message
            help_message = (
                "📱 *DocsApp WhatsApp Bot Help*\n\n"
                "Available commands:\n"
                "• *help* - Show this help message\n"
                "• *list* - List all your documents\n"
                "• *find [query]* - Search for documents\n"
                "• */ask [question]* - Ask a question about your documents\n\n"
                "You can also upload documents directly to this chat."
            )
            
            # Add a unique identifier and timestamp to prevent deduplication
            timestamp = int(time.time())
            unique_id = f"help-{command_id}-{timestamp}"
            help_message = f"{help_message}\n\nCommand ID: {unique_id}"
            
            logger.info(f"[DEBUG] Sending help command response to {from_number}")
            print(f"[DEBUG] {command_id} - Sending help response with length {len(help_message)}")
            
            # Pass the message_type parameter to ensure it bypasses deduplication
            send_result = await self.message_sender.send_message(
                from_number, 
                help_message, 
                message_type="help_command",
                bypass_deduplication=True,
                max_retries=3
            )
            logger.info(f"[DEBUG] Help command response send result: {send_result}")
            print(f"[DEBUG] {command_id} - Help command response send result: {send_result}")
            
            return "Help command processed", 200
        except Exception as e:
            logger.error(f"[DEBUG] Error in _handle_help_command: {str(e)}", exc_info=True)
            error_msg = f"❌ Error processing help command. Please try again. (Error ID: {command_id})"
            await self.message_sender.send_message(
                from_number, 
                error_msg, 
                message_type="error_message",
                bypass_deduplication=True
            )
            return "Help command error", 500
        
    async def _handle_list_command(self, from_number):
        """
        Handle the 'list' command.
        
        Args:
            from_number: The sender's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing list command for {from_number}")
        command_id = hashlib.md5(f"list:{from_number}:{int(time.time())}".encode()).hexdigest()[:8]
        print(f"[DEBUG] List command ID: {command_id}")
        
        try:
            # Get documents from docs_app
            logger.info(f"[DEBUG] Calling docs_app.list_documents for {from_number}")
            doc_list, file_ids = self.docs_app.list_documents(from_number)
            logger.info(f"[DEBUG] docs_app.list_documents returned {len(doc_list)} documents and {len(file_ids)} file IDs")
            
            if doc_list:
                # Format document list
                message_parts = ["📚 Your Documents:\n"]
                
                # Add each document to the message
                message_parts.extend(doc_list)
                
                message = "\n".join(message_parts)
                logger.info(f"[DEBUG] Found {len(doc_list)} documents for {from_number}")
                logger.info(f"[DEBUG] Message preview: {message[:100]}...")
            else:
                message = "You don't have any documents yet. Send me a file to get started!"
                logger.info(f"[DEBUG] No documents found for {from_number}")
            
            # Add a unique identifier and timestamp to the message to prevent deduplication
            timestamp = int(time.time())
            unique_id = f"list-{command_id}-{timestamp}"
            message = f"{message}\n\nCommand ID: {unique_id}"
            
            logger.info(f"[DEBUG] Sending list command response to {from_number}")
            print(f"[DEBUG] {command_id} - Sending list response with length {len(message)}")
            
            # Send the message with explicit bypass_deduplication=True
            send_result = await self.message_sender.send_message(
                from_number, 
                message, 
                message_type="list_command",
                bypass_deduplication=True,
                max_retries=3
            )
            
            logger.info(f"[DEBUG] List command response send result: {send_result}")
            print(f"[DEBUG] {command_id} - List command response send result: {send_result}")
            
            # If sending failed, try an alternative approach
            if not send_result:
                print(f"[DEBUG] {command_id} - First attempt failed, trying alternative approach")
                # Try sending a simpler message with a different message type
                alt_message = f"List command processed. You have {len(doc_list) if doc_list else 0} documents."
                alt_message += f"\n\nRetry ID: {unique_id}-retry-{int(time.time())}"
                
                send_result = await self.message_sender.send_message(
                    from_number,
                    alt_message,
                    message_type="outgoing_message",  # Use a different message type
                    bypass_deduplication=True,
                    max_retries=3
                )
                print(f"[DEBUG] {command_id} - Alternative message send result: {send_result}")
            
            return "List command processed", 200
        except Exception as e:
            logger.error(f"[DEBUG] Error in _handle_list_command: {str(e)}", exc_info=True)
            error_msg = f"❌ Error retrieving your documents. Please try again. (Error ID: {command_id})"
            
            try:
                await self.message_sender.send_message(
                    from_number, 
                    error_msg, 
                    message_type="error_message",
                    bypass_deduplication=True
                )
            except Exception as send_err:
                print(f"[DEBUG] {command_id} - Error sending error message: {str(send_err)}")
            
            return "List command error", 500
        
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
        command_id = hashlib.md5(f"find:{from_number}:{query}:{int(time.time())}".encode()).hexdigest()[:8]
        print(f"[DEBUG] Find command ID: {command_id}")
        
        # Use docs_app to retrieve document
        try:
            result = self.docs_app.retrieve_document(from_number, query)
            
            if result:
                logger.info(f"[DEBUG] Found matching document for query '{query}'")
                message = "Found matching documents!"
            else:
                logger.info(f"[DEBUG] No documents found for query '{query}'")
                message = "No documents found matching your query."
            
            # Add a unique identifier and timestamp to prevent deduplication
            timestamp = int(time.time())
            unique_id = f"find-{command_id}-{timestamp}"
            message = f"{message}\n\nCommand ID: {unique_id}"
                
            logger.info(f"[DEBUG] Sending find command response to {from_number}")
            print(f"[DEBUG] {command_id} - Sending find response with length {len(message)}")
            
            # Pass the message_type parameter to ensure it bypasses deduplication
            send_result = await self.message_sender.send_message(
                from_number, 
                message, 
                message_type="find_command",
                bypass_deduplication=True,
                max_retries=3
            )
            logger.info(f"[DEBUG] Find command response send result: {send_result}")
            print(f"[DEBUG] {command_id} - Find command response send result: {send_result}")
            
            return "Find command processed", 200
        except Exception as e:
            logger.error(f"[DEBUG] Error in _handle_find_command: {str(e)}", exc_info=True)
            error_msg = f"❌ Error searching for documents. Please try again. (Error ID: {command_id})"
            await self.message_sender.send_message(
                from_number, 
                error_msg, 
                message_type="error_message",
                bypass_deduplication=True
            )
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
        command_id = hashlib.md5(f"ask:{from_number}:{question}:{int(time.time())}".encode()).hexdigest()[:8]
        print(f"[DEBUG] Ask command ID: {command_id}")
        
        try:
            # Send an acknowledgment message first
            ack_message = f"🔍 Processing your question: '{question}'\n\nThis may take a moment..."
            await self.message_sender.send_message(
                from_number, 
                ack_message, 
                message_type="ask_command_ack",
                bypass_deduplication=True
            )
            
            # Process the question
            logger.info(f"[DEBUG] Calling docs_app.ask_question for {from_number}")
            result = await self.docs_app.ask_question(from_number, question)
            logger.info(f"[DEBUG] docs_app.ask_question returned: {result}")
            
            if result and result.get('status') == 'success':
                message = result.get('message', 'Here is your answer:')
                
                # Format answers if available
                if 'answers' in result and result['answers']:
                    answers = result['answers']
                    message_parts = [message, ""]
                    
                    for i, answer in enumerate(answers, 1):
                        doc_name = answer.get('document', 'Unknown document')
                        answer_text = answer.get('answer', 'No answer found')
                        message_parts.append(f"📄 *Document {i}: {doc_name}*")
                        message_parts.append(answer_text)
                        message_parts.append("")
                    
                    message = "\n".join(message_parts)
                
                logger.info(f"[DEBUG] Generated answer for question '{question}'")
                logger.info(f"[DEBUG] Answer preview: {message[:100]}...")
            else:
                error = result.get('error', 'Unknown error') if result else 'Failed to process question'
                message = f"❌ Sorry, I couldn't answer your question: {error}"
                logger.info(f"[DEBUG] Failed to answer question '{question}': {error}")
            
            # Add a unique identifier and timestamp to prevent deduplication
            timestamp = int(time.time())
            unique_id = f"ask-{command_id}-{timestamp}"
            message = f"{message}\n\nCommand ID: {unique_id}"
            
            logger.info(f"[DEBUG] Sending ask command response to {from_number}")
            print(f"[DEBUG] {command_id} - Sending ask response with length {len(message)}")
            
            # Send the answer
            send_result = await self.message_sender.send_message(
                from_number, 
                message, 
                message_type="ask_command",
                bypass_deduplication=True,
                max_retries=3
            )
            logger.info(f"[DEBUG] Ask command response send result: {send_result}")
            print(f"[DEBUG] {command_id} - Ask command response send result: {send_result}")
            
            return "Ask command processed", 200
        except Exception as e:
            logger.error(f"[DEBUG] Error in _handle_ask_command: {str(e)}", exc_info=True)
            error_msg = f"❌ Error processing your question. Please try again. (Error ID: {command_id})"
            await self.message_sender.send_message(
                from_number, 
                error_msg, 
                message_type="error_message",
                bypass_deduplication=True
            )
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