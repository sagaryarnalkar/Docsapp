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
        
    async def send_message(self, to_number, message):
        """
        Send a WhatsApp message with deduplication.
        
        Args:
            to_number: Recipient's phone number
            message: Message text to send
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        try:
            # Generate a unique message ID for logging
            message_hash = hashlib.md5(f"{to_number}:{message}".encode()).hexdigest()[:8]
            logger.info(f"[DEBUG] Processing message {message_hash} to {to_number}")
            logger.info(f"[DEBUG] Message content: {message[:50]}{'...' if len(message) > 50 else ''}")
            
            # Check if token is known to be invalid
            if not self.token_valid:
                logger.error(f"[DEBUG] Cannot send message {message_hash}: WhatsApp access token is invalid")
                print(f"⚠️ Cannot send message to {to_number}: WhatsApp access token is invalid")
                print("Please update the WHATSAPP_ACCESS_TOKEN in your .env file")
                return False
                
            # Generate a unique key for this message
            message_key = f"{to_number}:{message}"
            current_time = int(time.time())
            
            # Clean up old sent messages (older than 1 hour)
            cutoff_time = current_time - 3600
            old_count = len(self.sent_messages)
            self.sent_messages = {k:v for k,v in self.sent_messages.items() if v > cutoff_time}
            new_count = len(self.sent_messages)
            if old_count != new_count:
                logger.info(f"[DEBUG] Cleaned up {old_count - new_count} old messages from deduplication cache")
            
            # Messages that should always be sent (bypass deduplication)
            is_no_documents = "You don't have any stored documents" in message
            is_list_command = "Your documents:" in message or is_no_documents
            is_help_command = "Available commands:" in message
            is_find_command = "Found matching documents" in message or "No documents found matching" in message
            is_ask_command = "Here are the answers from your documents" in message or "No relevant information found" in message
            
            is_important_message = is_list_command or is_help_command or is_find_command or is_ask_command
            
            if is_important_message:
                logger.info(f"[DEBUG] Message {message_hash} is important and will bypass deduplication")
                if is_list_command:
                    logger.info(f"[DEBUG] Message is a LIST command response")
                elif is_help_command:
                    logger.info(f"[DEBUG] Message is a HELP command response")
                elif is_find_command:
                    logger.info(f"[DEBUG] Message is a FIND command response")
                elif is_ask_command:
                    logger.info(f"[DEBUG] Message is an ASK command response")
                
                # Don't return here, continue with sending the message
            # Regular deduplication for other messages
            elif message_key in self.sent_messages:
                time_since_sent = current_time - self.sent_messages[message_key]
                if time_since_sent < 60:  # 60 seconds deduplication window
                    logger.info(f"[DEBUG] Skipping duplicate message {message_hash} to {to_number}: sent {time_since_sent}s ago")
                    return True
                else:
                    logger.info(f"[DEBUG] Message {message_hash} was sent before, but {time_since_sent}s ago, so sending again")
            
            # Enhanced deduplication for document processing messages
            # Create message type flags for different kinds of notifications
            is_document_stored = "Document" in message and "stored successfully" in message
            is_processing_started = "Document processing started" in message
            is_processing_completed = "has been processed successfully" in message or "processing completed with issues" in message
            is_error_message = "error processing your document" in message
            
            # Apply more aggressive deduplication for document notifications
            # EXCEPT for completion notifications which should always be sent
            if (is_document_stored or is_processing_started) and not is_processing_completed and not is_error_message:
                # Create a simplified key based on the message type
                simplified_key = None
                dedup_window = 60  # Default window (60 seconds)
                
                if is_document_stored:
                    simplified_key = f"{to_number}:document_stored"
                    dedup_window = 300  # 5 minutes for storage confirmations
                    logger.info(f"[DEBUG] Message {message_hash} is a document storage confirmation")
                elif is_processing_started:
                    simplified_key = f"{to_number}:processing_started"
                    dedup_window = 300  # 5 minutes for processing start notifications
                    logger.info(f"[DEBUG] Message {message_hash} is a processing start notification")
                
                if simplified_key and simplified_key in self.sent_messages:
                    time_since_sent = current_time - self.sent_messages[simplified_key]
                    if time_since_sent < dedup_window:
                        logger.info(f"[DEBUG] Skipping duplicate notification {message_hash} to {to_number} (type: {simplified_key}, sent {time_since_sent}s ago)")
                        return True
                
                # Store both the exact message and the simplified version if we have one
                if simplified_key:
                    self.sent_messages[simplified_key] = current_time
                    logger.info(f"[DEBUG] Storing simplified key {simplified_key} in deduplication cache")
            
            # For completion notifications, we'll still track them but never skip sending them
            if is_processing_completed:
                logger.info(f"[DEBUG] Message {message_hash} is a completion notification (always sent)")
                simplified_key = f"{to_number}:processing_completed"
                self.sent_messages[simplified_key] = current_time
            
            if is_error_message:
                logger.info(f"[DEBUG] Message {message_hash} is an error notification (always sent)")
                simplified_key = f"{to_number}:processing_error"
                self.sent_messages[simplified_key] = current_time
            
            # Prepare the API request
            url = self.base_url
            
            data = {
                'messaging_product': 'whatsapp',
                'to': to_number,
                'type': 'text',
                'text': {'body': message}
            }
            
            logger.info(f"[DEBUG] Sending message {message_hash} to {to_number}")
            logger.info(f"[DEBUG] URL: {url}")
            logger.info(f"[DEBUG] Data: {json.dumps(data)}")
            
            # Use aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=data) as response:
                    response_text = await response.text()
                    logger.info(f"[DEBUG] Response Status for message {message_hash}: {response.status}")
                    logger.info(f"[DEBUG] Response Headers: {dict(response.headers)}")
                    logger.info(f"[DEBUG] Response Body: {response_text}")
                    
                    # Handle token expiration errors
                    if response.status in [400, 401]:
                        try:
                            error_data = json.loads(response_text)
                            error_message = error_data.get('error', {}).get('message', '')
                            error_code = error_data.get('error', {}).get('code', 0)
                            
                            # Check for token-related errors
                            token_error_keywords = ['access token', 'token', 'auth', 'expired', 'invalid']
                            is_token_error = any(keyword in error_message.lower() for keyword in token_error_keywords)
                            
                            if is_token_error or error_code in [190, 104]:
                                self.token_valid = False
                                error_msg = f"⚠️ WhatsApp access token error: {error_message}"
                                logger.error(f"[DEBUG] {error_msg}")
                                print("\n" + "="*80)
                                print(error_msg)
                                print("Please update the WHATSAPP_ACCESS_TOKEN in your .env file")
                                print("See whatsapp_token_guide.md for instructions")
                                print("="*80 + "\n")
                                return False
                        except Exception as e:
                            logger.error(f"[DEBUG] Error parsing error response for message {message_hash}: {str(e)}")
                    
                    if response.status == 200:
                        # Mark message as sent
                        self.sent_messages[message_key] = current_time
                        logger.info(f"[DEBUG] Message {message_hash} sent successfully, stored in deduplication cache")
                        
                        # Parse the response to get the message ID
                        try:
                            response_data = json.loads(response_text)
                            message_id = response_data.get('messages', [{}])[0].get('id')
                            logger.info(f"[DEBUG] WhatsApp message ID for {message_hash}: {message_id}")
                        except Exception as e:
                            logger.error(f"[DEBUG] Error parsing message ID from response: {str(e)}")
                        
                        return True
                    else:
                        logger.error(f"[DEBUG] Failed to send message {message_hash}. Status code: {response.status}")
                        return False
            
        except Exception as e:
            logger.error(f"[DEBUG] Error sending WhatsApp message: {str(e)}")
            import traceback
            logger.error(f"[DEBUG] Send Message Traceback: {traceback.format_exc()}")
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