# models/database.py
import sqlite3
from contextlib import contextmanager
import logging
from config import DB_DIR
from sqlalchemy import create_engine, Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Ensure the database directory exists and is persistent
PERSISTENT_DB_DIR = "/data/docsapp/db"
os.makedirs(PERSISTENT_DB_DIR, exist_ok=True)

class DatabasePool:
    _instance = None
    
    def __new__(cls, db_name):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
            cls._instance.db_path = f"{PERSISTENT_DB_DIR}/{db_name}"
            print(f"Using persistent database at: {cls._instance.db_path}")
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

# Create base class for declarative models
Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    user_phone = Column(String, nullable=False)
    file_id = Column(String, nullable=False)  # Google Drive file ID
    filename = Column(String, nullable=False)
    description = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    mime_type = Column(String)
    data_store_id = Column(String)
    document_id = Column(String)

# Create database engine with persistent storage
db_path = os.path.join(PERSISTENT_DB_DIR, 'documents.db')
os.makedirs(os.path.dirname(db_path), exist_ok=True)
print(f"Initializing database at: {db_path}")
engine = create_engine(f'sqlite:///{db_path}')

# Create all tables
Base.metadata.create_all(engine)
print("Database tables created successfully")

# Create session factory
Session = sessionmaker(bind=engine)