"""
Token Storage
-----------
This module provides functionality for storing and retrieving OAuth tokens.
It supports both SQLAlchemy ORM and direct SQLite access for backward compatibility.
"""

import os
import json
import logging
from datetime import datetime
from models.database import UserToken, Session, get_session

logger = logging.getLogger(__name__)

class TokenStorage:
    """
    Manages the storage and retrieval of OAuth tokens.
    Supports both SQLAlchemy ORM and direct SQLite access for backward compatibility.
    """
    
    def __init__(self, db_pool=None):
        """
        Initialize the token storage.
        
        Args:
            db_pool: Database pool for legacy SQLite access (optional)
        """
        self.db_pool = db_pool
        self._initialize_storage()
        
    def _initialize_storage(self):
        """Initialize the token storage system."""
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
            if self.db_pool:
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
            else:
                logger.error("No database pool provided for legacy SQLite access")
    
    def store_tokens(self, phone_number, tokens):
        """
        Store OAuth tokens for a user.
        
        Args:
            phone_number: The user's phone number
            tokens: OAuth tokens as string or dict
            
        Returns:
            bool: True if successful, False otherwise
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
                if self.db_pool:
                    with self.db_pool.get_cursor() as cursor:
                        cursor.execute('''
                            INSERT INTO users (phone_number, tokens, updated_at)
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                            ON CONFLICT(phone_number) DO UPDATE SET
                            tokens = excluded.tokens,
                            updated_at = CURRENT_TIMESTAMP
                            ''', (phone_number, tokens_str))
                        logger.info(f"Stored tokens for user {phone_number} using direct SQLite")
                else:
                    logger.error("No database pool provided for legacy SQLite access")
                    return False
                    
            return True
        except Exception as e:
            logger.error(f"Error storing tokens: {str(e)}")
            return False
    
    def get_tokens(self, phone_number):
        """
        Get OAuth tokens for a user.
        
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
                if self.db_pool:
                    with self.db_pool.get_cursor() as cursor:
                        cursor.execute('SELECT tokens FROM users WHERE phone_number = ?', (phone_number,))
                        result = cursor.fetchone()
                        if result:
                            return json.loads(result[0])
                        return None
                else:
                    logger.error("No database pool provided for legacy SQLite access")
                    return None
        except Exception as e:
            logger.error(f"Error getting tokens: {str(e)}")
            return None
            
    def get_user_data(self, phone_number):
        """
        Get all user data from the database.
        
        Args:
            phone_number: The user's phone number
            
        Returns:
            dict: User data including tokens and timestamps, or None if not found
        """
        try:
            if self.use_orm:
                # Use SQLAlchemy ORM
                session = get_session()
                try:
                    user_token = session.query(UserToken).filter_by(phone_number=phone_number).first()
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
                if self.db_pool:
                    with self.db_pool.get_cursor() as cursor:
                        cursor.execute('SELECT tokens, created_at, updated_at FROM users WHERE phone_number = ?', (phone_number,))
                        result = cursor.fetchone()
                        if result:
                            return {
                                'tokens': json.loads(result[0]),
                                'created_at': result[1],
                                'updated_at': result[2]
                            }
                        return None
                else:
                    logger.error("No database pool provided for legacy SQLite access")
                    return None
        except Exception as e:
            logger.error(f"Error getting user data: {str(e)}")
            return None
