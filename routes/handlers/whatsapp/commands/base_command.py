"""
Base Command Handler
-----------------
This module provides a base command handler for WhatsApp commands.
"""

import logging
import traceback
import uuid
import time
import hashlib
import random

logger = logging.getLogger(__name__)

class BaseCommandHandler:
    """
    Base class for WhatsApp command handlers.
    
    This class provides common functionality for command handlers:
    1. Generating command IDs
    2. Handling exceptions
    3. Sending responses and error messages
    4. Formatting messages
    """
    
    def __init__(self, docs_app, message_sender):
        """
        Initialize the base command handler.
        
        Args:
            docs_app: The DocsApp instance for document operations
            message_sender: The MessageSender instance for sending responses
        """
        print(f"[DEBUG] BaseCommandHandler initializing with docs_app: {docs_app}")
        print(f"[DEBUG] BaseCommandHandler message_sender: {message_sender}")
        self.docs_app = docs_app
        self.message_sender = message_sender
        
    def generate_command_id(self, command_type, from_number):
        """
        Generate a unique ID for a command execution.
        
        Args:
            command_type: The type of command
            from_number: The sender's phone number
            
        Returns:
            str: A unique command ID
        """
        timestamp = int(time.time())
        random_suffix = random.randint(1000, 9999)
        command_id = f"{command_type[:4]}-{timestamp}-{random_suffix}"
        print(f"[DEBUG] Generated command ID: {command_id} for {command_type} command from {from_number}")
        return command_id
        
    def handle_exception(self, exception, command_id):
        """
        Handle an exception during command processing.
        
        Args:
            exception: The exception that occurred
            command_id: The command ID
            
        Returns:
            str: An error message
        """
        error_message = str(exception)
        print(f"[DEBUG] {command_id} - Exception in command handler: {error_message}")
        print(f"[DEBUG] {command_id} - Traceback: {traceback.format_exc()}")
        logger.error(f"[DEBUG] {command_id} - Command error: {error_message}", exc_info=True)
        return error_message
        
    async def send_response(self, to_number, message, message_type, command_id):
        """
        Send a response to the user.
        
        Args:
            to_number: The recipient's phone number
            message: The message to send
            message_type: The type of message
            command_id: The command ID
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        print(f"[DEBUG] {command_id} - Sending response to {to_number}")
        print(f"[DEBUG] {command_id} - Message type: {message_type}")
        print(f"[DEBUG] {command_id} - Message preview: {message[:100]}...")
        
        try:
            # Add a timestamp to the log for tracking
            log_timestamp = int(time.time())
            
            # Send the message
            success = await self.message_sender.send_message(
                to_number,
                message,
                message_type=message_type,
                bypass_deduplication=False
            )
            
            duration = int(time.time()) - log_timestamp
            print(f"[DEBUG] {command_id} - Response sent: {success} (took {duration}s)")
            return success
        except Exception as e:
            print(f"[DEBUG] {command_id} - Error sending response: {str(e)}")
            print(f"[DEBUG] {command_id} - Send error traceback: {traceback.format_exc()}")
            return False
            
    async def send_error_message(self, to_number, error_message, command_id):
        """
        Send an error message to the user.
        
        Args:
            to_number: The recipient's phone number
            error_message: The error message to send
            command_id: The command ID
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        print(f"[DEBUG] {command_id} - Sending error message to {to_number}")
        print(f"[DEBUG] {command_id} - Error message: {error_message}")
        
        try:
            # Make sure the error message is unique to avoid deduplication
            unique_error = self.add_unique_identifier(error_message, "error", command_id)
            
            # Send the error message directly, bypassing deduplication
            success = await self.message_sender.send_message(
                to_number,
                unique_error,
                message_type="error",
                bypass_deduplication=True
            )
            
            print(f"[DEBUG] {command_id} - Error message sent: {success}")
            return success
        except Exception as e:
            print(f"[DEBUG] {command_id} - Error sending error message: {str(e)}")
            print(f"[DEBUG] {command_id} - Error message send error traceback: {traceback.format_exc()}")
            return False
            
    def add_unique_identifier(self, message, command_type, command_id):
        """
        Add a unique identifier to a message to prevent deduplication.
        
        Args:
            message: The message to add an identifier to
            command_type: The type of command
            command_id: The command ID
            
        Returns:
            str: The message with a unique identifier
        """
        # Generate a unique hash based on the message content and time
        timestamp = int(time.time())
        unique_hash = hashlib.md5(f"{message}:{command_id}:{timestamp}".encode()).hexdigest()[:8]
        
        # Add the identifier as an invisible character at the end of the message
        identified_message = f"{message}\n\n<!-- {command_type}:{unique_hash} -->"
        print(f"[DEBUG] Added unique identifier to message: {unique_hash}")
        return identified_message 