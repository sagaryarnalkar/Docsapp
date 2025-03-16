# models/database.py
import sqlite3
from contextlib import contextmanager
import logging
from config import DB_DIR
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Boolean, Text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
import shutil
from datetime import datetime
import urllib.parse
from sqlalchemy import func

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
    
class UserToken(Base):
    __tablename__ = 'user_tokens'
    
    id = Column(Integer, primary_key=True)
    phone_number = Column(String, nullable=False, unique=True)
    tokens = Column(Text, nullable=False)  # JSON string of tokens
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
class ProcessedMessage(Base):
    __tablename__ = 'processed_messages'
    
    id = Column(Integer, primary_key=True)
    message_key = Column(String, nullable=False, unique=True)
    processed_at = Column(DateTime, default=datetime.utcnow)
    message_type = Column(String)  # Type of message (document, notification, etc.)
    expires_at = Column(DateTime)  # When this record should be cleaned up

# Database connection setup
def get_database_url():
    """Get the database URL from environment or use SQLite as fallback"""
    # Check for PostgreSQL connection URL from Render
    postgres_url = os.environ.get('DATABASE_URL')
    
    if postgres_url:
        # Ensure the URL uses the correct driver for SQLAlchemy
        if postgres_url.startswith('postgres:'):
            postgres_url = postgres_url.replace('postgres:', 'postgresql:')
        print(f"Using PostgreSQL database: {postgres_url.split('@')[1] if '@' in postgres_url else 'unknown'}")
        
        # Test the PostgreSQL connection
        try:
            from sqlalchemy import create_engine
            test_engine = create_engine(postgres_url, connect_args={'connect_timeout': 5})
            with test_engine.connect() as conn:
                print("✅ Successfully connected to PostgreSQL database")
            return postgres_url
        except Exception as e:
            print(f"❌ Error connecting to PostgreSQL: {str(e)}")
            print("Falling back to SQLite database")
    else:
        print("No PostgreSQL URL found in environment variables")
    
    # Fallback to SQLite
    db_path = os.path.join(PERSISTENT_DB_DIR, 'documents.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    print(f"Using SQLite database at: {db_path}")
    return f'sqlite:///{db_path}'

# Create database engine with the appropriate connection URL
database_url = get_database_url()

# Configure engine parameters based on database type
engine_params = {
    'pool_pre_ping': True
}

# Add PostgreSQL-specific parameters only if using PostgreSQL
if database_url.startswith('postgresql'):
    engine_params.update({
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 300,
        'connect_args': {'connect_timeout': 10}
    })

# Create engine with appropriate parameters
engine = create_engine(database_url, **engine_params)

# Create session factory
Session = sessionmaker(bind=engine)

# Create all tables
try:
    print("Attempting to create database tables...")
    # First check if tables already exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    print(f"Existing tables: {existing_tables}")
    
    # Create tables that don't exist
    Base.metadata.create_all(engine)
    
    # Verify tables were created
    inspector = inspect(engine)
    tables_after = inspector.get_table_names()
    print(f"Tables after creation: {tables_after}")
    print(f"✅ Database tables created/verified successfully")
    
    # Test query to ensure database is working
    with Session() as session:
        # Count documents
        doc_count = session.query(func.count(Document.id)).scalar()
        print(f"Document count in database: {doc_count}")
        
        # Count user tokens
        user_count = session.query(func.count(UserToken.id)).scalar()
        print(f"User count in database: {user_count}")
except Exception as e:
    print(f"❌ Error creating/verifying database tables: {str(e)}")
    import traceback
    print(traceback.format_exc())

def get_session():
    """Get a database session"""
    return Session()

def migrate_sqlite_to_postgres():
    """Migrate data from SQLite to PostgreSQL if needed"""
    # Only run if we're using PostgreSQL and migration hasn't been done
    if not database_url.startswith('postgresql') or os.environ.get('DB_MIGRATION_COMPLETED'):
        return
        
    try:
        print("Checking if migration from SQLite to PostgreSQL is needed...")
        sqlite_path = os.path.join(PERSISTENT_DB_DIR, 'documents.db')
        
        if not os.path.exists(sqlite_path):
            print("No SQLite database found, skipping migration")
            return
            
        # Check if PostgreSQL already has data
        session = Session()
        doc_count = session.query(Document).count()
        session.close()
        
        if doc_count > 0:
            print(f"PostgreSQL already has {doc_count} documents, skipping migration")
            return
            
        print("Starting migration from SQLite to PostgreSQL...")
        
        # Create a temporary SQLite engine
        sqlite_engine = create_engine(f'sqlite:///{sqlite_path}')
        SQLiteSession = sessionmaker(bind=sqlite_engine)
        sqlite_session = SQLiteSession()
        
        # Migrate documents
        documents = sqlite_session.query(Document).all()
        print(f"Found {len(documents)} documents to migrate")
        
        pg_session = Session()
        for doc in documents:
            new_doc = Document(
                user_phone=doc.user_phone,
                file_id=doc.file_id,
                filename=doc.filename,
                description=doc.description,
                upload_date=doc.upload_date,
                mime_type=doc.mime_type,
                data_store_id=doc.data_store_id,
                document_id=doc.document_id
            )
            pg_session.add(new_doc)
        
        # Migrate user tokens
        try:
            user_tokens = sqlite_session.query(UserToken).all()
            print(f"Found {len(user_tokens)} user tokens to migrate")
            
            for token in user_tokens:
                new_token = UserToken(
                    phone_number=token.phone_number,
                    tokens=token.tokens,
                    created_at=token.created_at,
                    updated_at=token.updated_at
                )
                pg_session.add(new_token)
        except Exception as e:
            print(f"Error migrating user tokens: {str(e)}")
            # Continue with migration even if user tokens fail
        
        pg_session.commit()
        pg_session.close()
        sqlite_session.close()
        
        print("✅ Migration completed successfully")
        os.environ['DB_MIGRATION_COMPLETED'] = 'true'
        
    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        import traceback
        print(traceback.format_exc())

# Try to run migration if needed
try:
    migrate_sqlite_to_postgres()
except Exception as e:
    print(f"Migration attempt failed: {str(e)}")
    import traceback
    print(traceback.format_exc())