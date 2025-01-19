from flask import request, Response
from datetime import datetime
from twilio.twiml.messaging_response import MessagingResponse
from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os

from config import (
    BASE_DIR, TEMP_DIR, SCOPES, OAUTH_REDIRECT_URI,
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
)
from models.user_state import UserState
from models.docs_app import DocsApp
from .handlers import AuthHandler, MediaHandler, DocumentHandler, CommandHandler
from utils.logger import logger
from utils.response_builder import ResponseBuilder

# Initialize state
user_state = UserState()
docs_app = DocsApp()

# Global dictionaries
pending_descriptions = {}  # Format: {phone_number_index: {'file_path': path, 'filename': name, 'timestamp': datetime}}
user_documents = {}  # Format: {phone_number: [(id, drive_file_id, filename), ...]}

# Initialize handlers
auth_handler = AuthHandler(user_state)
media_handler = MediaHandler(docs_app, pending_descriptions)
document_handler = DocumentHandler(docs_app, user_documents)
command_handler = CommandHandler(media_handler, document_handler)

def handle_webhook():
    """Main webhook handler for WhatsApp messages"""
    start_time = datetime.now()
    
    # Print complete raw request data
    print("\n=== RAW REQUEST DATA ===")
    print("Method:", request.method)
    print("Headers:", dict(request.headers))
    
    # Get raw data
    raw_data = request.get_data()
    print("Raw Data:", raw_data)
    
    # Try to decode if it's binary
    try:
        decoded_data = raw_data.decode('utf-8', errors='ignore')
        print("Decoded Data:", decoded_data)
    except:
        print("Could not decode raw data")
    
    # Print all request attributes
    print("\nAll Request Values:")
    for key in dir(request):
        if not key.startswith('_'):
            try:
                value = getattr(request, key)
                if not callable(value):
                    print(f"{key}: {value}")
            except:
                continue
    
    try:
        # Set default response
        default_response = MessagingResponse()
        default_response.message("❌ Processing your request... Please try again.")
        
        # Parse request
        incoming_msg = request.values.get('Body', '').lower()
        user_phone = request.values.get('From', '')
        has_media = request.values.get('NumMedia', '0') != '0'
        
        print(f"\nProcessing: Message='{incoming_msg}', Phone={user_phone}, Has Media={has_media}")
        
        # Add extra WhatsApp info to request_values
        enhanced_values = dict(request.values)
        enhanced_values['raw_data'] = raw_data
        enhanced_values['raw_headers'] = dict(request.headers)
        
        # Validate user phone
        if not user_phone:
            logger.error("Missing user phone number")
            return str(default_response)

        # Check authorization
        if not user_state.is_authorized(user_phone):
            return auth_handler.handle_authorization(user_phone)

        # Handle media upload
        if has_media:
            response_text = media_handler.handle_media_upload(enhanced_values, user_phone, incoming_msg)
            return ResponseBuilder.create_response(response_text)

        # Handle pending description
        if any(key.startswith(f"{user_phone}_") for key in pending_descriptions):
            response_text = media_handler.handle_pending_description(user_phone, incoming_msg)
            return ResponseBuilder.create_response(response_text)

        # Handle commands
        response_text = command_handler.handle_command(incoming_msg, user_phone, request.values)
        return ResponseBuilder.create_response(response_text)
        
    except Exception as e:
        logger.error(f"Error in webhook: {str(e)}", exc_info=True)
        return str(default_response)
    finally:
        process_time = datetime.now() - start_time
        print(f"Request processed in {process_time.total_seconds()} seconds")

def handle_oauth_callback():
    """Handle OAuth callback from Google"""
    try:
        logger.debug(f"OAuth callback received. URL: {request.url}")
        
        flow = InstalledAppFlow.from_client_secrets_file(
            os.path.join(BASE_DIR, 'credentials.json'),
            SCOPES, 
            redirect_uri=OAUTH_REDIRECT_URI
        )
        
        flow.fetch_token(authorization_response=request.url)
        
        # Get credentials and store them
        creds = flow.credentials
        token_data = json.loads(creds.to_json())
        
        temp_user_file = os.path.join(TEMP_DIR, 'temp_user.txt')
        if os.path.exists(temp_user_file):
            with open(temp_user_file, 'r') as f:
                phone = f.read().strip()
            user_state.store_tokens(phone, token_data)
            os.remove(temp_user_file)
            logger.debug(f"Successfully stored tokens for user {phone}")
        
        return """
        <html>
            <body style="display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif;">
                <div style="text-align: center; padding: 20px;">
                    <h1 style="color: #4CAF50;">✅ Authorization Successful!</h1>
                    <p style="font-size: 18px;">You can now close this window and return to WhatsApp.</p>
                </div>
            </body>
        </html>
        """
    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}")
        return f"""
        <html>
            <body style="display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif;">
                <div style="text-align: center; padding: 20px;">
                    <h1 style="color: #f44336;">❌ Authorization Failed</h1>
                    <p style="font-size: 18px;">Error: {str(e)}</p>
                    <p>Please try again. You can close this window and return to WhatsApp.</p>
                </div>
            </body>
        </html>
        """