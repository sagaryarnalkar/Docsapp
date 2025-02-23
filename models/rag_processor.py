import os
import io
import logging
import time
import json
from typing import Dict, List, Optional
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import storage
from google.cloud import documentai
from google.api_core import retry
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, SCOPES
from .database import Document
from .user_state import UserState
from google.cloud import aiplatform

logger = logging.getLogger(__name__)

class RAGProcessorError(Exception):
    """Custom exception for RAG processor errors."""
    pass

class RAGProcessor:
    def __init__(self, project_id, location, credentials_path):
        # Store both numeric and human-readable project IDs
        self.project_id = project_id  # Human-readable ID (e.g. docsapp-447706)
        self.numeric_project_id = "290892119731"  # Numeric ID for model access
        self.location = location
        self.credentials_path = credentials_path
        self.temp_bucket_name = f"{self.project_id}-temp"
        self.last_api_call = time.time()
        self.min_delay = 1.0  # Minimum delay between API calls
        self.is_available = False
        
        try:
            # Load service account credentials explicitly
            print(f"Loading credentials from: {self.credentials_path}")
            service_info = json.load(open(self.credentials_path))
            creds_project_id = service_info.get('project_id')
            service_account_email = service_info.get('client_email')
            print(f"Credentials project ID: {creds_project_id}")
            print(f"Service Account Email: {service_account_email}")
            
            # Verify project ID matches
            if creds_project_id != self.project_id:
                error_msg = f"Credentials project ID ({creds_project_id}) does not match target project ID ({self.project_id})"
                print(f"Error: {error_msg}")
                print(f"Please ensure you are using the service account from project {self.project_id}")
                raise RAGProcessorError(error_msg)
            
            # Load credentials with explicit project and scopes
            self.credentials = service_account.Credentials.from_service_account_info(
                service_info,
                scopes=[
                    'https://www.googleapis.com/auth/cloud-platform',
                    'https://www.googleapis.com/auth/drive',
                    'https://www.googleapis.com/auth/drive.file',
                    'https://www.googleapis.com/auth/drive.readonly'
                ]
            ).with_quota_project(self.project_id)
            
            print("Successfully loaded service account credentials")
            
            # Initialize storage client with explicit project
            self.storage_client = storage.Client(
                project=self.project_id,
                credentials=self.credentials
            )
            print(f"Storage client initialized with project: {self.project_id}")
            
            # Initialize Vertex AI with explicit project
            vertexai.init(
                project=self.numeric_project_id,  # Use numeric ID for Vertex AI
                location=self.location,
                credentials=self.credentials
            )
            print(f"Vertex AI initialized successfully with project: {self.numeric_project_id}")
            
            # Initialize Drive service
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            print("Drive service initialized successfully")
            
            # Initialize Gemini Pro
            try:
                print("Initializing Gemini Pro...")
                self.language_model = GenerativeModel("gemini-pro")
                
                # Test model access
                print("Testing access to Gemini Pro...")
                test_response = self.language_model.generate_content(
                    "Test query to verify model access."
                )
                print("Successfully verified access to Gemini Pro")
                self.is_available = True
                
            except Exception as e:
                print(f"Failed to initialize Gemini Pro: {str(e)}")
                print(f"Error type: {type(e)}")
                print(f"Error details: {str(e)}")
                self.is_available = False
                raise
                
        except Exception as e:
            print(f"Error during initialization: {str(e)}")
            print(f"Project ID: {self.project_id}")
            print(f"Location: {self.location}")
            print(f"Credentials path: {self.credentials_path}")
            self.is_available = False
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

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict]:
        """Split text into overlapping chunks with metadata"""
        chunks = []
        start = 0
        
        while start < len(text):
            # Get chunk with overlap
            end = start + chunk_size
            chunk_text = text[start:end]
            
            # Add some context by not breaking mid-sentence
            if end < len(text):
                last_period = chunk_text.rfind('.')
                if last_period != -1:
                    end = start + last_period + 1
                    chunk_text = text[start:end]
            
            # Create chunk with metadata
            chunk = {
                'text': chunk_text,
                'metadata': {
                    'start_char': start,
                    'end_char': end,
                    'chunk_index': len(chunks)
                }
            }
            chunks.append(chunk)
            
            # Move start position, accounting for overlap
            start = end - overlap
            
        return chunks

    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Vertex AI's text embedding model"""
        try:
            # Initialize the embedding model
            model = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")
            
            # Generate embeddings in batches
            embeddings = []
            batch_size = 5  # Adjust based on rate limits
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = model.get_embeddings(batch)
                embeddings.extend([emb.values for emb in batch_embeddings])
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise

    async def _store_embeddings(self, embeddings: List[List[float]], chunks: List[Dict], index_id: str = None) -> str:
        """Store embeddings in Vertex AI Vector Search"""
        try:
            # Initialize Vertex AI Vector Search client
            client = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=f"projects/{self.numeric_project_id}/locations/{self.location}/indexEndpoints/{index_id}"
            )
            
            # Prepare documents with embeddings and metadata
            documents = []
            for embedding, chunk in zip(embeddings, chunks):
                doc = {
                    'embedding': embedding,
                    'metadata': {
                        'text': chunk['text'],
                        **chunk['metadata']
                    }
                }
                documents.append(doc)
            
            # Store in vector index
            response = client.upsert_datapoints(
                embeddings=[doc['embedding'] for doc in documents],
                metadata=[doc['metadata'] for doc in documents]
            )
            
            return response.index_id
            
        except Exception as e:
            logger.error(f"Error storing embeddings: {str(e)}")
            raise

    async def _search_similar_chunks(self, query_embedding: List[float], index_id: str, top_k: int = 5) -> List[Dict]:
        """Search for similar chunks in Vector Search"""
        try:
            # Initialize Vector Search client
            client = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=f"projects/{self.numeric_project_id}/locations/{self.location}/indexEndpoints/{index_id}"
            )
            
            # Search for similar chunks
            response = client.find_neighbors(
                deployed_index_id=index_id,
                queries=[query_embedding],
                num_neighbors=top_k
            )
            
            # Get matching chunks with scores
            matches = []
            for neighbor in response.nearest_neighbors[0]:
                matches.append({
                    'text': neighbor.metadata['text'],
                    'score': neighbor.distance,
                    'metadata': neighbor.metadata
                })
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching similar chunks: {str(e)}")
            raise

    def _create_rag_prompt(self, question: str, relevant_chunks: List[Dict]) -> str:
        """Create a prompt for RAG using relevant chunks"""
        # Combine relevant chunks into context
        context = "\n\n".join([
            f"Chunk {i+1}:\n{chunk['text']}"
            for i, chunk in enumerate(relevant_chunks)
        ])
        
        return f"""Answer the following question using only the provided context. If the answer cannot be found in the context, say so explicitly.

Context:
{context}

Question: {question}

Instructions:
1. Answer based only on the provided context
2. If information is missing or unclear, say so
3. Cite specific parts of the context
4. Be concise but complete

Answer:"""

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
            
            # 1. Copy file to GCS for processing
            gcs_uri = await self._copy_drive_to_gcs(file_id, user_phone)
            print(f"File copied to GCS: {gcs_uri}")
            
            # 2. Extract text from document
            text_content = await self._extract_text(gcs_uri, mime_type)
            print("Text extracted successfully")
            
            # 3. Split text into chunks
            chunks = self._chunk_text(text_content)
            print(f"Split into {len(chunks)} chunks")
            
            # 4. Generate embeddings
            chunk_texts = [chunk['text'] for chunk in chunks]
            embeddings = await self._generate_embeddings(chunk_texts)
            print("Generated embeddings successfully")
            
            # 5. Store embeddings in Vector Search
            index_id = await self._store_embeddings(embeddings, chunks)
            print(f"Stored embeddings with index ID: {index_id}")
            
            return {
                "status": "success",
                "data_store_id": index_id,
                "document_id": file_id
            }
            
        except Exception as e:
            print(f"Error processing document: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Error processing document: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "data_store_id": None,
                "document_id": None
            }

    async def query_documents(self, question: str, data_store_id: str) -> Dict:
        """Query documents using Vertex AI Vector Search and LLM."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            print(f"\n=== Processing Question ===")
            print(f"Question: {question}")
            print(f"Data Store ID: {data_store_id}")
            
            # 1. Generate embedding for question
            question_embeddings = await self._generate_embeddings([question])
            question_embedding = question_embeddings[0]
            print("Generated question embedding")
            
            # 2. Search for similar chunks
            relevant_chunks = await self._search_similar_chunks(
                question_embedding, 
                data_store_id
            )
            print(f"Found {len(relevant_chunks)} relevant chunks")
            
            # 3. Create RAG prompt
            prompt = self._create_rag_prompt(question, relevant_chunks)
            
            # 4. Generate answer using Gemini Pro
            response = self.language_model.generate_content(prompt)
            print("Generated answer successfully")
            
            return {
                "status": "success",
                "answer": response.text,
                "sources": [chunk['metadata'] for chunk in relevant_chunks]
            }
            
        except Exception as e:
            print(f"Error querying documents: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Error querying documents: {str(e)}")
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
            
            response = self.language_model.generate_content(prompt)
            
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
            response = self.language_model.generate_content(prompt)
            
            return response.text
            
        except RAGProcessorError:
            raise
        except Exception as e:
            logger.error(f"Error processing question: {str(e)}", exc_info=True)
            raise RAGProcessorError(f"Failed to process question: {str(e)}")

    def _get_drive_service(self, user_phone=None):
        """Get Google Drive service instance"""
        try:
            # Always use the service account credentials
            return build('drive', 'v3', credentials=self.credentials)
        except Exception as e:
            logger.error(f"Error getting Drive service: {str(e)}")
            raise RAGProcessorError(f"Failed to get Drive service: {str(e)}") 