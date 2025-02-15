import os
import logging
import time
from typing import Dict, List, Optional
import vertexai
from vertexai.language_models import TextGenerationModel
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, Content, Part
from vertexai_preview import generative_models
from vertexai_preview.generative_models import GenerativeModel as PreviewGenerativeModel
from google.cloud import storage
from google.cloud import documentai_v1 as documentai
from google.api_core import retry
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION

logger = logging.getLogger(__name__)

class RAGProcessor:
    def __init__(self):
        self.is_available = False
        self.last_api_call = 0
        self.min_delay = 1.0  # Minimum delay between API calls in seconds
        
        try:
            # Check if all required Google Cloud configs are available
            if not os.getenv('GOOGLE_CLOUD_PROJECT') or not os.getenv('GOOGLE_CLOUD_LOCATION') or not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                logger.warning("Google Cloud configuration incomplete. RAG features will be disabled.")
                return

            self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            self.location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            
            # Initialize Vertex AI
            vertexai.init(project=self.project_id, location=self.location)
            
            # Initialize Gemini Pro model for both standard and preview features
            self.model = GenerativeModel("gemini-pro")
            self.preview_model = PreviewGenerativeModel("gemini-pro")
            
            # Initialize Document AI
            self.docai_client = documentai.DocumentProcessorServiceClient()
            self.processor_name = f"projects/{self.project_id}/locations/{self.location}/processors/YOUR_PROCESSOR_ID"
            
            # Initialize Storage client for temporary file storage
            self.storage_client = storage.Client()
            self.temp_bucket_name = f"{self.project_id}-temp-docs"
            self.ensure_temp_bucket_exists()
            
            self.is_available = True
            logger.info("RAG processor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RAG processor: {str(e)}")
            self.is_available = False

    def ensure_temp_bucket_exists(self):
        """Ensure temporary storage bucket exists"""
        try:
            bucket = self.storage_client.bucket(self.temp_bucket_name)
            if not bucket.exists():
                bucket = self.storage_client.create_bucket(
                    self.temp_bucket_name,
                    location=self.location
                )
                logger.info(f"Created temporary bucket: {self.temp_bucket_name}")
        except Exception as e:
            logger.error(f"Error ensuring temp bucket exists: {str(e)}")
            raise

    def _rate_limit(self):
        """Implement rate limiting for API calls"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_api_call
        if time_since_last_call < self.min_delay:
            time.sleep(self.min_delay - time_since_last_call)
        self.last_api_call = time.time()

    async def process_document_async(self, file_id: str, mime_type: str) -> Dict:
        """Process a document asynchronously using Vertex AI's built-in RAG functionality."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available",
                "data_store_id": None,
                "document_id": None
            }

        try:
            logger.info(f"Processing document: {file_id} ({mime_type})")
            self._rate_limit()
            
            # Download file from Google Drive to GCS
            gcs_uri = await self._copy_drive_to_gcs(file_id)
            
            # Use Vertex AI's built-in file import for RAG
            file_data = generative_models.FileData(
                file_uri=gcs_uri,
                mime_type=mime_type
            )
            
            # Import file into Vertex AI
            response = await self.preview_model.import_file_async(
                file_data=file_data,
                project=self.project_id,
                location=self.location
            )
            
            # Wait for import to complete
            file_id = response.result()
            
            logger.info(f"Document processed successfully with file_id: {file_id}")
            return {
                "status": "success",
                "data_store_id": file_id,
                "document_id": file_id
            }
            
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "data_store_id": None,
                "document_id": None
            }

    async def _copy_drive_to_gcs(self, file_id: str) -> str:
        """Copy file from Google Drive to GCS and return the GCS URI"""
        try:
            # Get file metadata and content from Google Drive
            drive_service = self._get_drive_service()
            file_metadata = drive_service.files().get(fileId=file_id).execute()
            file_content = drive_service.files().get_media(fileId=file_id).execute()
            
            # Upload to GCS
            bucket = self.storage_client.bucket(self.temp_bucket_name)
            blob = bucket.blob(f"temp/{file_id}/{file_metadata['name']}")
            blob.upload_from_string(file_content)
            
            gcs_uri = f"gs://{self.temp_bucket_name}/{blob.name}"
            logger.info(f"File copied to GCS: {gcs_uri}")
            return gcs_uri
            
        except Exception as e:
            logger.error(f"Error copying file to GCS: {str(e)}")
            raise

    async def query_documents(self, user_query: str, data_store_id: str) -> Dict:
        """Query documents using Vertex AI's built-in RAG functionality."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            logger.info(f"Querying documents with: {user_query}")
            self._rate_limit()
            
            # Create content with file context
            content = generative_models.Content(
                parts=[
                    generative_models.Part.from_text(
                        "You are a helpful assistant analyzing documents. Using only the provided context, "
                        "answer the following question. If the answer cannot be found in the context, "
                        "explicitly say so. If the context contains partial information, acknowledge what "
                        "is known and what is missing."
                    ),
                    generative_models.Part.from_text(f"Question: {user_query}")
                ]
            )
            
            # Query using the imported file
            response = await self.preview_model.generate_content(
                content,
                generation_config=generative_models.GenerationConfig(
                    temperature=0.2,
                    candidate_count=1
                ),
                file_ids=[data_store_id]
            )
            
            return {
                "status": "success",
                "answer": response.text,
                "sources": response.metadata.get("citations", [])
            }
            
        except Exception as e:
            logger.error(f"Error querying documents: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_document_summary(self, data_store_id: str, document_id: str) -> Dict:
        """Get a comprehensive document summary using Vertex AI's built-in RAG functionality."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            logger.info(f"Generating summary for document: {document_id}")
            self._rate_limit()
            
            # Create content for summary generation
            content = generative_models.Content(
                parts=[
                    generative_models.Part.from_text(
                        """Please provide a comprehensive summary of the document.
                        Include:
                        1. Main topics and key points
                        2. Important findings or conclusions
                        3. Any significant dates, numbers, or statistics
                        4. Document structure and organization"""
                    )
                ]
            )
            
            # Generate summary using the imported file
            response = await self.preview_model.generate_content(
                content,
                generation_config=generative_models.GenerationConfig(
                    temperature=0.2,
                    candidate_count=1
                ),
                file_ids=[data_store_id]
            )
            
            return {
                "status": "success",
                "summary": response.text,
                "metadata": response.metadata
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            } 