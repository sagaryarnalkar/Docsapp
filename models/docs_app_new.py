"""
DocsApp module (Legacy)

This file provides backward compatibility by importing the refactored DocsApp
from the models.docs package. For new code, import directly from models.docs.
"""

import warnings
from .docs import DocsApp

# Display deprecation warning
warnings.warn(
    "Direct import from models.docs_app is deprecated. Use models.docs instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
__all__ = ['DocsApp'] 