"""
WhatsApp Message Sender
----------------------
This module handles sending messages to WhatsApp users without deduplication
to ensure all messages are delivered.
"""

import json
import time
import logging
import aiohttp
import hashlib
import os
import asyncio
from datetime import datetime
from http import HTTPStatus
from config import WHATSAPP_API_URL, WHATSAPP_PHONE_NUMBER_ID
import traceback
import random

logger = logging.getLogger(__name__)

class MessageSender:
    """
    Handles sending messages to WhatsApp users.
    
    This class is responsible for:
    1. Sending text messages to WhatsApp users
    2. Handling API errors and token expiration
    3. Implementing retry logic for failed messages
    """
    
    def __init__(self, access_token=None, phone_number_id=None, api_version="v22.0"):
        """
        Initialize the message sender.
        
        Args:
            access_token: WhatsApp API access token
            phone_number_id: WhatsApp phone number ID
            api_version: WhatsApp API version
        """
        # Get credentials from environment if not provided
        self.access_token = access_token or os.environ.get('WHATSAPP_ACCESS_TOKEN')
        self.phone_number_id = phone_number_id or os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
        self.api_version = api_version or os.environ.get('WHATSAPP_API_VERSION', 'v22.0')
        
        # Fix for swapped environment variables
        # If access_token starts with 'v' and api_version starts with 'EAA', they're swapped
        if self.access_token and self.api_version:
            if self.access_token.startswith('v') and len(self.access_token) < 10 and self.api_version.startswith('EAA') and len(self.api_version) > 20:
                print("DETECTED SWAPPED ENVIRONMENT VARIABLES - FIXING AUTOMATICALLY")
                self.access_token, self.api_version = self.api_version, self.access_token
        
        # Ensure we're using the correct URL structure with API version
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        self.token_valid = bool(self.access_token and not self.access_token.startswith('YOUR_') and len(self.access_token) > 20)
        self.debug_mode = True   # Enable debug mode for detailed logging
        
        # Check if the token is obviously invalid
        if not self.token_valid:
            logger.error("⚠️ WhatsApp access token appears to be a placeholder or expired!")
            print("⚠️ WhatsApp access token appears to be a placeholder or expired!")
            print("Please update the WHATSAPP_ACCESS_TOKEN in your .env file")
        
        logger.info(f"[DEBUG] MessageSender initialized with API version {api_version}")
        logger.info(f"[DEBUG] Phone Number ID: {phone_number_id}")
        logger.info(f"[DEBUG] Token valid: {self.token_valid}")
        
        # Track recently sent messages to prevent duplicates
        self._recent_messages = {}
        self._deduplication_window = 60  # seconds
        
        logger.info(f"[DEBUG] MessageSender initialized with API URL: {self.base_url}")
        print(f"[DEBUG] MessageSender initialized with API URL: {self.base_url}")
        
    async def send_message(self, to_number, message, message_type="text", bypass_deduplication=False, max_retries=3):
        """
        Send a message to a WhatsApp user.
        
        Args:
            to_number: The recipient's phone number
            message: The message to send
            message_type: The type of message (for logging)
            bypass_deduplication: Whether to bypass deduplication checks
            max_retries: Maximum number of retry attempts
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            # IMPORTANT: Force bypass_deduplication to True for ALL outgoing messages
            bypass_deduplication = True
            
            # Generate a unique hash for this message for tracking in logs
            message_hash = hashlib.md5(f"{to_number}:{message[:20]}:{int(time.time())}".encode()).hexdigest()[:8]
            
            print(f"\n==================================================")
            print(f"[DEBUG] MESSAGE SENDER START - {message_hash}")
            print(f"[DEBUG] To: {to_number}")
            print(f"[DEBUG] Message Type: {message_type or 'outgoing_message'}")  # Default type for all outgoing messages
            print(f"[DEBUG] Message Length: {len(message)} characters")
            print(f"[DEBUG] Message Preview: {message[:50]}...")
            print(f"[DEBUG] DEDUPLICATION BYPASS: {bypass_deduplication} (FORCED TO TRUE)")
            
            # Print token information for debugging
            print(f"[DEBUG] {message_hash} - WHATSAPP ACCESS TOKEN: {self.access_token[:5]}...{self.access_token[-5:] if len(self.access_token) > 10 else ''}")
            print(f"[DEBUG] {message_hash} - TOKEN LENGTH: {len(self.access_token)}")
            print(f"[DEBUG] {message_hash} - TOKEN FORMAT CORRECT: {self.access_token.startswith('EAA')}")
            print(f"==================================================")
            
            # Always add a timestamp to ensure uniqueness
            timestamp = int(time.time())
            readable_time = datetime.now().strftime("%H:%M:%S")
            
            # Only add timestamp if not already present
            if "Timestamp:" not in message and "(as of " not in message:
                message = f"{message}\n\nTimestamp: {timestamp} ({readable_time})"
                print(f"[DEBUG] {message_hash} - Added timestamp {timestamp} to message")
            
            # Prepare the API request - Fix: Use the base_url property that's already correctly constructed
            url = self.base_url
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'to': to_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            print(f"[DEBUG] {message_hash} - Sending message to WhatsApp API")
            print(f"[DEBUG] {message_hash} - URL: {url}")
            print(f"[DEBUG] {message_hash} - URL COMPONENTS:")
            print(f"[DEBUG] {message_hash} -   Base: https://graph.facebook.com")
            print(f"[DEBUG] {message_hash} -   API Version: {self.api_version}")
            print(f"[DEBUG] {message_hash} -   Phone Number ID: {self.phone_number_id}")
            print(f"[DEBUG] {message_hash} - HEADERS:")
            print(f"[DEBUG] {message_hash} -   Content-Type: {headers['Content-Type']}")
            print(f"[DEBUG] {message_hash} -   Authorization: Bearer {self.access_token[:5]}...{self.access_token[-5:] if len(self.access_token) > 10 else ''}")
            print(f"[DEBUG] {message_hash} - Data: {json.dumps(data)}")
            
            # EXTREME ERROR HANDLING SECTION - ❗❗❗
            try:
                print(f"[DEBUG] {message_hash} - ❗❗❗ CRITICAL SECTION - ABOUT TO MAKE API CALL ❗❗❗")
                print(f"[DEBUG] {message_hash} - Time before API call: {time.time()}")
                
                # The actual API call - THIS IS WHERE EXECUTION STOPS
                async with aiohttp.ClientSession() as session:
                    print(f"[DEBUG] {message_hash} - ❗❗❗ aiohttp.ClientSession created successfully ❗❗❗")
                    try:
                        # Try a more robust approach to making the API call
                        print(f"[DEBUG] {message_hash} - ❗❗❗ About to call session.post ❗❗❗")
                        
                        # Create a timeout
                        timeout = aiohttp.ClientTimeout(total=30)  # 30 seconds timeout
                        
                        # Make the API call with a timeout
                        async with session.post(url, json=data, headers=headers, timeout=timeout) as response:
                            print(f"[DEBUG] {message_hash} - ❗❗❗ session.post COMPLETED ❗❗❗")
                            print(f"[DEBUG] {message_hash} - ❗❗❗ Got API response at {time.time()} ❗❗❗")
                            print(f"[DEBUG] {message_hash} - Response Status: {response.status}")
                            
                            # Get headers and print them for debugging
                            response_headers = dict(response.headers)
                            print(f"[DEBUG] {message_hash} - Response Headers: {response_headers}")
                            
                            # Read the response body
                            response_text = await response.text()
                            print(f"[DEBUG] {message_hash} - Response Body: {response_text}")
                            
                            # Parse the response JSON
                            try:
                                response_json = await response.json()
                                print(f"[DEBUG] {message_hash} - Response parsed as JSON successfully")
                            except Exception as json_err:
                                print(f"[DEBUG] {message_hash} - Error parsing response as JSON: {str(json_err)}")
                                print(f"[DEBUG] {message_hash} - Raw response text: {response_text}")
                                response_json = {}
                            
                            # Check if the request was successful
                            if response.status == HTTPStatus.OK:
                                print(f"[DEBUG] {message_hash} - Message sent successfully! Message ID: {response_json.get('messages', [{}])[0].get('id', 'unknown')}")
                                print(f"[DEBUG] {message_hash} - Message delivery successful after 0 retries")
                                return True
                            else:
                                print(f"[DEBUG] {message_hash} - API returned non-200 status code: {response.status}")
                                print(f"[DEBUG] {message_hash} - API error response: {response_text}")
                                # Try using direct API call via aiohttp.request
                                print(f"[DEBUG] {message_hash} - ❗❗❗ Attempting fallback via aiohttp.request ❗❗❗")
                                try:
                                    raw_response = await session.request(method="POST", url=url, json=data, headers=headers, timeout=timeout)
                                    raw_text = await raw_response.text()
                                    print(f"[DEBUG] {message_hash} - ❗❗❗ Fallback response: Status {raw_response.status} ❗❗❗")
                                    print(f"[DEBUG] {message_hash} - ❗❗❗ Fallback response text: {raw_text} ❗❗❗")
                                    if raw_response.status == 200:
                                        print(f"[DEBUG] {message_hash} - ❗❗❗ Fallback succeeded! ❗❗❗")
                                        return True
                                except Exception as fallback_err:
                                    print(f"[DEBUG] {message_hash} - ❗❗❗ Fallback also failed: {str(fallback_err)} ❗❗❗")
                                    print(f"[DEBUG] {message_hash} - ❗❗❗ Fallback traceback: {traceback.format_exc()} ❗❗❗")
                                
                                print(f"[DEBUG] {message_hash} - API fallbacks exhausted, message sending failed")
                                return False
                    except Exception as post_err:
                        print(f"[DEBUG] {message_hash} - ❗❗❗ session.post EXCEPTION: {str(post_err)} ❗❗❗")
                        print(f"[DEBUG] {message_hash} - ❗❗❗ TRACEBACK for session.post: {traceback.format_exc()} ❗❗❗")
                        
                        # Try alternatives - Direct requests library as last resort
                        try:
                            print(f"[DEBUG] {message_hash} - ❗❗❗ FINAL FALLBACK: Using requests library directly ❗❗❗")
                            import requests
                            
                            # Make a synchronous request
                            sync_response = requests.post(url, json=data, headers=headers, timeout=30)
                            print(f"[DEBUG] {message_hash} - ❗❗❗ requests.post completed with status: {sync_response.status_code} ❗❗❗")
                            print(f"[DEBUG] {message_hash} - ❗❗❗ synchronous response text: {sync_response.text} ❗❗❗")
                            
                            if sync_response.status_code == 200:
                                print(f"[DEBUG] {message_hash} - ❗❗❗ FINAL FALLBACK SUCCEEDED! ❗❗❗")
                                return True
                            else:
                                print(f"[DEBUG] {message_hash} - ❗❗❗ FINAL FALLBACK FAILED with status {sync_response.status_code} ❗❗❗")
                                raise Exception(f"FINAL FALLBACK FAILED: {sync_response.text}")
                        except Exception as req_err:
                            print(f"[DEBUG] {message_hash} - ❗❗❗ FINAL FALLBACK EXCEPTION: {str(req_err)} ❗❗❗")
                            print(f"[DEBUG] {message_hash} - ❗❗❗ FINAL FALLBACK TRACEBACK: {traceback.format_exc()} ❗❗❗")
                            raise req_err
            except Exception as session_err:
                print(f"[DEBUG] {message_hash} - ❗❗❗ CLIENT SESSION EXCEPTION: {str(session_err)} ❗❗❗")
                print(f"[DEBUG] {message_hash} - ❗❗❗ CLIENT SESSION TRACEBACK: {traceback.format_exc()} ❗❗❗")
                
                # ABSOLUTE LAST RESORT - DIRECT URLLIB3 
                try:
                    print(f"[DEBUG] {message_hash} - ❗❗❗ ABSOLUTE LAST RESORT: Using urllib3 directly ❗❗❗")
                    import urllib3
                    import json as json_lib
                    
                    http = urllib3.PoolManager()
                    encoded_data = json_lib.dumps(data).encode('utf-8')
                    
                    response = http.request(
                        'POST',
                        url,
                        body=encoded_data,
                        headers={
                            'Content-Type': 'application/json',
                            'Authorization': f'Bearer {self.access_token}'
                        }
                    )
                    
                    print(f"[DEBUG] {message_hash} - ❗❗❗ URLLIB3 RESPONSE: {response.status} ❗❗❗")
                    print(f"[DEBUG] {message_hash} - ❗❗❗ URLLIB3 DATA: {response.data.decode('utf-8')} ❗❗❗")
                    
                    if response.status == 200:
                        print(f"[DEBUG] {message_hash} - ❗❗❗ URLLIB3 SUCCEEDED! ❗❗❗")
                        return True
                    else:
                        print(f"[DEBUG] {message_hash} - ❗❗❗ URLLIB3 FAILED ❗❗❗")
                        return False
                except Exception as urllib_err:
                    print(f"[DEBUG] {message_hash} - ❗❗❗ URLLIB3 EXCEPTION: {str(urllib_err)} ❗❗❗")
                    print(f"[DEBUG] {message_hash} - ❗❗❗ URLLIB3 TRACEBACK: {traceback.format_exc()} ❗❗❗")
                    # Don't raise, just return False
                    return False
            
        except Exception as e:
            print(f"[DEBUG] ❌ ERROR SENDING MESSAGE: {str(e)}")
            print(f"[DEBUG] ❌ TRACEBACK: {traceback.format_exc()}")
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def mark_message_as_read(self, message_id):
        """
        Mark a WhatsApp message as read to update read receipts.
        
        Args:
            message_id: The WhatsApp message ID to mark as read
            
        Returns:
            bool: True if the message was marked as read successfully, False otherwise
        """
        try:
            logger.info(f"[DEBUG] Marking message as read: {message_id}")
            
            # Print token information for debugging
            print(f"[DEBUG] MARK AS READ - WHATSAPP ACCESS TOKEN: {self.access_token[:5]}...{self.access_token[-5:] if len(self.access_token) > 10 else ''}")
            print(f"[DEBUG] MARK AS READ - TOKEN LENGTH: {len(self.access_token)}")
            print(f"[DEBUG] MARK AS READ - TOKEN FORMAT CORRECT: {self.access_token.startswith('EAA')}")
            
            # Check if token is known to be invalid
            if not self.token_valid:
                logger.error("[DEBUG] Cannot mark message as read: WhatsApp access token is invalid")
                return False
            
            # Use the base_url property that's already correctly constructed
            url = self.base_url
            
            data = {
                'messaging_product': 'whatsapp',
                'status': 'read',
                'message_id': message_id
            }
            
            logger.info(f"[DEBUG] Mark as read URL: {url}")
            logger.info(f"[DEBUG] Mark as read data: {json.dumps(data)}")
            logger.info(f"[DEBUG] Mark as read headers: Content-Type={self.headers['Content-Type']}, Authorization=Bearer {self.access_token[:5]}...{self.access_token[-5:] if len(self.access_token) > 10 else ''}")
            
            # Use aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=data) as response:
                    response_text = await response.text()
                    logger.info(f"[DEBUG] Mark as read response status: {response.status}")
                    logger.info(f"[DEBUG] Mark as read response body: {response_text}")
                    
                    # Handle token expiration errors
                    if response.status in [400, 401]:
                        try:
                            error_data = json.loads(response_text)
                            error_message = error_data.get('error', {}).get('message', '')
                            if 'access token' in error_message.lower():
                                self.token_valid = False
                                logger.error(f"[DEBUG] WhatsApp access token error: {error_message}")
                                print(f"⚠️ WhatsApp access token error: {error_message}")
                                print("Please update the WHATSAPP_ACCESS_TOKEN in your .env file")
                                return False
                        except Exception as e:
                            logger.error(f"[DEBUG] Error parsing error response: {str(e)}")
                    
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"[DEBUG] Error marking message as read: {str(e)}")
            import traceback
            logger.error(f"[DEBUG] Mark as read traceback: {traceback.format_exc()}")
            return False 

    async def send_message_direct(self, to_number, message, message_type=None):
        """
        Send a message directly to a WhatsApp user with minimal processing.
        This uses the exact same approach as the sign-in messages which are working.
        
        Args:
            to_number: The recipient's phone number
            message: The message text to send
            message_type: Optional type of message (for logging only)
            
        Returns:
            bool: Whether the message was sent successfully
        """
        try:
            # Generate a unique hash for this message for tracking in logs
            message_hash = hashlib.md5(f"{to_number}:{message[:20]}:{int(time.time())}".encode()).hexdigest()[:8]
            
            print(f"\n==================================================")
            print(f"[DEBUG] DIRECT MESSAGE SENDER - {message_hash}")
            print(f"[DEBUG] To: {to_number}")
            print(f"[DEBUG] Message Type: {message_type or 'direct_message'}")
            print(f"[DEBUG] Message Length: {len(message)} characters")
            print(f"[DEBUG] Message Preview: {message[:50]}...")
            
            # Always add a timestamp to ensure uniqueness
            timestamp = int(time.time())
            readable_time = datetime.now().strftime("%H:%M:%S")
            
            # Only add timestamp if not already present
            if "Timestamp:" not in message and "(as of " not in message:
                message = f"{message}\n\nTimestamp: {timestamp} ({readable_time})"
                print(f"[DEBUG] {message_hash} - Added timestamp {timestamp} to message")
            
            # Prepare the API request
            url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            data = {
                'messaging_product': 'whatsapp',
                'to': to_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            print(f"[DEBUG] {message_hash} - Sending direct message to WhatsApp API")
            print(f"[DEBUG] {message_hash} - URL: {url}")
            
            # Send the message
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data, timeout=30) as response:
                    response_text = await response.text()
                    print(f"[DEBUG] {message_hash} - Response Status: {response.status}")
                    print(f"[DEBUG] {message_hash} - Response Body: {response_text}")
                    
                    if response.status == 200:
                        try:
                            response_data = json.loads(response_text)
                            message_id = response_data.get('messages', [{}])[0].get('id')
                            print(f"[DEBUG] {message_hash} - Direct message sent successfully! Message ID: {message_id}")
                            return True
                        except Exception as parse_err:
                            print(f"[DEBUG] {message_hash} - Error parsing response: {str(parse_err)}")
                            return True  # Assume success if status is 200
                    else:
                        print(f"[DEBUG] {message_hash} - Failed to send direct message. Response: {response_text}")
                        return False
                        
        except Exception as e:
            print(f"[ERROR] Error sending direct message: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            return False 

    def _cleanup_old_messages(self, current_time):
        """
        Remove old messages from the deduplication cache.
        
        Args:
            current_time: The current time
        """
        # Remove messages older than the deduplication window
        old_messages = [
            msg_hash for msg_hash, sent_time in self._recent_messages.items()
            if current_time - sent_time > self._deduplication_window
        ]
        
        if old_messages:
            print(f"[DEBUG] Cleaning up {len(old_messages)} old messages from deduplication cache")
            for msg_hash in old_messages:
                del self._recent_messages[msg_hash]
                
        # Log cache size periodically
        if len(self._recent_messages) > 0 and len(self._recent_messages) % 10 == 0:
            print(f"[DEBUG] Current deduplication cache size: {len(self._recent_messages)} messages")

    async def send_direct_message(self, to_number, message, message_type="direct"):
        """
        Send a message directly to WhatsApp API, bypassing all abstractions.
        This is a last-resort method for when the main send_message method fails.
        
        Args:
            to_number: The recipient's phone number
            message: The message to send
            message_type: The type of message (for logging)
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # Generate a unique ID for tracking this direct message
        message_id = f"direct-{int(time.time())}-{random.randint(1000, 9999)}"
        print(f"\n====== DIRECT MESSAGE ATTEMPT {message_id} ======")
        print(f"[DIRECT] {message_id} - Sending direct message to {to_number}")
        print(f"[DIRECT] {message_id} - Message type: {message_type}")
        print(f"[DIRECT] {message_id} - Message preview: {message[:100]}...")
        
        try:
            # Add a timestamp to ensure uniqueness
            timestamp = int(time.time())
            message_with_timestamp = f"{message}\n\n⏰ {timestamp}"
            
            # Prepare the direct API request
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Construct the payload directly
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {
                    "body": message_with_timestamp
                }
            }
            
            print(f"[DIRECT] {message_id} - API URL: {self.base_url}")
            print(f"[DIRECT] {message_id} - Headers (partial): Authorization: Bearer {self.access_token[:5]}...")
            print(f"[DIRECT] {message_id} - Payload: {json.dumps(payload)[:200]}...")
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=30  # 30 second timeout
                ) as response:
                    end_time = time.time()
                    elapsed = round(end_time - start_time, 2)
                    
                    status_code = response.status
                    response_text = await response.text()
                    
                    print(f"[DIRECT] {message_id} - Response status: {status_code} (took {elapsed}s)")
                    print(f"[DIRECT] {message_id} - Response: {response_text[:200]}...")
                    
                    # Check if the request was successful
                    if status_code in (200, 201):
                        print(f"[DIRECT] {message_id} - Message sent successfully!")
                        
                        # Try to parse and log the message ID
                        try:
                            response_json = json.loads(response_text)
                            wa_message_id = response_json.get("messages", [{}])[0].get("id", "unknown")
                            print(f"[DIRECT] {message_id} - WhatsApp message ID: {wa_message_id}")
                        except Exception as json_err:
                            print(f"[DIRECT] {message_id} - Could not parse message ID: {str(json_err)}")
                            
                        return True
                    else:
                        # Request failed
                        print(f"[DIRECT] {message_id} - Failed to send message: {status_code}")
                        print(f"[DIRECT] {message_id} - Error response: {response_text}")
                        return False
                        
        except aiohttp.ClientError as client_err:
            print(f"[DIRECT] {message_id} - HTTP client error: {str(client_err)}")
            return False
        except asyncio.TimeoutError:
            print(f"[DIRECT] {message_id} - Request timed out after 30 seconds")
            return False
        except Exception as e:
            print(f"[DIRECT] {message_id} - Unexpected error: {str(e)}")
            print(f"[DIRECT] {message_id} - Traceback: {traceback.format_exc()}")
            return False 