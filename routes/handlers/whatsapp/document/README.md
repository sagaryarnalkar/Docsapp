# WhatsApp Document Processing Module

This module handles all aspects of document processing for WhatsApp messages, including downloading, storing, and processing documents with RAG.

## Architecture

The document processing system uses a modular architecture to separate concerns and make the code more maintainable:

```
WhatsAppHandler
      |
      ↓
WhatsAppDocumentProcessor (compatibility layer)
      |
      ↓
DocumentProcessor (core processing logic)
     / \
    /   \
   ↓     ↓
DocumentDownloader   DocumentTracker
```

### Components

- **DocumentProcessor**: Core document processing logic that coordinates the entire workflow
- **DocumentDownloader**: Handles downloading documents from WhatsApp API
- **DocumentTracker**: Tracks document states and prevents duplicate processing
- **WhatsAppMessageSender**: Sends messages to users via WhatsApp
- **Error handling**: Custom exceptions for different error scenarios

## Usage

The document processing system is designed to be used as follows:

```python
# Create a document processor
processor = WhatsAppDocumentProcessor(docs_app, message_sender, deduplication_service)

# Process a document message
result = await processor.process_document_message(message)

# Or use the handle_document method for compatibility with the old interface
response, status = await processor.handle_document(from_number, document, message)
```

## Error Handling

The module includes several exception types for different error scenarios:

- **WhatsAppDocumentError**: Base exception for all document errors
- **DocumentDownloadError**: Error downloading a document
- **DocumentStorageError**: Error storing a document in Google Drive
- **DocumentProcessingError**: Error processing a document with RAG

## Flowchart

The document processing flow works as follows:

1. Receive document message from WhatsApp
2. Extract document data and sender information
3. Check for duplicate processing
4. Download document from WhatsApp API
5. Store document in Google Drive
6. Process document with RAG (if needed)
7. Send status messages to user

## Future Improvements

Future improvements to the document processing system could include:

- Redis-based tracking for better scaling
- Rate limiting for document processing
- Support for more document types
- Better error recovery mechanisms 