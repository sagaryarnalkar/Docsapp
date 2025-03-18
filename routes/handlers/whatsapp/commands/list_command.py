"""
List Command Handler for WhatsApp
------------------------------
This module handles the 'list' command to display the user's documents.
"""

import logging
import traceback
import time
import sys
from ..commands.base_command import BaseCommandHandler, extreme_debug

logger = logging.getLogger(__name__)

extreme_debug("LIST COMMAND MODULE LOADED")

class ListCommandHandler(BaseCommandHandler):
    """
    Handler for the 'list' command.
    
    This command lists all documents stored by the user.
    """
    
    def __init__(self, docs_app, message_sender):
        extreme_debug(f"ListCommandHandler.__init__ starting with docs_app={docs_app}, message_sender={message_sender}")
        super().__init__(docs_app, message_sender)
        extreme_debug("ListCommandHandler.__init__ completed successfully")
    
    async def handle(self, from_number):
        """
        Handle the 'list' command.
        
        Args:
            from_number: The user's phone number
            
        Returns:
            tuple: (message, status_code)
        """
        extreme_debug(f"LIST COMMAND HANDLE STARTED - from_number={from_number}")
        print(f"❗❗❗ ABSOLUTE BASIC LIST COMMAND START - {time.time()} ❗❗❗")
        
        # Step 1: Check if we can print at all
        extreme_debug("STEP 1: Basic print check")
        print(f"❗❗❗ STEP 1: Basic print check ❗❗❗")
        
        # Step 2: Check if message_sender exists
        extreme_debug("STEP 2: Checking message_sender")
        print(f"❗❗❗ STEP 2: Checking message_sender ❗❗❗")
        try:
            if self.message_sender:
                extreme_debug(f"message_sender exists: {type(self.message_sender)}")
                print(f"❗❗❗ message_sender exists: {type(self.message_sender)} ❗❗❗")
            else:
                extreme_debug("message_sender is None!")
                print(f"❗❗❗ message_sender is None! ❗❗❗")
                return "Message sender is None", 500
        except Exception as e:
            extreme_debug(f"Error accessing message_sender: {str(e)}")
            extreme_debug(f"Traceback: {traceback.format_exc()}")
            print(f"❗❗❗ Error accessing message_sender: {str(e)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            return f"Error accessing message_sender: {str(e)}", 500
        
        # Step 3: Create message
        try:
            extreme_debug("STEP 3: Creating message")
            print(f"❗❗❗ STEP 3: Creating message ❗❗❗")
            timestamp = int(time.time())
            message = f"ULTRA BASIC LIST COMMAND RESPONSE ({timestamp})"
            extreme_debug(f"Message created: {message}")
            print(f"❗❗❗ Message created: {message} ❗❗❗")
        except Exception as e:
            extreme_debug(f"Error creating message: {str(e)}")
            extreme_debug(f"Traceback: {traceback.format_exc()}")
            print(f"❗❗❗ Error creating message: {str(e)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            return f"Error creating message: {str(e)}", 500
        
        # Step 4: Try to send message
        extreme_debug("STEP 4: Attempting to send message")
        print(f"❗❗❗ STEP 4: Attempting to send message ❗❗❗")
        try:
            extreme_debug("About to call send_message")
            print(f"❗❗❗ About to call send_message ❗❗❗")
            success = await self.message_sender.send_message(
                from_number,
                message,
                message_type="ultra_basic_list",
                bypass_deduplication=True
            )
            extreme_debug(f"send_message called, result: {success}")
            print(f"❗❗❗ send_message called, result: {success} ❗❗❗")
            
            if success:
                extreme_debug("Message sent successfully")
                print(f"❗❗❗ Message sent successfully ❗❗❗")
                return "Basic list command processed", 200
            else:
                extreme_debug("Failed to send message")
                print(f"❗❗❗ Failed to send message ❗❗❗")
                return "Failed to send basic list response", 500
        except Exception as send_err:
            extreme_debug(f"Exception sending message: {str(send_err)}")
            extreme_debug(f"Traceback: {traceback.format_exc()}")
            print(f"❗❗❗ Exception sending message: {str(send_err)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            return f"Error sending basic list message: {str(send_err)}", 500 