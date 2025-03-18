import os
import logging
import asyncio
from datetime import datetime
from googleapiclient.http import MediaFileUpload
from ..database import Session, Document

logger = logging.getLogger(__name__)

async def store_document_in_drive(service, folder_id, file_path, filename, user_phone):
    """Store a document in Google Drive"""
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

        return {
            'file_id': file['id'],
            'mime_type': file.get('mimeType')
        }
    except Exception as e:
        logger.error(f"Drive upload failed: {str(e)}")
        return None

async def verify_file_in_drive(service, file_id):
    """Verify that a file exists and is accessible in Drive"""
    try:
        verification = service.files().get(
            fileId=file_id,
            fields='id, name, mimeType',
            supportsAllDrives=True
        ).execute()
        return verification
    except Exception as e:
        logger.error(f"File verification failed: {str(e)}")
        return None

async def store_document_metadata(user_phone, file_id, filename, description, mime_type):
    """Store document metadata in the database"""
    try:
        with Session() as session:
            doc = Document(
                user_phone=user_phone,
                file_id=file_id,
                filename=filename,
                description=description,
                mime_type=mime_type,
                upload_date=datetime.now()
            )
            session.add(doc)
            session.commit()
            return doc.id
    except Exception as e:
        logger.error(f"Database storage failed: {str(e)}")
        return None

async def update_document_with_rag_data(file_id, data_store_id, document_id):
    """Update a document with RAG processing results"""
    try:
        with Session() as session:
            doc = session.query(Document).filter(
                Document.file_id == file_id
            ).first()
            if doc:
                doc.data_store_id = data_store_id
                doc.document_id = document_id
                session.commit()
                return True
    except Exception as e:
        logger.error(f"Error updating document with RAG data: {str(e)}")
    return False 