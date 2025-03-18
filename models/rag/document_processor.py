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
    
    def __init__(self, drive_service, document_ai_client=None, project_id=None, location=None):
        """
        Initialize the document processor.
        
        Args:
            drive_service: Google Drive service
            document_ai_client: Google Document AI client (optional)
            project_id: Google Cloud project ID (needed for Document AI)
            location: Google Cloud location (needed for Document AI)
        """
        self.drive_service = drive_service
        self.document_ai_client = document_ai_client
        self.project_id = project_id
        self.location = location
    
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
                text += page.extract_text() + "\n\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {str(e)}")
            raise DocumentProcessorError(f"Failed to extract text from PDF: {str(e)}")
    
    def _extract_text_from_google_doc(self, file_content: io.BytesIO) -> str:
        """Extract text from a Google Doc"""
        # This would normally use Document AI or other methods
        # For now, we'll just return a placeholder
        return "Google Doc text extraction not implemented" 