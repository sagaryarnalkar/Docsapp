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
import inspect
import sys
import random
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
        print(f"[DEBUG-INIT] CommandProcessor initialization STARTING")
        print(f"[DEBUG-INIT] docs_app type: {type(docs_app)}")
        print(f"[DEBUG-INIT] message_sender type: {type(message_sender)}")
        
        # Extra safety checks for docs_app
        if docs_app is None:
            print(f"[DEBUG-INIT] WARNING: docs_app is None!")
        
        # Try to print some information about the docs_app object
        try:
            print(f"[DEBUG-INIT] docs_app methods: {dir(docs_app)}")
            print(f"[DEBUG-INIT] docs_app has list_documents: {'list_documents' in dir(docs_app)}")
        except Exception as init_err:
            print(f"[DEBUG-INIT] Error inspecting docs_app: {str(init_err)}")
        
        self.docs_app = docs_app
        self.message_sender = message_sender
        
        # Initialize the intent detector
        self.intent_detector = IntentDetector()
        
        # Initialize command handlers with more debugging
        print(f"[DEBUG-INIT] Creating command handlers...")
        try:
            self.help_handler = HelpCommandHandler(docs_app, message_sender)
            print(f"[DEBUG-INIT] HelpCommandHandler created")
        except Exception as help_err:
            print(f"[DEBUG-INIT] Error creating HelpCommandHandler: {str(help_err)}")
            print(f"[DEBUG-INIT] Traceback: {traceback.format_exc()}")
            self.help_handler = None
            
        try:
            print(f"[DEBUG-INIT] Creating ListCommandHandler with docs_app: {docs_app}")
            self.list_handler = ListCommandHandler(docs_app, message_sender)
            print(f"[DEBUG-INIT] ListCommandHandler created: {self.list_handler}")
            print(f"[DEBUG-INIT] ListCommandHandler type: {type(self.list_handler)}")
            print(f"[DEBUG-INIT] ListCommandHandler docs_app: {self.list_handler.docs_app}")
        except Exception as list_err:
            print(f"[DEBUG-INIT] Error creating ListCommandHandler: {str(list_err)}")
            print(f"[DEBUG-INIT] Traceback: {traceback.format_exc()}")
            self.list_handler = None
            
        try:
            self.find_handler = FindCommandHandler(docs_app, message_sender)
            print(f"[DEBUG-INIT] FindCommandHandler created")
        except Exception as find_err:
            print(f"[DEBUG-INIT] Error creating FindCommandHandler: {str(find_err)}")
            self.find_handler = None
            
        try:
            self.ask_handler = AskCommandHandler(docs_app, message_sender)
            print(f"[DEBUG-INIT] AskCommandHandler created")
        except Exception as ask_err:
            print(f"[DEBUG-INIT] Error creating AskCommandHandler: {str(ask_err)}")
            self.ask_handler = None

        self.logger = logging.getLogger(__name__)
        print(f"[DEBUG-INIT] CommandProcessor initialization COMPLETED")
        
    async def handle_command(self, from_number, command_text):
        """
        Process a command from a WhatsApp user.
        
        Args:
            from_number: The sender's phone number
            command_text: The command text
            
        Returns:
            tuple: (response_message, status_code)
        """
        cmd_trace_id = f"CMD-{time.time()}-{random.randint(1000, 9999)}"
        print(f"\n==================================================")
        print(f"[DEBUG-CMD] {cmd_trace_id} COMMAND PROCESSING START")
        print(f"[DEBUG-CMD] {cmd_trace_id} From: {from_number}")
        print(f"[DEBUG-CMD] {cmd_trace_id} Text: '{command_text}'")
        print(f"[DEBUG-CMD] {cmd_trace_id} Command processor object: {self}")
        print(f"[DEBUG-CMD] {cmd_trace_id} docs_app: {self.docs_app}")
        print(f"[DEBUG-CMD] {cmd_trace_id} message_sender: {self.message_sender}")
        print(f"==================================================")
        
        try:
            print(f"[DEBUG-CMD] {cmd_trace_id} Normalizing command text")
            # Normalize command text
            normalized_text = command_text.strip().lower()
            print(f"[DEBUG-CMD] {cmd_trace_id} Normalized text: '{normalized_text}'")
            
            print(f"[DEBUG-CMD] {cmd_trace_id} Detecting intent via intent_detector: {self.intent_detector}")
            # Detect command intent
            command_intent = self.intent_detector.detect_intent(normalized_text)
            print(f"[DEBUG-CMD] {cmd_trace_id} Detected intent: {command_intent}")
            
            # Process the command based on the detected intent
            if command_intent == "help":
                print(f"[DEBUG-CMD] {cmd_trace_id} Processing help command")
                if self.help_handler is None:
                    print(f"[DEBUG-CMD] {cmd_trace_id} ERROR: help_handler is None!")
                    return "Help handler unavailable", 500
                print(f"[DEBUG-CMD] {cmd_trace_id} Calling help_handler.handle")
                return await self.help_handler.handle(from_number)
                
            elif command_intent == "list":
                print(f"[DEBUG-CMD] {cmd_trace_id} Processing list command")
                if self.list_handler is None:
                    print(f"[DEBUG-CMD] {cmd_trace_id} ERROR: list_handler is None!")
                    return "List handler unavailable", 500
                    
                # Extra debugging on list_handler
                print(f"[DEBUG-CMD] {cmd_trace_id} list_handler: {self.list_handler}")
                print(f"[DEBUG-CMD] {cmd_trace_id} list_handler.docs_app: {self.list_handler.docs_app}")
                print(f"[DEBUG-CMD] {cmd_trace_id} list_handler methods: {dir(self.list_handler)}")
                
                try:
                    # Even more debugging
                    print(f"[DEBUG-CMD] {cmd_trace_id} Calling handle method on list_handler")
                    handle_method = getattr(self.list_handler, 'handle')
                    print(f"[DEBUG-CMD] {cmd_trace_id} Handle method exists: {handle_method}")
                    print(f"[DEBUG-CMD] {cmd_trace_id} Handle method signature: {inspect.signature(handle_method)}")
                    
                    # Call the handle method
                    print(f"[DEBUG-CMD] {cmd_trace_id} Calling list_handler.handle({from_number})")
                    result = await self.list_handler.handle(from_number)
                    print(f"[DEBUG-CMD] {cmd_trace_id} List command result: {result}")
                    return result
                except Exception as list_err:
                    print(f"[DEBUG-CMD] {cmd_trace_id} List command execution error: {str(list_err)}")
                    print(f"[DEBUG-CMD] {cmd_trace_id} List error traceback: {traceback.format_exc()}")
                    
                    # Last resort - try to send a simple error message directly
                    try:
                        print(f"[DEBUG-CMD] {cmd_trace_id} Sending fallback error message")
                        await self.message_sender.send_message(
                            from_number,
                            f"❌ Error executing list command: {str(list_err)}",
                            message_type="error",
                            bypass_deduplication=True
                        )
                    except Exception as msg_err:
                        print(f"[DEBUG-CMD] {cmd_trace_id} Failed to send error message: {str(msg_err)}")
                        
                    return f"Error processing list command: {str(list_err)}", 500
                
            elif command_intent == "find":
                print(f"[DEBUG-CMD] {cmd_trace_id} Processing find command")
                if self.find_handler is None:
                    print(f"[DEBUG-CMD] {cmd_trace_id} ERROR: find_handler is None!")
                    return "Find handler unavailable", 500
                print(f"[DEBUG-CMD] {cmd_trace_id} Calling find_handler.handle")
                return await self.find_handler.handle(from_number, normalized_text)
                
            elif command_intent == "ask":
                print(f"[DEBUG-CMD] {cmd_trace_id} Processing ask command")
                if self.ask_handler is None:
                    print(f"[DEBUG-CMD] {cmd_trace_id} ERROR: ask_handler is None!")
                    return "Ask handler unavailable", 500
                
                print(f"[DEBUG-CMD] {cmd_trace_id} Extracting question from command text")
                # Extract question by removing the 'ask' keyword
                # e.g., "ask what is in document" -> "what is in document"
                question = command_text.strip()
                for ask_phrase in self.intent_detector.ASK_PHRASES:
                    if question.lower().startswith(ask_phrase):
                        question = question[len(ask_phrase):].strip()
                        break
                
                print(f"[DEBUG-CMD] {cmd_trace_id} Extracted question: '{question}'")
                print(f"[DEBUG-CMD] {cmd_trace_id} Calling ask_handler.handle")
                return await self.ask_handler.handle(from_number, question)
                
            elif command_intent == "new_document":
                print(f"[DEBUG-CMD] {cmd_trace_id} New document command detected but handler not implemented")
                await self.message_sender.send_message(
                    from_number,
                    "Creating new documents is not implemented yet. Please try using 'help' for available commands.",
                    message_type="info",
                    bypass_deduplication=True
                )
                return "New document command not implemented", 200
                
            else:
                # Unknown command intent, send welcome message
                print(f"[DEBUG-CMD] {cmd_trace_id} Unknown command intent: {command_intent}, sending welcome message")
                await self.message_sender.send_message(
                    from_number,
                    WHATSAPP_WELCOME_MESSAGE
                )
                return "Welcome message sent", 200
                
        except Exception as e:
            print(f"[DEBUG-CMD] {cmd_trace_id} Command processor error: {str(e)}")
            print(f"[DEBUG-CMD] {cmd_trace_id} Command processor traceback: {traceback.format_exc()}")
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
                print(f"[DEBUG-CMD] {cmd_trace_id} Error sending error message: {str(send_err)}")
            
            return "Command processing error", 500 