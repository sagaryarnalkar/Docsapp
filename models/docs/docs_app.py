import os
import logging
import asyncio
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS
from models.user_state import UserState
from models.database import DatabasePool
from ..rag_processor import RAGProcessor
from .drive_service import get_drive_service, get_or_create_folder, set_file_permissions
from .document_storage import (
    store_document_in_drive, 
    verify_file_in_drive, 
    store_document_metadata,
    update_document_with_rag_data
)
from .document_processing import (
    process_document_with_rag,
    download_and_process_file,
    calculate_similarity
)
from .document_retrieval import (
    get_user_documents_from_drive,
    get_user_documents_from_db,
    find_documents_by_query,
    count_user_documents
)

logger = logging.getLogger(__name__)
user_state = UserState()

class DocsApp:
    """
    Main DocsApp class for document management.
    This class has been refactored to use modular components.
    """
    
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

    def _get_drive_service(self, user_phone):
        """Get or create Google Drive service for the user"""
        try:
            # Get credentials from user state
            credentials = self._get_user_credentials(user_phone)
            if not credentials:
                return None

            return get_drive_service(credentials)
        except Exception as e:
            logger.error(f"Error getting Drive service: {str(e)}")
            return None

    def _get_user_credentials(self, user_phone):
        """Get user's Google credentials from user state"""
        try:
            return user_state.get_credentials(user_phone)
        except Exception as e:
            logger.error(f"Error getting user credentials: {str(e)}")
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
            folder_id = get_or_create_folder(service, self.folder_name)
            if not folder_id:
                logger.error("Failed to get/create Drive folder")
                return False

            print("Uploading file to Drive...")
            # Upload file to Drive
            upload_result = await store_document_in_drive(
                service, folder_id, file_path, filename, user_phone
            )
            
            if not upload_result:
                return False
                
            file_id = upload_result['file_id']
            mime_type = upload_result['mime_type']
            
            # Verify file exists and is accessible
            verification = await verify_file_in_drive(service, file_id)
            if not verification:
                return False
            
            # Set file permissions to ensure access
            try:
                permission_result = set_file_permissions(
                    service, 
                    file_id, 
                    self.rag_processor.credentials.service_account_email
                )
                if not permission_result:
                    logger.error("Failed to set file permissions")
            except Exception as pe:
                logger.error(f"Error setting file permissions: {str(pe)}")
                
            # Store metadata in SQLite without waiting for RAG processing
            print("\nStoring document metadata...")
            doc_id = await store_document_metadata(
                user_phone, file_id, filename, description, mime_type
            )
            
            if not doc_id:
                # Try to delete the file from Drive since DB storage failed
                try:
                    service.files().delete(fileId=file_id).execute()
                except Exception as del_err:
                    logger.error(f"Failed to delete file from Drive after DB error: {str(del_err)}")
                return False

            # Process document with RAG
            print("\nProcessing document with RAG...")
            rag_result = await process_document_with_rag(
                self.rag_processor, file_id, mime_type, user_phone
            )
            
            if rag_result and rag_result.get('status') == 'success':
                # Update document with RAG processing results
                await update_document_with_rag_data(
                    file_id,
                    rag_result.get('data_store_id'),
                    rag_result.get('document_id')
                )
            
            return {
                'status': 'success',
                'file_id': file_id,
                'mime_type': mime_type
            }

        except Exception as e:
            print(f"Error storing document: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Error storing document: {str(e)}")
            return False

    async def get_user_documents(self, user_phone):
        """Get all documents for a specific user"""
        return await get_user_documents_from_db(user_phone)

    async def find_documents(self, user_phone, query):
        """Find documents matching a query"""
        return await find_documents_by_query(user_phone, query)

    async def ask_question(self, user_phone, question):
        """Ask a question about the user's documents"""
        try:
            if not self.rag_processor or not self.rag_processor.is_available:
                return {
                    'status': 'error',
                    'error': 'RAG processor not available'
                }
                
            # Use the RAG processor to answer the question
            response = await self.rag_processor.ask_question_async(
                question, user_phone
            )
            
            return response
        except Exception as e:
            logger.error(f"Error asking question: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            } 