"""
WhatsApp Message Sender
----------------------
This module provides a message sender for WhatsApp messages.
"""

import os
import json
import logging
import aiohttp
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger(__name__)

class WhatsAppMessageSender:
    """
    Sends messages to WhatsApp using the Cloud API.
    
    This class handles sending various types of messages to WhatsApp,
    including text messages and interactive messages.
    """
    
    def __init__(self, 
                 api_version: Optional[str] = None, 
                 phone_number_id: Optional[str] = None, 
                 access_token: Optional[str] = None):
        """
        Initialize the WhatsApp message sender.
        
        Args:
            api_version: WhatsApp API version (defaults to environment variable)
            phone_number_id: WhatsApp phone number ID (defaults to environment variable)
            access_token: WhatsApp access token (defaults to environment variable)
        """
        # Use provided values or get from environment
        self.api_version = api_version or os.environ.get('WHATSAPP_API_VERSION', 'v17.0')
        self.phone_number_id = phone_number_id or os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
        self.access_token = access_token or os.environ.get('WHATSAPP_ACCESS_TOKEN')
        
        # Validate configuration
        if not self.phone_number_id or not self.access_token:
            logger.error("Missing WhatsApp API credentials")
        
        # Set API endpoint
        self.api_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
    
    async def send_text_message(self, to_number: str, text: str) -> Dict[str, Any]:
        """
        Send a text message to a WhatsApp user.
        
        Args:
            to_number: Recipient's phone number
            text: Message text to send
            
        Returns:
            Dict: API response
        """
        # Prepare the message payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": text
            }
        }
        
        # Send the message
        return await self._send_message(payload)
    
    async def send_interactive_message(self, to_number: str, header: Optional[str], body: str, 
                                      footer: Optional[str], buttons: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Send an interactive message with buttons.
        
        Args:
            to_number: Recipient's phone number
            header: Optional header text
            body: Main message body
            footer: Optional footer text
            buttons: List of button objects with "id" and "title" keys
            
        Returns:
            Dict: API response
        """
        # Prepare the message payload
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": button["id"],
                                "title": button["title"]
                            }
                        } for button in buttons
                    ]
                }
            }
        }
        
        # Add header if provided
        if header:
            payload["interactive"]["header"] = {
                "type": "text",
                "text": header
            }
        
        # Add footer if provided
        if footer:
            payload["interactive"]["footer"] = {
                "text": footer
            }
        
        # Send the message
        return await self._send_message(payload)
    
    async def _send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to the WhatsApp API.
        
        Args:
            payload: Message payload to send
            
        Returns:
            Dict: API response
            
        Raises:
            Exception: If the API request fails
        """
        try:
            # Set up headers with authorization
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.access_token}"
            }
            
            # Log the outgoing message (without sensitive data)
            sanitized_payload = json.loads(json.dumps(payload))
            if 'to' in sanitized_payload:
                sanitized_payload['to'] = f"{sanitized_payload['to'][:4]}...{sanitized_payload['to'][-4:]}"
            logger.debug(f"Sending WhatsApp message: {json.dumps(sanitized_payload)}")
            
            # Make the API request
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    result = await response.json()
                    
                    # Check for errors
                    if response.status >= 400:
                        error_msg = result.get('error', {}).get('message', 'Unknown error')
                        logger.error(f"WhatsApp API error ({response.status}): {error_msg}")
                        raise Exception(f"WhatsApp API error: {error_msg}")
                    
                    logger.debug(f"WhatsApp API response: {json.dumps(result)}")
                    return result
                    
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}", exc_info=True)
            raise 