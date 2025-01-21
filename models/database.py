# models/database.py
import sqlite3
from contextlib import contextmanager
import logging
from config import DB_DIR

logger = logging.getLogger(__name__)

class DatabasePool:
    _instance = None
    
    def __new__(cls, db_name):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
            cls._instance.db_path = f"{DB_DIR}/{db_name}"
            cls._instance.init_pool()
        return cls._instance
    
    def init_pool(self):
        """Initialize the connection pool settings"""
        # SQLite doesn't need traditional connection pooling
        # but we'll implement connection management
        self.max_connections = 5
        self.timeout = 30.0
        
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.db_path,
                timeout=self.timeout,
                isolation_level=None  # Enable autocommit mode
            )
            conn.row_factory = sqlite3.Row  # Enable row factory for better data access
            yield conn
        except sqlite3.Error as e:
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()
                
    @contextmanager
    def get_cursor(self):
        """Get a cursor using a managed connection"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
            finally:
                cursor.close()