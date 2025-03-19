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
import urllib.request
import urllib.error
import http.client

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
        
    async def send_whatsapp_api_request(self, payload, message_hash="unknown", request_type="message"):
        """
        Core method for making WhatsApp API requests.
        
        Args:
            payload: The JSON payload to send to the WhatsApp API
            message_hash: Identifier for this message (for logging)
            request_type: Type of request (message, mark_read, etc.)
            
        Returns:
            tuple: (success, response_data, status_code)
        """
        url = self.base_url
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        
        print(f"[DEBUG] {message_hash} - Making WhatsApp API {request_type} request")
        print(f"[DEBUG] {message_hash} - URL: {url}")
        print(f"[DEBUG] {message_hash} - Payload: {json.dumps(payload)}")
        
        # Try multiple methods to ensure message delivery
        
        # Method 1: Using urllib
        try:
            print(f"[DEBUG] {message_hash} - Trying urllib.request method")
            data_bytes = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method='POST')
            
            with urllib.request.urlopen(req, timeout=30) as response:
                print(f"[DEBUG] {message_hash} - urllib.request succeeded")
                response_data = response.read().decode('utf-8')
                status_code = response.status
                
                print(f"[DEBUG] {message_hash} - Response Status: {status_code}")
                print(f"[DEBUG] {message_hash} - Response Data: {response_data}")
                
                return (status_code == 200, response_data, status_code)
        
        except (urllib.error.HTTPError, urllib.error.URLError) as err:
            print(f"[DEBUG] {message_hash} - urllib.request failed: {str(err)}")
            error_response = ""
            if hasattr(err, 'read'):
                try:
                    error_response = err.read().decode('utf-8')
                    print(f"[DEBUG] {message_hash} - Error response: {error_response}")
                except:
                    pass
        
        # Method 2: Using http.client
        try:
            print(f"[DEBUG] {message_hash} - Trying http.client method")
            conn = http.client.HTTPSConnection("graph.facebook.com")
            path = f"/{self.api_version}/{self.phone_number_id}/messages"
            
            conn.request("POST", path, json.dumps(payload), headers)
            res = conn.getresponse()
            response_data = res.read().decode('utf-8')
            
            print(f"[DEBUG] {message_hash} - http.client Response Status: {res.status}")
            print(f"[DEBUG] {message_hash} - http.client Response: {response_data}")
            
            conn.close()
            return (res.status == 200, response_data, res.status)
            
        except Exception as http_client_err:
            print(f"[DEBUG] {message_hash} - http.client failed: {str(http_client_err)}")
        
        # Method 3: Using requests if available
        try:
            print(f"[DEBUG] {message_hash} - Trying requests library method")
            import requests
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            print(f"[DEBUG] {message_hash} - requests Response Status: {response.status_code}")
            print(f"[DEBUG] {message_hash} - requests Response: {response.text}")
            
            return (response.status_code == 200, response.text, response.status_code)
            
        except ImportError:
            print(f"[DEBUG] {message_hash} - requests library not available")
        except Exception as requests_err:
            print(f"[DEBUG] {message_hash} - requests method failed: {str(requests_err)}")
        
        # If we got here, all methods failed
        print(f"[DEBUG] {message_hash} - All API request methods failed")
        return (False, "All request methods failed", 500)
        
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
            
            # Prepare payload
            data = {
                'messaging_product': 'whatsapp',
                'to': to_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            # Send the request using the unified API method
            success, response_data, status_code = await self.send_whatsapp_api_request(
                payload=data,
                message_hash=message_hash,
                request_type="text_message"
            )
            
            if success:
                print(f"[DEBUG] {message_hash} - Message sent successfully!")
                
                # Try to get message ID from response
                try:
                    response_json = json.loads(response_data)
                    message_id = response_json.get('messages', [{}])[0].get('id', 'unknown')
                    print(f"[DEBUG] {message_hash} - Message ID: {message_id}")
                except Exception as json_err:
                    print(f"[DEBUG] {message_hash} - Error parsing JSON response: {str(json_err)}")
                
                return True
            else:
                print(f"[DEBUG] {message_hash} - Failed to send message. Status: {status_code}")
                return False
                
        except Exception as e:
            print(f"[DEBUG] {message_hash} - Unexpected error in send_message: {str(e)}")
            print(f"[DEBUG] {message_hash} - Traceback: {traceback.format_exc()}")
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
            
            # Prepare payload
            data = {
                'messaging_product': 'whatsapp',
                'status': 'read',
                'message_id': message_id
            }
            
            # Generate a hash for this request for logging
            mark_read_hash = hashlib.md5(f"mark_read:{message_id}:{int(time.time())}".encode()).hexdigest()[:8]
            
            # Send the request using the unified API method
            success, response_data, status_code = await self.send_whatsapp_api_request(
                payload=data,
                message_hash=mark_read_hash,
                request_type="mark_as_read"
            )
            
            # Handle token expiration errors
            if not success and status_code in [400, 401]:
                try:
                    error_data = json.loads(response_data)
                    error_message = error_data.get('error', {}).get('message', '')
                    if 'access token' in error_message.lower():
                        self.token_valid = False
                        logger.error(f"[DEBUG] WhatsApp access token error: {error_message}")
                        print(f"⚠️ WhatsApp access token error: {error_message}")
                        print("Please update the WHATSAPP_ACCESS_TOKEN in your .env file")
                except Exception as e:
                    logger.error(f"[DEBUG] Error parsing error response: {str(e)}")
            
            return success
                
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
            
            # Prepare payload
            data = {
                'messaging_product': 'whatsapp',
                'to': to_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            # Send the request using the unified API method
            success, response_data, status_code = await self.send_whatsapp_api_request(
                payload=data,
                message_hash=message_hash,
                request_type="direct_message"
            )
            
            if success:
                print(f"[DEBUG] {message_hash} - Direct message sent successfully!")
                return True
            else:
                print(f"[DEBUG] {message_hash} - Failed to send direct message. Status: {status_code}")
                return False
                
        except Exception as e:
            print(f"[DEBUG] {message_hash} - Error in send_message_direct: {str(e)}")
            print(f"[DEBUG] {message_hash} - Traceback: {traceback.format_exc()}")
            return False

    def _cleanup_old_messages(self, current_time):
        """
        Remove old messages from the deduplication cache.
        
        Args:
            current_time: Current timestamp for comparison
        """
        # Identify messages older than the deduplication window
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
            
            # Construct the payload directly
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {
                    "body": message_with_timestamp
                }
            }
            
            # Send the request using the unified API method
            success, response_data, status_code = await self.send_whatsapp_api_request(
                payload=payload,
                message_hash=message_id,
                request_type="emergency_direct"
            )
            
            if success:
                print(f"[DIRECT] {message_id} - Message sent successfully!")
                
                # Try to parse and log the message ID
                try:
                    response_json = json.loads(response_data)
                    wa_message_id = response_json.get("messages", [{}])[0].get("id", "unknown")
                    print(f"[DIRECT] {message_id} - WhatsApp message ID: {wa_message_id}")
                except Exception as json_err:
                    print(f"[DIRECT] {message_id} - Could not parse message ID: {str(json_err)}")
                    
                return True
            else:
                # Request failed
                print(f"[DIRECT] {message_id} - Failed to send message: {status_code}")
                print(f"[DIRECT] {message_id} - Error response: {response_data}")
                return False
                
        except Exception as e:
            print(f"[DIRECT] {message_id} - Unexpected error: {str(e)}")
            print(f"[DIRECT] {message_id} - Traceback: {traceback.format_exc()}")
            return False 