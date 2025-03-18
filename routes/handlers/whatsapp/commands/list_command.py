"""
List Command Handler for WhatsApp
------------------------------
This module handles the 'list' command to display the user's documents.
"""

import logging
import traceback
import time
import sys
import os
from ..commands.base_command import BaseCommandHandler, extreme_debug

logger = logging.getLogger(__name__)

extreme_debug("LIST COMMAND MODULE LOADED")

# Create a direct file-based logger that doesn't rely on any other mechanism
LOG_FILE = "list_command_debug.log"

def file_log(message):
    """Write directly to a log file with timestamp"""
    try:
        with open(LOG_FILE, "a") as f:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
            f.flush()
    except Exception as e:
        # If we can't even log to a file, try stderr as last resort
        sys.stderr.write(f"CRITICAL ERROR LOGGING: {str(e)}\n")
        sys.stderr.write(f"Original message: {message}\n")
        sys.stderr.flush()

file_log("=============================================")
file_log(f"LIST COMMAND MODULE LOADED AT {time.time()}")
file_log(f"CURRENT DIRECTORY: {os.getcwd()}")
file_log("=============================================")

class ListCommandHandler(BaseCommandHandler):
    """
    Handler for the 'list' command.
    
    This command lists all documents stored by the user.
    """
    
    def __init__(self, docs_app, message_sender):
        file_log(f"ListCommandHandler.__init__ starting with docs_app={docs_app}, message_sender={message_sender}")
        extreme_debug(f"ListCommandHandler.__init__ starting with docs_app={docs_app}, message_sender={message_sender}")
        super().__init__(docs_app, message_sender)
        extreme_debug("ListCommandHandler.__init__ completed successfully")
        file_log("ListCommandHandler.__init__ completed successfully")
    
    async def handle(self, from_number):
        """
        Handle the 'list' command.
        
        Args:
            from_number: The user's phone number
            
        Returns:
            tuple: (message, status_code)
        """
        file_log(f"================== LIST COMMAND EXECUTION START ==================")
        file_log(f"handle() called with from_number={from_number}")
        file_log(f"Time: {time.time()}")
        file_log(f"self.docs_app: {self.docs_app}")
        file_log(f"self.message_sender: {self.message_sender}")
        
        extreme_debug(f"LIST COMMAND HANDLE STARTED - from_number={from_number}")
        print(f"❗❗❗ ABSOLUTE BASIC LIST COMMAND START - {time.time()} ❗❗❗")
        
        # Step 1: Check if we can print at all
        extreme_debug("STEP 1: Basic print check")
        print(f"❗❗❗ STEP 1: Basic print check ❗❗❗")
        file_log("STEP 1: Basic print check - SUCCESS")
        
        # Step 2: Check if message_sender exists
        extreme_debug("STEP 2: Checking message_sender")
        print(f"❗❗❗ STEP 2: Checking message_sender ❗❗❗")
        file_log("STEP 2: Checking message_sender")
        try:
            if self.message_sender:
                extreme_debug(f"message_sender exists: {type(self.message_sender)}")
                print(f"❗❗❗ message_sender exists: {type(self.message_sender)} ❗❗❗")
                file_log(f"message_sender exists: {type(self.message_sender)}")
            else:
                extreme_debug("message_sender is None!")
                print(f"❗❗❗ message_sender is None! ❗❗❗")
                file_log("CRITICAL ERROR: message_sender is None!")
                return "Message sender is None", 500
        except Exception as e:
            extreme_debug(f"Error accessing message_sender: {str(e)}")
            extreme_debug(f"Traceback: {traceback.format_exc()}")
            print(f"❗❗❗ Error accessing message_sender: {str(e)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            file_log(f"Error accessing message_sender: {str(e)}")
            file_log(f"Traceback: {traceback.format_exc()}")
            return f"Error accessing message_sender: {str(e)}", 500
        
        # Step 3: Create message
        try:
            extreme_debug("STEP 3: Creating message")
            print(f"❗❗❗ STEP 3: Creating message ❗❗❗")
            file_log("STEP 3: Creating message")
            timestamp = int(time.time())
            message = f"📋 Your Documents (Fixed Response):\n\n1. Sample Document 1.pdf\n2. Sample Document 2.docx\n\n(This is a hardcoded test response at {timestamp})"
            extreme_debug(f"Message created: {message}")
            print(f"❗❗❗ Message created: {message} ❗❗❗")
            file_log(f"Message created: {message}")
        except Exception as e:
            extreme_debug(f"Error creating message: {str(e)}")
            extreme_debug(f"Traceback: {traceback.format_exc()}")
            print(f"❗❗❗ Error creating message: {str(e)} ❗❗❗")
            print(f"❗❗❗ Traceback: {traceback.format_exc()} ❗❗❗")
            file_log(f"Error creating message: {str(e)}")
            file_log(f"Traceback: {traceback.format_exc()}")
            return f"Error creating message: {str(e)}", 500
        
        # Step 4: Try to send message
        extreme_debug("STEP 4: Attempting to send message")
        print(f"❗❗❗ STEP 4: Attempting to send message ❗❗❗")
        file_log("STEP 4: Attempting to send message")
        try:
            extreme_debug("About to call send_message")
            print(f"❗❗❗ About to call send_message ❗❗❗")
            file_log(f"About to call message_sender.send_message with from_number={from_number}")
            file_log(f"message_sender: {self.message_sender}")
            file_log(f"message_sender methods: {dir(self.message_sender)}")
            
            try:
                success = await self.message_sender.send_message(
                    from_number,
                    message,
                    message_type="fixed_list_response",
                    bypass_deduplication=True
                )
                extreme_debug(f"send_message called, result: {success}")
                print(f"❗❗❗ send_message called, result: {success} ❗❗❗")
                file_log(f"send_message called, result: {success}")
            
                if success:
                    extreme_debug("Message sent successfully")
                    print(f"❗❗❗ Message sent successfully ❗❗❗")
                    file_log("Message sent successfully")
                    return "Fixed list response sent", 200
                else:
                    extreme_debug("Failed to send message")
                    print(f"❗❗❗ Failed to send message ❗❗❗")
                    file_log("Failed to send message - attempting direct message")
                    
                    # Try alternative direct sending method if available
                    if hasattr(self.message_sender, 'send_direct_message'):
                        file_log("Attempting send_direct_message method")
                        success = await self.message_sender.send_direct_message(
                            from_number,
                            f"FALLBACK: {message}\n\n(Using direct method at {time.time()})",
                            message_type="direct_list"
                        )
                        file_log(f"Direct message result: {success}")
                        if success:
                            return "Direct list response sent", 200
                    
                    return "Failed to send list response", 500
            except Exception as send_err:
                file_log(f"Error calling send_message: {str(send_err)}")
                file_log(f"Traceback: {traceback.format_exc()}")
                
                # Try to make direct WhatsApp API call as emergency fallback
                try:
                    file_log("Making raw WhatsApp API call as final fallback")
                    import requests
                    import os
                    import json
                    
                    api_version = os.getenv('WHATSAPP_API_VERSION', 'v17.0')
                    phone_id = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
                    token = os.getenv('WHATSAPP_ACCESS_TOKEN')
                    
                    file_log(f"API params: version={api_version}, phone_id={phone_id}, token_length={len(token) if token else 0}")
                    
                    url = f'https://graph.facebook.com/{api_version}/{phone_id}/messages'
                    headers = {
                        'Authorization': f'Bearer {token}',
                        'Content-Type': 'application/json'
                    }
                    data = {
                        'messaging_product': 'whatsapp',
                        'to': from_number,
                        'type': 'text',
                        'text': {'body': f"🆘 EMERGENCY FALLBACK: Your documents list (hardcoded test at {time.time()})"}
                    }
                    
                    file_log(f"Making API POST request to {url}")
                    response = requests.post(url, headers=headers, json=data)
                    file_log(f"API response: Status {response.status_code}")
                    file_log(f"API response: {response.text}")
                    
                    if response.status_code == 200:
                        return "Emergency fallback message sent", 200
                    else:
                        return f"All message sending methods failed", 500
                        
                except Exception as api_err:
                    file_log(f"API fallback error: {str(api_err)}")
                    file_log(f"API fallback traceback: {traceback.format_exc()}")
                    return f"All messaging methods failed", 500
        except Exception as e:
            extreme_debug(f"Global error sending message: {str(e)}")
            extreme_debug(f"Global traceback: {traceback.format_exc()}")
            print(f"❗❗❗ Global error sending message: {str(e)} ❗❗❗")
            print(f"❗❗❗ Global traceback: {traceback.format_exc()} ❗❗❗")
            file_log(f"Global error sending message: {str(e)}")
            file_log(f"Global traceback: {traceback.format_exc()}")
            return f"Error sending message: {str(e)}", 500 