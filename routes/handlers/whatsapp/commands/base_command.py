"""
Base Command Handler
------------------
This module provides a base class for all command handlers.
"""

import logging
import hashlib
import time
import uuid
import traceback

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
        Send a response to the user using the same method as sign-in messages.
        
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
            print(f"\n==================================================")
            print(f"[DEBUG] SEND_RESPONSE START - {command_id}")
            print(f"[DEBUG] {command_id} - From: {from_number}")
            print(f"[DEBUG] {command_id} - Message Type: {message_type}")
            print(f"[DEBUG] {command_id} - Message Length: {len(message)} characters")
            print(f"[DEBUG] {command_id} - Message Preview: {message[:100]}...")
            print(f"[DEBUG] {command_id} - Message Sender: {self.message_sender}")
            print(f"==================================================")
            
            # Use the regular send_message method which is known to work for sign-in messages
            print(f"[DEBUG] {command_id} - Calling message_sender.send_message")
            
            # Try with direct access to message_sender attributes
            try:
                print(f"[DEBUG] {command_id} - Message sender API version: {self.message_sender.api_version}")
                print(f"[DEBUG] {command_id} - Message sender phone number ID: {self.message_sender.phone_number_id}")
                print(f"[DEBUG] {command_id} - Message sender access token: {self.message_sender.access_token[:5]}...{self.message_sender.access_token[-5:] if len(self.message_sender.access_token) > 10 else ''}")
            except Exception as attr_err:
                print(f"[DEBUG] {command_id} - Error accessing message_sender attributes: {str(attr_err)}")
            
            # Add a direct timestamp to the message for extra uniqueness
            direct_timestamp = int(time.time())
            if "Timestamp:" not in message:
                message += f"\n\nDirect Timestamp: {direct_timestamp}"
                print(f"[DEBUG] {command_id} - Added direct timestamp {direct_timestamp} to message")
            
            send_result = await self.message_sender.send_message(
                from_number,
                message,
                message_type=message_type,
                bypass_deduplication=True,  # Explicitly set to True
                max_retries=3
            )
            
            logger.info(f"[DEBUG] {message_type} response send result: {send_result}")
            print(f"[DEBUG] {command_id} - {message_type} response send result: {send_result}")
            
            # If send_message failed, try send_message_direct as a fallback
            if not send_result:
                print(f"[DEBUG] {command_id} - send_message failed, trying send_message_direct as fallback")
                
                # Add another timestamp for the fallback attempt
                fallback_timestamp = int(time.time())
                message += f"\n\nFallback Timestamp: {fallback_timestamp}"
                
                try:
                    fallback_result = await self.message_sender.send_message_direct(
                        from_number,
                        message,
                        message_type=message_type
                    )
                    print(f"[DEBUG] {command_id} - Fallback send_message_direct result: {fallback_result}")
                    return fallback_result
                except Exception as fallback_err:
                    print(f"[DEBUG] {command_id} - Fallback send_message_direct failed: {str(fallback_err)}")
                    print(f"[DEBUG] {command_id} - Fallback traceback: {traceback.format_exc()}")
                    return False
            
            return send_result
        except Exception as e:
            logger.error(f"[DEBUG] Error sending {message_type} response: {str(e)}", exc_info=True)
            print(f"[DEBUG] {command_id} - Error sending {message_type} response: {str(e)}")
            print(f"[DEBUG] {command_id} - Error traceback: {traceback.format_exc()}")
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
            print(f"[DEBUG] {command_id} - Sending error message: {error_message}")
            
            # Add a direct timestamp to the error message
            direct_timestamp = int(time.time())
            if "Timestamp:" not in error_message:
                error_message += f"\n\nError Timestamp: {direct_timestamp}"
            
            # Use the regular send_message method which is known to work for sign-in messages
            return await self.message_sender.send_message(
                from_number,
                error_message,
                message_type="error_message",
                bypass_deduplication=True,
                max_retries=3
            )
        except Exception as e:
            print(f"[DEBUG] {command_id} - Error sending error message: {str(e)}")
            print(f"[DEBUG] {command_id} - Error traceback: {traceback.format_exc()}")
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
        print(f"[ERROR] Traceback {error_id}: {traceback.format_exc()}")
        return f"❌ Sorry, an error occurred. Please try again. (Error ID: {error_id})" 