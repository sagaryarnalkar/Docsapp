"""
List Command Handler
-----------------
This module handles the 'list' command for WhatsApp users.
"""

import logging
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
        
        try:
            # Get documents from docs_app
            logger.info(f"[DEBUG] Calling docs_app.list_documents for {from_number}")
            doc_list, file_ids = self.docs_app.list_documents(from_number)
            logger.info(f"[DEBUG] docs_app.list_documents returned {len(doc_list)} documents and {len(file_ids)} file IDs")
            
            if doc_list:
                # Format document list
                message_parts = ["📚 Your Documents:\n"]
                
                # Add each document to the message
                message_parts.extend(doc_list)
                
                message = "\n".join(message_parts)
                logger.info(f"[DEBUG] Found {len(doc_list)} documents for {from_number}")
                logger.info(f"[DEBUG] Message preview: {message[:100]}...")
            else:
                message = "You don't have any documents yet. Send me a file to get started!"
                logger.info(f"[DEBUG] No documents found for {from_number}")
            
            # Add a unique identifier to prevent deduplication
            message = self.add_unique_identifier(message, "list", command_id)
            
            # Send the document list
            send_result = await self.send_response(
                from_number,
                message,
                "list_command",
                command_id
            )
            
            # If sending failed, try an alternative approach
            if not send_result:
                print(f"[DEBUG] {command_id} - First attempt failed, trying alternative approach")
                # Try sending a simpler message
                alt_message = f"List command processed. You have {len(doc_list) if doc_list else 0} documents."
                alt_message = self.add_unique_identifier(alt_message, "list", f"{command_id}-retry")
                
                send_result = await self.send_response(
                    from_number,
                    alt_message,
                    "list_command_retry",
                    command_id
                )
                print(f"[DEBUG] {command_id} - Alternative message send result: {send_result}")
            
            return "List command processed", 200
        except Exception as e:
            error_message = self.handle_exception(e, command_id)
            
            try:
                await self.send_error_message(
                    from_number,
                    f"❌ Error retrieving your documents. Please try again. (Error ID: {command_id})",
                    command_id
                )
            except Exception as send_err:
                print(f"[DEBUG] {command_id} - Error sending error message: {str(send_err)}")
            
            return "List command error", 500 