import os
import json
import time
from datetime import datetime, timedelta
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import SCOPES
from models.database import DatabasePool, PERSISTENT_DB_DIR
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import traceback

logger = logging.getLogger(__name__)

class UserState:
    def __init__(self):
        """Initialize the user state with a persistent database"""
        print(f"Initializing UserState with persistent database")
        self.db_pool = DatabasePool("users.db")
        self.init_users_db()
        # In-memory cache for credentials to avoid frequent DB access
        self.credentials_cache = {}
        self.last_cache_cleanup = datetime.now()

    def init_users_db(self):
        """Initialize the users database if it doesn't exist"""
        try:
            with self.db_pool.get_connection() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        phone_number TEXT PRIMARY KEY,
                        google_authorized INTEGER DEFAULT 0,
                        tokens TEXT,
                        last_refresh TIMESTAMP,
                        login_count INTEGER DEFAULT 0
                    )
                ''')
                print(f"✅ Users database initialized successfully")
                
                # Check if login_count column exists, add it if not
                try:
                    conn.execute("SELECT login_count FROM users LIMIT 1")
                    print("login_count column already exists")
                except Exception:
                    print("Adding login_count column to users table")
                    conn.execute("ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0")
                    print("✅ Added login_count column to users table")
                
                # Check if the table exists and has data
                cursor = conn.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                print(f"Found {count} users in the database")
                
        except Exception as e:
            print(f"❌ Error initializing users database: {str(e)}")
            logger.error(f"Failed to initialize users database: {str(e)}")
            traceback.print_exc()
    
    def store_tokens(self, phone_number, tokens):
        """Store the tokens for a user"""
        try:
            tokens_json = json.dumps(tokens)
            with self.db_pool.get_connection() as conn:
                # Check if user exists
                cursor = conn.execute(
                    "SELECT * FROM users WHERE phone_number = ?", 
                    (phone_number,)
                )
                user = cursor.fetchone()
                
                if user:
                    # Update existing user
                    conn.execute(
                        "UPDATE users SET google_authorized = 1, tokens = ?, last_refresh = ? WHERE phone_number = ?",
                        (tokens_json, datetime.now().isoformat(), phone_number)
                    )
                    print(f"✅ Updated tokens for user {phone_number}")
                else:
                    # Insert new user
                    conn.execute(
                        "INSERT INTO users (phone_number, google_authorized, tokens, last_refresh) VALUES (?, 1, ?, ?)",
                        (phone_number, tokens_json, datetime.now().isoformat())
                    )
                    print(f"✅ Created new user {phone_number} with tokens")
                
                # Update in-memory cache
                self.credentials_cache[phone_number] = self._create_credentials(tokens)
                return True
        except Exception as e:
            print(f"❌ Error storing tokens for user {phone_number}: {str(e)}")
            logger.error(f"Failed to store tokens for user {phone_number}: {str(e)}")
            traceback.print_exc()
            return False
    
    def get_tokens(self, phone_number):
        """Get the tokens for a user"""
        try:
            with self.db_pool.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT tokens FROM users WHERE phone_number = ? AND google_authorized = 1", 
                    (phone_number,)
                )
                user = cursor.fetchone()
                
                if user and user[0]:
                    tokens = json.loads(user[0])
                    print(f"✅ Retrieved tokens for user {phone_number}")
                    return tokens
                else:
                    print(f"⚠️ No tokens found for user {phone_number}")
                    return None
        except Exception as e:
            print(f"❌ Error retrieving tokens for user {phone_number}: {str(e)}")
            logger.error(f"Failed to get tokens for user {phone_number}: {str(e)}")
            traceback.print_exc()
            return None
    
    def get_credentials(self, phone_number):
        """Get the credentials for a user"""
        # Check cache first
        if phone_number in self.credentials_cache:
            print(f"Using cached credentials for user {phone_number}")
            return self.credentials_cache[phone_number]
        
        # Clean up cache periodically
        self._cleanup_cache()
        
        tokens = self.get_tokens(phone_number)
        if not tokens:
            print(f"⚠️ No tokens available for user {phone_number}")
            return None
        
        try:
            credentials = self._create_credentials(tokens)
            
            # Check if credentials are expired and refresh if needed
            if credentials.expired:
                print(f"Credentials expired for user {phone_number}, refreshing...")
                credentials.refresh(Request())
                # Store refreshed tokens
                self.store_tokens(phone_number, {
                    'token': credentials.token,
                    'refresh_token': credentials.refresh_token,
                    'token_uri': credentials.token_uri,
                    'client_id': credentials.client_id,
                    'client_secret': credentials.client_secret,
                    'scopes': credentials.scopes
                })
            
            # Cache the credentials
            self.credentials_cache[phone_number] = credentials
            return credentials
        except Exception as e:
            print(f"❌ Error creating credentials for user {phone_number}: {str(e)}")
            logger.error(f"Failed to create credentials for user {phone_number}: {str(e)}")
            traceback.print_exc()
            return None
    
    def _create_credentials(self, tokens):
        """Create credentials from tokens"""
        try:
            return Credentials(
                token=tokens.get('token'),
                refresh_token=tokens.get('refresh_token'),
                token_uri=tokens.get('token_uri'),
                client_id=tokens.get('client_id'),
                client_secret=tokens.get('client_secret'),
                scopes=tokens.get('scopes')
            )
        except Exception as e:
            print(f"❌ Error creating credentials from tokens: {str(e)}")
            logger.error(f"Failed to create credentials from tokens: {str(e)}")
            traceback.print_exc()
            return None
    
    def _cleanup_cache(self):
        """Clean up the credentials cache periodically"""
        now = datetime.now()
        if (now - self.last_cache_cleanup) > timedelta(hours=1):
            print("Cleaning up credentials cache")
            self.credentials_cache = {}
            self.last_cache_cleanup = now

    def is_authorized(self, phone):
        try:
            print(f"\n=== Checking Authorization for {phone} ===")
            
            # Try cache first
            if phone in self.credentials_cache:
                creds = self.credentials_cache[phone]
                if not creds.expired:
                    print("Using cached credentials")
                    return True
            
            # Get fresh credentials from database
            creds = self.get_credentials(phone)
            
            if not creds:
                print(f"No credentials found for {phone}")
                return False
                
            print(f"Credentials found:")
            print(f"Valid: {creds.valid}")
            print(f"Expired: {creds.expired if creds else None}")
            print(f"Has refresh token: {bool(creds.refresh_token) if creds else None}")
            
            if creds.expired and creds.refresh_token:
                print("Attempting to refresh expired credentials")
                try:
                    creds.refresh(Request())
                    # Store refreshed tokens
                    self.store_tokens(phone, json.loads(creds.to_json()))
                    print("Successfully refreshed credentials")
                    return True
                except Exception as e:
                    print(f"Error refreshing token: {str(e)}")
                    return False
            
            is_valid = creds is not None and creds.valid
            if is_valid:
                # Update cache
                self.credentials_cache[phone] = creds
            
            print(f"Final authorization status: {is_valid}")
            return is_valid
            
        except Exception as e:
            print(f"Error checking authorization: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False

    def get_credentials_from_database(self, phone):
        try:
            print(f"\n=== Getting Credentials for {phone} ===")
            with self.db_pool.get_cursor() as cursor:
                cursor.execute('SELECT tokens FROM users WHERE phone_number = ?', (phone,))
                result = cursor.fetchone()

            print(f"Database query result exists: {bool(result)}")

            if result and result[0]:
                try:
                    token_data = json.loads(result[0])
                    print("Successfully parsed token data")
                    print(f"Token data keys: {list(token_data.keys())}")
                    
                    creds = Credentials.from_authorized_user_info(token_data, SCOPES)
                    print("Successfully created credentials object")
                    
                    return creds
                except json.JSONDecodeError as e:
                    print(f"Error parsing token data: {str(e)}")
                    return None
                except Exception as e:
                    print(f"Error creating credentials: {str(e)}")
                    return None
            else:
                print("No token data found in database")
                return None
                
        except Exception as e:
            print(f"Error getting credentials: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return None