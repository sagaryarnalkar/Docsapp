import logging
from typing import Tuple, Dict, Optional
from models.rag_processor import RAGProcessor
from models.database import Session, Document
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS

logger = logging.getLogger(__name__)

class RAGHandler:
    def __init__(self, docs_app):
        self.docs_app = docs_app
        self.rag_processor = RAGProcessor(
            project_id="docsapp-447706",
            location=GOOGLE_CLOUD_LOCATION,
            credentials_path=GOOGLE_APPLICATION_CREDENTIALS
        )

    async def handle_question(self, from_number: str, question: str) -> Tuple[bool, str]:
        """
        Handle document questions with RAG, ensuring existing functionality is preserved
        Returns a tuple of (success, message)
        """
        try:
            if not self.rag_processor.is_available:
                return False, "⚠️ Document Q&A feature is not available at the moment. Your other commands will still work normally!"

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
            logger.error(f"Error in RAG processing: {str(e)}", exc_info=True)
            return False, "⚠️ Unable to process your question at the moment. Your other commands will still work normally!"

    async def process_document_async(self, file_id: str, mime_type: str, user_phone: str = None) -> Optional[Dict]:
        """
        Process document with RAG in the background
        Returns None if processing fails, to ensure main document storage continues
        """
        print(f"\n{'='*50}")
        print("RAG HANDLER: STARTING DOCUMENT PROCESSING")
        print(f"File ID: {file_id}")
        print(f"MIME Type: {mime_type}")
        print(f"User: {user_phone}")
        print(f"{'='*50}\n")

        if not file_id:
            logger.error("No file ID provided for RAG processing")
            return None

        if not self.rag_processor.is_available:
            logger.warning("RAG processing not available, skipping document processing")
            return None

        try:
            logger.info(f"Starting background RAG processing for document {file_id}")
            
            # Process document with RAG
            try:
                result = await self.rag_processor.process_document_async(file_id, mime_type, user_phone)
                print("\n=== RAG Processing Result ===")
                print(f"Status: {result.get('status')}")
                print(f"Document: {result.get('filename')}")
                print(f"Data Store ID: {result.get('data_store_id')}")
            except Exception as e:
                logger.error(f"RAG processing failed for document {file_id}: {str(e)}")
                return None
            
            if not result or result.get("status") != "success":
                error_msg = result.get('error', 'Unknown error') if result else 'Processing failed'
                logger.error(f"RAG processing failed for document {file_id}: {error_msg}")
                return None

            logger.info(f"Successfully processed document {file_id} with RAG")
            
            # Update document record with RAG processing results
            try:
                with Session() as session:
                    doc = session.query(Document).filter(Document.file_id == file_id).first()
                    if doc:
                        doc.data_store_id = result.get("data_store_id")
                        doc.document_id = result.get("document_id")
                        session.commit()
                        logger.info(f"Updated document {file_id} with RAG processing results")
                        
                        # Send success notification via WhatsApp
                        try:
                            from routes.handlers.whatsapp_handler import WhatsAppHandler
                            whatsapp = WhatsAppHandler(self.docs_app, {}, None)
                            success_message = (
                                f"✅ Document '{result.get('filename')}' has been processed and added to your knowledge base.\n\n"
                                "You can now ask questions about this document using the /ask command!"
                            )
                            await whatsapp.send_message(user_phone, success_message)
                            print(f"Sent success notification to {user_phone}")
                        except Exception as e:
                            print(f"Error sending success notification: {str(e)}")
                            # Don't fail the process if notification fails
                            
                    else:
                        logger.warning(f"Could not find document {file_id} to update RAG results")
            except Exception as e:
                logger.error(f"Failed to update document {file_id} with RAG results: {str(e)}")
                # Don't return None here - we still want to return the processing results
                
            return {
                "data_store_id": result.get("data_store_id"),
                "document_id": result.get("document_id"),
                "filename": result.get("filename")
            }

        except Exception as e:
            logger.error(f"Unexpected error in RAG document processing: {str(e)}", exc_info=True)
            return None

    async def get_document_summary(self, from_number: str, file_id: str) -> Tuple[bool, str]:
        """
        Get a summary of a document using RAG
        Returns a tuple of (success, message)
        """
        try:
            # Get document details from docs_app
            doc = self.docs_app.get_document_details(from_number, file_id)
            if not doc or not doc.get('data_store_id') or not doc.get('document_id'):
                return False, "❌ Document not found or not yet processed for summarization."

            result = self.rag_processor.get_document_summary(
                doc['data_store_id'],
                doc['document_id']
            )

            if result["status"] == "success":
                summary = result["summary"]
                metadata = result.get("metadata", {})
                
                # Format response with metadata if available
                response_parts = ["📑 Document Summary:\n"]
                if metadata.get('filename'):
                    response_parts.append(f"📄 Document: {metadata['filename']}")
                if metadata.get('page_count'):
                    response_parts.append(f"📚 Pages: {metadata['page_count']}")
                response_parts.append(f"\n{summary}")
                
                return True, "\n".join(response_parts)
            else:
                return False, "❌ Unable to generate summary at this time."

        except Exception as e:
            logger.error(f"Error getting document summary: {str(e)}", exc_info=True)
            return False, "❌ An error occurred while generating the summary." 