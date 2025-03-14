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
        
        # Initialize message sender
        api_version = os.environ.get('WHATSAPP_API_VERSION', 'v17.0')
        phone_number_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
        access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN')
        
        if not phone_number_id or not access_token:
            logger.error("Missing WhatsApp API credentials")
            print("❌ Missing WhatsApp API credentials")
            
        self.message_sender = MessageSender(api_version, phone_number_id, access_token)
        
        # Try to use Redis deduplication if available
        try:
            from .redis_deduplication import RedisDeduplicationManager
            redis_url = os.environ.get('REDIS_URL')
            if redis_url:
                self.deduplication = RedisDeduplicationManager(redis_url)
                logger.info("✅ Using Redis for message deduplication")
                print("✅ Using Redis for message deduplication")
            else:
                # Fall back to in-memory deduplication
                from .deduplication import DeduplicationManager
                self.deduplication = DeduplicationManager()
                logger.info("⚠️ Using in-memory message deduplication (Redis URL not found)")
                print("⚠️ Using in-memory message deduplication (Redis URL not found)")
        except Exception as e:
            # Fall back to in-memory deduplication on error
            from .deduplication import DeduplicationManager
            self.deduplication = DeduplicationManager()
            logger.error(f"❌ Error initializing Redis deduplication, falling back to in-memory: {str(e)}")
            print(f"❌ Error initializing Redis deduplication, falling back to in-memory: {str(e)}")
        
        # Initialize command processor with message sender
        self.command_processor = CommandProcessor(docs_app, self.message_sender)
        
        # Initialize document processor with message sender and deduplication
        self.document_processor = DocumentProcessor(docs_app, self.message_sender, self.deduplication)
        
        # Check if RAG processor is available
        self.rag_processor = docs_app.rag_processor if docs_app else None
        self.rag_available = (
            self.rag_processor is not None and 
            hasattr(self.rag_processor, 'is_available') and 
            self.rag_processor.is_available
        )
        
        # In-memory tracking for global deduplication (will be replaced by Redis)
        self.processed_messages = {}
        self.last_cleanup = time.time()

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
                
            # Mark the message as read to update read receipts
            await self.message_sender.mark_message_as_read(message_id)
            
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
                
                # IMPORTANT: Start document processing in the background
                # This allows us to return a 200 response to WhatsApp immediately
                asyncio.create_task(self._process_document_async(from_number, media_obj, message))
                return f"{message_type} received and processing started", 200
                
            # Handle text messages and document replies
            elif message_type == 'text':
                # Get the message text
                message_text = message.get('text', {}).get('body', '').strip()
                
                # Filter out system messages like "Fetch update"
                system_messages = ["fetch update", "sync", "refresh", "update", "status"]
                if message_text.lower() in system_messages:
                    print(f"Ignoring system message: '{message_text}'")
                    return "System message ignored", 200
                    
                # Check if this is a reply to a document (for adding descriptions)
                if 'context' in message:
                    print("Processing document reply...")
                    # IMPORTANT: Process document reply in the background
                    asyncio.create_task(self._process_document_reply_async(from_number, message))
                    return "Document reply received and processing started", 200
                # Handle regular text commands
                else:
                    print(f"Processing text message: {message_text}")
                    # IMPORTANT: Process text command in the background
                    asyncio.create_task(self._process_text_command_async(from_number, message_text))
                    return "Text command received and processing started", 200
            else:
                print(f"Unsupported message type: {message_type}")
                await self.message_sender.send_message(
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
                await self.message_sender.send_message(
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
                "🌟 *Welcome to Docverse!* 🌟\n\n"
                "Hey there! You've just stepped into your personal document universe. To get started, we'll send you a sign-in link to connect your Google Drive—then send us a ton of your documents, and we'll store them securely in your Google Drive (not with us!).\n\n"
                "Upload anytime, retrieve with ease, or ask any complex questions with our AI-powered search (we've got it covered!). For example, ask \"What's my passport number and address?\" and we'll fetch it from your passport document in a snap.\n\n"
                "Ready to revolutionize your file management? Click the link below:\n\n"
                f"{auth_url}\n\n"
                "After connecting, you can start sending documents right away!"
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
        Check if a message is a duplicate using the deduplication manager
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            message_key: A unique key for the message (usually message_id + timestamp)
            
        Returns:
            bool: True if the message is a duplicate, False otherwise
        """
        # First check using the deduplication manager
        if self.deduplication.is_duplicate_message(from_number, message_key):
            logger.info(f"Skipping duplicate message from {from_number}: {message_key}")
            return True
            
        # Mark the message as processed
        self._mark_message_processed(from_number, message_id, message_key, int(time.time()))
        return False
    
    def _mark_message_processed(self, from_number, message_id, message_key, timestamp):
        """
        Mark a message as processed in the deduplication manager
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            message_key: A unique key for the message
            timestamp: The timestamp when the message was processed
        """
        # Mark the message as processed in the deduplication manager
        try:
            # Track the message in the deduplication system
            self.deduplication.track_message_type(message_key, "text", from_number)
            logger.debug(f"Marked message as processed: {message_key}")
        except Exception as e:
            logger.error(f"Error marking message as processed: {str(e)}")
            
        # Also update the global tracking as a backup
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
        
    async def _process_document_async(self, from_number, media_obj, message):
        """
        Process a document asynchronously after acknowledging receipt
        
        Args:
            from_number: The sender's phone number
            media_obj: The media object from WhatsApp
            message: The full message object
        """
        try:
            result = await self.document_processor.handle_document(from_number, media_obj, message)
            logger.info(f"Async document processing completed: {result}")
        except Exception as e:
            logger.error(f"Error in async document processing: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Send error message to user
            try:
                await self.message_sender.send_message(
                    from_number, 
                    "❌ Sorry, I couldn't process your document. Please try again later."
                )
            except Exception as send_err:
                logger.error(f"Error sending error message: {str(send_err)}")
                
    async def _process_document_reply_async(self, from_number, message):
        """
        Process a document reply asynchronously after acknowledging receipt
        
        Args:
            from_number: The sender's phone number
            message: The message object
        """
        try:
            result = await self.document_processor.handle_document(from_number, None, message)
            logger.info(f"Async document reply processing completed: {result}")
        except Exception as e:
            logger.error(f"Error in async document reply processing: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Send error message to user
            try:
                await self.message_sender.send_message(
                    from_number, 
                    "❌ Sorry, I couldn't process your reply. Please try again later."
                )
            except Exception as send_err:
                logger.error(f"Error sending error message: {str(send_err)}")
                
    async def _process_text_command_async(self, from_number, message_text):
        """
        Process a text command asynchronously after acknowledging receipt
        
        Args:
            from_number: The sender's phone number
            message_text: The message text
        """
        try:
            result = await self.command_processor.handle_command(from_number, message_text)
            logger.info(f"Async text command processing completed: {result}")
        except Exception as e:
            logger.error(f"Error in async text command processing: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Send error message to user
            try:
                await self.message_sender.send_message(
                    from_number, 
                    "❌ Sorry, I couldn't process your command. Please try again later."
                )
            except Exception as send_err:
                logger.error(f"Error sending error message: {str(send_err)}") 