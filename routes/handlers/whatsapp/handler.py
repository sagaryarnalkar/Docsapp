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
from .document_processor import WhatsAppDocumentProcessor, WhatsAppHandlerError
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
        
        # Initialize auth handler
        from routes.handlers.auth_handler import AuthHandler
        self.auth_handler = AuthHandler(user_state)
        
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
        self.document_processor = WhatsAppDocumentProcessor(docs_app, self.message_sender, self.deduplication)
        
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

    async def send_message(self, to_number, message, message_type="outgoing_message"):
        """
        Send a WhatsApp message to a user.
        
        Args:
            to_number: The recipient's phone number
            message: The message text to send
            message_type: Type of message (default: "outgoing_message")
            
        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # Delegate to the message sender component
        return await self.message_sender.send_message(to_number, message, message_type=message_type)

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
            if self._is_duplicate_message(from_number, message_id, message_key, message.get('type')):
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

    def _is_duplicate_message(self, from_number, message_id, message_key, message_type=None):
        """
        Check if a message is a duplicate.
        
        Args:
            from_number: The sender's phone number
            message_id: The WhatsApp message ID
            message_key: A unique key for this message
            message_type: Optional type of message (e.g., "list_command")
            
        Returns:
            bool: True if the message is a duplicate, False otherwise
        """
        try:
            # TEMPORARY FIX: Disable deduplication for ALL messages
            print(f"[DEBUG] TEMPORARY FIX: DEDUPLICATION DISABLED FOR ALL MESSAGES IN HANDLER")
            return False
            
            # The code below is temporarily disabled
            """
            # Get the deduplication manager
            dedup = self._get_deduplication()
            
            # Check if this is a duplicate message
            is_duplicate = dedup.is_duplicate_message(from_number, message_id, message_type)
            
            # Debug logging
            if is_duplicate:
                print(f"[DEBUG] Message {message_id} from {from_number} is a duplicate")
            else:
                print(f"[DEBUG] Message {message_id} from {from_number} is new")
                
            return is_duplicate
            """
        except Exception as e:
            logger.error(f"Error checking for duplicate message: {str(e)}")
            # In case of error, assume it's not a duplicate to ensure processing
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
        # SUPER EMERGENCY ERROR CAPTURE - Write errors to a file
        import os
        error_log_path = os.path.join(os.getcwd(), 'whatsapp_error.log')
        
        def write_emergency_log(message):
            """Write a message to the emergency log file"""
            try:
                with open(error_log_path, 'a') as f:
                    f.write(f"{time.time()}: {message}\n")
            except Exception as log_err:
                print(f"Failed to write to emergency log: {str(log_err)}")
        
        write_emergency_log(f"STARTING _process_text_command_async with {from_number}, message: {message_text}")
        
        # EXTREME EMERGENCY TEST - Try sending a message directly from the handler, before the command processor
        try:
            # Only do this for List command
            if message_text.strip().lower() == 'list':
                print(f"🚨🚨🚨 DIRECT HANDLER MESSAGE ATTEMPT - BYPASSING COMMAND PROCESSOR 🚨🚨🚨")
                write_emergency_log(f"DIRECT HANDLER MESSAGE ATTEMPT - BYPASSING COMMAND PROCESSOR")
                
                # Send a message that's as simple as possible
                timestamp = int(time.time())
                direct_message = f"Direct message from handler (bypasses command processor): {timestamp}"
                
                # Try direct send
                try:
                    send_result = await self.message_sender.send_message(
                        from_number,
                        direct_message,
                        message_type="handler_direct_test",
                        bypass_deduplication=True
                    )
                    print(f"🚨🚨🚨 DIRECT MESSAGE ATTEMPT RESULT: {send_result} 🚨🚨🚨")
                    write_emergency_log(f"DIRECT MESSAGE RESULT: {send_result}")
                except Exception as direct_err:
                    err_text = f"Direct message error: {str(direct_err)}"
                    print(f"🚨🚨🚨 {err_text} 🚨🚨🚨")
                    write_emergency_log(err_text)
                    write_emergency_log(f"TRACE: {traceback.format_exc()}")
        except Exception as extreme_err:
            print(f"🚨🚨🚨 EXTREME EMERGENCY TEST FAILED: {str(extreme_err)} 🚨🚨🚨")
            write_emergency_log(f"EXTREME TEST FAILED: {str(extreme_err)}\n{traceback.format_exc()}")
        
        try:
            # Generate a unique ID for this command processing
            command_id = f"{int(time.time())}-{hash(message_text) % 10000:04d}"
            print(f"\n🔍🔍🔍 LATEST DEBUG - ASYNC COMMAND PROCESSING: {command_id} 🔍🔍🔍")
            print(f"🔹 [LATEST-DEBUG] Processing text command asynchronously - ID: {command_id}")
            print(f"🔹 [LATEST-DEBUG] From: {from_number}")
            print(f"🔹 [LATEST-DEBUG] Text: '{message_text}'")
            print(f"🔹 [LATEST-DEBUG] Is 'List' command: {message_text.strip().lower() == 'list'}")
            print(f"🔹 [LATEST-DEBUG] Command processor: {self.command_processor}")
            print(f"🔹 [LATEST-DEBUG] Command processor type: {type(self.command_processor)}")
            print(f"🔹 [LATEST-DEBUG] Command processor methods: {dir(self.command_processor)}")
            
            # Check docs_app
            print(f"🔹 [LATEST-DEBUG] docs_app: {self.docs_app}")
            print(f"🔹 [LATEST-DEBUG] docs_app type: {type(self.docs_app)}")
            if self.docs_app:
                try:
                    print(f"🔹 [LATEST-DEBUG] docs_app methods: {dir(self.docs_app)}")
                    print(f"🔹 [LATEST-DEBUG] Has list_documents: {'list_documents' in dir(self.docs_app)}")
                    print(f"🔹 [LATEST-DEBUG] Has get_user_documents: {'get_user_documents' in dir(self.docs_app)}")
                except Exception as docs_err:
                    print(f"🔹 [LATEST-DEBUG] Error inspecting docs_app: {str(docs_err)}")
            else:
                print(f"🔹 [LATEST-DEBUG] WARNING: docs_app is None!")
            
            # Add a small delay to ensure the 200 response has been sent back to WhatsApp
            # This helps prevent race conditions where the response is sent before the 200 acknowledgment
            await asyncio.sleep(0.5)

            # 🚨🚨🚨 EMERGENCY DIRECT HANDLING FOR LIST COMMAND 🚨🚨🚨
            is_list_command = message_text.strip().lower() == 'list'
            if is_list_command:
                write_emergency_log("Entering emergency List command handler")
                print(f"🔹 [LATEST-DEBUG] ⚠️ EMERGENCY DIRECT HANDLING FOR LIST COMMAND ⚠️")
                try:
                    # Get WhatsApp API credentials from the message_sender
                    write_emergency_log("Getting API credentials")
                    try:
                        phone_number_id = self.message_sender.phone_number_id
                        access_token = self.message_sender.access_token
                        api_version = self.message_sender.api_version
                        
                        write_emergency_log(f"Got credentials: API v{api_version}, Phone ID: {phone_number_id}, Token length: {len(access_token) if access_token else 'None'}")
                        print(f"🔹 [LATEST-DEBUG] API credentials - Version: {api_version}, Phone ID: {phone_number_id}")
                        print(f"🔹 [LATEST-DEBUG] Token length: {len(access_token) if access_token else 'None'}")
                    except Exception as cred_err:
                        error_msg = f"Error getting API credentials: {str(cred_err)}"
                        write_emergency_log(error_msg)
                        print(f"🔹 [LATEST-DEBUG] {error_msg}")
                        import traceback
                        write_emergency_log(f"Credential error traceback: {traceback.format_exc()}")
                    
                    # Try to send a direct message first - bypass all message_sender logic
                    try:
                        write_emergency_log("Attempting super direct message")
                        print(f"🔹 [LATEST-DEBUG] SUPER DIRECT MESSAGE - List Command detected")
                        
                        # Direct API call with minimal dependencies
                        import aiohttp
                        import json
                        
                        api_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
                        headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }
                        
                        # Make message unique with timestamp
                        timestamp = int(time.time())
                        direct_debug_msg = f"🧪 SUPER DIRECT: Detected 'List' command at {timestamp}"
                        
                        payload = {
                            "messaging_product": "whatsapp",
                            "recipient_type": "individual",
                            "to": from_number,
                            "type": "text",
                            "text": {"body": direct_debug_msg}
                        }
                        
                        write_emergency_log(f"Sending API request to {api_url}")
                        write_emergency_log(f"Payload: {json.dumps(payload)}")
                        
                        async with aiohttp.ClientSession() as session:
                            print(f"🔹 [LATEST-DEBUG] Sending direct WhatsApp API request")
                            print(f"🔹 [LATEST-DEBUG] API URL: {api_url}")
                            print(f"🔹 [LATEST-DEBUG] Payload: {json.dumps(payload)}")
                            print(f"🔹 [LATEST-DEBUG] Headers: Authorization: Bearer {access_token[:5]}...{access_token[-5:] if len(access_token) > 10 else '***'}")
                            
                            try:
                                async with session.post(api_url, json=payload, headers=headers) as response:
                                    status = response.status
                                    resp_text = await response.text()
                                    write_emergency_log(f"API response status: {status}, response: {resp_text}")
                                    print(f"🔹 [LATEST-DEBUG] Direct API response status: {status}")
                                    print(f"🔹 [LATEST-DEBUG] Direct API response: {resp_text}")
                            except Exception as req_err:
                                error_msg = f"Direct API request error: {str(req_err)}"
                                write_emergency_log(error_msg)
                                write_emergency_log(f"Request error traceback: {traceback.format_exc()}")
                                print(f"🔹 [LATEST-DEBUG] {error_msg}")
                    except Exception as super_direct_err:
                        error_msg = f"Super direct message failed: {str(super_direct_err)}"
                        write_emergency_log(error_msg)
                        write_emergency_log(f"Super direct traceback: {traceback.format_exc()}")
                        print(f"🔹 [LATEST-DEBUG] {error_msg}")
                        print(f"🔹 [LATEST-DEBUG] Traceback: {traceback.format_exc()}")
                    
                    # Now try to get documents directly
                    try:
                        write_emergency_log("Attempting to get documents directly")
                        print(f"🔹 [LATEST-DEBUG] Calling docs_app.get_user_documents directly (SYNC)")
                        
                        # IMPORTANT CHANGE: get_user_documents might need to be called synchronously
                        documents = None
                        error_msg = None
                        
                        write_emergency_log(f"docs_app: {self.docs_app}, type: {type(self.docs_app) if self.docs_app else 'None'}")
                        if hasattr(self.docs_app, 'get_user_documents'):
                            write_emergency_log("docs_app has get_user_documents method")
                        else:
                            write_emergency_log("ERROR: docs_app does not have get_user_documents method")
                            
                        try:
                            # Try synchronous call first
                            write_emergency_log(f"Attempting synchronous get_user_documents({from_number})")
                            documents = self.docs_app.get_user_documents(from_number)
                            write_emergency_log("Sync call succeeded")
                            print(f"🔹 [LATEST-DEBUG] Sync call succeeded")
                        except AttributeError as attr_err:
                            error_msg = f"AttributeError in sync call: {str(attr_err)}"
                            write_emergency_log(error_msg)
                            write_emergency_log(f"AttributeError traceback: {traceback.format_exc()}")
                            print(f"🔹 [LATEST-DEBUG] {error_msg}")
                        except TypeError as type_err:
                            error_msg = f"TypeError in sync call: {str(type_err)}"
                            write_emergency_log(error_msg)
                            write_emergency_log(f"TypeError traceback: {traceback.format_exc()}")
                            print(f"🔹 [LATEST-DEBUG] {error_msg}")
                        except Exception as sync_err:
                            error_msg = f"Sync get_user_documents failed: {str(sync_err)}"
                            write_emergency_log(error_msg)
                            write_emergency_log(f"Sync error traceback: {traceback.format_exc()}")
                            print(f"🔹 [LATEST-DEBUG] {error_msg}")
                            print(f"🔹 [LATEST-DEBUG] Trying async call...")
                            error_msg = f"SyncError: {str(sync_err)}"
                            
                            # Fallback to async call
                            try:
                                write_emergency_log(f"Attempting async get_user_documents({from_number})")
                                
                                # Special handling for possibly coroutine functions
                                try:
                                    result = self.docs_app.get_user_documents(from_number)
                                    if asyncio.iscoroutine(result):
                                        write_emergency_log("Result is a coroutine, awaiting it")
                                        documents = await result
                                    else:
                                        write_emergency_log("Result is not a coroutine")
                                        documents = result
                                except Exception as special_err:
                                    write_emergency_log(f"Special coroutine handling failed: {str(special_err)}")
                                    write_emergency_log(f"Special error traceback: {traceback.format_exc()}")
                                    
                                    # Try standard await
                                    write_emergency_log("Falling back to standard await")
                                    documents = await self.docs_app.get_user_documents(from_number)
                                
                                write_emergency_log("Async call succeeded")
                                print(f"🔹 [LATEST-DEBUG] Async call succeeded")
                                error_msg = None  # Clear error message on success
                            except Exception as async_err:
                                error_msg = f"Async get_user_documents also failed: {str(async_err)}"
                                write_emergency_log(error_msg)
                                write_emergency_log(f"Async error traceback: {traceback.format_exc()}")
                                print(f"🔹 [LATEST-DEBUG] {error_msg}")
                                print(f"🔹 [LATEST-DEBUG] Traceback: {traceback.format_exc()}")
                                error_msg = f"AsyncError: {str(async_err)}"
                        
                        # If we couldn't get documents at all, send error message
                        if documents is None:
                            write_emergency_log(f"Failed to get documents: {error_msg}")
                            print(f"🔹 [LATEST-DEBUG] Failed to get documents: {error_msg}")
                            docs_error_msg = f"🧪 DEBUG: Failed to get documents. Error: {error_msg if error_msg else 'Unknown'}"
                            
                            # Try direct message
                            try:
                                write_emergency_log(f"Sending error message: {docs_error_msg}")
                                await self.message_sender.send_message(
                                    from_number,
                                    docs_error_msg,
                                    message_type="list_error_debug",
                                    bypass_deduplication=True
                                )
                            except Exception as err_msg_err:
                                error_msg = f"Failed to send error message: {str(err_msg_err)}"
                                write_emergency_log(error_msg)
                                write_emergency_log(f"Error message error traceback: {traceback.format_exc()}")
                                print(f"🔹 [LATEST-DEBUG] {error_msg}")
                        else:
                            doc_count = len(documents) if documents else 0
                            write_emergency_log(f"Got {doc_count} documents directly: {documents}")
                            print(f"🔹 [LATEST-DEBUG] Got {doc_count} documents directly: {documents}")
                            
                            message = f"📄 *Your Documents (Emergency Mode):*\n\n"
                            if documents and doc_count > 0:
                                for i, doc in enumerate(documents, 1):
                                    try:
                                        doc_name = doc.get('name', 'Unnamed Document')
                                        doc_type = doc.get('type', 'Unknown Type')
                                        doc_id = doc.get('id', 'unknown')
                                        message += f"{i}. *{doc_name}*\n   Type: {doc_type}\n   ID: {doc_id}\n\n"
                                    except Exception as format_err:
                                        error_msg = f"Error formatting document {i}: {str(format_err)}"
                                        write_emergency_log(error_msg)
                                        print(f"🔹 [LATEST-DEBUG] {error_msg}")
                                        message += f"{i}. Error formatting document\n\n"
                            else:
                                message = "📂 You don't have any documents stored yet. Send a document to store it."
                            
                            # Add timestamp to prevent deduplication
                            timestamp = int(time.time())
                            message += f"\n\n_Emergency List generated at: {timestamp}_"
                            
                            # Send through message_sender (more reliable than direct API)
                            try:
                                write_emergency_log(f"Sending document list through message_sender: {message[:100]}...")
                                print(f"🔹 [LATEST-DEBUG] Sending message through message_sender")
                                send_result = await self.message_sender.send_message(
                                    from_number,
                                    message,
                                    message_type="list_emergency_result",
                                    bypass_deduplication=True
                                )
                                write_emergency_log(f"Message sent result: {send_result}")
                                print(f"🔹 [LATEST-DEBUG] Message sent result: {send_result}")
                            except Exception as send_err:
                                error_msg = f"Error sending through message_sender: {str(send_err)}"
                                write_emergency_log(error_msg)
                                write_emergency_log(f"Message send error traceback: {traceback.format_exc()}")
                                print(f"🔹 [LATEST-DEBUG] {error_msg}")
                                print(f"🔹 [LATEST-DEBUG] Traceback: {traceback.format_exc()}")
                                
                                # Try fallback direct API call
                                try:
                                    write_emergency_log("Attempting fallback direct API call")
                                    api_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
                                    headers = {
                                        "Authorization": f"Bearer {access_token}",
                                        "Content-Type": "application/json"
                                    }
                                    
                                    payload = {
                                        "messaging_product": "whatsapp",
                                        "recipient_type": "individual",
                                        "to": from_number,
                                        "type": "text",
                                        "text": {"body": message}
                                    }
                                    
                                    async with aiohttp.ClientSession() as session:
                                        write_emergency_log("Sending document list via direct API call")
                                        print(f"🔹 [LATEST-DEBUG] Sending document list via direct API call")
                                        async with session.post(api_url, json=payload, headers=headers) as response:
                                            status = response.status
                                            resp_text = await response.text()
                                            write_emergency_log(f"Document list API response status: {status}, response: {resp_text}")
                                            print(f"🔹 [LATEST-DEBUG] Document list API response status: {status}")
                                            print(f"🔹 [LATEST-DEBUG] Document list API response: {resp_text}")
                                except Exception as direct_api_err:
                                    error_msg = f"Document list API error: {str(direct_api_err)}"
                                    write_emergency_log(error_msg)
                                    write_emergency_log(f"Direct API error traceback: {traceback.format_exc()}")
                                    print(f"🔹 [LATEST-DEBUG] {error_msg}")
                                    print(f"🔹 [LATEST-DEBUG] Traceback: {traceback.format_exc()}")
                        
                        # Try to continue with normal command processing
                        write_emergency_log("Emergency handling completed, continuing with normal command processing")
                        print(f"🔹 [LATEST-DEBUG] Continuing with normal command processing...")
                    except Exception as direct_docs_err:
                        error_msg = f"Emergency document retrieval failed: {str(direct_docs_err)}"
                        write_emergency_log(error_msg)
                        write_emergency_log(f"Document retrieval error traceback: {traceback.format_exc()}")
                        print(f"🔹 [LATEST-DEBUG] {error_msg}")
                        print(f"🔹 [LATEST-DEBUG] Traceback: {traceback.format_exc()}")
                        
                        # Send error message
                        try:
                            error_msg = f"❌ Emergency handler couldn't retrieve your documents. Error: {str(direct_docs_err)[:50]}..."
                            timestamp = int(time.time())
                            error_msg += f"\n\nTimestamp: {timestamp}"
                            
                            write_emergency_log(f"Sending final error message: {error_msg}")
                            await self.message_sender.send_message(
                                from_number,
                                error_msg,
                                message_type="emergency_error",
                                bypass_deduplication=True
                            )
                        except Exception as error_send_err:
                            error_msg = f"Error message send failed: {str(error_send_err)}"
                            write_emergency_log(error_msg)
                            write_emergency_log(f"Error send traceback: {traceback.format_exc()}")
                            print(f"🔹 [LATEST-DEBUG] {error_msg}")
                except Exception as emergency_err:
                    error_msg = f"Emergency handler failed: {str(emergency_err)}"
                    write_emergency_log(error_msg)
                    write_emergency_log(f"Emergency handler traceback: {traceback.format_exc()}")
                    print(f"🔹 [LATEST-DEBUG] {error_msg}")
                    print(f"🔹 [LATEST-DEBUG] Traceback: {traceback.format_exc()}")
                    
                    # Last resort direct error
                    try:
                        super_error = f"🚨 CRITICAL ERROR in emergency handler: {str(emergency_err)[:100]}"
                        write_emergency_log(f"Sending super error: {super_error}")
                        await self.message_sender.send_message(
                            from_number,
                            super_error,
                            message_type="critical_error",
                            bypass_deduplication=True
                        )
                    except:
                        write_emergency_log("Failed to send critical error")
            
            try:
                write_emergency_log("Proceeding with normal command processor")
                print(f"🔹 [LATEST-DEBUG] Calling command_processor.handle_command({from_number}, {message_text})")
                result_future = self.command_processor.handle_command(from_number, message_text)
                if not asyncio.iscoroutine(result_future):
                    print(f"🔹 [LATEST-DEBUG] WARNING: handle_command did not return a coroutine object! Got {type(result_future)}")
                    result = result_future  # Not awaitable, just use the value
                else:
                    print(f"🔹 [LATEST-DEBUG] Awaiting coroutine result...")
                    result = await result_future
                
                print(f"🔹 [LATEST-DEBUG] handle_command completed with result: {result}")
                logger.info(f"Async text command processing completed: {result}")
            except Exception as cmd_err:
                print(f"🔹 [LATEST-DEBUG] Error calling command_processor.handle_command: {str(cmd_err)}")
                print(f"🔹 [LATEST-DEBUG] Error traceback: {traceback.format_exc()}")
                result = (f"Error: {str(cmd_err)}", 500)
            
            # If the command processing returned a failure status code, try to send a direct message
            if isinstance(result, tuple) and len(result) > 1 and result[1] >= 400:
                print(f"🔹 [LATEST-DEBUG] Command {command_id} failed with status {result[1]}, sending direct error message")
                error_msg = f"❌ Sorry, there was an issue processing your command. Please try again. (ID: {command_id})"
                
                # Try all available message sending methods
                try:
                    # First attempt - regular message_sender
                    print(f"🔹 [LATEST-DEBUG] Sending error message via message_sender.send_message")
                    send_result = await self.message_sender.send_message(
                        from_number,
                        error_msg,
                        message_type="command_error",
                        bypass_deduplication=True
                    )
                    
                    if not send_result:
                        print(f"🔹 [LATEST-DEBUG] Regular send_message failed, trying send_direct_message")
                        # Second attempt - direct message
                        try:
                            send_result = await self.message_sender.send_direct_message(
                                from_number,
                                error_msg,
                                message_type="direct_error"
                            )
                            print(f"🔹 [LATEST-DEBUG] Direct message result: {send_result}")
                        except Exception as direct_err:
                            print(f"🔹 [LATEST-DEBUG] Direct message error: {str(direct_err)}")
                except Exception as send_err:
                    print(f"🔹 [LATEST-DEBUG] Error sending error message: {str(send_err)}")
        except Exception as e:
            error_msg = f"Error in async text command processing: {str(e)}"
            write_emergency_log(error_msg)
            import traceback
            error_trace = traceback.format_exc()
            write_emergency_log(f"Final error traceback: {error_trace}")
            logger.error(error_msg)
            logger.error(f"Traceback: {error_trace}")
            print(f"🔹 [LATEST-DEBUG] Command processing error: {str(e)}")
            print(f"🔹 [LATEST-DEBUG] Traceback: {error_trace}")
            
            # Generate a unique error ID
            error_id = f"{int(time.time())}-{hash(str(e)) % 10000:04d}"
            
            # Send error message to user with multiple attempts
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    error_msg = f"❌ Sorry, I couldn't process your command due to an error. Please try again later. (Error ID: {error_id})"
                    if attempt > 0:
                        error_msg += f" (Retry {attempt+1}/{max_retries})"
                    
                    # Try both regular and direct message sending
                    send_result = False
                    
                    # First attempt - regular message sender
                    try:
                        send_result = await self.message_sender.send_message(
                            from_number,
                            error_msg,
                            message_type="command_error",
                            bypass_deduplication=True
                        )
                    except Exception as reg_err:
                        print(f"🔹 [LATEST-DEBUG] Regular send failed: {str(reg_err)}")
                    
                    # If regular send failed, try direct message
                    if not send_result:
                        try:
                            send_result = await self.message_sender.send_direct_message(
                                from_number,
                                error_msg,
                                message_type="direct_error"
                            )
                        except Exception as direct_err:
                            print(f"🔹 [LATEST-DEBUG] Direct send failed: {str(direct_err)}")
                    
                    if send_result:
                        print(f"🔹 [LATEST-DEBUG] Successfully sent error message on attempt {attempt+1}")
                        break
                    else:
                        print(f"🔹 [LATEST-DEBUG] Failed to send error message on attempt {attempt+1}, retrying...")
                        await asyncio.sleep(1)  # Wait before retrying
                except Exception as send_err:
                    logger.error(f"Error sending error message (attempt {attempt+1}): {str(send_err)}")
                    print(f"🔹 [LATEST-DEBUG] Failed to send error message: {str(send_err)}")
                    await asyncio.sleep(1)  # Wait before retrying 