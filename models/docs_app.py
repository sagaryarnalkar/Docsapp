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
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from config import DB_DIR, SCOPES
from models.user_state import UserState
from models.database import DatabasePool

logger = logging.getLogger(__name__)
user_state = UserState()

class DocsApp:
    def __init__(self):
        self.db_pool = DatabasePool('documents.db')
        self.init_database()

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

    def cosine_similarity_score(query_vector, stored_vector):
        """
        Computes cosine similarity between query and stored document embedding.
        """
        if not stored_vector:
            return 0  # No embedding, skip
        query_vector = np.array(json.loads(query_vector)).reshape(1, -1)
        stored_vector = np.array(json.loads(stored_vector)).reshape(1, -1)
        return cosine_similarity(query_vector, stored_vector)[0][0]

    def calculate_similarity(self, text1, text2):
        """Calculate similarity between two texts"""
        # Convert to sets of words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))

        return intersection / union if union > 0 else 0

    def get_drive_service(self, phone):
        """Get Google Drive service for user"""
        try:
            creds = user_state.get_credentials(phone)
            if not creds:
                logger.error(f"No credentials found for user {phone}")
                return None

            if creds.expired and creds.refresh_token:
                logger.debug("Refreshing expired credentials")
                creds.refresh(Request())
                user_state.store_tokens(phone, json.loads(creds.to_json()))

            return build('drive', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Error getting drive service: {str(e)}")
            return None

    def get_or_create_app_folder(self, drive_service, user_phone):
        """Get or create the DocsApp Files folder"""
        try:
            # Check if folder exists
            results = drive_service.files().list(
                q="name='DocsApp Files' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces='drive',
                fields='files(id, name)'
            ).execute()

            items = results.get('files', [])

            if items:
                logger.debug("Found existing DocsApp folder")
                return items[0]['id']
            else:
                # Create folder
                logger.debug("Creating new DocsApp folder")
                file_metadata = {
                    'name': 'DocsApp Files',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                file = drive_service.files().create(
                    body=file_metadata,
                    fields='id'
                ).execute()
                return file.get('id')
        except Exception as e:
            logger.error(f"Error with app folder: {str(e)}")
            return None

    def store_document(self, user_phone, file_path, description, original_filename=None):
        """Store document in Drive with original filename"""
        try:
            print("\n=== STORING DOCUMENT ===")
            print(f"User Phone: {user_phone}")
            print(f"File Path: {file_path}")
            print(f"Description: {description}")
            print(f"Original Filename: {original_filename}")

            drive_service = self.get_drive_service(user_phone)
            if not drive_service:
                print("Failed to get drive service")
                return False

            # Get Google account info
            try:
                user_info = drive_service.about().get(fields="user").execute()
                google_id = user_info['user']['emailAddress']
                print(f"Google Account ID: {google_id}")
            except Exception as e:
                print(f"Error getting Google account info: {str(e)}")
                return False

            folder_id = self.get_or_create_app_folder(drive_service, user_phone)
            if not folder_id:
                print("Failed to get or create app folder")
                return False

            # Handle filename
            if original_filename:
                print(f"Using original filename: {original_filename}")
                name, ext = os.path.splitext(original_filename)
                if not ext:
                    mime_type, _ = mimetypes.guess_type(file_path)
                    ext = mimetypes.guess_extension(mime_type) if mime_type else '.txt'
                    original_filename = f"{name}{ext}"
                    print(f"Added extension to filename: {original_filename}")
            else:
                mime_type, _ = mimetypes.guess_type(file_path)
                ext = mimetypes.guess_extension(mime_type) if mime_type else '.txt'
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                original_filename = f"Document_{timestamp}{ext}"
                print(f"Generated new filename: {original_filename}")

            print(f"Final filename for storage: {original_filename}")

            file_metadata = {
                'name': original_filename,
                'parents': [folder_id]
            }
            print(f"Drive file metadata: {file_metadata}")

            media = MediaFileUpload(file_path, resumable=True)
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name'
            ).execute()

            print(f"File created in Drive with name: {file.get('name')}")

            # Store in database using connection pool
            with self.db_pool.get_cursor() as cursor:
                # First check if Google ID exists
                cursor.execute('SELECT id, phone_numbers FROM documents WHERE google_id = ? LIMIT 1', (google_id,))
                existing_user = cursor.fetchone()

                if existing_user:
                    # Update phone numbers for existing user
                    existing_phones = json.loads(existing_user[1]) if existing_user[1] else []
                    if user_phone not in existing_phones:
                        existing_phones.append(user_phone)
                        cursor.execute(
                            'UPDATE documents SET phone_numbers = ? WHERE google_id = ?',
                            (json.dumps(existing_phones), google_id)
                        )
                        print(f"Updated phone numbers for Google ID: {existing_phones}")

                # Insert new document
                cursor.execute('''
                    INSERT INTO documents (
                        google_id, phone_numbers, drive_file_id,
                        folder_id, description, filename
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    google_id,
                    json.dumps([user_phone]),  # Original phone_numbers
                    file.get('id'),            # drive_file_id
                    folder_id,                 # Google Drive folder ID
                    description,               # User-provided description
                    original_filename          # Original filename
                ))

            print(f"Document stored successfully with filename: {original_filename}")
            return True

        except Exception as e:
            print(f"Error storing document: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

    def get_document(self, file_id, user_phone):
        """Get document from Drive"""
        try:
            drive_service = self.get_drive_service(user_phone)
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

    def update_document_description(self, user_phone, doc_id, additional_description):
        """Update document description by appending new text"""
        try:
            print(f"\n=== Updating Document Description ===")
            print(f"Document ID: {doc_id}")
            print(f"Additional Description: {additional_description}")

            with self.db_pool.get_cursor() as cursor:
                # Get current description
                cursor.execute('''
                    SELECT description, filename
                    FROM documents
                    WHERE id = ? AND user_phone = ?
                ''', (doc_id, user_phone))

                result = cursor.fetchone()
                if not result:
                    print("Document not found")
                    return False

                current_description, filename = result
                print(f"Current description: {current_description}")
                print(f"Filename: {filename}")

                # If there's no current description, use the additional one directly
                if not current_description or current_description.isspace():
                    new_description = additional_description
                else:
                    new_description = f"{current_description} | {additional_description}"

                print(f"New description will be: {new_description}")

                # Update description
                cursor.execute('''
                    UPDATE documents
                    SET description = ?
                    WHERE id = ? AND user_phone = ?
                ''', (new_description, doc_id, user_phone))

            print("Description updated successfully")
            return True

        except Exception as e:
            print(f"Error updating document description: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return False

    def list_documents(self, user_phone):
        """List all documents for a user"""
        try:
            logger.debug(f"\n=== Listing Documents ===")
            logger.debug(f"User Phone: {user_phone}")

            with self.db_pool.get_cursor() as cursor:
                # First, log all documents
                cursor.execute('''
                    SELECT id, drive_file_id, filename, description, upload_date
                    FROM documents
                    WHERE user_phone = ?
                    ORDER BY upload_date DESC
                ''', (user_phone,))

                all_docs = cursor.fetchall()
                logger.debug("\nAll documents in database:")
                for doc in all_docs:
                    logger.debug(f"ID: {doc[0]}, Drive ID: {doc[1]}, Filename: {doc[2]}, Description: {doc[3]}, Upload Date: {doc[4]}")

                cursor.execute('''
                    SELECT id, drive_file_id, filename, description
                    FROM documents
                    WHERE user_phone = ?
                    ORDER BY upload_date DESC
                ''', (user_phone,))
                documents = cursor.fetchall()

                if documents:
                    document_list = [
                        f"{i+1}. {filename} - {description}"
                        for i, (doc_id, drive_id, filename, description) in enumerate(documents)
                    ]
                    documents_formatted = [(doc_id, drive_id, filename) for doc_id, drive_id, filename, _ in documents]
                    return document_list, documents_formatted
                return None, None

        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return None, None

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
                        drive_service = self.get_drive_service(user_phone)
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
        """
        Hybrid search: combines text match + embedding similarity.
        """
        try:
            query_words = query.lower().split()
            with self.db_pool.get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, filename, description, drive_file_id
                    FROM documents
                    WHERE user_phone = ?
                """, (user_phone,))
                
                documents = cursor.fetchall()
                results = []
                
                for doc in documents:
                    doc_id, filename, description, file_id = doc
                    score = 0
                    
                    # Text-based search
                    if any(word in filename.lower() for word in query_words):
                        score += 0.5
                    if description and any(word in description.lower() for word in query_words):
                        score += 0.3
                        
                    if score > 0:
                        results.append((file_id, filename, description, score))
                
                results = sorted(results, key=lambda x: x[3], reverse=True)[:5]  # Top 5 results
                
                if results:
                    return results
                return "No relevant documents found."
                
        except Exception as e:
            logging.error(f"Error retrieving document: {e}")
            return None

    def search_document(self, query):
        """Search and retrieve document"""
        try:
            # Your search logic here
            pass
        except Exception as e:
            logging.error(f"Error searching document: {e}")
            return None