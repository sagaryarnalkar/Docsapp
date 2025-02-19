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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, SCOPES
from .database import Document
from .user_state import UserState

logger = logging.getLogger(__name__)

class RAGProcessorError(Exception):
    """Custom exception for RAG processor errors."""
    pass

class RAGProcessor:
    def __init__(self, project_id, location, credentials_path):
        self.project_id = project_id
        self.location = location
        self.credentials_path = credentials_path
        
        try:
            # Load service account credentials explicitly
            print(f"Loading credentials from: {self.credentials_path}")
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            print("Successfully loaded service account credentials")
            
            # Initialize storage client with explicit credentials
            storage_client = storage.Client(
                project=self.project_id,
                credentials=credentials
            )
            print(f"Storage client initialized with project: {self.project_id}")
            
            # Initialize Vertex AI with explicit project and credentials
            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=credentials
            )
            print(f"Vertex AI initialized successfully with project: {self.project_id}")
            
            # Try loading the model with explicit error handling
            model_versions = ["text-bison@002", "text-bison@001"]
            last_error = None
            
            for model_version in model_versions:
                try:
                    print(f"Attempting to load model version: {model_version}")
                    self.language_model = TextGenerationModel.from_pretrained(
                        model_version,
                        project=self.project_id,
                        location=self.location
                    )
                    print(f"Successfully loaded model version: {model_version}")
                    
                    # Verify model access with a test query
                    test_response = self.language_model.predict(
                        "Test query to verify model access.",
                        temperature=0,
                        max_output_tokens=5
                    )
                    print("Model access verified with test query")
                    break
                except Exception as e:
                    last_error = e
                    print(f"Failed to load model version {model_version}: {str(e)}")
            
            if not hasattr(self, 'language_model'):
                raise Exception(f"Failed to load any model version. Last error: {str(last_error)}")
                
        except Exception as e:
            print(f"Error during initialization: {str(e)}")
            print(f"Project ID: {self.project_id}")
            print(f"Location: {self.location}")
            print(f"Credentials path: {self.credentials_path}")
            raise

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
            print(f"\n=== Processing Document ===")
            print(f"File ID: {file_id}")
            print(f"MIME Type: {mime_type}")
            print(f"User: {user_phone}")
            
            self._rate_limit()
            
            # Download file from Google Drive to GCS
            print("Copying file to GCS...")
            gcs_uri = await self._copy_drive_to_gcs(file_id, user_phone)
            print(f"File copied to GCS: {gcs_uri}")
            
            # For now, store the GCS URI as the data store ID
            # This will be used to retrieve the document content later
            print("Document processing complete")
            return {
                "status": "success",
                "data_store_id": gcs_uri,
                "document_id": file_id
            }
            
        except RAGProcessorError as e:
            print(f"RAG processing error: {str(e)}")
            logger.error(f"RAG processing error: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "data_store_id": None,
                "document_id": None
            }
        except Exception as e:
            print(f"Unexpected error processing document: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
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
        if not self.is_available or not self.language_model:
            return {
                "status": "error",
                "error": "RAG processing or language model not available"
            }

        try:
            print(f"\n=== Querying Document ===")
            print(f"Query: {user_query}")
            print(f"Data Store ID: {data_store_id}")
            
            self._rate_limit()
            
            # Get document content from GCS
            print("Getting document content...")
            try:
                bucket_name = self.temp_bucket_name
                blob_path = data_store_id.replace(f"gs://{bucket_name}/", "")
                bucket = self.storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                content = blob.download_as_bytes()
                print("Successfully retrieved document content")

                # For PDF files, we need to extract text
                if blob_path.lower().endswith('.pdf'):
                    try:
                        # Initialize Document AI
                        client = documentai.DocumentProcessorServiceClient()
                        name = client.processor_path(self.project_id, self.location, "general-processor")
                        
                        # Process the document content
                        document = documentai.Document(
                            content=content,
                            mime_type='application/pdf'
                        )
                        
                        request = documentai.ProcessRequest(
                            name=name,
                            document=document
                        )
                        
                        result = client.process_document(request=request)
                        text_content = result.document.text
                        print("Successfully extracted text using Document AI")
                    except Exception as doc_ai_error:
                        print(f"Document AI error: {str(doc_ai_error)}")
                        # Fallback to simple text extraction if Document AI fails
                        try:
                            import io
                            from PyPDF2 import PdfReader
                            reader = PdfReader(io.BytesIO(content))
                            text_content = ""
                            for page in reader.pages:
                                text_content += page.extract_text() + "\n"
                            print("Successfully extracted text using PyPDF2 fallback")
                        except Exception as pdf_error:
                            print(f"PDF extraction error: {str(pdf_error)}")
                            return {
                                "status": "error",
                                "error": "Could not extract text from PDF document"
                            }
                else:
                    # For text files, try different encodings
                    encodings = ['utf-8', 'latin-1', 'cp1252']
                    text_content = None
                    for encoding in encodings:
                        try:
                            text_content = content.decode(encoding)
                            print(f"Successfully decoded content using {encoding}")
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    if text_content is None:
                        print("Could not decode document content with any encoding")
                        return {
                            "status": "error",
                            "error": "Could not decode document content"
                        }
                
                # Create prompt with document content
                prompt = f"""Using the following document content, answer this question: {user_query}

Document Content:
{text_content}

Instructions:
1. Answer the question based only on the information in the document
2. If the answer cannot be found in the document, explicitly say so
3. If you find partial information, explain what is known and what is missing
4. Be specific and cite relevant details from the document

Question: {user_query}"""
                
                print("Generating answer...")
                try:
                    response = self.language_model.predict(
                        prompt,
                        temperature=0.3,
                        max_output_tokens=1024,
                        top_k=40,
                        top_p=0.8,
                    )
                    print("Answer generated successfully")
                    
                    return {
                        "status": "success",
                        "answer": response.text,
                        "sources": []
                    }
                except Exception as model_error:
                    print(f"Error generating answer: {str(model_error)}")
                    return {
                        "status": "error",
                        "error": f"Could not generate answer: {str(model_error)}"
                    }
                
            except Exception as e:
                print(f"Error getting document content: {str(e)}")
                return {
                    "status": "error",
                    "error": f"Could not retrieve document content: {str(e)}"
                }
            
        except Exception as e:
            print(f"Error querying documents: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
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
            
            response = self.language_model.predict(prompt)
            
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
            response = self.language_model.predict(
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