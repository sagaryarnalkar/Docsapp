# WhatsApp Handler Package

This package contains a modular implementation of the WhatsApp message handling system for DocsApp. It's designed to be maintainable, testable, and easy to understand.

## Structure

The package is organized into the following components:

- **handler.py**: The main coordinator that orchestrates all WhatsApp interactions
- **message_sender.py**: Handles sending messages to WhatsApp users with deduplication
- **document_processor.py**: Processes documents from WhatsApp (upload, download, RAG processing)
- **command_processor.py**: Handles text commands from users (help, list, find, ask)
- **deduplication.py**: Manages deduplication of messages and document processing

## Component Responsibilities

### WhatsAppHandler (handler.py)

The main entry point for all WhatsApp interactions. It:
- Coordinates all message processing
- Delegates specific tasks to specialized components
- Handles authentication and authorization
- Routes messages based on their type

### MessageSender (message_sender.py)

Responsible for sending messages to WhatsApp users. It:
- Sends text messages via the WhatsApp API
- Prevents duplicate messages from being sent
- Handles API errors and token expiration
- Provides special handling for document confirmations

### DocumentProcessor (document_processor.py)

Handles all document-related operations. It:
- Downloads documents from WhatsApp
- Stores documents in Google Drive
- Processes documents with RAG
- Handles document replies for adding descriptions

### CommandProcessor (command_processor.py)

Processes text commands from users. It:
- Parses and routes text commands
- Handles help, list, find, and ask commands
- Formats responses for different command types

### DeduplicationManager (deduplication.py)

Manages deduplication to prevent processing the same message or document multiple times. It:
- Tracks processed messages
- Tracks processed documents
- Tracks documents currently being processed
- Cleans up old tracking data to prevent memory leaks

## Error Handling

The package uses a custom exception class `WhatsAppHandlerError` to signal that an error has been properly handled (e.g., by sending an error message to the user), so the calling code doesn't need to send additional error messages.

## Usage

The package is designed to be used through the main `WhatsAppHandler` class. The original `whatsapp_handler.py` file has been replaced with a compatibility wrapper that imports and re-exports the new implementation, ensuring backward compatibility with existing code.

Example:

```python
from routes.handlers.whatsapp_handler import WhatsAppHandler

# Create a WhatsApp handler
whatsapp_handler = WhatsAppHandler(docs_app, pending_descriptions, user_state)

# Handle an incoming message
result = await whatsapp_handler.handle_incoming_message(webhook_data) 