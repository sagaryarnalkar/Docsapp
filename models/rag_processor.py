import os
import logging
import time
import json
from typing import Dict, List, Optional
import vertexai
from vertexai.language_models import TextGenerationModel
from google.cloud import aiplatform
from google.cloud import storage
from google.cloud import documentai
from google.api_core import retry
from googleapiclient.discovery import build
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, SCOPES
from .database import Document
from .user_state import UserState

logger = logging.getLogger(__name__)

class RAGProcessorError(Exception):
    """Custom exception for RAG processor errors."""
    pass

class RAGProcessor:
    def __init__(self):
        self.is_available = False
        self.last_api_call = 0
        self.min_delay = 1.0  # Minimum delay between API calls in seconds
        self.user_state = UserState()
        
        try:
            print("\n=== RAG Processor Initialization ===")
            # Check if all required Google Cloud configs are available
            print(f"GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
            print(f"GOOGLE_CLOUD_LOCATION: {os.getenv('GOOGLE_CLOUD_LOCATION')}")
            print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
            
            if not os.getenv('GOOGLE_CLOUD_PROJECT') or not os.getenv('GOOGLE_CLOUD_LOCATION') or not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                logger.warning("Google Cloud configuration incomplete. RAG features will be disabled.")
                print("Missing required Google Cloud configuration")
                return

            # Check if credentials file exists
            creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not os.path.exists(creds_path):
                print(f"Credentials file not found at: {creds_path}")
                logger.warning(f"Google Cloud credentials file not found at {creds_path}")
                return

            print(f"Found credentials file at: {creds_path}")
            print(f"File permissions: {oct(os.stat(creds_path).st_mode)[-3:]}")

            # Read and validate credentials file
            try:
                with open(creds_path, 'r') as f:
                    creds_content = f.read()
                    creds_json = json.loads(creds_content)
                    print("Successfully read and parsed credentials file")
                    print(f"Credential type: {creds_json.get('type')}")
                    print(f"Project ID from creds: {creds_json.get('project_id')}")
            except Exception as e:
                print(f"Error reading credentials file: {str(e)}")
                raise

            self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            self.location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            
            # Initialize Vertex AI
            print("Initializing Vertex AI...")
            vertexai.init(project=self.project_id, location=self.location)
            print("Vertex AI initialized successfully")
            
            # Initialize language model
            print("Loading language model...")
            self.model = TextGenerationModel.from_pretrained("text-bison@001")
            print("Language model loaded successfully")
            
            # Initialize Storage client for temporary file storage
            print("Initializing Storage client...")
            self.storage_client = storage.Client()
            self.temp_bucket_name = f"{self.project_id}-temp-docs"
            print(f"Storage client initialized with bucket name: {self.temp_bucket_name}")
            
            print("Ensuring bucket exists...")
            self.ensure_temp_bucket_exists()
            print("Bucket setup complete")
            
            self.is_available = True
            print("RAG processor initialization complete!")
            logger.info("RAG processor initialized successfully")
        except Exception as e:
            print(f"\nError initializing RAG processor: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Failed to initialize RAG processor: {str(e)}")
            self.is_available = False

    def ensure_temp_bucket_exists(self):
        """Ensure temporary storage bucket exists"""
        try:
            bucket = self.storage_client.bucket(self.temp_bucket_name)
            if not bucket.exists():
                try:
                    bucket = self.storage_client.create_bucket(
                        self.temp_bucket_name,
                        location=self.location
                    )
                    logger.info(f"Created temporary bucket: {self.temp_bucket_name}")
                except Exception as e:
                    # If bucket already exists (409 error), that's fine
                    if "409" in str(e) and "already own it" in str(e):
                        logger.info(f"Bucket {self.temp_bucket_name} already exists")
                        return
                    raise  # Re-raise other exceptions
            logger.info(f"Using existing bucket: {self.temp_bucket_name}")
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

    async def process_document_async(self, file_id: str, mime_type: str, user_phone: str = None) -> Dict:
        """Process a document asynchronously using Vertex AI."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available",
                "data_store_id": None,
                "document_id": None
            }

        try:
            logger.info(f"Processing document: {file_id} ({mime_type}) for user: {user_phone}")
            self._rate_limit()
            
            # Download file from Google Drive to GCS
            gcs_uri = await self._copy_drive_to_gcs(file_id, user_phone)
            
            # For now, just store the file ID and GCS URI
            logger.info(f"Document processed successfully with file_id: {file_id}")
            return {
                "status": "success",
                "data_store_id": gcs_uri,
                "document_id": file_id
            }
            
        except RAGProcessorError as e:
            logger.error(f"RAG processing error: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "data_store_id": None,
                "document_id": None
            }
        except Exception as e:
            logger.error(f"Unexpected error processing document: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": "An unexpected error occurred",
                "data_store_id": None,
                "document_id": None
            }

    async def _copy_drive_to_gcs(self, file_id: str, user_phone: str = None) -> str:
        """Copy file from Google Drive to GCS and return the GCS URI"""
        try:
            # Get file metadata and content from Google Drive
            drive_service = self._get_drive_service(user_phone)
            if not drive_service:
                raise RAGProcessorError("Could not initialize Drive service")

            try:
                logger.info(f"Fetching file metadata for {file_id}")
                file_metadata = drive_service.files().get(fileId=file_id).execute()
                logger.info(f"Fetching file content for {file_id}")
                file_content = drive_service.files().get_media(fileId=file_id).execute()
            except Exception as e:
                raise RAGProcessorError(f"Could not access file in Drive: {str(e)}")
            
            # Upload to GCS
            try:
                logger.info(f"Uploading file to GCS bucket: {self.temp_bucket_name}")
                bucket = self.storage_client.bucket(self.temp_bucket_name)
                blob = bucket.blob(f"temp/{file_id}/{file_metadata['name']}")
                blob.upload_from_string(file_content)
                
                gcs_uri = f"gs://{self.temp_bucket_name}/{blob.name}"
                logger.info(f"File copied to GCS: {gcs_uri}")
                return gcs_uri
            except Exception as e:
                raise RAGProcessorError(f"Could not upload to GCS: {str(e)}")
            
        except RAGProcessorError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error copying file to GCS: {str(e)}", exc_info=True)
            raise RAGProcessorError(f"Failed to copy file: {str(e)}")

    async def query_documents(self, user_query: str, data_store_id: str) -> Dict:
        """Query documents using Vertex AI."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            logger.info(f"Querying documents with: {user_query}")
            self._rate_limit()
            
            prompt = f"""Using the document context, answer the following question. 
            If the answer cannot be found in the context, explicitly say so. 
            If the context contains partial information, acknowledge what is known and what is missing.

            Question: {user_query}"""
            
            response = self.model.predict(prompt)
            
            return {
                "status": "success",
                "answer": response.text,
                "sources": []
            }
            
        except Exception as e:
            logger.error(f"Error querying documents: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_document_summary(self, data_store_id: str, document_id: str) -> Dict:
        """Get a comprehensive document summary using Vertex AI."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            logger.info(f"Generating summary for document: {document_id}")
            self._rate_limit()
            
            prompt = """Please provide a comprehensive summary of the document.
            Include:
            1. Main topics and key points
            2. Important findings or conclusions
            3. Any significant dates, numbers, or statistics
            4. Document structure and organization"""
            
            response = self.model.predict(prompt)
            
            return {
                "status": "success",
                "summary": response.text,
                "metadata": {}
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def process_question(self, question: str, documents: List[Document], user_phone: str = None) -> str:
        """Process a question against the given documents"""
        if not self.is_available:
            raise RAGProcessorError("RAG processing is not available")

        try:
            # Validate input
            if not question or not documents:
                raise RAGProcessorError("Question and documents are required")

            # Get Drive service for accessing documents
            drive_service = self._get_drive_service(user_phone)
            if not drive_service:
                raise RAGProcessorError("Could not access Google Drive")

            # Combine document information
            document_texts = []
            for doc in documents:
                try:
                    # Get document metadata
                    file_metadata = drive_service.files().get(
                        fileId=doc.file_id, 
                        fields='name,mimeType'
                    ).execute()

                    doc_info = [
                        f"Document: {file_metadata.get('name', doc.filename)}",
                        f"Type: {file_metadata.get('mimeType', 'unknown')}"
                    ]

                    if doc.description:
                        doc_info.append(f"Description: {doc.description}")

                    document_texts.append("\n".join(doc_info))
                except Exception as e:
                    logger.warning(f"Could not get metadata for document {doc.file_id}: {str(e)}")
                    # Still include basic information
                    document_texts.append(f"Document: {doc.filename}\nDescription: {doc.description}")
            
            if not document_texts:
                raise RAGProcessorError("No accessible documents found")

            combined_text = "\n\n".join(document_texts)
            
            # Create prompt with more context
            prompt = f"""Based on the following document information, please answer this question: {question}

Available Documents:
{combined_text}

Instructions:
1. Answer the question based only on the information provided in the documents
2. If the answer cannot be found in the documents, explicitly say so
3. If you find partial information, explain what is known and what is missing
4. If multiple documents contain relevant information, mention which document provides each piece of information

Question: {question}
"""
            
            # Generate response with controlled parameters
            response = self.model.predict(
                prompt,
                temperature=0.3,  # Lower temperature for more focused responses
                max_output_tokens=1024,
                top_k=40,
                top_p=0.8,
            )
            
            return response.text
            
        except RAGProcessorError:
            raise
        except Exception as e:
            logger.error(f"Error processing question: {str(e)}", exc_info=True)
            raise RAGProcessorError(f"Failed to process question: {str(e)}")

    def _get_drive_service(self, user_phone=None):
        """Get Google Drive service instance"""
        try:
            if user_phone:
                # Get user-specific credentials
                credentials = self.user_state.get_credentials(user_phone)
                if not credentials:
                    raise RAGProcessorError("User not authorized")
            else:
                # Use application default credentials
                credentials = None
            
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"Error getting Drive service: {str(e)}")
            raise RAGProcessorError(f"Failed to get Drive service: {str(e)}") 