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

# EXTREME EMERGENCY DEBUG - USE DIRECT PRINTS
# Create function to log to stderr (by default) instead of stdout
import sys
def extreme_debug(message):
    sys.stderr.write(f"🔴🔴🔴 {message}\n")
    sys.stderr.flush()
    # Also print to stdout
    print(f"🔴🔴🔴 {message}")

extreme_debug("COMMAND PROCESSOR LOADED - LATEST VERSION WITH EXTREME DEBUGGING")

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

extreme_debug("WELCOME MESSAGE DEFINED")

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
        extreme_debug("CommandProcessor.__init__ STARTED")
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
            print(f"[DEBUG-INIT] docs_app has get_user_documents: {'get_user_documents' in dir(docs_app)}")
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
            extreme_debug(f"Creating ListCommandHandler with docs_app: {docs_app} and message_sender: {message_sender}")
            self.list_handler = ListCommandHandler(docs_app, message_sender)
            extreme_debug(f"ListCommandHandler created successfully: {self.list_handler}")
            print(f"[DEBUG-INIT] ListCommandHandler created: {self.list_handler}")
            print(f"[DEBUG-INIT] ListCommandHandler type: {type(self.list_handler)}")
            print(f"[DEBUG-INIT] ListCommandHandler docs_app: {self.list_handler.docs_app}")
        except Exception as list_err:
            extreme_debug(f"ListCommandHandler creation FAILED with error: {str(list_err)}")
            extreme_debug(f"Traceback: {traceback.format_exc()}")
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
        extreme_debug("CommandProcessor.__init__ COMPLETED")
        
    async def handle_command(self, from_number, command_text):
        """
        Process a command and return a response.
        
        Args:
            from_number: The user's phone number
            command_text: The command text
            
        Returns:
            tuple: (response_message, status_code)
        """
        command_id = f"CMD-{time.time()}-{random.randint(1000, 9999)}"
        print(f"🔴🔴🔴 CommandProcessor.handle_command ENTERED with from_number={from_number}, command_text={command_text}")
        
        # Print extensive debug information
        print(f"==================================================")
        print(f"[DEBUG-CMD] {command_id} COMMAND PROCESSING START")
        print(f"[DEBUG-CMD] {command_id} From: {from_number}")
        print(f"🔴🔴🔴 CommandProcessor.handle_command ENTERED with from_number={from_number}, command_text={command_text}")
        print(f"[DEBUG-CMD] {command_id} Text: '{command_text}'")
        print(f"[DEBUG-CMD] {command_id} Command processor object: {self}")
        print(f"[DEBUG-CMD] {command_id} docs_app: {self.docs_app}")
        print(f"[DEBUG-CMD] {command_id} message_sender: {self.message_sender}")
        print(f"==================================================")
        
        try:
            # Log the entry into the try block to check for exceptions
            print(f"🔴🔴🔴 CommandProcessor.handle_command - try block entered")
            print(f"🔴🔴🔴 CommandProcessor.handle_command - try block entered")
            
            print(f"[DEBUG-CMD] {command_id} Normalizing command text")
            command_text = command_text.lower().strip()
            print(f"[DEBUG-CMD] {command_id} Normalized text: '{command_text}'")
            
            # Detect intent using the intent detector
            print(f"[DEBUG-CMD] {command_id} Detecting intent via intent_detector: {self.intent_detector}")
            intent = self.intent_detector.detect_intent(command_text)
            print(f"[DEBUG-CMD] {command_id} Detected intent: {intent}")
            print(f"🔴🔴🔴 Detected intent: {intent}")
            
            # ULTRA DIRECT LIST COMMAND HANDLING FOR DEBUGGING
            if intent == "list":
                print(f"🔴🔴🔴 ❗❗❗ LIST COMMAND BRANCH ENTERED ❗❗❗")
                print(f"[DEBUG-CMD] {command_id} Processing list command")
                
                # Write to a file for emergency debugging
                with open("critical_list_command.log", "a") as f:
                    f.write(f"[{time.time()}] LIST COMMAND RECEIVED from {from_number}\n")
                    f.write(f"[{time.time()}] Intent detection worked correctly: {intent}\n")
                
                # EXTREME EMERGENCY DIRECT RESPONSE
                print(f"🔴🔴🔴 ❗❗❗ EMERGENCY LIST RESPONSE - DIRECT EXECUTION ❗❗❗")
                print(f"🔴🔴🔴 ❗❗❗ Sending ultra simple message to {from_number} ❗❗❗")
                
                try:
                    # First try message sender
                    success = await self.message_sender.send_message(
                        from_number,
                        f"EMERGENCY Direct Response from CommandProcessor: This bypasses the list handler completely. Time: {int(time.time())}\n\nTimestamp: {int(time.time())} ({time.strftime('%H:%M:%S')})",
                        message_type="emergency_cmd_processor_direct",
                        bypass_deduplication=True
                    )
                    with open("critical_list_command.log", "a") as f:
                        f.write(f"[{time.time()}] DIRECT MESSAGE SENDER RESULT: {success}\n")
                    
                    # ATOMIC DIRECT API CALL AS FINAL RESORT
                    try:
                        with open("critical_list_command.log", "a") as f:
                            f.write(f"[{time.time()}] ATTEMPTING DIRECT API CALL\n")
                            
                        # Get API credentials directly from environment
                        import os
                        import requests
                        import json
                        
                        api_version = os.environ.get('WHATSAPP_API_VERSION', 'v17.0')
                        phone_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
                        token = os.environ.get('WHATSAPP_ACCESS_TOKEN')
                        timestamp = int(time.time())
                        
                        with open("critical_list_command.log", "a") as f:
                            f.write(f"[{time.time()}] API PARAMS: version={api_version}, phone_id={phone_id}, token_length={len(token) if token else 0}\n")
                        
                        # Create URL and headers for direct API call
                        url = f'https://graph.facebook.com/{api_version}/{phone_id}/messages'
                        headers = {
                            'Authorization': f'Bearer {token}',
                            'Content-Type': 'application/json'
                        }
                        
                        # Prepare message data
                        message_data = {
                            'messaging_product': 'whatsapp',
                            'to': from_number,
                            'type': 'text',
                            'text': {
                                'body': f"🆘 ATOMIC API CALL from CommandProcessor: This is the deepest level emergency response at {timestamp}.\n\n1. Sample Document 1.pdf\n2. Sample Document 2.docx"
                            }
                        }
                        
                        with open("critical_list_command.log", "a") as f:
                            f.write(f"[{time.time()}] SENDING API REQUEST to {url}\n")
                            f.write(f"[{time.time()}] HEADERS: {headers}\n")
                            f.write(f"[{time.time()}] DATA: {message_data}\n")
                        
                        # Make the API call
                        try:
                            print(f"MAKING DIRECT API CALL to {url}")
                            response = requests.post(url, headers=headers, json=message_data)
                            
                            print(f"DIRECT API RESPONSE: {response.status_code} - {response.text}")
                            with open("critical_list_command.log", "a") as f:
                                f.write(f"[{time.time()}] API RESPONSE: Status {response.status_code}\n")
                                f.write(f"[{time.time()}] API RESPONSE BODY: {response.text}\n")
                                
                            # Check if successful (status code 200)
                            if response.status_code == 200:
                                with open("critical_list_command.log", "a") as f:
                                    f.write(f"[{time.time()}] ATOMIC API CALL SUCCESSFUL!\n")
                                return "Emergency list response sent via direct API", 200
                            else:
                                with open("critical_list_command.log", "a") as f:
                                    f.write(f"[{time.time()}] API CALL FAILED WITH STATUS {response.status_code}\n")
                        except Exception as req_err:
                            print(f"ERROR MAKING DIRECT API CALL: {str(req_err)}")
                            with open("critical_list_command.log", "a") as f:
                                f.write(f"[{time.time()}] API REQUEST EXCEPTION: {str(req_err)}\n")
                                import traceback
                                f.write(f"[{time.time()}] TRACEBACK: {traceback.format_exc()}\n")
                    except Exception as api_err:
                        print(f"ERROR IN ATOMIC API BLOCK: {str(api_err)}")
                        with open("critical_list_command.log", "a") as f:
                            f.write(f"[{time.time()}] ATOMIC API BLOCK EXCEPTION: {str(api_err)}\n")
                            import traceback
                            f.write(f"[{time.time()}] TRACEBACK: {traceback.format_exc()}\n")
                    
                    # Return a response regardless of success or failure
                    # This ensures the handler completes properly
                    return "List command emergency handling completed", 200
                    
                except Exception as e:
                    print(f"🔴🔴🔴 ERROR SENDING EMERGENCY MESSAGE: {str(e)}")
                    with open("critical_list_command.log", "a") as f:
                        f.write(f"[{time.time()}] ERROR SENDING EMERGENCY MESSAGE: {str(e)}\n")
                        import traceback
                        f.write(f"[{time.time()}] TRACEBACK: {traceback.format_exc()}\n")
                    return f"Error processing list command: {str(e)}", 500
                
            elif intent == "help":
                extreme_debug(f"Help command branch entered")
                print(f"[DEBUG-CMD] {command_id} Processing help command")
                if self.help_handler is None:
                    print(f"[DEBUG-CMD] {command_id} ERROR: help_handler is None!")
                    return "Help handler unavailable", 500
                print(f"[DEBUG-CMD] {command_id} Calling help_handler.handle")
                return await self.help_handler.handle(from_number)
                
            elif intent == "find":
                extreme_debug(f"Find command branch entered")
                print(f"[DEBUG-CMD] {command_id} Processing find command")
                if self.find_handler is None:
                    print(f"[DEBUG-CMD] {command_id} ERROR: find_handler is None!")
                    return "Find handler unavailable", 500
                print(f"[DEBUG-CMD] {command_id} Calling find_handler.handle")
                return await self.find_handler.handle(from_number, command_text)
                
            elif intent == "ask":
                extreme_debug(f"Ask command branch entered")
                print(f"[DEBUG-CMD] {command_id} Processing ask command")
                if self.ask_handler is None:
                    print(f"[DEBUG-CMD] {command_id} ERROR: ask_handler is None!")
                    return "Ask handler unavailable", 500
                
                print(f"[DEBUG-CMD] {command_id} Extracting question from command text")
                # Extract question by removing the 'ask' keyword
                # e.g., "ask what is in document" -> "what is in document"
                question = command_text.strip()
                for ask_phrase in self.intent_detector.ASK_PHRASES:
                    if question.lower().startswith(ask_phrase):
                        question = question[len(ask_phrase):].strip()
                        break
                
                print(f"[DEBUG-CMD] {command_id} Extracted question: '{question}'")
                print(f"[DEBUG-CMD] {command_id} Calling ask_handler.handle")
                return await self.ask_handler.handle(from_number, question)
                
            elif intent == "new_document":
                extreme_debug(f"New document command branch entered")
                print(f"[DEBUG-CMD] {command_id} New document command detected but handler not implemented")
                await self.message_sender.send_message(
                    from_number,
                    "Creating new documents is not implemented yet. Please try using 'help' for available commands.",
                    message_type="info",
                    bypass_deduplication=True
                )
                return "New document command not implemented", 200
                
            else:
                # Unknown command intent, send welcome message
                extreme_debug(f"Unknown command branch entered")
                print(f"[DEBUG-CMD] {command_id} Unknown command intent: {intent}, sending welcome message")
                await self.message_sender.send_message(
                    from_number,
                    WHATSAPP_WELCOME_MESSAGE
                )
                return "Welcome message sent", 200
                
        except Exception as e:
            extreme_debug(f"❗❗❗ COMMAND PROCESSOR GLOBAL ERROR: {str(e)} ❗❗❗")
            extreme_debug(f"❗❗❗ GLOBAL TRACEBACK: {traceback.format_exc()} ❗❗❗")
            print(f"[DEBUG-CMD] {command_id} Command processor error: {str(e)}")
            print(f"[DEBUG-CMD] {command_id} Command processor traceback: {traceback.format_exc()}")
            # Send error message to user
            try:
                error_message = f"❌ Sorry, I couldn't process your command. Error: {str(e)[:100]}..."
                error_message += f"\n\nTimestamp: {int(time.time())}"
                await self.message_sender.send_message(
                    from_number, 
                    error_message,
                    message_type="error",
                    bypass_deduplication=True
                )
            except Exception as err_msg_err:
                extreme_debug(f"Failed to send error message: {str(err_msg_err)}")
                print(f"[DEBUG-CMD] {command_id} Failed to send error message: {str(err_msg_err)}")
            
            return "Error processing command", 500 