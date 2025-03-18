"""
WhatsApp Routes
--------------
This module defines the routes for handling WhatsApp messages.
"""

import logging
import json
import asyncio
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from models import DocsApp
from routes.handlers.whatsapp.document_handler import WhatsAppDocumentHandler

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/whatsapp",
    tags=["whatsapp"],
)

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

# Routes
@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks, docs_app: DocsApp = Depends(get_docs_app)):
    """
    Handle incoming messages from WhatsApp.
    """
    try:
        # Parse the incoming webhook payload
        payload = await request.json()
        logger.debug(f"Received WhatsApp webhook: {json.dumps(payload)}")
        
        # Handle verification challenge
        if 'hub.challenge' in request.query_params:
            challenge = request.query_params['hub.challenge']
            logger.info(f"Returning challenge: {challenge}")
            return JSONResponse(content=int(challenge))
        
        # Process the message in the background
        background_tasks.add_task(process_message, payload, docs_app)
        
        # Return immediately to acknowledge receipt
        return JSONResponse(content={"status": "processing"})
        
    except Exception as e:
        logger.error(f"Error handling WhatsApp webhook: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

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