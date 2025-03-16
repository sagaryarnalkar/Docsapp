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
from .document_processor import WhatsAppHandlerError
from .commands.intent_detector import IntentDetector
from .commands.help_command import HelpCommandHandler
from .commands.list_command_debug import ListCommandHandler
from .commands.find_command import FindCommandHandler
from .commands.ask_command import AskCommandHandler

logger = logging.getLogger(__name__)

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
        self.docs_app = docs_app
        self.message_sender = message_sender
        
        # Initialize the intent detector
        self.intent_detector = IntentDetector()
        
        # Initialize command handlers
        self.help_handler = HelpCommandHandler(docs_app, message_sender)
        self.list_handler = ListCommandHandler(docs_app, message_sender)
        self.find_handler = FindCommandHandler(docs_app, message_sender)
        self.ask_handler = AskCommandHandler(docs_app, message_sender)
        
        logger.info("[DEBUG] CommandProcessor initialized")
        print("[DEBUG] CommandProcessor initialized with message_sender:", message_sender)
        
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
            
            # Detect command intent
            intent = self.intent_detector.detect_intent(text)
            print(f"[DEBUG] {command_hash} - Command intent detection result: {intent}")
            
            if intent:
                command_type = intent.get('type')
                
                if command_type == 'help':
                    print(f"[DEBUG] {command_hash} - Executing HELP command")
                    try:
                        result = await self.help_handler.handle(from_number)
                        print(f"[DEBUG] {command_hash} - HELP command completed with result: {result}")
                        return result
                    except Exception as e:
                        print(f"[DEBUG] {command_hash} - HELP command failed with error: {str(e)}")
                        import traceback
                        print(f"[DEBUG] {command_hash} - Traceback: {traceback.format_exc()}")
                        raise
                    
                elif command_type == 'list':
                    print(f"[DEBUG] {command_hash} - Executing LIST command")
                    try:
                        print(f"[DEBUG] {command_hash} - LIST handler type: {type(self.list_handler)}")
                        print(f"[DEBUG] {command_hash} - LIST handler docs_app: {self.list_handler.docs_app}")
                        print(f"[DEBUG] {command_hash} - LIST handler message_sender: {self.list_handler.message_sender}")
                        result = await self.list_handler.handle(from_number)
                        print(f"[DEBUG] {command_hash} - LIST command completed with result: {result}")
                        return result
                    except Exception as e:
                        print(f"[DEBUG] {command_hash} - LIST command failed with error: {str(e)}")
                        import traceback
                        print(f"[DEBUG] {command_hash} - Traceback: {traceback.format_exc()}")
                        raise
                    
                elif command_type == 'find':
                    query = intent.get('query', '')
                    print(f"[DEBUG] {command_hash} - Executing FIND command with query: '{query}'")
                    try:
                        result = await self.find_handler.handle(from_number, query)
                        print(f"[DEBUG] {command_hash} - FIND command completed with result: {result}")
                        return result
                    except Exception as e:
                        print(f"[DEBUG] {command_hash} - FIND command failed with error: {str(e)}")
                        import traceback
                        print(f"[DEBUG] {command_hash} - Traceback: {traceback.format_exc()}")
                        raise
                    
                elif command_type == 'ask':
                    question = intent.get('question', '')
                    print(f"[DEBUG] {command_hash} - Executing ASK command with question: '{question}'")
                    try:
                        result = await self.ask_handler.handle(from_number, question)
                        print(f"[DEBUG] {command_hash} - ASK command completed with result: {result}")
                        return result
                    except Exception as e:
                        print(f"[DEBUG] {command_hash} - ASK command failed with error: {str(e)}")
                        import traceback
                        print(f"[DEBUG] {command_hash} - Traceback: {traceback.format_exc()}")
                        raise
                    
                else:
                    print(f"[DEBUG] {command_hash} - Unsupported command type: {command_type}")
                    return False, f"Sorry, the '{command_type}' command is not supported yet."
            
            # No command detected
            print(f"[DEBUG] {command_hash} - No command detected in text: '{text}'")
            return False, "I'm not sure what you're asking. Try 'help' to see available commands."
            
        except Exception as e:
            error_id = str(uuid.uuid4())[:8]
            print(f"[ERROR] Command processing error {error_id}: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback {error_id}: {traceback.format_exc()}")
            return False, f"❌ Sorry, an error occurred while processing your command. (Error ID: {error_id})" 