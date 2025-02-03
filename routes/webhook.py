# routes/webhook.py
import logging
import json
from flask import request, redirect, session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from config import (
    OAUTH_REDIRECT_URI,
    SCOPES,
    BASE_DIR
)
from models.user_state import UserState

logger = logging.getLogger(__name__)
user_state = UserState()

def handle_webhook():
    """Handle incoming webhook requests"""
    try:
        data = request.get_json()
        logger.debug(f"Webhook data: {data}")
        return "OK"
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return "Error", 500

def handle_oauth_callback():
    """Handle OAuth callback from Google"""
    try:
        # OAuth callback logic here
        return redirect('/')
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}")
        return "Error", 500