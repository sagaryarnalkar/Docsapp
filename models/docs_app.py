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
from config import DB_DIR, SCOPES, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS
from models.user_state import UserState
from models.database import DatabasePool
from .database import Session, Document
from .rag_processor import RAGProcessor
import asyncio

logger = logging.getLogger(__name__)
user_state = UserState()

class DocsApp:
    def __init__(self):
        """Initialize the DocsApp with necessary services"""
        try:
            # Initialize RAG processor
            print("\n=== Initializing DocsApp ===")
            print(f"Project ID: {GOOGLE_CLOUD_PROJECT}")
            print(f"Location: {GOOGLE_CLOUD_LOCATION}")
            print(f"Credentials path: {GOOGLE_APPLICATION_CREDENTIALS}")
            
            self.rag_processor = RAGProcessor(
                project_id=GOOGLE_CLOUD_PROJECT,
                location=GOOGLE_CLOUD_LOCATION,
                credentials_path=GOOGLE_APPLICATION_CREDENTIALS
            )
            print("✅ RAG processor initialized successfully")
            
        except Exception as e:
            print(f"❌ Error initializing DocsApp: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            self.rag_processor = None
        self.db_pool = DatabasePool('documents.db')
        self.folder_name = 'DocsApp Files'  # Exact match for the folder name in Google Drive
        self.drive_service = None

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

    async def store_document(self, user_phone, file_path, description, filename):
        """Store document in Drive and metadata in SQLite"""
        try:
            print(f"\n=== Storing Document ===")
            print(f"User: {user_phone}")
            print(f"File: {filename}")
            print(f"Description: {description}")
            
            # Validate inputs
            if not user_phone or not file_path or not filename:
                logger.error("Missing required parameters for document storage")
                return False
                
            # Verify file exists
            if not os.path.exists(file_path):
                logger.error(f"File not found at path: {file_path}")
                return False
                
            # Get Drive service using user's OAuth credentials
            service = self._get_drive_service(user_phone)
            if not service:
                logger.error("Failed to get Drive service")
                return False

            # Get or create DocsApp folder
            folder_id = self._get_or_create_folder(service, self.folder_name)
            if not folder_id:
                logger.error("Failed to get/create Drive folder")
                return False

            print("Uploading file to Drive...")
            try:
                # Upload file to Drive with specific permissions
                file_metadata = {
                    'name': filename,
                    'parents': [folder_id],
                    'appProperties': {
                        'docsapp_owner': user_phone,  # Tag file with owner info
                        'docsapp_created': 'true'     # Mark as created by our app
                    }
                }
                
                media = MediaFileUpload(
                    file_path,
                    resumable=True
                )
                
                file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, mimeType',
                    supportsAllDrives=True
                ).execute()
                
                print(f"File uploaded to Drive with ID: {file['id']}")
                print(f"MIME Type: {file.get('mimeType')}")
                
                # Verify file exists and is accessible
                try:
                    verification = service.files().get(
                        fileId=file['id'],
                        fields='id, name, mimeType',
                        supportsAllDrives=True
                    ).execute()
                    print(f"✅ File verification successful: {verification.get('name')}")
                except Exception as ve:
                    print(f"❌ File verification failed: {str(ve)}")
                    return False
                
                # Set file permissions to ensure access
                try:
                    permission = {
                        'type': 'user',
                        'role': 'writer',
                        'emailAddress': self.rag_processor.credentials.service_account_email
                    }
                    service.permissions().create(
                        fileId=file['id'],
                        body=permission,
                        fields='id',
                        supportsAllDrives=True
                    ).execute()
                    print("✅ File permissions set successfully")
                except Exception as pe:
                    print(f"❌ Error setting file permissions: {str(pe)}")
                    return False
                
            except Exception as e:
                logger.error(f"Drive upload failed: {str(e)}")
                return False

            # Store metadata in SQLite without waiting for RAG processing
            print("\nStoring document metadata...")
            try:
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
                    print("Document metadata stored successfully")
            except Exception as e:
                logger.error(f"Database storage failed: {str(e)}")
                # Try to delete the file from Drive since DB storage failed
                try:
                    service.files().delete(fileId=file['id']).execute()
                except Exception as del_err:
                    logger.error(f"Failed to delete file from Drive after DB error: {str(del_err)}")
                return False

            # Process document with RAG
            print("\nProcessing document with RAG...")
            try:
                if self.rag_processor and self.rag_processor.is_available:
                    # Add delay to ensure file is fully available
                    await asyncio.sleep(2)
                    rag_result = await self.rag_processor.process_document_async(
                        file['id'],
                        file.get('mimeType'),
                        user_phone
                    )
                    print(f"RAG processing result: {rag_result}")
                    
                    if rag_result.get('status') == 'success':
                        # Update document with RAG processing results
                        with Session() as session:
                            doc = session.query(Document).filter(
                                Document.file_id == file['id']
                            ).first()
                            if doc:
                                doc.data_store_id = rag_result.get('data_store_id')
                                doc.document_id = rag_result.get('document_id')
                                session.commit()
                                print("Updated document with RAG processing results")
                    else:
                        print(f"RAG processing failed: {rag_result.get('error')}")
                else:
                    print("RAG processor not available")
            except Exception as e:
                print(f"Error in RAG processing: {str(e)}")
                import traceback
                print(f"RAG processing traceback:\n{traceback.format_exc()}")
                # Don't return False here - the document is still stored

            return {
                'status': 'success',
                'file_id': file['id'],
                'mime_type': file.get('mimeType')
            }

        except Exception as e:
            print(f"Error storing document: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Error storing document: {str(e)}")
            return False

    async def ask_question(self, user_phone, question):
        """Ask a question about the user's documents"""
        try:
            print(f"\n{'='*50}")
            print("PROCESSING QUESTION")
            print(f"User: {user_phone}")
            print(f"Question: {question}")
            print(f"{'='*50}\n")
            
            # Check if RAG processor is initialized
            if self.rag_processor is None:
                print("❌ RAG processor is not initialized")
                return {
                    "status": "error",
                    "message": "Document Q&A feature is not available at the moment. Please try again later."
                }
            
            # Verify that query_documents method exists
            if not hasattr(self.rag_processor, 'query_documents'):
                print("❌ RAG processor does not have query_documents method")
                print(f"RAG processor type: {type(self.rag_processor)}")
                print(f"RAG processor attributes: {dir(self.rag_processor)}")
                return {
                    "status": "error",
                    "message": "Document Q&A feature is not properly configured. Please contact support."
                }
            
            # Get all data store IDs for the user's documents
            with Session() as session:
                print("\n=== Checking Available Documents ===")
                # First get all documents
                all_docs = session.query(Document).filter(
                    Document.user_phone == user_phone
                ).all()
                print(f"Total documents found: {len(all_docs)}")
                
                # Then filter for processed ones
                docs = [doc for doc in all_docs if doc.data_store_id is not None]
                print(f"Processed documents: {len(docs)}")
                
                if all_docs and not docs:
                    print("Documents found but none are processed yet")
                    return {
                        "status": "error",
                        "message": "Your documents are still being processed. Please try again in a few moments."
                    }
                
                if not docs:
                    print("No documents found at all")
                    return {
                        "status": "error",
                        "message": "No processed documents found to answer questions from. Please upload some documents first."
                    }
                
                print("\n=== Available Documents ===")
                for doc in docs:
                    print(f"- {doc.filename}")
                    print(f"  ID: {doc.file_id}")
                    print(f"  Data Store ID: {doc.data_store_id}")
                
                # Query across all user's documents
                print("\n=== Querying Documents ===")
                all_answers = []
                for doc in docs:
                    print(f"\nQuerying document: {doc.filename}")
                    try:
                        # Debug info
                        print(f"RAG processor type: {type(self.rag_processor)}")
                        print(f"Data store ID: {doc.data_store_id}")
                        print(f"Question: {question}")
                        
                        result = await self.rag_processor.query_documents(
                            question,
                            doc.data_store_id
                        )
                        print(f"Query result status: {result.get('status')}")
                        if result.get("status") == "success":
                            print("Successfully got answer")
                            all_answers.append({
                                "answer": result["answer"],
                                "document": doc.filename,
                                "sources": result["sources"]
                            })
                        else:
                            print(f"Query failed: {result.get('error')}")
                    except Exception as e:
                        print(f"Error querying document {doc.filename}: {str(e)}")
                        import traceback
                        print(f"Query error traceback:\n{traceback.format_exc()}")
                        continue

                if not all_answers:
                    print("\nNo answers found in any documents")
                    return {
                        "status": "error",
                        "message": "No relevant information found in your documents."
                    }

                print(f"\nFound {len(all_answers)} answers")
                return {
                    "status": "success",
                    "answers": all_answers
                }

        except Exception as e:
            print(f"\n{'='*50}")
            print("ERROR PROCESSING QUESTION")
            print(f"Error: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            print(f"{'='*50}")
            logger.error(f"Error processing question: {str(e)}")
            return {
                "status": "error",
                "message": f"Error processing your question: {str(e)}"
            }

    def get_document_summary(self, user_phone, file_id):
        """Get a summary of a specific document"""
        try:
            with Session() as session:
                doc = session.query(Document).filter(
                    Document.user_phone == user_phone,
                    Document.file_id == file_id
                ).first()
                
                if not doc or not doc.data_store_id:
                    return {
                        "status": "error",
                        "message": "Document not found or not processed yet."
                    }
                
                return self.rag_processor.get_document_summary(
                    doc.data_store_id,
                    doc.document_id
                )

        except Exception as e:
            logger.error(f"Error getting document summary: {str(e)}")
            return {
                "status": "error",
                "message": f"Error getting document summary: {str(e)}"
            }

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
        """Get user's Google credentials from user state"""
        try:
            return user_state.get_credentials(user_phone)
        except Exception as e:
            logger.error(f"Error getting user credentials: {str(e)}")
            return None

    async def get_user_documents(self, user_phone):
        """Get all documents created by our app for a specific user"""
        try:
            # Get Drive service using user's OAuth credentials
            service = self._get_drive_service(user_phone)
            if not service:
                logger.error("Failed to get Drive service")
                return []

            # Search for files created by our app for this user
            query = (
                "appProperties has { key='docsapp_created' and value='true' } and "
                f"appProperties has {{ key='docsapp_owner' and value='{user_phone}' }}"
            )
            
            results = service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, createdTime)',
                orderBy='createdTime desc'
            ).execute()

            return results.get('files', [])

        except Exception as e:
            logger.error(f"Error retrieving user documents: {str(e)}")
            return []