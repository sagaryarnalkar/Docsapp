import os
import json
import io
import logging
import mimetypes
from datetime import datetime
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
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
                cursor.execute('''
                    INSERT INTO documents (user_phone, drive_file_id, folder_id, description, filename)
                    VALUES (?, ?, ?, ?, ?)
                ''', (user_phone, file.get('id'), folder_id, description, original_filename))

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

    def retrieve_document(self, user_phone, query):
        """Search and retrieve document"""
        try:
            with self.db_pool.get_cursor() as cursor:
                cursor.execute(
                    'SELECT id, drive_file_id, filename, description FROM documents WHERE user_phone = ?', 
                    (user_phone,)
                )
                documents = cursor.fetchall()

                if not documents:
                    return None, None, None, None

                # Calculate similarity scores
                similarities = []
                for doc in documents:
                    doc_id, file_id, filename, description = doc
                    # Calculate score for filename and description
                    base_score = self.calculate_similarity(query, f"{filename} {description}")

                    # Check for partial matches
                    query_words = query.lower().split()
                    content_words = (f"{filename} {description}").lower().split()
                    for q_word in query_words:
                        for c_word in content_words:
                            if q_word in c_word or c_word in q_word:
                                base_score += 0.2

                    if base_score > 0.7:  # Strong match
                        score_category = "Strong"
                        final_score = base_score
                    elif base_score > 0.4:  # Medium match
                        score_category = "Medium"
                        final_score = base_score
                    else:
                        continue  # Skip weak matches

                    similarities.append((final_score, doc_id, file_id, filename, description, score_category))

                # Sort by similarity score
                similarities.sort(reverse=True)

                if similarities:
                    if len(similarities) == 1:
                        # Single match
                        _, doc_id, file_id, filename, _, category = similarities[0]
                        logger.debug(f"Found single {category} match: {filename}")
                        file_data, content_type = self.get_document(file_id, user_phone)
                        return file_data, filename, content_type, None
                    else:
                        # Multiple matches
                        descriptions = [
                            f"{i+1}. {desc} ({category} match)"
                            for i, (_, _, _, _, desc, category) in enumerate(similarities[:5])
                        ]
                        matches = [(doc_id, file_id, filename) for _, doc_id, file_id, filename, _, _ in similarities[:5]]
                        logger.debug("\nMultiple matches found:")
                        for i, (doc_id, file_id, filename) in enumerate(matches):
                            logger.debug(f"{i+1}. ID: {doc_id}, File ID: {file_id}, Filename: {filename}")
                        return None, None, None, (descriptions, matches)

                return None, None, None, None

        except Exception as e:
            logger.error(f"Error retrieving document: {str(e)}")
            return None, None, None, None