import os
import json
import logging
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import DB_DIR, SCOPES
from models.database import DatabasePool

logger = logging.getLogger(__name__)

class UserState:
    def __init__(self):
        self.db_pool = DatabasePool('users.db')
        self.init_database()
        self._credentials_cache = {}  # In-memory cache for credentials

    def init_database(self):
        with self.db_pool.get_cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    phone TEXT PRIMARY KEY,
                    google_authorized BOOLEAN DEFAULT FALSE,
                    tokens TEXT,
                    last_refresh TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_phone ON users(phone)')

    def store_tokens(self, phone, tokens):
        try:
            print(f"\n=== Storing Tokens for {phone} ===")
            print(f"Token data keys: {list(tokens.keys())}")
            
            with self.db_pool.get_cursor() as cursor:
                cursor.execute('''
                    INSERT OR REPLACE INTO users (phone, google_authorized, tokens, last_refresh)
                    VALUES (?, TRUE, ?, CURRENT_TIMESTAMP)
                ''', (phone, json.dumps(tokens)))
            print("Successfully stored tokens in database")
            
            # Update cache
            self._credentials_cache[phone] = Credentials.from_authorized_user_info(tokens, SCOPES)
            
        except Exception as e:
            print(f"Error storing tokens: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise

    def is_authorized(self, phone):
        try:
            print(f"\n=== Checking Authorization for {phone} ===")
            
            # Try cache first
            if phone in self._credentials_cache:
                creds = self._credentials_cache[phone]
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
                self._credentials_cache[phone] = creds
            
            print(f"Final authorization status: {is_valid}")
            return is_valid
            
        except Exception as e:
            print(f"Error checking authorization: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False

    def get_credentials(self, phone):
        try:
            print(f"\n=== Getting Credentials for {phone} ===")
            with self.db_pool.get_cursor() as cursor:
                cursor.execute('SELECT tokens FROM users WHERE phone = ?', (phone,))
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