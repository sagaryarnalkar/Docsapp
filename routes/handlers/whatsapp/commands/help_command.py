"""
Help Command Handler
-----------------
This module handles the 'help' command for WhatsApp users.
"""

import logging
from .base_command import BaseCommandHandler

logger = logging.getLogger(__name__)

class HelpCommandHandler(BaseCommandHandler):
    """
    Handles the 'help' command for WhatsApp users.
    
    This class is responsible for:
    1. Generating a help message with available commands
    2. Sending the help message to the user
    """
    
    async def handle(self, from_number):
        """
        Handle the 'help' command.
        
        Args:
            from_number: The sender's phone number
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing help command for {from_number}")
        command_id = self.generate_command_id("help", from_number)
        print(f"[DEBUG] Help command ID: {command_id}")
        
        try:
            # Create help message
            message = (
                "📱 *DocsApp WhatsApp Bot Help*\n\n"
                "Here are the commands you can use:\n\n"
                "• *help* - Show this help message\n"
                "• *list* - List all your documents\n"
                "• *find [query]* - Search for documents containing [query]\n"
                "• */ask [question]* - Ask a question about your documents\n\n"
                "You can also send me documents, images, or PDFs to store them."
            )
            
            # Add a unique identifier to prevent deduplication
            message = self.add_unique_identifier(message, "help", command_id)
            
            # Send the help message
            send_result = await self.send_response(
                from_number,
                message,
                "help_command",
                command_id
            )
            
            return "Help command processed", 200
        except Exception as e:
            error_message = self.handle_exception(e, command_id)
            
            try:
                await self.send_error_message(from_number, error_message, command_id)
            except Exception as send_err:
                print(f"[DEBUG] {command_id} - Error sending error message: {str(send_err)}")
            
            return "Help command error", 500 