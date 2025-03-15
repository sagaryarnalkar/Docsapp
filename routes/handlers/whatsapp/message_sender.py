"""
WhatsApp Message Sender
----------------------
This module handles sending messages to WhatsApp users with deduplication
to prevent sending the same message multiple times.
"""

import json
import time
import logging
import aiohttp
import hashlib

logger = logging.getLogger(__name__)

class MessageSender:
    """
    Handles sending messages to WhatsApp users with deduplication.
    
    This class is responsible for:
    1. Sending text messages to WhatsApp users
    2. Preventing duplicate messages from being sent
    3. Handling API errors and token expiration
    """
    
    def __init__(self, api_version, phone_number_id, access_token):
        """
        Initialize the message sender.
        
        Args:
            api_version: WhatsApp API version
            phone_number_id: WhatsApp phone number ID
            access_token: WhatsApp access token
        """
        self.api_version = api_version
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.base_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}"
        }
        self.sent_messages = {}  # Track sent messages to prevent duplicates
        self.token_valid = True  # Track if the token is valid
        self.debug_mode = True   # Enable debug mode for detailed logging
        
        # Check if the token is obviously invalid
        if "EXPIRED_TOKEN" in access_token or "REPLACE" in access_token:
            self.token_valid = False
            logger.error("⚠️ WhatsApp access token appears to be a placeholder or expired!")
            print("⚠️ WhatsApp access token appears to be a placeholder or expired!")
            print("Please update the WHATSAPP_ACCESS_TOKEN in your .env file")
        
        logger.info(f"[DEBUG] MessageSender initialized with API version {api_version}")
        logger.info(f"[DEBUG] Phone Number ID: {phone_number_id}")
        logger.info(f"[DEBUG] Token valid: {self.token_valid}")
        
    async def send_message(self, to_number, message, message_type=None, bypass_deduplication=False):
        """
        Send a message to a WhatsApp user.
        
        Args:
            to_number: The recipient's phone number
            message: The message text to send
            message_type: Optional type of message (e.g., "list_command")
            bypass_deduplication: Whether to bypass deduplication checks
            
        Returns:
            bool: Whether the message was sent successfully
        """
        try:
            # Generate a unique hash for this message for tracking in logs
            message_hash = hashlib.md5(f"{to_number}:{message[:20]}:{int(time.time())}".encode()).hexdigest()[:8]
            
            print(f"\n==================================================")
            print(f"[DEBUG] MESSAGE SENDER START - {message_hash}")
            print(f"[DEBUG] To: {to_number}")
            print(f"[DEBUG] Message Type: {message_type}")
            print(f"[DEBUG] Bypass Deduplication: {bypass_deduplication}")
            print(f"[DEBUG] Message Length: {len(message)} characters")
            print(f"[DEBUG] Message Preview: {message[:50]}...")
            print(f"==================================================")
            
            # Check if this is a command response that should bypass deduplication
            is_command_response = message_type in ["list_command", "help_command", "find_command", "ask_command"]
            
            if is_command_response or bypass_deduplication:
                print(f"[DEBUG] {message_hash} - Command response or bypass flag set, forcing unique message")
                # Add a timestamp to force uniqueness if not already present
                if "Timestamp:" not in message and "(as of " not in message and "(Check: " not in message:
                    timestamp = int(time.time())
                    message = f"{message}\n\nTimestamp: {timestamp}"
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
            
            print(f"[DEBUG] {message_hash} - Sending message to WhatsApp API")
            print(f"[DEBUG] {message_hash} - URL: {url}")
            print(f"[DEBUG] {message_hash} - Data: {json.dumps(data)}")
            
            # Send the message
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=data) as response:
                    response_text = await response.text()
                    print(f"[DEBUG] {message_hash} - Response Status: {response.status}")
                    print(f"[DEBUG] {message_hash} - Response Headers: {dict(response.headers)}")
                    print(f"[DEBUG] {message_hash} - Response Body: {response_text}")
                    
                    if response.status == 200:
                        try:
                            response_data = json.loads(response_text)
                            message_id = response_data.get('messages', [{}])[0].get('id')
                            print(f"[DEBUG] {message_hash} - Message sent successfully! Message ID: {message_id}")
                            
                            # Track this message as sent
                            if message_type:
                                print(f"[DEBUG] {message_hash} - Tracking message type: {message_type}")
                                # Track in Redis if available
                                try:
                                    redis_client = self._get_redis_client()
                                    if redis_client:
                                        key = f"sent:{to_number}:{message_type}:{int(time.time())}"
                                        redis_client.set(key, message_id, ex=3600)  # Expire after 1 hour
                                        print(f"[DEBUG] {message_hash} - Tracked in Redis with key: {key}")
                                except Exception as redis_err:
                                    print(f"[DEBUG] {message_hash} - Redis tracking error: {str(redis_err)}")
                            
                            return True
                        except Exception as parse_err:
                            print(f"[DEBUG] {message_hash} - Error parsing response: {str(parse_err)}")
                            return True  # Assume success if status is 200
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
                        except Exception as e:
                            print(f"[DEBUG] {message_hash} - Error parsing error response: {str(e)}")
                        
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
            
            # Check if token is known to be invalid
            if not self.token_valid:
                logger.error("[DEBUG] Cannot mark message as read: WhatsApp access token is invalid")
                return False
                
            url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
            
            data = {
                'messaging_product': 'whatsapp',
                'status': 'read',
                'message_id': message_id
            }
            
            logger.info(f"[DEBUG] Mark as read URL: {url}")
            logger.info(f"[DEBUG] Mark as read data: {json.dumps(data)}")
            
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

    def _get_redis_client(self):
        """Get a Redis client for tracking messages."""
        try:
            import os
            import redis
            
            redis_url = os.environ.get('REDIS_URL')
            if not redis_url:
                print("[DEBUG] No Redis URL found in environment variables")
                return None
                
            redis_client = redis.Redis.from_url(
                redis_url,
                socket_timeout=2,
                socket_connect_timeout=2,
                decode_responses=True
            )
            
            # Test the connection
            redis_client.ping()
            return redis_client
        except ImportError:
            print("[DEBUG] Redis package not installed")
            return None
        except Exception as e:
            print(f"[DEBUG] Error connecting to Redis: {str(e)}")
            return None 