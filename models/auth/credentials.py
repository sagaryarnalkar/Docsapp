"""
Credential Management
------------------
This module provides functionality for managing Google OAuth credentials,
including creating, refreshing, and validating credentials.
"""

import json
import time
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import SCOPES

logger = logging.getLogger(__name__)

class CredentialManager:
    """
    Manages Google OAuth credentials, including creating, refreshing, and validating.
    """
    
    def __init__(self, token_storage):
        """
        Initialize the credential manager.
        
        Args:
            token_storage: The token storage instance
        """
        self.token_storage = token_storage
        self.credentials_cache = {}  # In-memory cache for credentials
        self.last_cleanup = time.time()
        
    def get_credentials(self, phone_number):
        """
        Get Google OAuth credentials for a user.
        
        Args:
            phone_number: The user's phone number
            
        Returns:
            Credentials: Google OAuth credentials or None if not found
        """
        # Check if we have cached credentials
        if phone_number in self.credentials_cache:
            creds = self.credentials_cache[phone_number]
            # Check if credentials are valid
            if creds and not creds.expired:
                return creds
                
        # Get tokens from database
        tokens = self.token_storage.get_tokens(phone_number)
        if not tokens:
            logger.warning(f"No tokens found for user {phone_number}")
            return None
            
        try:
            # Create credentials from tokens
            creds = self._create_credentials(tokens)
            
            # Refresh token if expired
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"Refreshing expired token for user {phone_number}")
                creds.refresh(Request())
                # Store refreshed tokens
                self.token_storage.store_tokens(phone_number, creds.to_json())
                
            # Cache credentials
            self.credentials_cache[phone_number] = creds
            
            # Clean up cache periodically
            self._cleanup_cache()
            
            return creds
        except Exception as e:
            logger.error(f"Error creating credentials: {str(e)}")
            return None
    
    def _create_credentials(self, tokens):
        """
        Create Google OAuth credentials from tokens.
        
        Args:
            tokens: OAuth tokens as dict
            
        Returns:
            Credentials: Google OAuth credentials
        """
        try:
            if isinstance(tokens, str):
                tokens = json.loads(tokens)
                
            return Credentials(
                token=tokens.get('token') or tokens.get('access_token'),
                refresh_token=tokens.get('refresh_token'),
                token_uri=tokens.get('token_uri'),
                client_id=tokens.get('client_id'),
                client_secret=tokens.get('client_secret'),
                scopes=tokens.get('scopes') or SCOPES
            )
        except Exception as e:
            logger.error(f"Error creating credentials: {str(e)}")
            return None
    
    def _cleanup_cache(self):
        """Clean up the credentials cache periodically."""
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:  # Clean up every hour
            logger.info("Cleaning up credentials cache")
            self.credentials_cache = {}
            self.last_cleanup = current_time
            
    def is_authorized(self, phone_number):
        """
        Check if a user is authorized.
        
        Args:
            phone_number: The user's phone number
            
        Returns:
            bool: True if the user is authorized, False otherwise
        """
        try:
            print(f"[DEBUG] Checking authorization for user: {phone_number}")
            
            # Check if we have credentials in the cache
            if phone_number in self.credentials_cache:
                print(f"[DEBUG] Found credentials in cache for {phone_number}")
                credentials = self.credentials_cache[phone_number]
            else:
                print(f"[DEBUG] No credentials in cache for {phone_number}, retrieving from database")
                credentials = self.get_credentials(phone_number)
                
            if not credentials:
                print(f"[DEBUG] No credentials found for {phone_number}")
                return False
                
            # Check if credentials are valid
            if credentials.valid:
                print(f"[DEBUG] Credentials for {phone_number} are valid")
                return True
                
            # Check if credentials can be refreshed
            if credentials.expired and credentials.refresh_token:
                print(f"[DEBUG] Credentials for {phone_number} are expired but can be refreshed")
                try:
                    credentials.refresh(Request())
                    # Store refreshed tokens
                    self.token_storage.store_tokens(phone_number, credentials.to_json())
                    print(f"[DEBUG] Refreshed credentials for {phone_number}")
                    return True
                except Exception as e:
                    print(f"[DEBUG] Error refreshing credentials for {phone_number}: {str(e)}")
                    return False
            
            print(f"[DEBUG] Credentials for {phone_number} are expired and cannot be refreshed")
            return False
        except Exception as e:
            print(f"[DEBUG] Error checking authorization for {phone_number}: {str(e)}")
            logger.error(f"Error checking authorization: {str(e)}")
            return False 