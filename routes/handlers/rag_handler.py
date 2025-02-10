import logging
from models.rag_processor import RAGProcessor

logger = logging.getLogger(__name__)

class RAGHandler:
    def __init__(self, docs_app):
        self.docs_app = docs_app
        self.rag_processor = RAGProcessor()

    async def handle_question(self, from_number, question):
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
                response = "📝 Here are the answers from your documents:\n\n"
                for idx, answer in enumerate(result["answers"], 1):
                    response += f"Document {idx}: {answer['document']}\n"
                    response += f"Answer: {answer['answer']}\n\n"
                return True, response
            else:
                return False, result.get("message", "No relevant information found in your documents.")

        except Exception as e:
            logger.error(f"Error in RAG processing: {str(e)}")
            return False, "⚠️ Unable to process your question at the moment. Your other commands will still work normally!"

    async def process_document_async(self, file_id, mime_type):
        """
        Process document with RAG in the background
        Returns None if processing fails, to ensure main document storage continues
        """
        try:
            if not self.rag_processor.is_available:
                logger.warning("RAG processing not available, skipping document processing")
                return None

            result = await self.rag_processor.process_document_async(file_id, mime_type)
            if result["status"] == "success":
                return {
                    "data_store_id": result.get("data_store_id"),
                    "document_id": result.get("document_id")
                }
            return None

        except Exception as e:
            logger.error(f"Error in RAG document processing: {str(e)}")
            return None 