# models/database.py
import sqlite3
from contextlib import contextmanager
import logging
from config import DB_DIR
from sqlalchemy import create_engine, Column, String, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import shutil
from datetime import datetime

logger = logging.getLogger(__name__)

# Ensure the database directory exists and is persistent
# Try multiple locations for persistence
PERSISTENT_DB_DIR = os.environ.get("PERSISTENT_DB_PATH", "/data/docsapp/db")
if not os.path.exists(PERSISTENT_DB_DIR):
    # Try alternative locations
    alt_locations = [
        "/tmp/docsapp/db",  # Render tmp directory
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/db"),  # Local project directory
        DB_DIR  # From config
    ]
    
    for location in alt_locations:
        try:
            os.makedirs(location, exist_ok=True)
            print(f"Trying alternative persistent directory: {location}")
            # Check if directory is writable
            test_file = os.path.join(location, "test_write.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print(f"✅ Alternative directory is writable: {location}")
            PERSISTENT_DB_DIR = location
            break
        except Exception as e:
            print(f"⚠️ Error with alternative directory {location}: {str(e)}")

print(f"Using database directory: {PERSISTENT_DB_DIR}")
print(f"Directory exists: {os.path.exists(PERSISTENT_DB_DIR)}")
try:
    print(f"Directory contents: {os.listdir(PERSISTENT_DB_DIR)}")
except Exception as e:
    print(f"Could not list directory contents: {str(e)}")

class DatabasePool:
    _instance = None
    
    def __new__(cls, db_name):
        if cls._instance is None:
            cls._instance = super(DatabasePool, cls).__new__(cls)
            cls._instance.db_path = f"{PERSISTENT_DB_DIR}/{db_name}"
            print(f"Using persistent database at: {cls._instance.db_path}")
            
            # Check if database exists, if not, try to restore from backup
            if not os.path.exists(cls._instance.db_path):
                print(f"Database file not found at {cls._instance.db_path}")
                backup_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"../backup/{db_name}")
                if os.path.exists(backup_path):
                    print(f"Restoring database from backup: {backup_path}")
                    try:
                        shutil.copy(backup_path, cls._instance.db_path)
                        print(f"✅ Database restored from backup")
                    except Exception as e:
                        print(f"❌ Failed to restore database: {str(e)}")
            
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
            print(f"❌ Database connection error: {str(e)}")
            print(f"Database path: {self.db_path}")
            print(f"Directory exists: {os.path.exists(os.path.dirname(self.db_path))}")
            print(f"File exists: {os.path.exists(self.db_path)}")
            if os.path.exists(self.db_path):
                print(f"File permissions: {oct(os.stat(self.db_path).st_mode)[-3:]}")
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