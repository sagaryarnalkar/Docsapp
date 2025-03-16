"""
Find Command Handler
-----------------
This module handles the 'find' command for WhatsApp users.
"""

import logging
from .base_command import BaseCommandHandler

logger = logging.getLogger(__name__)

class FindCommandHandler(BaseCommandHandler):
    """
    Handles the 'find' command for WhatsApp users.
    
    This class is responsible for:
    1. Searching for documents matching a query
    2. Formatting the search results
    3. Sending the search results to the user
    """
    
    async def handle(self, from_number, query):
        """
        Handle the 'find' command.
        
        Args:
            from_number: The sender's phone number
            query: The search query
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing find command for {from_number} with query '{query}'")
        command_id = self.generate_command_id("find", from_number, query)
        print(f"[DEBUG] Find command ID: {command_id}")
        
        try:
            # Get documents from docs_app
            logger.info(f"[DEBUG] Calling docs_app.retrieve_document for {from_number} with query '{query}'")
            doc_list, file_ids = self.docs_app.retrieve_document(from_number, query)
            logger.info(f"[DEBUG] docs_app.retrieve_document returned {len(doc_list)} documents")
            
            if doc_list:
                # Format document list
                message_parts = [f"🔍 Search results for '{query}':\n"]
                
                # Add each document to the message
                message_parts.extend(doc_list)
                
                message = "\n".join(message_parts)
                logger.info(f"[DEBUG] Found {len(doc_list)} documents for query '{query}'")
                logger.info(f"[DEBUG] Message preview: {message[:100]}...")
            else:
                message = f"No documents found matching '{query}'. Try a different search term."
                logger.info(f"[DEBUG] No documents found for query '{query}'")
            
            # Add a unique identifier to prevent deduplication
            message = self.add_unique_identifier(message, "find", command_id)
            
            # Send the search results
            send_result = await self.send_response(
                from_number,
                message,
                "find_command",
                command_id
            )
            
            return "Find command processed", 200
        except Exception as e:
            error_message = self.handle_exception(e, command_id)
            
            try:
                await self.send_error_message(
                    from_number,
                    f"❌ Error searching for documents. Please try again. (Error ID: {command_id})",
                    command_id
                )
            except Exception as send_err:
                print(f"[DEBUG] {command_id} - Error sending error message: {str(send_err)}")
            
            return "Find command error", 500 