"""
Ask Command Handler
----------------
This module handles the '/ask' command for WhatsApp users.
"""

import logging
from .base_command import BaseCommandHandler

logger = logging.getLogger(__name__)

class AskCommandHandler(BaseCommandHandler):
    """
    Handles the '/ask' command for WhatsApp users.
    
    This class is responsible for:
    1. Processing questions about documents
    2. Retrieving answers from the docs_app
    3. Formatting and sending the answers to the user
    """
    
    async def handle(self, from_number, question):
        """
        Handle the '/ask' command.
        
        Args:
            from_number: The sender's phone number
            question: The question to ask
            
        Returns:
            tuple: (response_message, status_code)
        """
        logger.info(f"[DEBUG] Processing ask command for {from_number} with question: '{question}'")
        command_id = self.generate_command_id("ask", from_number, question)
        print(f"[DEBUG] Ask command ID: {command_id}")
        
        try:
            # Send an acknowledgment message first
            ack_message = f"🔍 Processing your question: '{question}'\n\nThis may take a moment..."
            ack_message = self.add_unique_identifier(ack_message, "ask_ack", command_id)
            
            await self.send_response(
                from_number,
                ack_message,
                "ask_command_ack",
                command_id
            )
            
            # Process the question
            logger.info(f"[DEBUG] Calling docs_app.ask_question for {from_number}")
            result = await self.docs_app.ask_question(from_number, question)
            logger.info(f"[DEBUG] docs_app.ask_question returned: {result}")
            
            if result and result.get('status') == 'success':
                message = result.get('message', 'Here is your answer:')
                
                # Format answers if available
                if 'answers' in result and result['answers']:
                    answers = result['answers']
                    message_parts = [message, ""]
                    
                    for i, answer in enumerate(answers, 1):
                        doc_name = answer.get('document', 'Unknown document')
                        answer_text = answer.get('answer', 'No answer found')
                        message_parts.append(f"📄 *Document {i}: {doc_name}*")
                        message_parts.append(answer_text)
                        message_parts.append("")
                    
                    message = "\n".join(message_parts)
                
                logger.info(f"[DEBUG] Generated answer for question '{question}'")
                logger.info(f"[DEBUG] Answer preview: {message[:100]}...")
            else:
                error = result.get('error', 'Unknown error') if result else 'Failed to process question'
                message = f"❌ Sorry, I couldn't answer your question: {error}"
                logger.info(f"[DEBUG] Failed to answer question '{question}': {error}")
            
            # Add a unique identifier to prevent deduplication
            message = self.add_unique_identifier(message, "ask", command_id)
            
            # Send the answer
            send_result = await self.send_response(
                from_number,
                message,
                "ask_command",
                command_id
            )
            
            return "Ask command processed", 200
        except Exception as e:
            error_message = self.handle_exception(e, command_id)
            
            try:
                await self.send_error_message(
                    from_number,
                    f"❌ Error processing your question. Please try again. (Error ID: {command_id})",
                    command_id
                )
            except Exception as send_err:
                print(f"[DEBUG] {command_id} - Error sending error message: {str(send_err)}")
            
            return "Ask command error", 500 