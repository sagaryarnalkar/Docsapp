"""
WhatsApp Routes for Flask
--------------
This module defines the Flask route helper functions for handling WhatsApp messages.
"""

import logging
import json
import asyncio
import threading
from typing import Dict, Any, Optional, List

from flask import request, jsonify

from models import DocsApp
from routes.handlers.whatsapp.document_handler import WhatsAppDocumentHandler

logger = logging.getLogger(__name__)

# Global DocsApp instance
_docs_app = None

def get_docs_app():
    """Get or create a DocsApp instance."""
    global _docs_app
    if _docs_app is None:
        _docs_app = DocsApp()
    return _docs_app

# Helper functions
def is_document_message(message: Dict[str, Any]) -> bool:
    """Check if a message contains a document."""
    # Direct check
    if 'document' in message:
        return True
    
    # Check WhatsApp Cloud API format
    if 'messages' in message and len(message['messages']) > 0:
        msg = message['messages'][0]
        if 'document' in msg:
            return True
    
    # Check other formats
    for key in ['attachments', 'media']:
        if key in message and message[key]:
            attachments = message[key]
            if isinstance(attachments, list) and len(attachments) > 0:
                attachment = attachments[0]
                if isinstance(attachment, dict) and 'type' in attachment and attachment['type'] == 'document':
                    return True
    
    return False

def register_whatsapp_routes(app):
    """
    Register WhatsApp webhook routes with Flask.
    
    Args:
        app: Flask application
    """
    @app.route("/webhook", methods=["GET", "POST"])
    def whatsapp_webhook():
        """
        Handle incoming messages from WhatsApp.
        """
        try:
            # Handle GET request for webhook verification
            if request.method == "GET":
                # Handle verification challenge
                challenge = request.args.get("hub.challenge")
                if challenge:
                    logger.info(f"Returning challenge: {challenge}")
                    return challenge
                return "OK"
            
            # Parse the incoming webhook payload for POST requests
            payload = request.json
            logger.debug(f"Received WhatsApp webhook: {json.dumps(payload)}")
            
            # Process the message in the background
            docs_app = get_docs_app()
            
            def run_async_process():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(process_message(payload, docs_app))
                loop.close()
                
            thread = threading.Thread(target=run_async_process)
            thread.daemon = True
            thread.start()
            
            # Return immediately to acknowledge receipt
            return jsonify({"status": "processing"})
            
        except Exception as e:
            logger.error(f"Error handling WhatsApp webhook: {str(e)}", exc_info=True)
            return jsonify({
                "error": str(e)
            }), 500

async def process_message(payload: Dict[str, Any], docs_app: DocsApp):
    """
    Process a message from WhatsApp in the background.
    
    Args:
        payload: The webhook payload
        docs_app: DocsApp instance
    """
    try:
        # Extract the message from the payload
        message = extract_message_from_payload(payload)
        if not message:
            logger.warning("No message found in payload")
            return
        
        # Route the message to the appropriate handler
        if is_document_message(message):
            await handle_document_message(message, docs_app)
        else:
            # Handle other message types (not implemented in this example)
            logger.info("Received non-document message, not implemented")
            
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)

def extract_message_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract the message from the webhook payload.
    
    Args:
        payload: The webhook payload
        
    Returns:
        Optional[Dict[str, Any]]: The message or None if not found
    """
    # WhatsApp Cloud API format
    if 'entry' in payload and len(payload['entry']) > 0:
        entry = payload['entry'][0]
        if 'changes' in entry and len(entry['changes']) > 0:
            change = entry['changes'][0]
            if 'value' in change and 'messages' in change['value'] and len(change['value']['messages']) > 0:
                return change['value']
    
    # Fallback: return the entire payload if no structure is recognized
    return payload

async def handle_document_message(message: Dict[str, Any], docs_app: DocsApp):
    """
    Handle a document message.
    
    Args:
        message: The message containing a document
        docs_app: DocsApp instance
    """
    try:
        # Create document handler
        document_handler = WhatsAppDocumentHandler(docs_app)
        
        # Process the document
        result = await document_handler.handle_message(message)
        
        logger.info(f"Document processing result: {result}")
        
    except Exception as e:
        logger.error(f"Error handling document message: {str(e)}", exc_info=True) 