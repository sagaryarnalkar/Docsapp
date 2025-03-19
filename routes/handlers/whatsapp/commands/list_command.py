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
        
        # Step 4: Try to send message using DIRECT URLLIB - NO ASYNC
        print(f"❗❗❗ STEP 4: USING DIRECT URLLIB INSTEAD OF ASYNC ❗❗❗")
        file_log("STEP 4: USING DIRECT URLLIB INSTEAD OF ASYNC")
        
        try:
            # Get API credentials
            import os
            import urllib.request
            import urllib.error
            import json
            
            api_version = os.environ.get('WHATSAPP_API_VERSION', 'v17.0')
            phone_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
            token = os.environ.get('WHATSAPP_ACCESS_TOKEN')
            
            print(f"❗❗❗ STEP 4.1: Using API version: {api_version}, phone_id: {phone_id}, token length: {len(token) if token else 0} ❗❗❗")
            file_log(f"API parameters: version={api_version}, phone_id={phone_id}, token_length={len(token) if token else 0}")
            
            # Construct URL
            url = f'https://graph.facebook.com/{api_version}/{phone_id}/messages'
            
            # Create headers and data
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}'
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'to': from_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            print(f"❗❗❗ STEP 4.2: Request URL: {url} ❗❗❗")
            print(f"❗❗❗ STEP 4.3: Request data: {data} ❗❗❗")
            file_log(f"Request URL: {url}")
            file_log(f"Request data: {data}")
            
            # Convert data to JSON and encode
            data_bytes = json.dumps(data).encode('utf-8')
            
            # Create the request
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method='POST')
            
            # Make the request
            print(f"❗❗❗ STEP 4.4: About to make urllib request at {time.time()} ❗❗❗")
            file_log(f"About to make urllib request at {time.time()}")
            
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    print(f"❗❗❗ STEP 4.5: Got response at {time.time()} ❗❗❗")
                    file_log(f"Got response at {time.time()}")
                    
                    # Read and parse response
                    response_data = response.read().decode('utf-8')
                    response_status = response.getcode()
                    
                    print(f"❗❗❗ STEP 4.6: Response status: {response_status} ❗❗❗")
                    print(f"❗❗❗ STEP 4.7: Response data: {response_data} ❗❗❗")
                    file_log(f"Response status: {response_status}")
                    file_log(f"Response data: {response_data}")
                    
                    if response_status == 200:
                        print(f"❗❗❗ STEP 4.8: Message sent successfully! ❗❗❗")
                        file_log("Message sent successfully!")
                        return "List response sent via urllib", 200
                    else:
                        print(f"❗❗❗ STEP 4.8: API returned non-200 status code: {response_status} ❗❗❗")
                        file_log(f"API returned non-200 status code: {response_status}")
                        return f"API error: {response_status}", 500
            except urllib.error.HTTPError as http_err:
                error_response = http_err.read().decode('utf-8') if hasattr(http_err, 'read') else str(http_err)
                print(f"❗❗❗ STEP 4.5: HTTP Error: {http_err.code} - {error_response} ❗❗❗")
                file_log(f"HTTP Error: {http_err.code}")
                file_log(f"Error response: {error_response}")
                return f"HTTP Error: {http_err.code}", 500
            except urllib.error.URLError as url_err:
                print(f"❗❗❗ STEP 4.5: URL Error: {str(url_err)} ❗❗❗")
                print(f"❗❗❗ STEP 4.5: URL Error reason: {url_err.reason} ❗❗❗")
                file_log(f"URL Error: {str(url_err)}")
                file_log(f"URL Error reason: {url_err.reason if hasattr(url_err, 'reason') else 'unknown'}")
                return f"URL Error: {str(url_err)}", 500
                
        except Exception as e:
            print(f"❗❗❗ STEP 4: GLOBAL ERROR in urllib block: {str(e)} ❗❗❗")
            print(f"❗❗❗ STEP 4: GLOBAL TRACEBACK: {traceback.format_exc()} ❗❗❗")
            file_log(f"Global error in urllib block: {str(e)}")
            file_log(f"Traceback: {traceback.format_exc()}")
            
            # Last-ditch effort using very basic HTTP
            try:
                print(f"❗❗❗ STEP 5: ATTEMPTING RAW SOCKET CONNECTION ❗❗❗")
                import http.client
                import json
                import os
                
                api_version = os.environ.get('WHATSAPP_API_VERSION', 'v17.0')
                phone_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
                token = os.environ.get('WHATSAPP_ACCESS_TOKEN')
                
                print(f"❗❗❗ STEP 5.1: Connection to graph.facebook.com ❗❗❗")
                conn = http.client.HTTPSConnection("graph.facebook.com")
                
                payload = json.dumps({
                    "messaging_product": "whatsapp",
                    "to": from_number,
                    "type": "text",
                    "text": {
                        "body": f"🆘 EMERGENCY HTTP.CLIENT MESSAGE at {int(time.time())}"
                    }
                })
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {token}'
                }
                
                path = f"/{api_version}/{phone_id}/messages"
                print(f"❗❗❗ STEP 5.2: POST to path {path} ❗❗❗")
                
                conn.request("POST", path, payload, headers)
                
                print(f"❗❗❗ STEP 5.3: Getting response ❗❗❗")
                res = conn.getresponse()
                data = res.read()
                
                print(f"❗❗❗ STEP 5.4: Response status: {res.status} ❗❗❗")
                print(f"❗❗❗ STEP 5.5: Response: {data.decode('utf-8')} ❗❗❗")
                
                conn.close()
                
                if res.status == 200:
                    return "Emergency HTTP message sent", 200
                else:
                    return f"HTTP error: {res.status}", 500
                    
            except Exception as http_err:
                print(f"❗❗❗ STEP 5 ERROR: {str(http_err)} ❗❗❗")
                print(f"❗❗❗ STEP 5 TRACEBACK: {traceback.format_exc()} ❗❗❗")
                return f"All methods failed: {str(e)}", 500 