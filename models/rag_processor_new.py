"""
RAG Processor (Legacy)

This file provides backward compatibility by importing the refactored RAGProcessor
from the models.rag package. For new code, import directly from models.rag.
"""

import warnings
from .rag import RAGProcessor, RAGProcessorError

# Display deprecation warning
warnings.warn(
    "Direct import from models.rag_processor is deprecated. Use models.rag instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
__all__ = ['RAGProcessor', 'RAGProcessorError'] 