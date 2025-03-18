"""
WhatsApp Document Downloader
--------------------------
This module handles downloading documents from WhatsApp.
"""

import os
import logging
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from config import WHATSAPP_ACCESS_TOKEN, TEMP_DIR
from .errors import DocumentDownloadError

logger = logging.getLogger(__name__)

class DocumentDownloader:
    """
    Downloads documents from WhatsApp.
    
    This class is responsible for:
    1. Downloading documents from WhatsApp API
    2. Saving documents to temporary storage
    """
    
    def __init__(self, access_token=None, temp_dir=None):
        """
        Initialize the document downloader.
        
        Args:
            access_token: WhatsApp API access token (defaults to config)
            temp_dir: Directory for temporary files (defaults to config)
        """
        self.access_token = access_token or WHATSAPP_ACCESS_TOKEN
        self.temp_dir = temp_dir or TEMP_DIR
        
        # Ensure temp directory exists
        os.makedirs(self.temp_dir, exist_ok=True)
    
    async def download_document(self, document_id: str, filename: str) -> str:
        """
        Download a document from WhatsApp.
        
        Args:
            document_id: WhatsApp document ID
            filename: Filename to save as
            
        Returns:
            str: Path to downloaded file
            
        Raises:
            DocumentDownloadError: If download fails
        """
        try:
            logger.info(f"Downloading document: {document_id} as {filename}")
            
            # Construct URL for document media
            url = f"https://graph.facebook.com/v17.0/{document_id}"
            
            # Create a safe filename
            safe_filename = self._sanitize_filename(filename)
            temp_path = os.path.join(self.temp_dir, safe_filename)
            
            # Get media URL
            media_url = await self._get_media_url(url)
            if not media_url:
                raise DocumentDownloadError(f"Failed to get media URL for document {document_id}")
                
            # Download the file
            await self._download_file(media_url, temp_path)
            
            logger.info(f"Document downloaded successfully: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Error downloading document: {str(e)}")
            raise DocumentDownloadError(f"Failed to download document: {str(e)}")
    
    async def _get_media_url(self, url: str) -> Optional[str]:
        """
        Get the media URL for a document.
        
        Args:
            url: WhatsApp API URL for the document
            
        Returns:
            str or None: Media URL if successful, None otherwise
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error getting media URL: {response.status}")
                        text = await response.text()
                        logger.error(f"Response: {text}")
                        return None
                        
                    data = await response.json()
                    return data.get("url")
                    
        except Exception as e:
            logger.error(f"Error getting media URL: {str(e)}")
            return None
    
    async def _download_file(self, url: str, path: str) -> None:
        """
        Download a file from a URL.
        
        Args:
            url: URL to download from
            path: Path to save to
            
        Raises:
            DocumentDownloadError: If download fails
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Error downloading file: {response.status}")
                        text = await response.text()
                        logger.error(f"Response: {text}")
                        raise DocumentDownloadError(f"Failed to download file: HTTP {response.status}")
                        
                    # Write the file in chunks
                    with open(path, "wb") as f:
                        while True:
                            chunk = await response.content.read(8192)  # 8KB chunks
                            if not chunk:
                                break
                            f.write(chunk)
                            
        except Exception as e:
            logger.error(f"Error downloading file: {str(e)}")
            # Clean up partial file if it exists
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
            raise DocumentDownloadError(f"Failed to download file: {str(e)}")
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize a filename to be safe for the filesystem.
        
        Args:
            filename: Original filename
            
        Returns:
            str: Sanitized filename
        """
        # Replace invalid characters with underscores
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
            
        # Ensure filename is not too long
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:196] + ext  # 196 + 4 (typical extension) = 200
            
        return filename 