"""
Main RAG Processor

This module contains the main RAG processor class which coordinates the RAG pipeline,
including document processing, chunking, embedding, and query answering.
"""

import os
import logging
import asyncio
from typing import Dict, List, Optional, Any

import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import storage
from google.cloud import documentai
from google.oauth2 import service_account
from googleapiclient.discovery import build

from .text_chunker import TextChunker
from .embedding_generator import EmbeddingGenerator
from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

class RAGProcessorError(Exception):
    """Custom exception for RAG processor errors."""
    pass

class RAGProcessor:
    """
    Coordinates the RAG (Retrieval Augmented Generation) pipeline.
    
    This class handles:
    - Document processing
    - Text chunking
    - Embedding generation
    - Vector storage
    - Query answering
    """
    
    def __init__(self, project_id, location, credentials_path):
        """
        Initialize the RAG processor with Google Cloud credentials
        
        Args:
            project_id: Google Cloud project ID
            location: Google Cloud location
            credentials_path: Path to Google Cloud credentials JSON file
        """
        self.project_id = project_id
        self.location = location
        self.credentials_path = credentials_path
        self.is_available = False
        
        print(f"\n=== Initializing RAG Processor ===")
        print(f"Project ID: {project_id}")
        print(f"Location: {location}")
        print(f"Credentials path: {credentials_path}")
        
        try:
            # Load credentials
            self._load_credentials()
            
            # Initialize components
            self._init_storage_client()
            self._init_vertex_ai()
            self._init_drive_service()
            self._init_document_ai()
            
            # Set up RAG components
            self.text_chunker = TextChunker()
            self.embedding_generator = EmbeddingGenerator(self.project_id, self.location)
            self.document_processor = DocumentProcessor(
                self.drive_service, 
                self.document_ai_client,
                self.project_id,
                self.location,
                self.storage_client
            )
            
            # Mark as available
            self.is_available = True
            print("=== RAG Processor Initialized ===\n")
            
        except Exception as e:
            print(f"❌ Error initializing RAG processor: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Error initializing RAG processor: {str(e)}")
    
    def _load_credentials(self):
        """Load Google Cloud credentials"""
        try:
            # Check if credentials file exists
            if not os.path.exists(self.credentials_path):
                print(f"⚠️ Warning: Credentials file not found at {self.credentials_path}")
                # Try to use the environment variable path
                env_creds = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
                if env_creds and os.path.exists(env_creds):
                    self.credentials_path = env_creds
                    print(f"Using credentials from environment: {env_creds}")
                else:
                    raise RAGProcessorError("No valid credentials file found")
            
            # Load service account credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            print("✅ Successfully loaded service account credentials")
        except Exception as e:
            logger.error(f"Error loading credentials: {str(e)}")
            raise RAGProcessorError(f"Failed to load credentials: {str(e)}")
    
    def _init_storage_client(self):
        """Initialize Google Cloud Storage client"""
        try:
            self.storage_client = storage.Client(
                project=self.project_id,
                credentials=self.credentials
            )
            print("✅ Successfully initialized storage client")
        except Exception as e:
            logger.error(f"Error initializing storage client: {str(e)}")
            raise RAGProcessorError(f"Failed to initialize storage client: {str(e)}")
    
    def _init_vertex_ai(self):
        """Initialize Vertex AI and language models"""
        try:
            print("Initializing Vertex AI...")
            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=self.credentials
            )
            
            print("Initializing Gemini model...")
            try:
                print("Attempting to initialize model: gemini-pro")
                self.language_model = GenerativeModel("gemini-pro")
                print("✅ Successfully initialized gemini-pro model")
            except Exception as model_error:
                logger.error(f"Error initializing Gemini model: {str(model_error)}")
                raise RAGProcessorError(f"Failed to initialize language model: {str(model_error)}")
            
            print("✅ Successfully initialized Vertex AI")
        except Exception as e:
            logger.error(f"Error initializing Vertex AI: {str(e)}")
            raise RAGProcessorError(f"Failed to initialize Vertex AI: {str(e)}")
    
    def _init_drive_service(self):
        """Initialize Google Drive service"""
        try:
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            print("✅ Successfully initialized Drive service")
        except Exception as e:
            logger.error(f"Error initializing Drive service: {str(e)}")
            raise RAGProcessorError(f"Failed to initialize Drive service: {str(e)}")
    
    def _init_document_ai(self):
        """Initialize Document AI client"""
        try:
            self.document_ai_client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{self.location}-documentai.googleapis.com"}
            )
            print("✅ Successfully initialized Document AI client")
        except Exception as e:
            logger.error(f"Error initializing Document AI client: {str(e)}")
            print(f"⚠️ Document AI initialization failed, OCR functionality will be limited")
            self.document_ai_client = None
    
    async def process_document_async(self, file_id, mime_type, user_phone):
        """
        Process a document asynchronously
        
        Args:
            file_id: Google Drive file ID
            mime_type: MIME type of the document
            user_phone: User phone number
            
        Returns:
            Dictionary with processing results
        """
        try:
            print(f"\n=== Processing Document ===")
            print(f"File ID: {file_id}")
            print(f"MIME Type: {mime_type}")
            print(f"User: {user_phone}")
            
            if not self.is_available:
                return {
                    'status': 'error',
                    'error': 'RAG processor not available'
                }
            
            # Process the document using our document processor
            result = await self.document_processor.process_document(file_id, mime_type, user_phone)
            
            # For now, we return a simple success result
            # In a full implementation, we would:
            # 1. Chunk the extracted text
            # 2. Generate embeddings for the chunks
            # 3. Store the chunks and embeddings in a vector store
            
            if result['status'] == 'success':
                return {
                    'status': 'success',
                    'file_id': file_id,
                    'data_store_id': f"temp-store-{file_id[:8]}",  # Placeholder
                    'document_id': f"doc-{file_id[:8]}"           # Placeholder
                }
            else:
                return {
                    'status': 'error',
                    'error': result.get('error', 'Unknown error processing document')
                }
                
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def ask_question_async(self, question, user_phone):
        """
        Answer a question using RAG
        
        Args:
            question: User's question
            user_phone: User phone number
            
        Returns:
            Dictionary with answer results
        """
        try:
            print(f"\n=== Answering Question ===")
            print(f"Question: {question}")
            print(f"User: {user_phone}")
            
            if not self.is_available:
                return {
                    'status': 'error',
                    'error': 'RAG processor not available'
                }
            
            # For now, we return a simple response
            # In a full implementation, we would:
            # 1. Retrieve relevant document chunks based on the question
            # 2. Create a prompt with the question and retrieved chunks
            # 3. Generate an answer using the language model
            
            # Simple direct call to language model
            prompt = f"Please answer this question: {question}\n\n" + \
                     "If you don't know the answer, just say so."
                     
            response = self.language_model.generate_content(prompt)
            answer = response.text
            
            return {
                'status': 'success',
                'answer': answer,
                'sources': []  # Would include document sources in full implementation
            }
                
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return {
                'status': 'error',
                'error': str(e)
            } 