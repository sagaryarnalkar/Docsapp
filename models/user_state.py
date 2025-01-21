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

    def init_database(self):
        with self.db_pool.get_cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    phone TEXT PRIMARY KEY,
                    google_authorized BOOLEAN DEFAULT FALSE,
                    tokens TEXT
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_phone ON users(phone)')

    def store_tokens(self, phone, tokens):
        with self.db_pool.get_cursor() as cursor:
            cursor.execute('''
                INSERT OR REPLACE INTO users (phone, google_authorized, tokens)
                VALUES (?, TRUE, ?)
            ''', (phone, json.dumps(tokens)))
        logger.debug(f"Stored tokens for user {phone}")

    def is_authorized(self, phone):
        try:
            creds = self.get_credentials(phone)
            logger.debug(f"Checking authorization for {phone}")
            logger.debug(f"Credentials found: {creds is not None}")
            if creds:
                logger.debug(f"Credentials valid: {creds.valid}")
                logger.debug(f"Credentials expired: {creds.expired if creds else None}")
                logger.debug(f"Has refresh token: {bool(creds.refresh_token) if creds else None}")
            return creds is not None and creds.valid
        except Exception as e:
            logger.error(f"Error checking authorization: {str(e)}")
            return False

    def get_credentials(self, phone):
        try:
            with self.db_pool.get_cursor() as cursor:
                cursor.execute('SELECT tokens FROM users WHERE phone = ?', (phone,))
                result = cursor.fetchone()

            logger.debug(f"Getting credentials for {phone}")
            logger.debug(f"Database result: {bool(result)}")

            if result and result[0]:
                token_data = json.loads(result[0])
                creds = Credentials.from_authorized_user_info(token_data, SCOPES)

                if creds.expired and creds.refresh_token:
                    logger.debug("Refreshing expired credentials")
                    try:
                        creds.refresh(Request())
                        # Store refreshed tokens
                        self.store_tokens(phone, json.loads(creds.to_json()))
                    except Exception as e:
                        logger.error(f"Error refreshing token: {str(e)}")
                        return None
                return creds
            return None
        except Exception as e:
            logger.error(f"Error getting credentials: {str(e)}")
            return None