"""
RAG Processor - Compatibility Module

This module provides a compatibility layer between the original RAGProcessor implementation
and the new modular implementation. It can be used to gradually migrate to the new implementation.
"""

import os
import logging
import time
import json
from typing import Dict, List, Optional, Any, Union
import asyncio
from datetime import datetime

# Import the modular components
from .processor import RAGProcessor as ModularRAGProcessor
from .processor import RAGProcessorError

logger = logging.getLogger(__name__)

class CompatibilityRAGProcessor:
    """
    Compatibility wrapper for the RAGProcessor.
    
    This class maintains the same interface as the original RAGProcessor
    but delegates to the new modular implementation.
    """
    
    def __init__(
        self,
        project_id: str,
        location: str,
        credentials_path: str
    ):
        """
        Initialize the RAG processor with Google Cloud credentials.
        
        Args:
            project_id: Google Cloud project ID
            location: Google Cloud location
            credentials_path: Path to Google Cloud credentials file
        """
        # Store configuration
        self.project_id = project_id
        self.location = location
        self.credentials_path = credentials_path
        
        logger.info(f"Initializing RAG Processor (Compatibility Wrapper)")
        logger.info(f"Project ID: {project_id}")
        logger.info(f"Location: {location}")
        logger.info(f"Credentials path: {credentials_path}")
        
        try:
            # Initialize the modular implementation
            self._rag_processor = ModularRAGProcessor(
                project_id=project_id,
                location=location,
                credentials_path=credentials_path
            )
            
            # Set up properties for backward compatibility
            self.is_available = self._rag_processor.initialized
            if not self.is_available:
                logger.error(f"Error initializing RAG processor: {self._rag_processor.initialization_error}")
                raise RAGProcessorError(f"Failed to initialize RAG processor: {self._rag_processor.initialization_error}")
            
            # For backward compatibility, expose some of the original properties
            self.language_model = self._rag_processor.language_model
            
            # Set up temporary bucket for document processing
            self.temp_bucket_name = f"{project_id}-docsapp-temp"
            logger.info(f"Temporary bucket name: {self.temp_bucket_name}")
            
            # Rate limiting
            self.last_request_time = 0
            self.min_request_interval = 1.0  # seconds
            
        except Exception as e:
            logger.error(f"Error initializing RAG processor: {str(e)}", exc_info=True)
            self.is_available = False
            raise RAGProcessorError(f"Failed to initialize RAG processor: {str(e)}")
        
        logger.info("RAG Processor Initialized")
    
    def _rate_limit(self):
        """Implement rate limiting for API calls."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    async def process_document_async(
        self,
        file_id: str,
        mime_type: str,
        user_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a document asynchronously.
        
        Args:
            file_id: ID of the file to process
            mime_type: MIME type of the file
            user_phone: Optional user phone number for tracking
            
        Returns:
            Dictionary with processing results
        """
        logger.info(f"Starting document processing")
        logger.info(f"File ID: {file_id}")
        logger.info(f"MIME Type: {mime_type}")
        logger.info(f"User: {user_phone}")
        
        # Add timestamp for tracking processing time
        start_time = time.time()
        
        if not self.is_available:
            logger.warning("RAG processing not available")
            return {
                "status": "error",
                "error": "RAG processing not available",
                "data_store_id": None,
                "document_id": None,
                "filename": None
            }
        
        try:
            # Delegate to the modular implementation
            result = await self._rag_processor.process_document_async(file_id, mime_type, user_phone)
            
            logger.info(f"Document processing completed in {time.time() - start_time:.2f} seconds")
            
            return result
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}", exc_info=True)
            
            return {
                "status": "error",
                "error": str(e),
                "data_store_id": None,
                "document_id": None,
                "filename": "Unknown Document"
            }
    
    async def query_documents(
        self,
        question: str,
        data_store_id: str,
        user_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query documents to answer a question.
        
        Args:
            question: Question to answer
            data_store_id: ID of the data store to query
            user_phone: Optional user phone number for tracking
            
        Returns:
            Dictionary with query results
        """
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }
        
        try:
            logger.info(f"Processing question: {question}")
            logger.info(f"Data Store ID: {data_store_id}")
            
            # Delegate to the modular implementation
            return await self._rag_processor.query_documents(question, data_store_id, user_phone)
            
        except Exception as e:
            logger.error(f"Error querying documents: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": f"Error querying documents: {str(e)}"
            }
    
    # Add other methods as needed for backward compatibility 