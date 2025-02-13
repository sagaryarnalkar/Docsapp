# routes/handlers/auth_handler.py
import os
import json
import logging
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from config import BASE_DIR, TEMP_DIR, SCOPES, OAUTH_REDIRECT_URI
from utils.response_builder import ResponseBuilder

logger = logging.getLogger(__name__)

class AuthHandler:
    def __init__(self, user_state):
        self.user_state = user_state
        # Ensure temp directory exists
        os.makedirs(TEMP_DIR, exist_ok=True)

    def handle_authorization(self, user_phone):
        """Handle Google Drive authorization"""
        try:
            print(f"\n=== Starting Authorization for {user_phone} ===")
            
            # Load client configuration
            credentials_path = os.path.join(BASE_DIR, 'credentials.json')
            print(f"Loading credentials from: {credentials_path}")
            print(f"Current directory: {os.getcwd()}")
            print(f"BASE_DIR: {BASE_DIR}")
            
            if not os.path.exists(credentials_path):
                print(f"ERROR: credentials.json not found at {credentials_path}")
                return "❌ Error: OAuth credentials file not found."
            
            with open(credentials_path, 'r') as f:
                client_config = json.load(f)
                print("Successfully loaded client config")
                print(f"Redirect URI from config: {OAUTH_REDIRECT_URI}")
            
            # Create flow using client config
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=OAUTH_REDIRECT_URI
            )
            print("Successfully created OAuth flow")
            
            # Generate authorization URL
            auth_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            print(f"Generated auth URL: {auth_url}")
            
            # Store user phone for callback
            temp_file_path = os.path.join(TEMP_DIR, 'temp_user.txt')
            print(f"Storing user phone in: {temp_file_path}")
            with open(temp_file_path, 'w') as f:
                f.write(user_phone)
            print(f"Successfully stored user phone: {user_phone}")
            
            response = ResponseBuilder.get_auth_message(auth_url)
            print(f"Auth response: {response}")
            return response
            
        except Exception as e:
            logger.error(f"Error in handle_authorization: {str(e)}")
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Traceback: {error_trace}")
            print(f"Authorization Error: {str(e)}")
            print(f"Traceback: {error_trace}")
            return f"❌ Error setting up authorization: {str(e)}"

    def _get_success_html(self):
        """Get HTML for successful authorization"""
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

    def _get_error_html(self, error):
        """Get HTML for failed authorization"""
        return f"""
        <html>
            <body style="display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif;">
                <div style="text-align: center; padding: 20px;">
                    <h1 style="color: #f44336;">❌ Authorization Failed</h1>
                    <p style="font-size: 18px;">Error: {error}</p>
                    <p>Please try again. You can close this window and return to WhatsApp.</p>
                </div>
            </body>
        </html>
        """

    def handle_oauth_callback(self, request_url):
        """Handle OAuth callback"""
        try:
            logger.debug(f"OAuth callback received. URL: {request_url}")
            
            # Load client configuration
            with open(os.path.join(BASE_DIR, 'credentials.json'), 'r') as f:
                client_config = json.load(f)
            
            # Create flow using client config
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=OAUTH_REDIRECT_URI
            )
            
            # Fetch token using the callback URL
            flow.fetch_token(authorization_response=request_url)
            
            # Get credentials and store them
            creds = flow.credentials
            token_data = json.loads(creds.to_json())
            
            # Get user phone from temp file
            temp_user_file = os.path.join(TEMP_DIR, 'temp_user.txt')
            if os.path.exists(temp_user_file):
                with open(temp_user_file, 'r') as f:
                    phone = f.read().strip()
                self.user_state.store_tokens(phone, token_data)
                os.remove(temp_user_file)
                logger.debug(f"Successfully stored tokens for user {phone}")
                return self._get_success_html()
            else:
                logger.error("No temp user file found")
                return self._get_error_html("User session expired. Please try again.")
            
        except Exception as e:
            logger.error(f"Error in OAuth callback: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return self._get_error_html(str(e))

    def handle_auth(self, phone):
        """Handle authentication"""
        try:
            return self.user_state.is_authorized(phone)
        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            return False