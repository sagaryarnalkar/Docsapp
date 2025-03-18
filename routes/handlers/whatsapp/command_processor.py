"""
WhatsApp Command Processor
------------------------
This module handles processing text commands from WhatsApp users.
"""

import logging
import asyncio
import time
import hashlib
import uuid
import traceback
from .document_processor import WhatsAppHandlerError
from .commands.intent_detector import IntentDetector
from .commands.help_command import HelpCommandHandler
from .commands.list_command import ListCommandHandler
from .commands.find_command import FindCommandHandler
from .commands.ask_command import AskCommandHandler
# Define the welcome message directly here instead of importing
# from ...whatsapp_constants import WHATSAPP_WELCOME_MESSAGE

logger = logging.getLogger(__name__)

# Welcome message defined directly to avoid import issues
WHATSAPP_WELCOME_MESSAGE = (
    "🌟 *Welcome to Docverse!* 🌟\n\n"
    "Here's what you can do:\n\n"
    "📋 *Available Commands:*\n"
    "• Send any document to store it\n"
    "• *list* - View your stored documents\n"
    "• *find [text]* - Search for documents\n"
    "• *ask [question]* - Ask questions about your documents\n"
    "• *help* - Show all commands\n\n"
    "Need help? Just type 'help' anytime!"
)

class CommandProcessor:
    """
    Processes text commands from WhatsApp users.
    
    This class is responsible for:
    1. Parsing and routing text commands
    2. Delegating to the appropriate command handlers
    3. Handling errors and unknown commands
    """
    
    def __init__(self, docs_app, message_sender):
        """
        Initialize the command processor.
        
        Args:
            docs_app: The DocsApp instance for document operations
            message_sender: The MessageSender instance for sending responses
        """
        print(f"[DEBUG] Initializing CommandProcessor with docs_app: {docs_app}")
        print(f"[DEBUG] MessageSender: {message_sender}")
        
        self.docs_app = docs_app
        self.message_sender = message_sender
        
        # Initialize the intent detector
        self.intent_detector = IntentDetector()
        
        # Initialize command handlers
        self.help_handler = HelpCommandHandler(docs_app, message_sender)
        print(f"[DEBUG] Initialized HelpCommandHandler: {self.help_handler}")
        
        self.list_handler = ListCommandHandler(docs_app, message_sender)
        print(f"[DEBUG] Initialized ListCommandHandler: {self.list_handler}")
        print(f"[DEBUG] ListCommandHandler type: {type(self.list_handler)}")
        print(f"[DEBUG] ListCommandHandler docs_app: {self.list_handler.docs_app}")
        
        self.find_handler = FindCommandHandler(docs_app, message_sender)
        print(f"[DEBUG] Initialized FindCommandHandler: {self.find_handler}")
        
        self.ask_handler = AskCommandHandler(docs_app, message_sender)
        print(f"[DEBUG] Initialized AskCommandHandler: {self.ask_handler}")
        
        self.logger = logging.getLogger(__name__)
        
        logger.info("[DEBUG] CommandProcessor initialized")
        print("[DEBUG] CommandProcessor initialized with message_sender:", message_sender)
        
    async def handle_command(self, from_number, command_text):
        """
        Process a command from a WhatsApp user.
        
        Args:
            from_number: The sender's phone number
            command_text: The command text
            
        Returns:
            tuple: (response_message, status_code)
        """
        try:
            print(f"[DEBUG] CommandProcessor handling command: '{command_text}' from {from_number}")
            # Normalize command text
            normalized_text = command_text.strip().lower()
            print(f"[DEBUG] Normalized command text: '{normalized_text}'")
            
            # Detect command intent
            command_intent = self.intent_detector.detect_intent(normalized_text)
            print(f"[DEBUG] Detected intent: {command_intent}")
            
            # Process the command based on the detected intent
            if command_intent == "help":
                print(f"[DEBUG] Executing help command with {self.help_handler}")
                return await self.help_handler.handle(from_number)
                
            elif command_intent == "list":
                print(f"[DEBUG] Executing list command with handler: {self.list_handler}")
                print(f"[DEBUG] List handler docs_app: {self.list_handler.docs_app}")
                print(f"[DEBUG] List handler message_sender: {self.list_handler.message_sender}")
                try:
                    result = await self.list_handler.handle(from_number)
                    print(f"[DEBUG] List command result: {result}")
                    return result
                except Exception as list_err:
                    print(f"[DEBUG] List command execution error: {str(list_err)}")
                    print(f"[DEBUG] List error traceback: {traceback.format_exc()}")
                    return "Error processing list command", 500
                
            elif command_intent == "find":
                print(f"[DEBUG] Executing find command with {self.find_handler}")
                return await self.find_handler.handle(from_number, normalized_text)
                
            elif command_intent == "ask":
                print(f"[DEBUG] Executing ask command with {self.ask_handler}")
                # Extract question by removing the 'ask' keyword
                # e.g., "ask what is in document" -> "what is in document"
                question = command_text.strip()
                for ask_phrase in self.intent_detector.ASK_PHRASES:
                    if question.lower().startswith(ask_phrase):
                        question = question[len(ask_phrase):].strip()
                        break
                
                print(f"[DEBUG] Ask question: '{question}'")
                return await self.ask_handler.handle(from_number, question)
                
            elif command_intent == "new_document":
                print(f"[DEBUG] New document command detected but handler not implemented")
                await self.message_sender.send_message(
                    from_number,
                    "Creating new documents is not implemented yet. Please try using 'help' for available commands.",
                    message_type="info",
                    bypass_deduplication=True
                )
                return "New document command not implemented", 200
                
            else:
                # Unknown command intent, send welcome message
                print(f"[DEBUG] Unknown command intent: {command_intent}, sending welcome message")
                await self.message_sender.send_message(
                    from_number,
                    WHATSAPP_WELCOME_MESSAGE
                )
                return "Welcome message sent", 200
                
        except Exception as e:
            print(f"[DEBUG] Command processor error: {str(e)}")
            print(f"[DEBUG] Command processor traceback: {traceback.format_exc()}")
            # Send error message to user
            try:
                error_message = f"❌ Sorry, I couldn't process your command. Please try again or type 'help' for assistance."
                await self.message_sender.send_message(
                    from_number,
                    error_message,
                    message_type="error",
                    bypass_deduplication=True
                )
            except Exception as send_err:
                print(f"[DEBUG] Error sending error message: {str(send_err)}")
            
            return "Command processing error", 500 