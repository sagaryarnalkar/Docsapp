import os
import json
import time
import logging
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from config import SCOPES, OAUTH_REDIRECT_URI, GOOGLE_APPLICATION_CREDENTIALS
from models.database import UserToken, Session, get_session

# Set up logging
logger = logging.getLogger(__name__)

class UserState:
    """
    Manages user state, authentication, and token storage.
    Supports both SQLite direct access (legacy) and SQLAlchemy ORM (new).
    """
    def __init__(self):
        """Initialize the user state manager"""
        self.auth_codes = {}  # Temporary storage for auth codes
        self.credentials_cache = {}  # In-memory cache for credentials
        self.last_cleanup = time.time()
        self.init_users_db()
        
    def init_users_db(self):
        """Initialize the users database if it doesn't exist"""
        try:
            # Check if we can use the new ORM approach
            session = get_session()
            session.close()
            self.use_orm = True
            logger.info("Using ORM for user token storage")
        except Exception as e:
            # Fall back to direct SQLite if ORM fails
            self.use_orm = False
            logger.warning(f"Falling back to direct SQLite access: {str(e)}")
            
            # Legacy SQLite initialization
            from models.database import DatabasePool
            self.db_pool = DatabasePool("users.db")
            
            with self.db_pool.get_cursor() as cursor:
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    phone_number TEXT PRIMARY KEY,
                    tokens TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                logger.info("Users database initialized")
    
    def store_tokens(self, phone_number, tokens):
        """
        Store OAuth tokens for a user
        
        Args:
            phone_number: The user's phone number
            tokens: OAuth tokens as string or dict
        """
        try:
            # Convert tokens to string if it's a dict
            if isinstance(tokens, dict):
                tokens_str = json.dumps(tokens)
            else:
                tokens_str = tokens
                
            if self.use_orm:
                # Use SQLAlchemy ORM
                session = get_session()
                try:
                    # Check if user exists
                    user_token = session.query(UserToken).filter_by(phone_number=phone_number).first()
                    
                    if user_token:
                        # Update existing user
                        user_token.tokens = tokens_str
                        user_token.updated_at = datetime.utcnow()
                    else:
                        # Create new user
                        user_token = UserToken(
                            phone_number=phone_number,
                            tokens=tokens_str
                        )
                        session.add(user_token)
                        
                    session.commit()
                    logger.info(f"Stored tokens for user {phone_number} using ORM")
                except Exception as e:
                    session.rollback()
                    raise e
                finally:
                    session.close()
            else:
                # Legacy SQLite approach
                with self.db_pool.get_cursor() as cursor:
                    cursor.execute('''
                    INSERT INTO users (phone_number, tokens, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(phone_number) DO UPDATE SET
                    tokens = excluded.tokens,
                    updated_at = CURRENT_TIMESTAMP
                    ''', (phone_number, tokens_str))
                    logger.info(f"Stored tokens for user {phone_number} using direct SQLite")
                    
            # Update the in-memory cache
            self.credentials_cache[phone_number] = self._create_credentials(json.loads(tokens_str) if isinstance(tokens_str, str) else tokens_str)
            return True
        except Exception as e:
            logger.error(f"Error storing tokens: {str(e)}")
            return False
    
    def get_tokens(self, phone_number):
        """
        Get OAuth tokens for a user
        
        Args:
            phone_number: The user's phone number
            
        Returns:
            dict: OAuth tokens or None if not found
        """
        try:
            if self.use_orm:
                # Use SQLAlchemy ORM
                session = get_session()
                try:
                    user_token = session.query(UserToken).filter_by(phone_number=phone_number).first()
                    if user_token:
                        return json.loads(user_token.tokens)
                    return None
                finally:
                    session.close()
            else:
                # Legacy SQLite approach
                with self.db_pool.get_cursor() as cursor:
                    cursor.execute('SELECT tokens FROM users WHERE phone_number = ?', (phone_number,))
                    result = cursor.fetchone()
                    if result:
                        return json.loads(result[0])
                    return None
        except Exception as e:
            logger.error(f"Error getting tokens: {str(e)}")
            return None
    
    def get_credentials(self, phone_number):
        """
        Get Google OAuth credentials for a user
        
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
        tokens = self.get_tokens(phone_number)
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
                self.store_tokens(phone_number, creds.to_json())
                
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
        Create Google OAuth credentials from tokens
        
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
        """Clean up the credentials cache periodically"""
        current_time = time.time()
        if current_time - self.last_cleanup > 3600:  # Clean up every hour
            logger.info("Cleaning up credentials cache")
            self.credentials_cache = {}
            self.last_cleanup = current_time
    
    def is_authorized(self, phone):
        """
        Check if a user is authorized
        
        Args:
            phone: The user's phone number
            
        Returns:
            bool: True if authorized, False otherwise
        """
        try:
            # Get credentials
            creds = self.get_credentials(phone)
            
            # Check if credentials are valid
            if creds and not creds.expired:
                return True
                
            # Try to refresh token if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.store_tokens(phone, creds.to_json())
                    return True
                except Exception as e:
                    logger.error(f"Error refreshing token: {str(e)}")
                    return False
                    
            return False
        except Exception as e:
            logger.error(f"Error checking authorization: {str(e)}")
            return False
    
    def store_auth_code(self, code, state):
        """
        Store an authorization code from OAuth callback
        
        Args:
            code: The authorization code
            state: The state parameter (contains phone number)
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
        Get an authorization code for a state
        
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
    
    def get_credentials_from_database(self, phone):
        """
        Get credentials directly from database (for debugging)
        
        Args:
            phone: The user's phone number
            
        Returns:
            dict: Raw credentials data or None if not found
        """
        try:
            if self.use_orm:
                # Use SQLAlchemy ORM
                session = get_session()
                try:
                    user_token = session.query(UserToken).filter_by(phone_number=phone).first()
                    if user_token:
                        return {
                            'tokens': json.loads(user_token.tokens),
                            'created_at': user_token.created_at,
                            'updated_at': user_token.updated_at
                        }
                    return None
                finally:
                    session.close()
            else:
                # Legacy SQLite approach
                with self.db_pool.get_cursor() as cursor:
                    cursor.execute('SELECT tokens, created_at, updated_at FROM users WHERE phone_number = ?', (phone,))
                    result = cursor.fetchone()
                    if result:
                        return {
                            'tokens': json.loads(result[0]),
                            'created_at': result[1],
                            'updated_at': result[2]
                        }
                    return None
        except Exception as e:
            logger.error(f"Error getting credentials from database: {str(e)}")
            return None