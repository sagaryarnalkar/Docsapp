"""
Text Chunker for RAG

This module handles text chunking for RAG, including splitting text into appropriate chunks
with overlap and managing chunk metadata.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple, Any, Union

# Setup logging
logger = logging.getLogger(__name__)

class TextChunkerError(Exception):
    """Exception raised for errors in text chunking."""
    pass

class TextChunker:
    """
    Handles text chunking for RAG.
    
    This class is responsible for:
    - Splitting text into appropriate chunks
    - Handling overlap between chunks
    - Managing chunk metadata
    - Optimizing chunks for embedding and retrieval
    """
    
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        """
        Initialize the text chunker.
        
        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum size of a chunk to be considered valid
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
    
    def chunk_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Split text into chunks with metadata.
        
        Args:
            text: Text to split into chunks
            metadata: Optional metadata to include with each chunk
            
        Returns:
            List of dictionaries containing chunk text and metadata
        """
        try:
            if not text:
                return []
            
            # Initialize metadata if not provided
            if metadata is None:
                metadata = {}
            
            # Split text into chunks
            chunks = self._split_text(text)
            
            # Create chunk objects with metadata
            chunk_objects = []
            for i, chunk_text in enumerate(chunks):
                # Skip chunks that are too small
                if len(chunk_text) < self.min_chunk_size:
                    continue
                
                # Create chunk object
                chunk_object = {
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "chunk_index": i,
                        "chunk_count": len(chunks),
                        "chunk_size": len(chunk_text)
                    }
                }
                
                chunk_objects.append(chunk_object)
            
            return chunk_objects
            
        except Exception as e:
            logger.error(f"Failed to chunk text: {e}")
            raise TextChunkerError(f"Failed to chunk text: {e}")
    
    def _split_text(self, text: str) -> List[str]:
        """
        Split text into chunks based on chunk size and overlap.
        
        Args:
            text: Text to split
            
        Returns:
            List of text chunks
        """
        # If text is shorter than chunk size, return it as a single chunk
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Calculate end position
            end = start + self.chunk_size
            
            # If we're at the end of the text, just add the remaining text
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            # Try to find a good splitting point (end of sentence or paragraph)
            split_point = self._find_split_point(text, end)
            
            # Add the chunk
            chunks.append(text[start:split_point])
            
            # Move start position for next chunk, accounting for overlap
            start = split_point - self.chunk_overlap
            
            # Make sure we're making forward progress
            if start <= 0 or start >= len(text) - self.min_chunk_size:
                break
        
        return chunks
    
    def _find_split_point(self, text: str, end: int) -> int:
        """
        Find a good splitting point near the end position.
        
        Args:
            text: Text to split
            end: Target end position
            
        Returns:
            Actual split position
        """
        # Define a window to look for split points
        window_start = max(0, end - self.chunk_overlap)
        window_end = min(len(text), end + self.chunk_overlap)
        window_text = text[window_start:window_end]
        
        # Try to find paragraph break
        paragraph_matches = list(re.finditer(r'\n\s*\n', window_text))
        if paragraph_matches:
            # Find the closest paragraph break to the end position
            closest_match = min(paragraph_matches, key=lambda m: abs(m.start() + window_start - end))
            return closest_match.start() + window_start
        
        # Try to find sentence break
        sentence_matches = list(re.finditer(r'[.!?]\s+', window_text))
        if sentence_matches:
            # Find the closest sentence break to the end position
            closest_match = min(sentence_matches, key=lambda m: abs(m.end() + window_start - end))
            return closest_match.end() + window_start
        
        # If no good break point found, just use the original end
        return end
    
    def merge_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Merge chunks back into a single text.
        
        Args:
            chunks: List of chunk objects
            
        Returns:
            Merged text
        """
        try:
            # Sort chunks by index
            sorted_chunks = sorted(chunks, key=lambda c: c["metadata"].get("chunk_index", 0))
            
            # Extract text from each chunk
            texts = [chunk["text"] for chunk in sorted_chunks]
            
            # Join texts
            return "\n".join(texts)
            
        except Exception as e:
            logger.error(f"Failed to merge chunks: {e}")
            raise TextChunkerError(f"Failed to merge chunks: {e}")
    
    def optimize_chunk_size(self, text: str, target_chunk_count: int = 10) -> int:
        """
        Optimize chunk size to achieve a target number of chunks.
        
        Args:
            text: Text to analyze
            target_chunk_count: Target number of chunks
            
        Returns:
            Optimized chunk size
        """
        try:
            text_length = len(text)
            
            # Calculate optimal chunk size
            optimal_size = text_length // target_chunk_count
            
            # Ensure chunk size is reasonable
            min_size = 100
            max_size = 2000
            
            return max(min_size, min(optimal_size, max_size))
            
        except Exception as e:
            logger.error(f"Failed to optimize chunk size: {e}")
            raise TextChunkerError(f"Failed to optimize chunk size: {e}") 