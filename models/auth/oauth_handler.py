"""
OAuth Handler
-----------
This module provides functionality for handling the OAuth flow,
including generating authorization URLs and processing authorization codes.
"""

import os
import time
import json
import logging
from google_auth_oauthlib.flow import Flow
from config import SCOPES, OAUTH_REDIRECT_URI

logger = logging.getLogger(__name__)

class OAuthHandler:
    """
    Handles the OAuth flow, including authorization URL generation and code processing.
    """
    
    def __init__(self, token_storage, credential_manager):
        """
        Initialize the OAuth handler.
        
        Args:
            token_storage: The token storage instance
            credential_manager: The credential manager instance
        """
        self.token_storage = token_storage
        self.credential_manager = credential_manager
        self.auth_codes = {}  # Temporary storage for auth codes
        
    def generate_auth_url(self, phone_number):
        """
        Generate an authorization URL for a user.
        
        Args:
            phone_number: The user's phone number
            
        Returns:
            tuple: (auth_url, state) or (None, None) if an error occurs
        """
        try:
            # Create a flow instance
            flow = self._create_flow()
            
            # Generate a state parameter to identify the user
            state = f"phone_{phone_number}_{int(time.time())}"
            
            # Generate the authorization URL
            auth_url = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                state=state
            )[0]
            
            logger.info(f"Generated auth URL for user {phone_number}")
            return auth_url, state
        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}")
            return None, None
            
    def process_auth_code(self, auth_response, state=None):
        """
        Process an authorization code from the OAuth callback.
        
        Args:
            auth_response: The full authorization response URL
            state: The state parameter (optional, can be extracted from the URL)
            
        Returns:
            tuple: (success, phone_number) or (False, None) if an error occurs
        """
        try:
            # Create a flow instance
            flow = self._create_flow()
            
            # Extract the state parameter if not provided
            if not state and 'state=' in auth_response:
                state = auth_response.split('state=')[1].split('&')[0]
                
            # Extract the phone number from the state parameter
            if state and state.startswith('phone_'):
                phone_number = state.split('_')[1]
            else:
                logger.error(f"Invalid state parameter: {state}")
                return False, None
                
            # Process the authorization response
            flow.fetch_token(authorization_response=auth_response)
            
            # Get the credentials
            credentials = flow.credentials
            
            # Store the tokens
            tokens_json = credentials.to_json()
            success = self.token_storage.store_tokens(phone_number, tokens_json)
            
            if success:
                logger.info(f"Successfully processed auth code for user {phone_number}")
                return True, phone_number
            else:
                logger.error(f"Failed to store tokens for user {phone_number}")
                return False, phone_number
        except Exception as e:
            logger.error(f"Error processing auth code: {str(e)}")
            return False, None
            
    def store_auth_code(self, code, state):
        """
        Store an authorization code from OAuth callback.
        
        Args:
            code: The authorization code
            state: The state parameter (contains phone number)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if state:
                self.auth_codes[state] = {
                    'code': code,
                    'timestamp': time.time()
                }
                logger.info(f"Stored auth code for state {state}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error storing auth code: {str(e)}")
            return False
    
    def get_auth_code(self, state):
        """
        Get an authorization code for a state.
        
        Args:
            state: The state parameter (contains phone number)
            
        Returns:
            str: The authorization code or None if not found
        """
        try:
            if state in self.auth_codes:
                # Check if code is still valid (10 minutes)
                if time.time() - self.auth_codes[state]['timestamp'] < 600:
                    return self.auth_codes[state]['code']
                # Remove expired code
                del self.auth_codes[state]
            return None
        except Exception as e:
            logger.error(f"Error getting auth code: {str(e)}")
            return None
            
    def _create_flow(self):
        """
        Create an OAuth flow instance.
        
        Returns:
            Flow: The OAuth flow instance
        """
        # Check if we have credentials in environment variable
        oauth_credentials = os.environ.get('OAUTH_CREDENTIALS')
        if oauth_credentials:
            # Create flow from client config in environment variable
            client_config = json.loads(oauth_credentials)
            return Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=OAUTH_REDIRECT_URI
            )
        else:
            # Create flow from client secrets file
            return Flow.from_client_secrets_file(
                'credentials.json',
                scopes=SCOPES,
                redirect_uri=OAUTH_REDIRECT_URI
            ) 