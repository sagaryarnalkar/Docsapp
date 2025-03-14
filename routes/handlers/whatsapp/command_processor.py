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
        Process a text command from a user.
        
        Args:
            from_number: The sender's phone number
            text: The command text
            
        Returns:
            tuple: (response_message, status_code)
        """
        try:
            # Log the command
            logger.info(f"[DEBUG] Processing command: '{text}' from {from_number}")

            # Normalize the command
            command = text.lower().strip()
            
            # Check for system messages like "Fetch update"
            system_messages = ["fetch update", "sync", "refresh", "update", "status"]
            if command in system_messages:
                logger.info(f"[DEBUG] Ignoring system message: '{command}'")
                return "System message ignored", 200
            
            # Initialize or update user context
            if from_number not in self.user_context:
                self.user_context[from_number] = {
                    'document_count': 0,
                    'last_command': None,
                    'command_understood': False
                }
                logger.info(f"[DEBUG] Initialized user context for {from_number}")
                
            # Try to get document count
            try:
                document_list, _ = self.docs_app.list_documents(from_number)
                doc_count = len(document_list) if document_list else 0
                self.user_context[from_number]['document_count'] = doc_count
                logger.info(f"[DEBUG] User {from_number} has {doc_count} documents")
            except Exception as e:
                logger.error(f"[DEBUG] Error getting document count: {str(e)}")
            
            # Detect command intent from natural language using rule-based approach
            command_intent = self._detect_command_intent(command)
            logger.info(f"[DEBUG] Rule-based intent detection result: {command_intent}")
            
            # If rule-based detection fails, try Gemini-based intent classification
            if not command_intent and self.intent_classifier.is_available:
                logger.info("[DEBUG] Rule-based intent detection failed, trying Gemini classification")
                intent_result = await self.intent_classifier.classify_intent(command)
                
                if intent_result["status"] == "success" and intent_result["confidence"] > 0.7:
                    classified_intent = intent_result["intent"]
                    parameters = intent_result.get("parameters", {})
                    
                    logger.info(f"[DEBUG] Gemini classified intent: {classified_intent} (confidence: {intent_result['confidence']})")
                    
                    # Map the classified intent to a command
                    if classified_intent == "list_documents":
                        command_intent = "list"
                    elif classified_intent == "help":
                        command_intent = "help"
                    elif classified_intent == "find_document" and "search_query" in parameters:
                        command_intent = f"find {parameters['search_query']}"
                    elif classified_intent == "ask_question" and "question" in parameters:
                        command_intent = f"/ask {parameters['question']}"
                    elif classified_intent == "delete_document" and "document_id" in parameters:
                        command_intent = f"delete {parameters['document_id']}"
            
            if command_intent:
                logger.info(f"[DEBUG] Final detected command intent: {command_intent}")
                command = command_intent
                
                # Update user context - command was understood
                self.user_context[from_number]['command_understood'] = True
                
                # Process different commands - DIRECTLY EXECUTE THE INTENT
                if command == 'help':
                    self.user_context[from_number]['last_command'] = 'help'
                    logger.info(f"[DEBUG] Executing HELP command for {from_number}")
                    return await self._handle_help_command(from_number)
                elif command == 'list':
                    self.user_context[from_number]['last_command'] = 'list'
                    logger.info(f"[DEBUG] Executing LIST command for {from_number}")
                    return await self._handle_list_command(from_number)
                elif command.startswith('find '):
                    self.user_context[from_number]['last_command'] = 'find'
                    logger.info(f"[DEBUG] Executing FIND command for {from_number} with query: {command[5:].strip()}")
                    return await self._handle_find_command(from_number, command[5:].strip())
                elif command.startswith('/ask '):
                    self.user_context[from_number]['last_command'] = 'ask'
                    logger.info(f"[DEBUG] Executing ASK command for {from_number} with question: {command[5:].strip()}")
                    return await self._handle_ask_command(from_number, command[5:].strip())
                elif command.startswith('delete '):
                    self.user_context[from_number]['last_command'] = 'delete'
                    logger.info(f"[DEBUG] Executing DELETE command for {from_number} with target: {command[7:].strip()}")
                    # Check if we have a delete_document handler, otherwise use the standard one
                    if hasattr(self, '_handle_delete_command'):
                        return await self._handle_delete_command(from_number, command[7:].strip())
                    else:
                        # Use the standard message format for delete
                        await self.message_sender.send_message(
                            from_number, 
                            f"Deleting document: {command[7:].strip()}"
                        )
                        return "Delete command processed", 200
            else:
                # Command was not understood
                logger.info(f"[DEBUG] Unknown command: {command}")
                self.user_context[from_number]['last_command'] = 'unknown'
                self.user_context[from_number]['command_understood'] = False
                
                # Use Gemini to generate a more helpful response
                if self.response_generator.is_available:
                    logger.info(f"[DEBUG] Generating AI response for unknown command: {command}")
                    response = await self.response_generator.generate_response(
                        text, 
                        self.user_context[from_number]
                    )
                    await self.message_sender.send_message(from_number, response)
                    return "Unknown command handled with AI response", 200
                else:
                    # Fall back to standard help message
                    logger.info(f"[DEBUG] Using fallback help message for unknown command: {command}")
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
            logger.error(f"[DEBUG] Error in handle_command: {str(e)}", exc_info=True)
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
        """
        Handle the 'list' command.
        
        Args:
            from_number: The sender's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing list command for {from_number}")
        # Use docs_app to list documents
        try:
            document_list, file_ids = self.docs_app.list_documents(from_number)
            logger.info(f"[DEBUG] Found {len(document_list) if document_list else 0} documents for {from_number}")
            
            if document_list:
                message = "Your documents:\n\n" + "\n".join(document_list)
                logger.info(f"[DEBUG] Sending document list to {from_number} with {len(document_list)} documents")
            else:
                message = "You don't have any stored documents. Send me any document to store it, and I'll keep it safe in your Google Drive!"
                logger.info(f"[DEBUG] Sending empty document list message to {from_number}")
            
            # Force this message to be sent by adding a timestamp
            import time
            timestamp = int(time.time())
            message = f"{message}\n\nTimestamp: {timestamp}"
            
            logger.info(f"[DEBUG] Sending list command response to {from_number}")
            send_result = await self.message_sender.send_message(from_number, message)
            logger.info(f"[DEBUG] List command response send result: {send_result}")
            
            return "List command processed", 200
        except Exception as e:
            logger.error(f"[DEBUG] Error in _handle_list_command: {str(e)}", exc_info=True)
            error_msg = "❌ Error retrieving your documents. Please try again."
            await self.message_sender.send_message(from_number, error_msg)
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