"""
WhatsApp Handler - Main Coordinator
----------------------------------
This module contains the main WhatsAppHandler class that coordinates all WhatsApp
interactions. It delegates specific tasks to specialized modules.
"""

import json
import logging
import time
import asyncio
import os
from typing import Dict, Any, Tuple, Optional
from config import (
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_API_VERSION
)
from routes.handlers.auth_handler import AuthHandler
from .message_sender import MessageSender
from .document_processor import DocumentProcessor, WhatsAppHandlerError
from .command_processor import CommandProcessor
from .deduplication import DeduplicationManager

logger = logging.getLogger(__name__)

# Global message tracking to prevent duplicates across instances
# Format: {message_key: timestamp}
GLOBAL_MESSAGE_TRACKING = {}

class WhatsAppHandler:
    """
    Main handler for WhatsApp interactions.
    
    This class coordinates all WhatsApp message processing, delegating specific
    tasks to specialized components. It handles incoming messages, processes
    documents, and manages user interactions.
    """
    
    def __init__(self, docs_app, pending_descriptions, user_state):
        """
        Initialize the WhatsApp handler with necessary dependencies.
        
        Args:
            docs_app: The DocsApp instance for document operations
            pending_descriptions: Dictionary to track pending document descriptions
            user_state: UserState instance for managing user authentication state
        """
        # Store core dependencies
        self.docs_app = docs_app
        self.pending_descriptions = pending_descriptions
        self.user_state = user_state
        
        # Initialize WhatsApp API configuration
        self.api_version = WHATSAPP_API_VERSION
        self.phone_number_id = WHATSAPP_PHONE_NUMBER_ID
        self.access_token = WHATSAPP_ACCESS_TOKEN
        
        # Initialize specialized components
        self.auth_handler = AuthHandler(self.user_state)
        self.message_sender = MessageSender(
            self.api_version, 
            self.phone_number_id, 
            self.access_token
        )
        
        # Initialize deduplication manager
        self.deduplication = DeduplicationManager()
        
        # Try to initialize Redis deduplication manager if available
        try:
            from .redis_deduplication import RedisDeduplicationManager
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                self.redis_deduplication = RedisDeduplicationManager(redis_url)
                logger.info(f"Using Redis for message deduplication: {redis_url.split('@')[1] if '@' in redis_url else 'unknown'}")
                print(f"Using Redis for message deduplication")
            else:
                self.redis_deduplication = None
                logger.info("Redis URL not available, using in-memory deduplication")
                print("Redis URL not available, using in-memory deduplication")
        except ImportError as e:
            self.redis_deduplication = None
            logger.warning(f"Redis deduplication not available: {str(e)}")
            print(f"Redis deduplication not available: {str(e)}")
        
        # Initialize document processor with the appropriate deduplication manager
        self.document_processor = DocumentProcessor(
            self.docs_app, 
            self.message_sender,
            self._get_deduplication()
        )
        
        self.command_processor = CommandProcessor(
            self.docs_app, 
            self.message_sender
        )
        
        # Check if RAG processor is available
        self.rag_processor = docs_app.rag_processor if docs_app else None
        self.rag_available = (
            self.rag_processor is not None and 
            hasattr(self.rag_processor, 'is_available') and 
            self.rag_processor.is_available
        )
        
        # Clean up old global message tracking entries
        self._cleanup_global_tracking()

    async def send_message(self, to_number, message):
        """
        Send a WhatsApp message to a user.
        
        Args:
            to_number: The recipient's phone number
            message: The message text to send
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # Delegate to the message sender component
        return await self.message_sender.send_message(to_number, message)

    async def handle_incoming_message(self, data):
        """
        Process an incoming WhatsApp message.
        
        This is the main entry point for handling webhook events from WhatsApp.
        It identifies the message type and delegates to the appropriate handler.
        
        Args:
            data: The webhook payload from WhatsApp
            
        Returns:
            tuple: (response_message, status_code)
            
        Raises:
            WhatsAppHandlerError: If an error occurs that has been handled
        """
        try:
            print(f"\n{'='*50}")
            print("WHATSAPP MESSAGE PROCESSING START")
            print(f"{'='*50}")
            print(f"Raw Data: {json.dumps(data, indent=2)}")

            # Clean up tracking dictionaries
            self.deduplication.cleanup()
            self._cleanup_global_tracking()

            # Extract message data from the webhook payload
            entry = data.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})

            # Check if this is a status update (not a message)
            if 'statuses' in value:
                print("Status update received - ignoring")
                return "Status update processed", 200

            # Extract message data
            messages = value.get('messages', [])
            if not messages:
                print("No messages found in payload")
                return "No messages to process", 200

            message = messages[0]
            message_id = message.get('id')
            from_number = message.get('from')
            
            if not message_id or not from_number:
                print("Missing message ID or sender number")
                return "Invalid message data", 400
                
            # Create a more robust message key that combines the sender's number and message ID
            message_key = f"{from_number}:{message_id}"
            current_time = int(time.time())
            
            # Check for duplicate message using the appropriate deduplication mechanism
            if self._is_duplicate_message(from_number, message_id, message_key):
                print(f"DUPLICATE MESSAGE DETECTED: {message_key}")
                return "Duplicate message processing prevented", 200
            
            # Mark this message as being processed
            self._mark_message_processed(from_number, message_id, message_key, current_time)
            
            print(f"\n=== Message Details ===")
            print(f"From: {from_number}")
            print(f"Message ID: {message_id}")
            print(f"Message Key: {message_key}")

            # Check authentication status first for any message
            is_authorized = self.user_state.is_authorized(from_number)
            print(f"User authorization status: {is_authorized}")

            # Handle authentication if user is not authorized
            if not is_authorized:
                return await self._handle_unauthorized_user(from_number)

            # Process the message based on its type
            message_type = message.get('type')
            print(f"Message Type: {message_type}")

            # Handle all file types (document, image, video, audio)
            if message_type in ['document', 'image', 'video', 'audio']:
                print(f"Processing {message_type} message...")
                media_obj = message.get(message_type, {})
                if not media_obj:
                    print(f"No {message_type} object found in message")
                    return f"No {message_type} found", 400
                
                # For images and other media that might not have filename
                if message_type != 'document':
                    extension = {
                        'image': '.jpg',
                        'video': '.mp4',
                        'audio': '.mp3'
                    }.get(message_type, '')
                    media_obj['filename'] = f"{message_type}_{int(time.time())}{extension}"
                
                return await self.document_processor.handle_document(from_number, media_obj, message)
                
            # Handle text messages and document replies
            elif message_type == 'text':
                # Check if this is a reply to a document (for adding descriptions)
                if 'context' in message:
                    print("Processing document reply...")
                    return await self.document_processor.handle_document(from_number, None, message)
                # Handle regular text commands
                else:
                    print(f"Processing text message: {message.get('text', {}).get('body', '')}")
                    return await self.command_processor.handle_command(
                        from_number, 
                        message.get('text', {}).get('body', '')
                    )
            else:
                print(f"Unsupported message type: {message_type}")
                await self.send_message(
                    from_number, 
                    "Sorry, I don't understand this type of message. You can send me documents, "
                    "images, videos, audio files, or text commands."
                )
                raise WhatsAppHandlerError("Unsupported message type")

        except WhatsAppHandlerError:
            raise
        except Exception as e:
            logger.error(f"Error handling WhatsApp message: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Only try to send a message if we have a from_number
            if 'from_number' in locals() and from_number:
                await self.send_message(
                    from_number, 
                    "❌ Sorry, there was an error processing your request. Please try again later."
                )
            raise WhatsAppHandlerError(str(e))
            
    async def _handle_unauthorized_user(self, from_number):
        """
        Handle the case when a user is not authorized.
        
        Args:
            from_number: The user's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
        print("\n=== Starting OAuth Flow ===")
        auth_url = self.auth_handler.handle_authorization(from_number)
        print(f"Generated Auth URL: {auth_url}")

        if auth_url.startswith('http'):
            message = (
                "🔐 *Authorization Required*\n\n"
                "To use this bot and manage your documents, I need access to your Google Drive.\n\n"
                "Please click the link below to authorize:\n\n"
                f"{auth_url}\n\n"
                "After authorizing, you can start using the bot!"
            )
            print("\n=== Sending Auth Message ===")
            print(f"Message: {message}")
            
            send_result = await self.send_message(from_number, message)
            if not send_result:
                print("Failed to send authorization message - WhatsApp token may be invalid")
                return "WhatsApp token error", 500
            print(f"Successfully sent authorization URL to {from_number}")
        else:
            error_msg = "❌ Error getting authorization URL. Please try again later."
            await self.send_message(from_number, error_msg)
            print(f"Error with auth URL: {auth_url}")
        return "Authorization needed", 200

    # For backward compatibility - delegate to specialized components
    async def handle_document(self, from_number, document, message=None):
        """
        Handle an incoming document (backward compatibility method).
        
        Args:
            from_number: The sender's phone number
            document: The document data from WhatsApp
            message: The full message object (optional)
            
        Returns:
            tuple: (response_message, status_code)
        """
        return await self.document_processor.handle_document(from_number, document, message)
        
    async def handle_text_command(self, from_number, text):
        """
        Handle a text command (backward compatibility method).
        
        Args:
            from_number: The sender's phone number
            text: The command text
            
        Returns:
            tuple: (response_message, status_code)
        """
        return await self.command_processor.handle_command(from_number, text)

    def _is_duplicate_message(self, from_number, message_id, message_key):
        """
        Check if a message is a duplicate using the appropriate deduplication mechanism.
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            message_key: The combined key (from_number:message_id)
            
        Returns:
            bool: True if the message is a duplicate, False otherwise
        """
        # Use Redis if available
        if hasattr(self, 'redis_deduplication') and self.redis_deduplication:
            return self.redis_deduplication.is_duplicate_message(from_number, message_id)
        
        # Fall back to in-memory tracking
        is_duplicate = self._is_duplicate_by_global_tracking(message_key)
        
        # Also check the deduplication manager as a backup
        if not is_duplicate:
            is_duplicate = self.deduplication.is_duplicate_message(from_number, message_id)
            
        return is_duplicate
    
    def _mark_message_processed(self, from_number, message_id, message_key, timestamp):
        """
        Mark a message as processed using the appropriate deduplication mechanism.
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            message_key: The combined key (from_number:message_id)
            timestamp: The current timestamp
        """
        # Use Redis if available
        if hasattr(self, 'redis_deduplication') and self.redis_deduplication:
            # Redis tracking is handled in the is_duplicate_message method
            # which already marks the message as processed if it's not a duplicate
            pass
        else:
            # Fall back to in-memory tracking
            self._update_global_tracking(message_key, timestamp)

    def _is_duplicate_by_global_tracking(self, message_key):
        """
        Check if a message has already been processed using global tracking.
        
        Args:
            message_key: The message key (from_number:message_id)
            
        Returns:
            bool: True if this message has already been processed
        """
        return message_key in GLOBAL_MESSAGE_TRACKING
        
    def _update_global_tracking(self, message_key, timestamp):
        """
        Update global tracking for a message.
        
        Args:
            message_key: The message key (from_number:message_id)
            timestamp: The timestamp when the message was processed
        """
        GLOBAL_MESSAGE_TRACKING[message_key] = timestamp
        
        # Log the update
        logger.info(f"Updated global tracking for message: {message_key}")
        
    def _cleanup_global_tracking(self):
        """Clean up old global tracking entries to prevent memory leaks."""
        # Skip if using Redis (Redis handles expiration automatically)
        if hasattr(self, 'redis_deduplication') and self.redis_deduplication:
            return
            
        global GLOBAL_MESSAGE_TRACKING
        
        current_time = int(time.time())
        cutoff_time = current_time - 600  # 10 minutes
        
        # Count before cleanup
        count_before = len(GLOBAL_MESSAGE_TRACKING)
        
        # Remove old entries
        GLOBAL_MESSAGE_TRACKING = {
            k: v for k, v in GLOBAL_MESSAGE_TRACKING.items()
            if v > cutoff_time
        }
        
        # Count after cleanup
        count_after = len(GLOBAL_MESSAGE_TRACKING)
        
        if count_before != count_after:
            logger.info(f"Cleaned up global message tracking. Before: {count_before}, After: {count_after}")
    
    def _get_deduplication(self):
        """
        Get the appropriate deduplication manager.
        
        Returns:
            The Redis deduplication manager if available, otherwise the in-memory one
        """
        if hasattr(self, 'redis_deduplication') and self.redis_deduplication:
            return self.redis_deduplication
        return self.deduplication 