import os
import logging
import vertexai
from vertexai.language_models import TextGenerationModel
from google.cloud import aiplatform
from vertexai.preview.generative_models import GenerativeModel
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION

logger = logging.getLogger(__name__)

class RAGProcessor:
    def __init__(self):
        self.is_available = False
        try:
            # Check if all required Google Cloud configs are available
            if not os.getenv('GOOGLE_CLOUD_PROJECT') or not os.getenv('GOOGLE_CLOUD_LOCATION') or not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                logger.warning("Google Cloud configuration incomplete. RAG features will be disabled.")
                return

            self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            self.location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            vertexai.init(project=self.project_id, location=self.location)
            self.model = GenerativeModel("gemini-pro")
            self.is_available = True
            logger.info("RAG processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG processor: {str(e)}")
            self.is_available = False
        
    async def process_document_async(self, file_id, mime_type):
        """Process a document asynchronously using Vertex AI."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available",
                "data_store_id": None,
                "document_id": None
            }

        try:
            # Initialize Vertex AI
            aiplatform.init(project=self.project_id, location=self.location)
            
            # Create the data store
            data_store = aiplatform.DocumentDatastore()
            
            # Import the document from Google Drive
            import_file_config = {
                "gcs_source": {
                    "drive_file_id": file_id,
                    "mime_type": mime_type
                }
            }
            
            operation = data_store.import_documents_async(
                import_file_config=import_file_config,
                reconciliation_mode="INCREMENTAL"
            )
            
            # Wait for the operation to complete
            result = await operation.result()
            
            return {
                "status": "success",
                "data_store_id": data_store.name,
                "document_id": result.imported_document_ids[0]
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "data_store_id": None,
                "document_id": None
            }
    
    async def query_documents(self, user_query, data_store_id):
        """Query documents using RAG with Gemini."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            # Get the data store
            data_store = aiplatform.DocumentDatastore(data_store_id)
            
            # Search for relevant chunks
            search_results = data_store.search(
                query=user_query,
                num_results=5  # Get top 5 most relevant chunks
            )
            
            # Construct the prompt with context
            context = "\n\n".join([chunk.text for chunk in search_results])
            prompt = f"""Based on the following context, please answer the question. 
            If the answer cannot be found in the context, say so.
            
            Context:
            {context}
            
            Question: {user_query}
            
            Answer:"""
            
            # Generate response using Gemini
            response = self.model.generate_content(prompt)
            
            return {
                "status": "success",
                "answer": response.text,
                "sources": [
                    {
                        "document_id": chunk.document_id,
                        "relevance_score": chunk.relevance_score
                    } for chunk in search_results
                ]
            }
            
        except Exception as e:
            logger.error(f"Error querying documents: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def get_document_summary(self, data_store_id, document_id):
        """Get a summary of a document using Gemini."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            # Get the document content
            data_store = aiplatform.DocumentDatastore(data_store_id)
            document = data_store.get_document(document_id)
            
            # Generate summary using Gemini
            prompt = f"""Please provide a comprehensive summary of the following document:
            
            {document.text}
            
            Summary:"""
            
            response = self.model.generate_content(prompt)
            
            return {
                "status": "success",
                "summary": response.text
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            } 