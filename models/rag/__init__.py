"""
RAG (Retrieval-Augmented Generation) package

This package provides components for implementing RAG, including:
- Document processing
- Text chunking
- Embedding generation
- Vector storage
- LLM interface
"""

from .text_chunker import TextChunker
from .embedding_generator import EmbeddingGenerator
from .document_processor import DocumentProcessor
from .processor import RAGProcessor, RAGProcessorError

__all__ = [
    'TextChunker',
    'EmbeddingGenerator',
    'DocumentProcessor',
    'RAGProcessor',
    'RAGProcessorError'
] 