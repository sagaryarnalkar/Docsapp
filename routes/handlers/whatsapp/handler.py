"""
WhatsApp Handler - Main Coordinator
----------------------------------
This module contains the main WhatsAppHandler class that coordinates all WhatsApp
interactions. It delegates specific tasks to specialized modules.
"""

import json
import logging
import time
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
        self.deduplication = DeduplicationManager()
        self.document_processor = DocumentProcessor(
            self.docs_app, 
            self.message_sender,
            self.deduplication
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
            
            # Check for duplicate message processing
            if self.deduplication.is_duplicate_message(from_number, message_id):
                return "Duplicate message processing prevented", 200
            
            print(f"\n=== Message Details ===")
            print(f"From: {from_number}")

            # Check authentication status first for any message
            is_authorized = self.user_state.is_authorized(from_number)
            print(f"User authorization status: {is_authorized}")

            # Handle authentication if user is not authorized
            if not is_authorized:
                return await self._handle_unauthorized_user(from_number)

            # Process the message based on its type
            message_type = message.get('type')

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