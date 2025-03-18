"""
List Command Handler for WhatsApp
------------------------------
This module handles the 'list' command to display the user's documents.
"""

import logging
import traceback
import time
from ..commands.base_command import BaseCommandHandler

logger = logging.getLogger(__name__)

class ListCommandHandler(BaseCommandHandler):
    """
    Handler for the 'list' command.
    
    This command lists all documents stored by the user.
    """
    
    async def handle(self, from_number):
        """
        Handle the 'list' command.
        
        Args:
            from_number: The user's phone number
            
        Returns:
            tuple: (message, status_code)
        """
        print(f"❗❗❗ ABSOLUTE BASIC LIST COMMAND START - {time.time()} ❗❗❗")
        
        # Step 1: Check if we can print at all
        print(f"❗❗❗ STEP 1: Basic print check ❗❗❗")
        
        # Step 2: Check if message_sender exists
        print(f"❗❗❗ STEP 2: Checking message_sender ❗❗❗")
        try:
            if self.message_sender:
                print(f"❗❗❗ message_sender exists: {type(self.message_sender)} ❗❗❗")
            else:
                print(f"❗❗❗ message_sender is None! ❗❗❗")
                return "Message sender is None", 500
        except Exception as e:
            print(f"❗❗❗ Error accessing message_sender: {str(e)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            return f"Error accessing message_sender: {str(e)}", 500
        
        # Step 3: Create message
        try:
            print(f"❗❗❗ STEP 3: Creating message ❗❗❗")
            timestamp = int(time.time())
            message = f"ULTRA BASIC LIST COMMAND RESPONSE ({timestamp})"
            print(f"❗❗❗ Message created: {message} ❗❗❗")
        except Exception as e:
            print(f"❗❗❗ Error creating message: {str(e)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            return f"Error creating message: {str(e)}", 500
        
        # Step 4: Try to send message
        print(f"❗❗❗ STEP 4: Attempting to send message ❗❗❗")
        try:
            print(f"❗❗❗ About to call send_message ❗❗❗")
            success = await self.message_sender.send_message(
                from_number,
                message,
                message_type="ultra_basic_list",
                bypass_deduplication=True
            )
            print(f"❗❗❗ send_message called, result: {success} ❗❗❗")
            
            if success:
                print(f"❗❗❗ Message sent successfully ❗❗❗")
                return "Basic list command processed", 200
            else:
                print(f"❗❗❗ Failed to send message ❗❗❗")
                return "Failed to send basic list response", 500
        except Exception as send_err:
            print(f"❗❗❗ Exception sending message: {str(send_err)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            return f"Error sending basic list message: {str(send_err)}", 500 