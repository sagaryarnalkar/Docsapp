"""
WhatsApp Handler - Compatibility Wrapper
--------------------------------------
This module provides backward compatibility with the original WhatsApp handler.
It imports and re-exports the WhatsAppHandler and WhatsAppHandlerError from the
new modular structure.
"""

# Import from the new modular structure
from .whatsapp import WhatsAppHandler, WhatsAppHandlerError

# Re-export for backward compatibility
__all__ = ['WhatsAppHandler', 'WhatsAppHandlerError'] 