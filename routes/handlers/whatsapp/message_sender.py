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
            
            # Check for duplicate messages
            current_time = time.time()
            if not bypass_deduplication and message_hash in self._recent_messages:
                last_sent = self._recent_messages[message_hash]
                time_diff = current_time - last_sent
                
                if time_diff < self._deduplication_window:
                    print(f"[DEBUG] Duplicate message detected! Last sent {time_diff:.2f}s ago. Skipping.")
                    logger.warning(f"[DEBUG] Duplicate message detected! Last sent {time_diff:.2f}s ago. Skipping.")
                    return False
            
            # Clean up old messages
            self._cleanup_old_messages(current_time)
            
            # Add message to recent messages
            if not bypass_deduplication:
                self._recent_messages[message_hash] = current_time
            
            # Implement retry logic
            retry_count = 0
            success = False
            last_error = None
            
            while retry_count < max_retries and not success:
                if retry_count > 0:
                    print(f"[DEBUG] {message_hash} - Retry attempt {retry_count}/{max_retries}")
                    # Add a small delay between retries with exponential backoff
                    await asyncio.sleep(2 ** retry_count)
                
                try:
                    # Send the message
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, headers=headers, json=data, timeout=30) as response:
                            response_text = await response.text()
                            print(f"[DEBUG] {message_hash} - Response Status: {response.status}")
                            print(f"[DEBUG] {message_hash} - Response Headers: {dict(response.headers)}")
                            print(f"[DEBUG] {message_hash} - Response Body: {response_text}")
                            
                            if response.status == 200:
                                try:
                                    response_data = json.loads(response_text)
                                    message_id = response_data.get('messages', [{}])[0].get('id')
                                    print(f"[DEBUG] {message_hash} - Message sent successfully! Message ID: {message_id}")
                                    success = True
                                    break  # Exit the retry loop on success
                                except Exception as parse_err:
                                    print(f"[DEBUG] {message_hash} - Error parsing response: {str(parse_err)}")
                                    success = True  # Assume success if status is 200
                                    break  # Exit the retry loop on success
                            else:
                                print(f"[DEBUG] {message_hash} - Failed to send message. Response: {response_text}")
                                
                                # Check for token expiration
                                try:
                                    error_data = json.loads(response_text)
                                    error_message = error_data.get('error', {}).get('message', '')
                                    error_code = error_data.get('error', {}).get('code', '')
                                    
                                    print(f"[DEBUG] {message_hash} - Error Code: {error_code}")
                                    print(f"[DEBUG] {message_hash} - Error Message: {error_message}")
                                    
                                    if 'access token' in error_message.lower() or error_code == 190:
                                        print(f"[DEBUG] {message_hash} - ⚠️ WhatsApp access token has expired or is invalid!")
                                        # Don't retry token errors
                                        break
                                    
                                    # Store the error for logging
                                    last_error = f"Error {error_code}: {error_message}"
                                except Exception as e:
                                    print(f"[DEBUG] {message_hash} - Error parsing error response: {str(e)}")
                                    last_error = f"HTTP {response.status}: {response_text}"
                                
                                # Continue to retry for non-token errors
                except Exception as request_err:
                    print(f"[DEBUG] {message_hash} - Request error: {str(request_err)}")
                    last_error = str(request_err)
                
                retry_count += 1
            
            # Log the final outcome
            if success:
                print(f"[DEBUG] {message_hash} - Message delivery successful after {retry_count} retries")
                return True
            else:
                print(f"[DEBUG] {message_hash} - Message delivery failed after {retry_count} retries. Last error: {last_error}")
                
                # Log to a persistent file for debugging
                try:
                    with open("message_delivery_failures.log", "a") as f:
                        f.write(f"{datetime.now().isoformat()} - To: {to_number}, Type: {message_type}, Error: {last_error}\n")
                except Exception as log_err:
                    print(f"[DEBUG] {message_hash} - Error writing to failure log: {str(log_err)}")
                
                return False
                        
        except Exception as e:
            print(f"[ERROR] Error sending message: {str(e)}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
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