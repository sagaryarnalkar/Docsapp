"""
User State Module
---------------------------
This module provides the UserState class that manages user authentication and state.
It uses modular components for token storage, credential management, and OAuth flow handling.
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from config import SCOPES, OAUTH_REDIRECT_URI, GOOGLE_APPLICATION_CREDENTIALS
from models.database import UserToken, Session, get_session, DatabasePool

# Import the new modular components
from models.auth.token_storage import TokenStorage
from models.auth.credentials import CredentialManager
from models.auth.oauth_handler import OAuthHandler

# Set up logging
logger = logging.getLogger(__name__)

class UserState:
    """
    Manages user state, authentication, and token storage.
    Uses modular components while maintaining backward compatibility.
    """
    def __init__(self):
        """Initialize the user state manager"""
        # For backward compatibility
        self.auth_codes = {}  # Temporary storage for auth codes
        self.credentials_cache = {}  # In-memory cache for credentials
        self.last_cleanup = time.time()
        
        # Initialize database pool for legacy SQLite access
        self.db_pool = DatabasePool("users.db")
        
        # Initialize the new modular components
        self.token_storage = TokenStorage(self.db_pool)
        self.credential_manager = CredentialManager(self.token_storage)
        self.oauth_handler = OAuthHandler(self.token_storage, self.credential_manager)
        
        # Initialize database for backward compatibility
        self.init_users_db()
        
    def init_users_db(self):
        """Initialize the users database if it doesn't exist"""
        # This is now handled by TokenStorage, but kept for backward compatibility
        self.token_storage._initialize_storage()
        logger.info("Users database initialized")

    def store_tokens(self, phone_number, tokens):
        """Store OAuth tokens for a user"""
        return self.token_storage.store_tokens(phone_number, tokens)
    
    def get_tokens(self, phone_number):
        """Get OAuth tokens for a user"""
        return self.token_storage.get_tokens(phone_number)
    
    def get_credentials(self, phone_number):
        """Get OAuth credentials for a user"""
        return self.credential_manager.get_credentials(phone_number)
    
    def is_authorized(self, phone):
        """Check if a user is authorized"""
        return self.credential_manager.is_authorized(phone)
    
    def store_auth_code(self, code, state):
        """Store an OAuth authorization code"""
        return self.oauth_handler.store_auth_code(code, state)
    
    def get_auth_code(self, state):
        """Get an OAuth authorization code"""
        return self.oauth_handler.get_auth_code(state)
    
    def get_credentials_from_database(self, phone):
        """Get credentials from the database (legacy method)"""
        tokens = self.get_tokens(phone)
        if not tokens:
            return None
        
        return self._create_credentials(tokens)
    
    def _create_credentials(self, tokens):
        """Create credentials from tokens (legacy method)"""
        if not tokens:
            return None
            
        try:
            token_data = json.loads(tokens)
            credentials = Credentials(
                token=token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                client_id=token_data.get('client_id'),
                client_secret=token_data.get('client_secret'),
                scopes=token_data.get('scopes', SCOPES)
            )
            
            # Check if token is expired and refresh if needed
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                
            return credentials
        except Exception as e:
            logger.error(f"Error creating credentials: {str(e)}")
            return None
