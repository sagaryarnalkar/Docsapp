"""
Base Command Handler
------------------
This module provides a base class for all command handlers.
"""

import logging
import hashlib
import time
import uuid

logger = logging.getLogger(__name__)

class BaseCommandHandler:
    """
    Base class for all command handlers.
    
    This class provides common functionality for all command handlers:
    1. Generating command IDs
    2. Logging
    3. Error handling
    4. Message formatting
    """
    
    def __init__(self, docs_app, message_sender):
        """
        Initialize the base command handler.
        
        Args:
            docs_app: The DocsApp instance for document operations
            message_sender: The MessageSender instance for sending responses
        """
        self.docs_app = docs_app
        self.message_sender = message_sender
        
    def generate_command_id(self, command_type, from_number, additional_data=None):
        """
        Generate a unique command ID for tracking.
        
        Args:
            command_type: The type of command (e.g., 'help', 'list')
            from_number: The sender's phone number
            additional_data: Any additional data to include in the hash
            
        Returns:
            str: A unique command ID
        """
        timestamp = int(time.time())
        hash_data = f"{command_type}:{from_number}:{timestamp}"
        
        if additional_data:
            hash_data += f":{additional_data}"
            
        return hashlib.md5(hash_data.encode()).hexdigest()[:8]
        
    def add_unique_identifier(self, message, command_type, command_id):
        """
        Add a unique identifier to a message to prevent deduplication.
        
        Args:
            message: The message to add the identifier to
            command_type: The type of command (e.g., 'help', 'list')
            command_id: The command ID
            
        Returns:
            str: The message with the unique identifier
        """
        timestamp = int(time.time())
        unique_id = f"{command_type}-{command_id}-{timestamp}"
        return f"{message}\n\nCommand ID: {unique_id}"
        
    async def send_response(self, from_number, message, message_type, command_id):
        """
        Send a response to the user.
        
        Args:
            from_number: The recipient's phone number
            message: The message to send
            message_type: The type of message
            command_id: The command ID for logging
            
        Returns:
            bool: Whether the message was sent successfully
        """
        try:
            logger.info(f"[DEBUG] Sending {message_type} response to {from_number}")
            print(f"[DEBUG] {command_id} - Sending {message_type} response with length {len(message)}")
            
            send_result = await self.message_sender.send_message_direct(
                from_number,
                message,
                message_type=message_type
            )
            
            logger.info(f"[DEBUG] {message_type} response send result: {send_result}")
            print(f"[DEBUG] {command_id} - {message_type} response send result: {send_result}")
            
            return send_result
        except Exception as e:
            logger.error(f"[DEBUG] Error sending {message_type} response: {str(e)}", exc_info=True)
            print(f"[DEBUG] {command_id} - Error sending {message_type} response: {str(e)}")
            return False
            
    async def send_error_message(self, from_number, error_message, command_id):
        """
        Send an error message to the user.
        
        Args:
            from_number: The recipient's phone number
            error_message: The error message to send
            command_id: The command ID for logging
            
        Returns:
            bool: Whether the message was sent successfully
        """
        try:
            return await self.message_sender.send_message_direct(
                from_number,
                error_message,
                message_type="error_message"
            )
        except Exception as e:
            print(f"[DEBUG] {command_id} - Error sending error message: {str(e)}")
            return False
            
    def handle_exception(self, e, command_id=None):
        """
        Handle an exception and generate an error message.
        
        Args:
            e: The exception
            command_id: The command ID for logging
            
        Returns:
            str: An error message
        """
        error_id = command_id or str(uuid.uuid4())[:8]
        logger.error(f"[DEBUG] Error {error_id}: {str(e)}", exc_info=True)
        print(f"[ERROR] Error {error_id}: {str(e)}")
        import traceback
        print(f"[ERROR] Traceback {error_id}: {traceback.format_exc()}")
        return f"❌ Sorry, an error occurred. Please try again. (Error ID: {error_id})" 