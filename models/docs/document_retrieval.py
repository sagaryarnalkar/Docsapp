import logging
from ..database import Session, Document
from sqlalchemy import func
from .document_processing import calculate_similarity

logger = logging.getLogger(__name__)

async def get_user_documents_from_drive(service, user_phone):
    """Get all documents created by our app for a specific user from Drive"""
    try:
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
        logger.error(f"Error retrieving user documents from Drive: {str(e)}")
        return []

async def get_user_documents_from_db(user_phone):
    """Get all documents for a specific user from the database"""
    try:
        with Session() as session:
            docs = session.query(Document).filter(
                Document.user_phone == user_phone
            ).order_by(Document.upload_date.desc()).all()
            
            return [
                {
                    'id': doc.id,
                    'file_id': doc.file_id,
                    'filename': doc.filename,
                    'description': doc.description,
                    'upload_date': doc.upload_date,
                    'mime_type': doc.mime_type,
                    'data_store_id': doc.data_store_id,
                    'document_id': doc.document_id
                }
                for doc in docs
            ]
    except Exception as e:
        logger.error(f"Error retrieving user documents from DB: {str(e)}")
        return []

async def find_documents_by_query(user_phone, query):
    """Find documents matching a query"""
    try:
        with Session() as session:
            # Get all user documents
            docs = session.query(Document).filter(
                Document.user_phone == user_phone
            ).all()
            
            # Filter and score documents based on query match
            scored_docs = []
            for doc in docs:
                # Calculate similarity between query and document name/description
                name_score = calculate_similarity(query, doc.filename)
                desc_score = 0
                if doc.description:
                    desc_score = calculate_similarity(query, doc.description)
                
                # Use the higher score
                score = max(name_score, desc_score)
                
                # Add to results if score is above threshold
                if score > 0.1:  # Adjust threshold as needed
                    scored_docs.append({
                        'id': doc.id,
                        'file_id': doc.file_id,
                        'filename': doc.filename,
                        'description': doc.description,
                        'upload_date': doc.upload_date,
                        'mime_type': doc.mime_type,
                        'data_store_id': doc.data_store_id,
                        'document_id': doc.document_id,
                        'score': score
                    })
            
            # Sort by score (descending)
            scored_docs.sort(key=lambda x: x['score'], reverse=True)
            
            return scored_docs
    except Exception as e:
        logger.error(f"Error finding documents: {str(e)}")
        return []

async def count_user_documents(user_phone):
    """Count the number of documents a user has"""
    try:
        with Session() as session:
            count = session.query(func.count(Document.id)).filter(
                Document.user_phone == user_phone
            ).scalar()
            return count
    except Exception as e:
        logger.error(f"Error counting user documents: {str(e)}")
        return 0 