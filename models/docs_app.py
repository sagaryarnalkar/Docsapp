import os
import json
import io
import logging
import mimetypes
from datetime import datetime
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from config import DB_DIR, SCOPES
from models.user_state import UserState
from models.database import DatabasePool
from .database import Session, Document

logger = logging.getLogger(__name__)
user_state = UserState()

class DocsApp:
    def __init__(self):
        self.db_pool = DatabasePool('documents.db')
        self.init_database()
        self.folder_name = 'DocsApp Files'
        self.drive_service = None

    def init_database(self):
        """Initialize SQLite database to store document metadata"""
        try:
            with self.db_pool.get_cursor() as cursor:
                cursor.execute('''CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_phone TEXT NOT NULL,
                    drive_file_id TEXT NOT NULL,
                    folder_id TEXT,
                    description TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')

                # Add indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_user_phone ON documents(user_phone)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_upload_date ON documents(upload_date)')

            logger.debug("Documents database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}")
            raise

    def calculate_similarity(self, text1, text2):
        """Calculate similarity between two texts"""
        # Convert to sets of words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0

    def cosine_similarity_score(self, query_text, stored_text):
        """
        Computes similarity between query and stored document text using Jaccard similarity.
        Replaced cosine similarity to remove sklearn dependency.
        """
        return self.calculate_similarity(query_text, stored_text)

    def _get_drive_service(self, user_phone):
        """Get or create Google Drive service for the user"""
        try:
            # Get credentials from user state (implement this based on your auth system)
            credentials = self._get_user_credentials(user_phone)
            if not credentials:
                return None
            
            return build('drive', 'v3', credentials=credentials)
        except Exception as e:
            logger.error(f"Error getting Drive service: {str(e)}")
            return None

    def _get_or_create_folder(self, service, folder_name):
        """Get or create DocsApp folder in Drive"""
        try:
            # Check if folder exists
            results = service.files().list(
                q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()
            
            items = results.get('files', [])
            
            if items:
                return items[0]['id']
            
            # Create folder if it doesn't exist
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')
            
        except Exception as e:
            logger.error(f"Error with Drive folder: {str(e)}")
            return None

    def store_document(self, user_phone, file_path, description, filename):
        """Store document in Drive and metadata in SQLite"""
        try:
            # Get Drive service
            service = self._get_drive_service(user_phone)
            if not service:
                return False

            # Get or create DocsApp folder
            folder_id = self._get_or_create_folder(service, self.folder_name)
            if not folder_id:
                return False

            # Upload file to Drive
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(
                file_path,
                resumable=True
            )
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, mimeType'
            ).execute()

            # Store metadata in SQLite
            with Session() as session:
                doc = Document(
                    user_phone=user_phone,
                    file_id=file['id'],
                    filename=filename,
                    description=description,
                    mime_type=file.get('mimeType')
                )
                session.add(doc)
                session.commit()

            return True

        except Exception as e:
            logger.error(f"Error storing document: {str(e)}")
            return False

    def get_document(self, file_id, user_phone):
        """Get document from Drive"""
        try:
            drive_service = self._get_drive_service(user_phone)
            if not drive_service:
                return None, None

            file_metadata = drive_service.files().get(fileId=file_id, fields='mimeType,name').execute()
            content_type = file_metadata.get('mimeType', 'application/octet-stream')

            request = drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            fh.seek(0)
            return fh, content_type
        except Exception as e:
            logger.error(f"Error getting document: {str(e)}")
            return None, None

    def update_document_description(self, user_phone, file_id, description):
        """Update document description"""
        try:
            with Session() as session:
                doc = session.query(Document).filter(
                    Document.user_phone == user_phone,
                    Document.file_id == file_id
                ).first()
                
                if doc:
                    doc.description = description
                    session.commit()
                    return True
                return False

        except Exception as e:
            logger.error(f"Error updating description: {str(e)}")
            return False

    def list_documents(self, user_phone):
        """List all documents for a user"""
        try:
            with Session() as session:
                docs = session.query(Document).filter(
                    Document.user_phone == user_phone
                ).order_by(Document.upload_date.desc()).all()
                
                doc_list = []
                file_ids = []
                
                for i, doc in enumerate(docs, 1):
                    doc_list.append(f"{i}. {doc.filename} - {doc.description}")
                    file_ids.append((i, doc.file_id, doc.filename))
                
                return doc_list, file_ids

        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return [], []

    def delete_document(self, user_phone, doc_id):
        """Delete document from Drive and database"""
        try:
            with self.db_pool.get_cursor() as cursor:
                cursor.execute('''
                    SELECT drive_file_id, filename
                    FROM documents
                    WHERE user_phone = ? AND id = ?
                ''', (user_phone, doc_id))
                result = cursor.fetchone()

                if result:
                    drive_file_id, filename = result
                    try:
                        drive_service = self._get_drive_service(user_phone)
                        if drive_service:
                            drive_service.files().delete(fileId=drive_file_id).execute()
                            logger.debug(f"Deleted file from Drive: {filename}")
                    except Exception as e:
                        logger.error(f"Error deleting from Drive: {str(e)}")

                    # Delete from database even if Drive deletion fails
                    cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
                    logger.debug(f"Deleted document from database: {filename}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error in delete_document: {str(e)}")
            return False

    def update_user_phone(self, google_id, new_phone):
        """Add new phone number to user's record"""
        try:
            print(f"\n=== UPDATING USER PHONE ===")
            print(f"Google ID: {google_id}")
            print(f"New Phone: {new_phone}")

            with self.db_pool.get_cursor() as cursor:
                # Get existing phone numbers
                cursor.execute(
                    'SELECT phone_numbers FROM documents WHERE google_id = ?',
                    (google_id,)
                )
                result = cursor.fetchone()

                if result:
                    phones = json.loads(result[0]) if result[0] else []
                    if new_phone not in phones:
                        phones.append(new_phone)
                        cursor.execute(
                            'UPDATE documents SET phone_numbers = ? WHERE google_id = ?',
                            (json.dumps(phones), google_id)
                        )
                        print(f"Updated phone numbers: {phones}")
                        return True
                    else:
                        print(f"Phone number {new_phone} already exists for this account")
                        return True
                else:
                    print(f"No documents found for Google ID: {google_id}")
                    return False

        except Exception as e:
            print(f"Error updating user phone: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

    def retrieve_document(self, user_phone, query):
        """Search for documents by filename or description"""
        try:
            with Session() as session:
                # Search in SQLite for matching documents
                results = session.query(Document).filter(
                    Document.user_phone == user_phone,
                    (Document.filename.ilike(f'%{query}%') | 
                     Document.description.ilike(f'%{query}%'))
                ).all()
                
                if not results:
                    return None

                # Return the first matching document's Drive file
                service = self._get_drive_service(user_phone)
                if not service:
                    return None

                # Get the file from Drive
                file = service.files().get(
                    fileId=results[0].file_id,
                    fields='id, name, mimeType, webViewLink'
                ).execute()

                return file

        except Exception as e:
            logger.error(f"Error retrieving document: {str(e)}")
            return None

    def search_document(self, query):
        """Search and retrieve document"""
        try:
            # Your search logic here
            pass
        except Exception as e:
            logging.error(f"Error searching document: {e}")
            return None

    def process_document(self, file_path, file_type):
        """
        1. Extract text from document
        2. Generate search tokens using DeepSeek R1
        3. Create HTML summary
        4. Store everything in user's Drive
        """
        try:
            # Simple document processing
            tokens = ["document"]  # Basic token for now
            
            # Create HTML summary (placeholder for now)
            html_summary = f"<html><body>{file_path}</body></html>"
            
            return {
                'tokens': tokens,
                'html_summary': html_summary
            }
        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return None

    def generate_search_tokens(self, text):
        """Use DeepSeek R1 to generate search tokens"""
        # Add DeepSeek R1 API integration
        pass

    def create_html_summary(self, text):
        """Create structured HTML summary"""
        # Add structure detection
        # Add table detection
        # Add layout analysis
        pass

    def _get_user_credentials(self, user_phone):
        """Get user's Google credentials - implement based on your auth system"""
        # This should be implemented based on how you're storing user credentials
        pass