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
        
    async def send_message(self, to_number, message, message_type=None, bypass_deduplication=True, max_retries=3):
        """
        Send a message to a WhatsApp user.
        
        Args:
            to_number: The recipient's phone number
            message: The message text to send
            message_type: Optional type of message (e.g., "list_command")
            bypass_deduplication: Whether to bypass deduplication checks (default: True)
            max_retries: Maximum number of retry attempts
            
        Returns:
            bool: Whether the message was sent successfully
        """
        try:
            # Generate a unique hash for this message for tracking in logs
            message_hash = hashlib.md5(f"{to_number}:{message[:20]}:{int(time.time())}".encode()).hexdigest()[:8]
            
            print(f"\n==================================================")
            print(f"[DEBUG] MESSAGE SENDER START - {message_hash}")
            print(f"[DEBUG] To: {to_number}")
            print(f"[DEBUG] Message Type: {message_type or 'outgoing_message'}")  # Default type for all outgoing messages
            print(f"[DEBUG] Message Length: {len(message)} characters")
            print(f"[DEBUG] Message Preview: {message[:50]}...")
            
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