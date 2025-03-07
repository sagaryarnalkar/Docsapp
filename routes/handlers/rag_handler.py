import logging
from typing import Tuple, Dict, Optional
from models.rag_processor import RAGProcessor
from models.database import Session, Document
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS
import asyncio
from models.user_state import UserState

logger = logging.getLogger(__name__)

class RAGHandler:
    def __init__(self, docs_app):
        self.docs_app = docs_app
        # Use the RAG processor from docs_app instead of creating a new instance
        self.rag_processor = docs_app.rag_processor
        print(f"RAG Handler initialized with processor: {type(self.rag_processor)}")

    async def handle_question(self, from_number: str, question: str) -> Tuple[bool, str]:
        """
        Handle document questions with RAG, ensuring existing functionality is preserved
        Returns a tuple of (success, message)
        """
        try:
            # Check if RAG processor is available
            if self.rag_processor is None or not hasattr(self.rag_processor, 'is_available') or not self.rag_processor.is_available:
                print("❌ RAG processor not available in RAG handler")
                return False, "⚠️ Document Q&A feature is not available at the moment. Your other commands will still work normally!"

            # Use docs_app to process the question
            result = await self.docs_app.ask_question(from_number, question)
            
            if result["status"] == "success" and result.get("answers"):
                # Format answers from all relevant documents
                response_parts = ["📝 Here are the answers from your documents:\n"]
                
                for idx, answer in enumerate(result["answers"], 1):
                    # Format the answer section
                    response_parts.append(f"📄 Document {idx}: {answer['document']}")
                    response_parts.append(f"Answer: {answer['answer']}")
                    
                    # Add source information if available
                    if answer.get('sources'):
                        source_info = []
                        for source in answer['sources']:
                            metadata = source.get('metadata', {})
                            if metadata.get('page_number'):
                                source_info.append(f"Page {metadata['page_number']}")
                            if metadata.get('section'):
                                source_info.append(metadata['section'])
                        if source_info:
                            response_parts.append(f"Source: {', '.join(source_info)}")
                    
                    response_parts.append("")  # Add blank line between answers
                
                # Add a note about confidence if available
                if any(a.get('confidence') for a in result["answers"]):
                    response_parts.append("\nℹ️ Note: Answers are provided based on the relevant content found in your documents.")
                
                return True, "\n".join(response_parts)
            else:
                return False, result.get("message", "No relevant information found in your documents.")

        except Exception as e:
            logger.error(f"Error handling question: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, f"⚠️ Error processing your question: {str(e)}"

    async def process_document_async(self, file_id: str, mime_type: str, user_phone: str = None) -> Optional[Dict]:
        """Process a document asynchronously using RAG"""
        try:
            # Check if RAG processor is available
            if self.rag_processor is None:
                print("❌ RAG processor not available for document processing")
                return None
                
            # Process the document
            result = await self.rag_processor.process_document_async(file_id, mime_type, user_phone)
            
            # If processing was successful, send a notification
            if result["status"] == "success":
                # Send a WhatsApp message to notify the user
                try:
                    # Import WhatsAppHandler here to avoid circular import
                    from routes.handlers.whatsapp_handler import WhatsAppHandler
                    
                    # Create a fresh WhatsApp handler with user state
                    user_state = UserState()
                    whatsapp_handler = WhatsAppHandler(self.docs_app, {}, user_state)
                    
                    # Send success notification
                    message = "✅ Your document has been processed successfully and is now ready for Q&A! You can ask questions about it using the /ask command."
                    
                    # Try up to 3 times to send the notification
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            await whatsapp_handler.send_message(user_phone, message)
                            print(f"✅ Successfully sent processing completion notification to {user_phone}")
                            break
                        except Exception as send_err:
                            print(f"❌ Error sending notification (attempt {attempt+1}/{max_retries}): {str(send_err)}")
                            if attempt < max_retries - 1:
                                print(f"Retrying in 2 seconds...")
                                await asyncio.sleep(2)
                            else:
                                print(f"Failed to send notification after {max_retries} attempts")
                    
                except Exception as notify_err:
                    print(f"❌ Error sending notification: {str(notify_err)}")
                    import traceback
                    print(f"Notification error traceback:\n{traceback.format_exc()}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_document_summary(self, from_number: str, file_id: str) -> Tuple[bool, str]:
        """Get a summary of a document"""
        try:
            if not self.rag_processor:
                return False, "⚠️ Document summary feature is not available at the moment."
                
            # Get document from database
            document = self.docs_app.get_document(file_id, from_number)
            if not document:
                return False, "⚠️ Document not found. Please check the document ID and try again."
                
            if not document.data_store_id:
                return False, "⚠️ This document has not been processed yet. Please wait a moment and try again."
                
            # Get summary from RAG processor
            result = await self.rag_processor.get_document_summary(document.data_store_id, document.document_id)
            
            if result["status"] == "success":
                return True, f"📄 Document Summary: {document.filename}\n\n{result['summary']}"
            else:
                return False, result.get("message", "⚠️ Could not generate summary for this document.")
                
        except Exception as e:
            logger.error(f"Error getting document summary: {str(e)}")
            return False, f"⚠️ Error generating document summary: {str(e)}" 