"""
RAG Processor - Main coordinator for Retrieval Augmented Generation

This module contains the main RAGProcessor class that orchestrates the entire
RAG pipeline, including document processing, embedding generation, and question answering.
"""

import os
import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any, Union
from datetime import datetime

# Google Cloud imports
from google.cloud import documentai_v1 as documentai
from google.cloud import storage
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel

# Local imports
from .document_processor import DocumentProcessor
from .embedding_generator import EmbeddingGenerator
from .text_chunker import TextChunker
from .vector_store import VectorStore
from .llm_interface import LLMInterface

# Setup logging
logger = logging.getLogger(__name__)

class RAGProcessorError(Exception):
    """Exception raised for errors in the RAG processing pipeline."""
    pass

class RAGProcessor:
    """
    Main coordinator for Retrieval Augmented Generation (RAG) operations.
    
    This class orchestrates the entire RAG pipeline, including:
    - Document processing and text extraction
    - Text chunking and preparation
    - Embedding generation
    - Vector storage and retrieval
    - Language model interaction for question answering
    
    It provides a unified interface for the application to process documents
    and answer questions based on the processed documents.
    """
    
    def __init__(
        self,
        project_id: str = None,
        location: str = "us-central1",
        credentials_path: str = None,
        processor_id: str = None,
        bucket_name: str = None,
        collection_name: str = "default_collection"
    ):
        """
        Initialize the RAG processor with Google Cloud settings.
        
        Args:
            project_id: Google Cloud project ID
            location: Google Cloud location
            credentials_path: Path to Google Cloud credentials file
            processor_id: Document AI processor ID
            bucket_name: Google Cloud Storage bucket name
            collection_name: Name of the vector collection
        """
        # Initialize configuration
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self.location = location
        self.credentials_path = credentials_path
        self.processor_id = processor_id or os.environ.get("DOCUMENT_AI_PROCESSOR_ID")
        self.bucket_name = bucket_name or os.environ.get("GCS_BUCKET_NAME")
        self.collection_name = collection_name
        
        # Set up Google Cloud credentials if provided
        if self.credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
        
        # Initialize components (will be lazy-loaded when needed)
        self._document_processor = None
        self._embedding_generator = None
        self._text_chunker = None
        self._vector_store = None
        self._language_model = None
        self._llm_interface = None
        
        # Initialize Google Cloud clients (will be lazy-loaded when needed)
        self._documentai_client = None
        self._storage_client = None
        
        # Track initialization status
        self.initialized = False
        self.initialization_error = None
        
        # Try to initialize
        try:
            self._initialize()
            self.initialized = True
        except Exception as e:
            self.initialization_error = str(e)
            logger.error(f"Failed to initialize RAG processor: {e}")
    
    def _initialize(self):
        """Initialize Google Cloud services and components."""
        # Initialize Google Cloud AI Platform
        aiplatform.init(project=self.project_id, location=self.location)
        
        # Initialize components
        self._init_document_processor()
        self._init_embedding_generator()
        self._init_text_chunker()
        self._init_vector_store()
        self._init_language_model()
    
    def _init_document_processor(self):
        """Initialize the document processor component."""
        self._document_processor = DocumentProcessor(
            project_id=self.project_id,
            location=self.location,
            processor_id=self.processor_id
        )
    
    def _init_embedding_generator(self):
        """Initialize the embedding generator component."""
        self._embedding_generator = EmbeddingGenerator(
            project_id=self.project_id,
            location=self.location
        )
    
    def _init_text_chunker(self):
        """Initialize the text chunker component."""
        self._text_chunker = TextChunker()
    
    def _init_vector_store(self):
        """Initialize the vector store component."""
        self._vector_store = VectorStore(
            project_id=self.project_id,
            location=self.location,
            collection_name=self.collection_name
        )
    
    def _init_language_model(self):
        """Initialize the language model component."""
        try:
            # Try to initialize Gemini 2.0 Pro
            self._language_model = GenerativeModel("gemini-2.0-pro")
            logger.info("Successfully initialized Gemini 2.0 Pro model")
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini 2.0 Pro: {e}. Falling back to Gemini 1.0 Pro")
            try:
                # Fall back to Gemini 1.0 Pro
                self._language_model = GenerativeModel("gemini-1.0-pro")
                logger.info("Successfully initialized Gemini 1.0 Pro model")
            except Exception as e2:
                logger.error(f"Failed to initialize fallback model: {e2}")
                raise RAGProcessorError(f"Failed to initialize language models: {e2}")
        
        # Initialize LLM interface
        self._llm_interface = LLMInterface(self._language_model)
    
    @property
    def document_processor(self):
        """Get the document processor, initializing if needed."""
        if self._document_processor is None:
            self._init_document_processor()
        return self._document_processor
    
    @property
    def embedding_generator(self):
        """Get the embedding generator, initializing if needed."""
        if self._embedding_generator is None:
            self._init_embedding_generator()
        return self._embedding_generator
    
    @property
    def text_chunker(self):
        """Get the text chunker, initializing if needed."""
        if self._text_chunker is None:
            self._init_text_chunker()
        return self._text_chunker
    
    @property
    def vector_store(self):
        """Get the vector store, initializing if needed."""
        if self._vector_store is None:
            self._init_vector_store()
        return self._vector_store
    
    @property
    def language_model(self):
        """Get the language model, initializing if needed."""
        if self._language_model is None:
            self._init_language_model()
        return self._language_model
    
    @property
    def llm_interface(self):
        """Get the LLM interface, initializing if needed."""
        if self._llm_interface is None and self._language_model is not None:
            self._llm_interface = LLMInterface(self._language_model)
        return self._llm_interface
    
    # Main public methods will be implemented here
    
    async def process_document_async(self, file_id, mime_type, user_phone=None):
        """Process a document asynchronously."""
        # This will be implemented to coordinate the document processing pipeline
        pass
    
    async def query_documents(self, question, data_store_id=None, user_phone=None):
        """Query documents to answer a question."""
        # This will be implemented to coordinate the question answering pipeline
        pass
    
    # Additional methods will be added here 