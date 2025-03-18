"""
API Registration Module
---------------------
This module provides utilities for registering FastAPI routers with Flask.
"""

import logging
import json
from typing import Any, Dict, Optional, List, Union

from flask import Flask, request, jsonify, g
from fastapi import FastAPI, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse

from models.docs_app import DocsApp
from routes.whatsapp_routes import router as whatsapp_router

logger = logging.getLogger(__name__)

def register_fastapi_routes(flask_app: Flask) -> None:
    """
    Register FastAPI routes with a Flask application.
    
    This function creates a FastAPI instance and registers it with
    the provided Flask application.
    
    Args:
        flask_app: Flask application
    """
    # Create FastAPI app
    fastapi_app = FastAPI(
        title="DocsApp API",
        description="API for DocsApp",
        version="1.0.0",
    )
    
    # Register routers
    fastapi_app.include_router(whatsapp_router)
    
    # Create Flask route to handle FastAPI requests
    @flask_app.route("/api/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
    def api_proxy(path: str):
        """
        Proxy requests to FastAPI.
        
        Args:
            path: API path
            
        Returns:
            Response from FastAPI
        """
        # Forward request to FastAPI
        fastapi_request = Request(scope={
            "type": "http",
            "method": request.method,
            "path": f"/api/{path}",
            "query_string": request.query_string,
            "headers": [
                (k.lower().encode(), v.encode())
                for k, v in request.headers
            ],
            "client": ("127.0.0.1", 0),
            "server": ("127.0.0.1", 8000),
        })
        
        # Get response from FastAPI
        response = fastapi_app.handle_request(fastapi_request)
        
        # Return response
        return jsonify(response.body)
    
    logger.info("Registered FastAPI routes with Flask")

def register_whatsapp_webhook(flask_app: Flask) -> None:
    """
    Register the WhatsApp webhook directly with Flask.
    
    This function provides a more direct integration with Flask
    for the WhatsApp webhook, bypassing FastAPI.
    
    Args:
        flask_app: Flask application
    """
    docs_app = DocsApp()
    
    @flask_app.route("/webhook", methods=["GET", "POST"])
    def whatsapp_webhook():
        """
        Handle incoming messages from WhatsApp.
        
        Returns:
            Response for WhatsApp
        """
        try:
            # Get request data
            if request.method == "GET":
                # Handle verification challenge
                challenge = request.args.get("hub.challenge")
                if challenge:
                    logger.info(f"Returning challenge: {challenge}")
                    return challenge
                
                return "OK"
            
            # Parse the incoming webhook payload
            payload = request.json
            logger.debug(f"Received WhatsApp webhook: {json.dumps(payload)}")
            
            # Process the message asynchronously
            from routes.whatsapp_routes import process_message
            
            # Import asyncio
            import asyncio
            
            # Create background task
            def process_message_task():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(process_message(payload, docs_app))
                loop.close()
            
            # Start background task
            import threading
            thread = threading.Thread(target=process_message_task)
            thread.daemon = True
            thread.start()
            
            # Return immediately to acknowledge receipt
            return jsonify({"status": "processing"})
            
        except Exception as e:
            logger.error(f"Error handling WhatsApp webhook: {str(e)}", exc_info=True)
            return jsonify({
                "error": str(e)
            }), 500 