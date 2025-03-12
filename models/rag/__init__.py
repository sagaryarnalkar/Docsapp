"""
RAG Processor Package
-------------------
This package contains components for Retrieval Augmented Generation (RAG) processing.
It provides a modular approach to document processing, embedding generation,
and question answering using RAG techniques.

The main entry point is the RAGProcessor class which orchestrates all RAG operations.
"""

from .processor import RAGProcessor, RAGProcessorError
from .compatibility import CompatibilityRAGProcessor

__all__ = ['RAGProcessor', 'RAGProcessorError', 'CompatibilityRAGProcessor'] 