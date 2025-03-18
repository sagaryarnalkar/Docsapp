"""
WhatsApp Document Processing Errors
---------------------------------
This module defines exceptions for document processing.
"""

class WhatsAppDocumentError(Exception):
    """
    Custom exception for WhatsApp document processing errors that have already been 
    communicated to the user.
    
    This exception is used to signal that an error has occurred and has been
    properly handled (e.g., by sending an error message to the user), so the
    calling code doesn't need to send additional error messages.
    """
    pass

class DocumentDownloadError(WhatsAppDocumentError):
    """Exception raised when a document cannot be downloaded."""
    pass

class DocumentStorageError(WhatsAppDocumentError):
    """Exception raised when a document cannot be stored."""
    pass

class DocumentProcessingError(WhatsAppDocumentError):
    """Exception raised when a document cannot be processed."""
    pass 