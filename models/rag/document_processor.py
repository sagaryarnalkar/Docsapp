"""
Document Processor for RAG

This module handles document processing for RAG, including:
- Document downloading from Google Drive
- Text extraction from various file formats
- Document chunking and embedding
"""

import io
import os
import logging
from typing import Dict, List, Optional, Any
import asyncio

from google.cloud import documentai
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

class DocumentProcessorError(Exception):
    """Exception raised for errors in document processing."""
    pass

class DocumentProcessor:
    """
    Handles document processing for RAG.
    
    This class is responsible for:
    - Downloading documents from Google Drive
    - Extracting text from various document formats
    - Processing documents for RAG
    """
    
    def __init__(self, drive_service, document_ai_client=None, project_id=None, location=None, storage_client=None):
        """
        Initialize the document processor.
        
        Args:
            drive_service: Google Drive service
            document_ai_client: Google Document AI client (optional)
            project_id: Google Cloud project ID (needed for Document AI)
            location: Google Cloud location (needed for Document AI)
            storage_client: Google Cloud Storage client (optional)
        """
        self.drive_service = drive_service
        self.document_ai_client = document_ai_client
        self.project_id = project_id
        self.location = location
        self.storage_client = storage_client
        
        # Set up Document AI processor
        if document_ai_client and project_id and location:
            self.setup_document_ai()
    
    def setup_document_ai(self):
        """Set up Document AI processor"""
        try:
            self.document_ai_client = documentai.DocumentProcessorServiceClient(
                client_options={"api_endpoint": f"{self.location}-documentai.googleapis.com"}
            )
            logger.info("Document AI processor initialized")
        except Exception as e:
            logger.error(f"Error setting up Document AI: {str(e)}")
            self.document_ai_client = None
    
    async def download_file(self, file_id: str) -> Dict[str, Any]:
        """
        Download a file from Google Drive
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Dict containing file content, name and mime type
        """
        try:
            # Get file metadata
            file_metadata = self.drive_service.files().get(
                fileId=file_id,
                fields='name, mimeType'
            ).execute()
            
            # Get file content
            request = self.drive_service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            # Download file in chunks
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            # Reset IO position to beginning
            file_content.seek(0)
            
            return {
                'content': file_content,
                'name': file_metadata.get('name'),
                'mime_type': file_metadata.get('mimeType')
            }
        except HttpError as e:
            logger.error(f"HTTP error downloading file {file_id}: {str(e)}")
            raise DocumentProcessorError(f"Failed to download file: {str(e)}")
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {str(e)}")
            raise DocumentProcessorError(f"Failed to download file: {str(e)}")
    
    def extract_text(self, file_content: io.BytesIO, mime_type: str) -> str:
        """
        Extract text from a file based on its mime type
        
        Args:
            file_content: File content as BytesIO
            mime_type: MIME type of the file
            
        Returns:
            Extracted text
        """
        try:
            # Extract text based on file type
            if mime_type == 'application/pdf':
                return self._extract_text_from_pdf(file_content)
            elif mime_type.startswith('text/'):
                return file_content.read().decode('utf-8', errors='replace')
            elif mime_type.startswith('application/vnd.google-apps.'):
                return self._extract_text_from_google_doc(file_content)
            elif mime_type.startswith('image/'):
                return self._extract_text_from_image(file_content)
            else:
                # Try to extract text using Document AI for unsupported types
                if self.document_ai_client:
                    return self._extract_text_with_document_ai(file_content, mime_type)
                else:
                    raise DocumentProcessorError(f"Unsupported file type: {mime_type}")
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            raise DocumentProcessorError(f"Failed to extract text: {str(e)}")
    
    def _extract_text_from_pdf(self, file_content: io.BytesIO) -> str:
        """Extract text from a PDF file"""
        try:
            reader = PdfReader(file_content)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
                else:
                    # If PyPDF2 couldn't extract text, it might be a scanned PDF
                    # In a full implementation, we would use Document AI here
                    logger.warning("Page contains no extractable text - may be a scanned document")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise DocumentProcessorError(f"Failed to extract text from PDF: {str(e)}")
    
    def _extract_text_from_google_doc(self, file_content: io.BytesIO) -> str:
        """Extract text from a Google Doc"""
        # This would normally use Document AI or Google Drive API export
        # For now, return a placeholder with warning
        logger.warning("Google Doc text extraction is limited without export capabilities")
        return "Google Doc text extraction not fully implemented"
    
    def _extract_text_from_image(self, file_content: io.BytesIO) -> str:
        """Extract text from an image using Document AI (OCR)"""
        if self.document_ai_client:
            return self._extract_text_with_document_ai(file_content, "image/png")
        else:
            logger.warning("Image text extraction requires Document AI")
            return "Image text extraction not available without Document AI"
    
    def _extract_text_with_document_ai(self, file_content: io.BytesIO, mime_type: str) -> str:
        """Extract text using Document AI"""
        # This is a placeholder - in a real implementation this would use Document AI
        logger.warning("Document AI text extraction not fully implemented")
        return "Document AI text extraction not fully implemented"
    
    async def process_document(self, file_id: str, mime_type: str, user_id: str = None) -> Dict[str, Any]:
        """
        Process a document for RAG
        
        Args:
            file_id: Google Drive file ID
            mime_type: MIME type of the file
            user_id: User ID (optional)
            
        Returns:
            Dict containing processing results
        """
        try:
            # Download file
            file_data = await self.download_file(file_id)
            
            # Extract text
            text = self.extract_text(file_data['content'], mime_type)
            
            # Create a simple result
            return {
                'file_id': file_id,
                'filename': file_data['name'],
                'mime_type': mime_type,
                'text_length': len(text),
                'has_text': len(text) > 0,
                'user_id': user_id,
                'status': 'success'
            }
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {
                'file_id': file_id,
                'status': 'error',
                'error': str(e)
            } 