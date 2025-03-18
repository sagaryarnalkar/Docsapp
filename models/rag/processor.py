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
from google.oauth2 import service_account
from googleapiclient.discovery import build

from .text_chunker import TextChunker
from .embedding_generator import EmbeddingGenerator

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
            
            # Set up RAG components
            self.text_chunker = TextChunker()
            self.embedding_generator = EmbeddingGenerator(self.project_id, self.location)
            
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
                print("Attempting to initialize model: gemini-1.0-pro")
                self.language_model = GenerativeModel("gemini-1.0-pro")
                print("✅ Successfully initialized gemini-1.0-pro model")
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
    
    # Placeholder methods to be implemented in future PRs
    async def process_document_async(self, file_id, mime_type, user_phone):
        """Process a document asynchronously"""
        raise NotImplementedError("To be implemented")
    
    async def ask_question_async(self, question, user_phone):
        """Answer a question using RAG"""
        raise NotImplementedError("To be implemented") 