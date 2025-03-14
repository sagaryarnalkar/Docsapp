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
            # Generate a unique key for this message
            message_key = f"{to_number}:{message}"
            current_time = int(time.time())
            
            # Clean up old sent messages (older than 1 hour)
            cutoff_time = current_time - 3600
            self.sent_messages = {k:v for k,v in self.sent_messages.items() if v > cutoff_time}
            
            # Special handling for unknown command messages - always send these
            is_unknown_command = "I don't understand that command" in message
            if is_unknown_command:
                print(f"Sending unknown command message to {to_number} (bypassing deduplication)")
                # Don't return here, continue with sending the message
            # Regular deduplication for other messages
            elif message_key in self.sent_messages:
                time_since_sent = current_time - self.sent_messages[message_key]
                if time_since_sent < 60:  # 60 seconds deduplication window
                    print(f"Skipping duplicate message to {to_number}: {message[:50]}... (sent {time_since_sent}s ago)")
                    return True
                else:
                    print(f"Message was sent before, but {time_since_sent}s ago, so sending again")
            
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
                elif is_processing_started:
                    simplified_key = f"{to_number}:processing_started"
                    dedup_window = 300  # 5 minutes for processing start notifications
                
                if simplified_key and simplified_key in self.sent_messages:
                    time_since_sent = current_time - self.sent_messages[simplified_key]
                    if time_since_sent < dedup_window:
                        print(f"Skipping duplicate notification to {to_number} (type: {simplified_key}, sent {time_since_sent}s ago)")
                        return True
                
                # Store both the exact message and the simplified version if we have one
                if simplified_key:
                    self.sent_messages[simplified_key] = current_time
            
            # For completion notifications, we'll still track them but never skip sending them
            if is_processing_completed:
                print(f"Sending completion notification to {to_number} (always sent regardless of deduplication)")
                simplified_key = f"{to_number}:processing_completed"
                self.sent_messages[simplified_key] = current_time
            
            if is_error_message:
                print(f"Sending error notification to {to_number} (always sent regardless of deduplication)")
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
            
            print(f"\nSending message to {to_number}:")
            print(f"URL: {url}")
            print(f"Data: {json.dumps(data, indent=2)}")
            
            # Use aiohttp for async HTTP requests
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=data) as response:
                    response_text = await response.text()
                    print(f"Response Status: {response.status}")
                    print(f"Response Body: {response_text}")
                    
                    # Handle token expiration errors
                    if response.status == 400:
                        error_data = json.loads(response_text)
                        error_message = error_data.get('error', {}).get('message', '')
                        if 'access token' in error_message.lower():
                            print("WhatsApp access token error detected")
                            logger.error(f"WhatsApp API Error: {error_message}")
                            return False
                    
                    if response.status == 200:
                        # Mark message as sent
                        self.sent_messages[message_key] = current_time
                    
                    return response.status == 200
            
        except Exception as e:
            print(f"Error sending WhatsApp message: {str(e)}")
            import traceback
            print(f"Send Message Traceback: {traceback.format_exc()}")
            return False 