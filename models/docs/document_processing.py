import logging
import io
import asyncio
from googleapiclient.http import MediaIoBaseDownload

logger = logging.getLogger(__name__)

def calculate_similarity(text1, text2):
    """Calculate similarity between two texts using Jaccard similarity"""
    # Convert to sets of words
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    # Calculate Jaccard similarity
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))

    return intersection / union if union > 0 else 0

async def process_document_with_rag(rag_processor, file_id, mime_type, user_phone):
    """Process a document with RAG"""
    try:
        if not rag_processor or not rag_processor.is_available:
            logger.error("RAG processor not available")
            return {'status': 'error', 'error': 'RAG processor not available'}
            
        # Add delay to ensure file is fully available
        await asyncio.sleep(2)
        result = await rag_processor.process_document_async(
            file_id,
            mime_type,
            user_phone
        )
        
        return result
    except Exception as e:
        logger.error(f"Error in RAG processing: {str(e)}")
        import traceback
        logger.error(f"RAG processing traceback:\n{traceback.format_exc()}")
        return {'status': 'error', 'error': str(e)}

async def download_and_process_file(service, file_id):
    """Download a file from Drive and extract its text content"""
    try:
        # Get the file metadata
        file = service.files().get(fileId=file_id, fields='name, mimeType').execute()
        
        # Create a BytesIO stream for the file
        request = service.files().get_media(fileId=file_id)
        file_stream = io.BytesIO()
        downloader = MediaIoBaseDownload(file_stream, request)
        
        # Download the file
        done = False
        while not done:
            status, done = downloader.next_chunk()
            
        # Reset stream position
        file_stream.seek(0)
        
        return {
            'content': file_stream.getvalue(),
            'name': file.get('name'),
            'mime_type': file.get('mimeType')
        }
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return None

def generate_search_tokens(text):
    """Generate search tokens from text"""
    # Simple implementation - can be enhanced with NLP or AI
    if not text:
        return []
        
    # Convert to lowercase and split by whitespace
    tokens = text.lower().split()
    
    # Remove duplicates and sort
    unique_tokens = sorted(set(tokens))
    
    # Filter out tokens that are too short
    filtered_tokens = [token for token in unique_tokens if len(token) > 2]
    
    # Return up to 20 tokens
    return filtered_tokens[:20]

def create_html_summary(text):
    """Create a structured HTML summary of the document"""
    if not text:
        return "<p>No content available</p>"
        
    # Simple implementation - just wrap in paragraphs
    paragraphs = text.split('\n\n')
    html = ""
    
    for p in paragraphs:
        if p.strip():
            html += f"<p>{p.strip()}</p>\n"
            
    return html 