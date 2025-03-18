"""
List Command Handler
-----------------
This module handles the 'list' command for WhatsApp users.
"""

import logging
import traceback
import time
from .base_command import BaseCommandHandler

logger = logging.getLogger(__name__)

class ListCommandHandler(BaseCommandHandler):
    """
    Handles the 'list' command for WhatsApp users.
    
    This class is responsible for:
    1. Retrieving the user's documents from the docs_app
    2. Formatting the document list
    3. Sending the document list to the user
    """
    
    async def handle(self, from_number):
        """
        Handle the 'list' command.
        
        Args:
            from_number: The sender's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing list command for {from_number}")
        command_id = self.generate_command_id("list", from_number)
        print(f"[DEBUG] List command ID: {command_id}")
        print(f"[DEBUG] {command_id} - List handler docs_app: {self.docs_app}")
        print(f"[DEBUG] {command_id} - List handler message_sender: {self.message_sender}")
        print(f"[DEBUG] {command_id} - Message sender type: {type(self.message_sender)}")
        
        try:
            # Get documents from docs_app
            logger.info(f"[DEBUG] Calling docs_app.list_documents for {from_number}")
            print(f"[DEBUG] {command_id} - Calling docs_app.list_documents for {from_number}")
            
            # Add extra logging for docs_app
            print(f"[DEBUG] {command_id} - DocsApp type: {type(self.docs_app)}")
            
            try:
                doc_list, file_ids = self.docs_app.list_documents(from_number)
                logger.info(f"[DEBUG] docs_app.list_documents returned {len(doc_list)} documents and {len(file_ids)} file IDs")
                print(f"[DEBUG] {command_id} - docs_app.list_documents returned {len(doc_list)} documents and {len(file_ids)} file IDs")
            except Exception as list_err:
                print(f"[DEBUG] {command_id} - Error in docs_app.list_documents: {str(list_err)}")
                print(f"[DEBUG] {command_id} - Traceback: {traceback.format_exc()}")
                # Provide empty lists as fallback
                doc_list, file_ids = [], []
            
            if doc_list:
                # Format document list
                message_parts = ["📚 Your Documents:\n"]
                
                # Add each document to the message
                for i, doc in enumerate(doc_list):
                    print(f"[DEBUG] {command_id} - Document {i}: {doc[:50]}...")
                    message_parts.append(doc)
                
                message = "\n".join(message_parts)
                logger.info(f"[DEBUG] Found {len(doc_list)} documents for {from_number}")
                logger.info(f"[DEBUG] Message preview: {message[:100]}...")
                print(f"[DEBUG] {command_id} - Found {len(doc_list)} documents for {from_number}")
                print(f"[DEBUG] {command_id} - Message preview: {message[:100]}...")
            else:
                message = "You don't have any documents yet. Send me a file to get started!"
                logger.info(f"[DEBUG] No documents found for {from_number}")
                print(f"[DEBUG] {command_id} - No documents found for {from_number}")
            
            # Add a unique timestamp
            timestamp = int(time.time())
            message += f"\n\nRequest Time: {timestamp}"
            
            # Add a unique identifier to prevent deduplication
            message = self.add_unique_identifier(message, "list", command_id)
            print(f"[DEBUG] {command_id} - Final message with identifier: {message[:100]}...")
            
            # Send the document list
            print(f"[DEBUG] {command_id} - Calling send_response")
            send_result = await self.send_response(
                from_number,
                message,
                "list_command",
                command_id
            )
            print(f"[DEBUG] {command_id} - send_response returned: {send_result}")
            
            # If sending failed, try an alternative approach
            if not send_result:
                print(f"[DEBUG] {command_id} - First attempt failed, trying alternative approach")
                # Try sending a simpler message
                alt_message = f"List command processed. You have {len(doc_list) if doc_list else 0} documents."
                alt_message = self.add_unique_identifier(alt_message, "list", f"{command_id}-retry")
                print(f"[DEBUG] {command_id} - Alternative message: {alt_message}")
                
                # Directly use the message_sender
                try:
                    direct_result = await self.message_sender.send_message(
                        from_number,
                        alt_message,
                        message_type="list_command_direct",
                        bypass_deduplication=True
                    )
                    print(f"[DEBUG] {command_id} - Direct message sender result: {direct_result}")
                    send_result = direct_result
                except Exception as direct_err:
                    print(f"[DEBUG] {command_id} - Error with direct message sending: {str(direct_err)}")
                    print(f"[DEBUG] {command_id} - Direct message traceback: {traceback.format_exc()}")
            
            print(f"[DEBUG] {command_id} - List command completed successfully")
            return "List command processed", 200
        except Exception as e:
            print(f"[DEBUG] {command_id} - List command failed with error: {str(e)}")
            print(f"[DEBUG] {command_id} - Traceback: {traceback.format_exc()}")
            
            try:
                print(f"[DEBUG] {command_id} - Sending error message")
                error_msg = f"❌ Error retrieving your documents. Please try again. (Error ID: {command_id})"
                await self.send_error_message(
                    from_number,
                    error_msg,
                    command_id
                )
                print(f"[DEBUG] {command_id} - Error message sent")
            except Exception as send_err:
                print(f"[DEBUG] {command_id} - Error sending error message: {str(send_err)}")
                print(f"[DEBUG] {command_id} - Error message traceback: {traceback.format_exc()}")
                
                # Try one last direct approach
                try:
                    last_chance_msg = f"Sorry, I encountered an issue with the list command. (Error ID: {command_id})"
                    await self.message_sender.send_message(
                        from_number,
                        last_chance_msg,
                        message_type="error_direct",
                        bypass_deduplication=True
                    )
                except Exception as last_err:
                    print(f"[DEBUG] {command_id} - Final error attempt failed: {str(last_err)}")
            
            return "List command error", 500 