"""
List Command Handler for WhatsApp
------------------------------
This module handles the 'list' command to display the user's documents.
"""

import logging
import traceback
import time
import hashlib
import uuid
import json
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
        # LINE-BY-LINE DEBUGGING WITH PRINT STATEMENTS FOR RENDER
        def log_step(step):
            """Print a step to stdout for Render logs"""
            print(f"🔍🔍🔍 [RENDER-DEBUG] STEP {step} 🔍🔍🔍")
        
        log_step("1 - Function entry")
        
        # Generate a unique ID for this command execution
        try:
            command_id = self.generate_command_id("list", from_number)
            log_step("2 - Generated command ID: " + command_id)
        except Exception as gen_err:
            print(f"❌❌❌ ERROR IN STEP 2: {str(gen_err)} ❌❌❌")
            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return "Error generating command ID", 500
        
        try:
            print(f"\n==================================================")
            print(f"[DEBUG] LIST COMMAND EXECUTION START - {command_id}")
            print(f"[DEBUG] From: {from_number}")
            print(f"[DEBUG] Time: {int(time.time())}")
            log_step("3 - Printed debug headers")
        except Exception as print_err:
            print(f"❌❌❌ ERROR IN STEP 3: {str(print_err)} ❌❌❌")
            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return "Error in debug logging", 500
        
        try:
            # ULTRA SIMPLIFIED: Create pre-defined response
            log_step("4 - Starting to build message")
            message = f"📄 *Your Documents (Render Debug Version)*\n\n"
            message += f"1. *Sample Document 1*\n"
            message += f"   Type: PDF\n"
            message += f"   ID: sample-doc-1\n\n"
            message += f"2. *Sample Document 2*\n"
            message += f"   Type: DOCX\n"
            message += f"   ID: sample-doc-2\n\n"
            
            # Add a unique timestamp to prevent duplicate message detection
            timestamp = int(time.time())
            message += f"\n\n_List generated at: {timestamp}_"
            log_step("5 - Message built successfully")
            
            print(f"[DEBUG] {command_id} - Sending direct fixed response")
            log_step("6 - About to try message sending")
        except Exception as msg_err:
            print(f"❌❌❌ ERROR IN STEPS 4-6: {str(msg_err)} ❌❌❌")
            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            return "Error building message", 500
            
        # ATTEMPT 1: Super simplified direct message
        try:
            log_step("7 - Attempting most basic message send")
            print(f"[DEBUG] Message sender type: {type(self.message_sender)}")
            print(f"[DEBUG] Message sender methods: {dir(self.message_sender)}")
            
            success = await self.message_sender.send_message(
                from_number,
                "This is a test message from List command",
                message_type="test",
                bypass_deduplication=True
            )
            log_step(f"8 - Basic message result: {success}")
            
            if success:
                log_step("9 - Basic message succeeded, returning early")
                return "Test message sent", 200
        except Exception as basic_err:
            print(f"❌❌❌ ERROR IN BASIC MESSAGE: {str(basic_err)} ❌❌❌")
            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            # Continue to next approach
        
        # ATTEMPT 2: Try direct API call
        try:
            log_step("10 - Starting direct API attempt")
            try:
                import aiohttp
                log_step("11 - Imported aiohttp")
                
                # Get API credentials
                try:
                    api_version = "v17.0"
                    log_step("12 - Set API version")
                    
                    phone_number_id = "571053722749385"
                    log_step("13 - Set phone number ID")
                    
                    try:
                        access_token = self.message_sender.access_token
                        token_length = len(access_token) if access_token else 0
                        log_step(f"14 - Got access token, length: {token_length}")
                        print(f"[DEBUG] Access token first 10 chars: {access_token[:10] if access_token else 'NONE'}")
                    except Exception as token_err:
                        print(f"❌❌❌ ERROR GETTING TOKEN: {str(token_err)} ❌❌❌")
                        print(f"❌ TRACEBACK: {traceback.format_exc()}")
                        # Try hardcoded token from environment
                        try:
                            import os
                            access_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "")
                            log_step(f"14.1 - Using token from environment, length: {len(access_token)}")
                        except Exception as env_err:
                            print(f"❌❌❌ ERROR GETTING ENV TOKEN: {str(env_err)} ❌❌❌")
                            print(f"❌ TRACEBACK: {traceback.format_exc()}")
                            log_step("14.2 - Failed to get token from environment")
                            raise Exception("Could not get access token")
                            
                    api_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
                    log_step(f"15 - Constructed API URL: {api_url}")
                    
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    }
                    log_step("16 - Created headers")
                    
                    simplified_message = f"List command test message - timestamp: {timestamp}"
                    payload = {
                        "messaging_product": "whatsapp",
                        "recipient_type": "individual",
                        "to": from_number,
                        "type": "text",
                        "text": {"body": simplified_message}
                    }
                    log_step("17 - Created payload")
                    
                    # Print payload for debugging
                    print(f"[DEBUG] API URL: {api_url}")
                    print(f"[DEBUG] To: {from_number}")
                    print(f"[DEBUG] Payload: {json.dumps(payload)}")
                    
                    log_step("18 - About to create aiohttp session")
                    async with aiohttp.ClientSession() as session:
                        log_step("19 - Created session")
                        print(f"[DEBUG] {command_id} - Sending direct API request")
                        
                        log_step("20 - About to send request")
                        async with session.post(api_url, json=payload, headers=headers) as response:
                            log_step("21 - Got response")
                            status_code = response.status
                            log_step(f"22 - Status code: {status_code}")
                            
                            resp_text = await response.text()
                            log_step(f"23 - Response text: {resp_text[:100]}")
                            
                            print(f"[DEBUG] RESPONSE: status={status_code}, text={resp_text}")
                            
                            print(f"[DEBUG] {command_id} - API response: {status_code} {resp_text}")
                            
                            if status_code in (200, 201):
                                log_step("24 - Request succeeded")
                                return "List command direct API message sent", 200
                            else:
                                log_step(f"24 - Request failed: {status_code}")
                                raise Exception(f"API error: {status_code} {resp_text}")
                except Exception as inner_err:
                    print(f"❌❌❌ INNER ERROR: {str(inner_err)} ❌❌❌")
                    print(f"❌ TRACEBACK: {traceback.format_exc()}")
                    log_step(f"Inner error: {str(inner_err)}")
                    raise inner_err
            except Exception as api_err:
                print(f"❌❌❌ API ERROR: {str(api_err)} ❌❌❌")
                print(f"❌ TRACEBACK: {traceback.format_exc()}")
                log_step(f"25 - API error: {str(api_err)}")
                print(f"[DEBUG] {command_id} - Direct API failed: {str(api_err)}")
                raise api_err
        except Exception as direct_err:
            print(f"❌❌❌ DIRECT API ERROR: {str(direct_err)} ❌❌❌")
            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            log_step(f"26 - Direct API attempt failed: {str(direct_err)}")
            # Continue to next approach
                
        # ATTEMPT 3: Fallback to standard method
        try:
            log_step("27 - Trying standard message_sender")
            try:
                # Create a simpler minimal message
                simple_msg = f"Fallback List command message ({timestamp})"
                log_step("28 - Created simple fallback message")
                
                success = await self.message_sender.send_message(
                    from_number,
                    simple_msg,
                    message_type="list_fallback",
                    bypass_deduplication=True
                )
                log_step(f"29 - Fallback result: {success}")
                
                if success:
                    log_step("30 - Fallback succeeded")
                    return "List command processed (fallback)", 200
                else:
                    log_step("30 - Fallback failed")
                    return "Failed to send fallback response", 500
            except Exception as fallback_err:
                print(f"❌❌❌ FALLBACK ERROR: {str(fallback_err)} ❌❌❌")
                print(f"❌ TRACEBACK: {traceback.format_exc()}")
                log_step(f"31 - Fallback error: {str(fallback_err)}")
                print(f"[DEBUG] {command_id} - Fallback failed: {str(fallback_err)}")
                raise fallback_err
        except Exception as last_err:
            print(f"❌❌❌ FINAL ERROR: {str(last_err)} ❌❌❌")
            print(f"❌ TRACEBACK: {traceback.format_exc()}")
            log_step(f"32 - All approaches failed")
            return "All message sending approaches failed", 500 