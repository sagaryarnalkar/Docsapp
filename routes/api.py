"""API Routes Module"""


import logging
import traceback
import json
from flask import Blueprint, request, jsonify, current_app
from routes.handlers.whatsapp_handler import WhatsAppHandlerError

# Create a blueprint for API routes
api_bp = Blueprint('api', __name__)

logger = logging.getLogger(__name__)
