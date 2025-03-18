import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

def get_drive_service(user_credentials):
    """Create a Google Drive service with user credentials"""
    try:
        return build('drive', 'v3', credentials=user_credentials)
    except Exception as e:
        logger.error(f"Error creating Drive service: {str(e)}")
        return None

def get_or_create_folder(service, folder_name):
    """Get or create a folder in Google Drive"""
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
        logger.error(f"Error getting/creating folder: {str(e)}")
        return None

def download_file(service, file_id, mime_type=None):
    """Download a file from Google Drive"""
    try:
        # Get the file metadata
        file = service.files().get(fileId=file_id, fields='name, mimeType').execute()
        
        # Get the file content
        request = service.files().get_media(fileId=file_id)
        file_content = request.execute()
        
        return {
            'content': file_content,
            'name': file.get('name'),
            'mime_type': file.get('mimeType')
        }
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        return None

def set_file_permissions(service, file_id, email, role='writer'):
    """Set permissions for a file in Google Drive"""
    try:
        permission = {
            'type': 'user',
            'role': role,
            'emailAddress': email
        }
        
        service.permissions().create(
            fileId=file_id,
            body=permission,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        return True
    except Exception as e:
        logger.error(f"Error setting file permissions: {str(e)}")
        return False 