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
            print(f"\n{'='*50}")
            print(f"OAUTH FLOW START - Phone: {user_phone}")
            print(f"{'='*50}")
            
            # Try multiple possible paths for credentials
            possible_paths = [
                os.path.join(BASE_DIR, 'credentials.json'),
                '/app/credentials.json',
                os.path.join(os.getcwd(), 'credentials.json')
            ]
            
            print("\n=== Checking Credentials ===")
            credentials_found = False
            credentials_path = None
            client_config = None
            
            # First check if the environment variable is set
            oauth_creds = os.environ.get('OAUTH_CREDENTIALS')
            if oauth_creds:
                print("Found OAUTH_CREDENTIALS in environment")
                try:
                    client_config = json.loads(oauth_creds)
                    print("Successfully parsed credentials from environment")
                    print(f"Redirect URIs in config: {client_config.get('web', {}).get('redirect_uris', [])}")
                    credentials_found = True
                except json.JSONDecodeError as e:
                    print(f"Error parsing credentials from environment: {str(e)}")
            
            # If environment variable didn't work, try file paths
            if not credentials_found:
                for path in possible_paths:
                    print(f"Checking path: {path}")
                    if os.path.exists(path):
                        print(f"Found credentials at: {path}")
                        try:
                            with open(path, 'r') as f:
                                content = f.read()
                                client_config = json.loads(content)
                                print(f"Redirect URIs in config file: {client_config.get('web', {}).get('redirect_uris', [])}")
                                credentials_path = path
                                credentials_found = True
                                break
                        except Exception as e:
                            print(f"Error reading {path}: {str(e)}")
            
            if not credentials_found:
                print("\n=== ERROR: No Valid Credentials Found ===")
                print(f"Current directory: {os.getcwd()}")
                print(f"BASE_DIR: {BASE_DIR}")
                print(f"Available environment variables: {list(os.environ.keys())}")
                return "❌ Error: OAuth credentials not found"
            
            print("\n=== Creating OAuth Flow ===")
            print(f"Using redirect URI: {OAUTH_REDIRECT_URI}")
            
            # Create flow using client config
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=OAUTH_REDIRECT_URI
            )
            
            # Generate authorization URL with state parameter
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            
            print("\n=== Generated Auth URL ===")
            print(f"Full Auth URL: {auth_url}")
            print(f"State parameter: {state}")
            
            # Store user phone for callback
            temp_file_path = os.path.join(TEMP_DIR, 'temp_user.txt')
            print(f"\nStoring user data at: {temp_file_path}")
            with open(temp_file_path, 'w') as f:
                f.write(user_phone)
            
            print("\n=== OAuth Flow Setup Complete ===")
            return auth_url
            
        except Exception as e:
            print(f"\n{'='*50}")
            print("OAUTH FLOW ERROR")
            print(f"Error: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            print(f"{'='*50}\n")
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
            print("\n=== Processing OAuth Callback ===")
            
            # Force HTTPS for the callback URL
            if request_url.startswith('http://'):
                request_url = 'https://' + request_url[7:]
            print(f"Using secure URL: {request_url}")
            
            # Try multiple possible paths for credentials
            possible_paths = [
                os.path.join(BASE_DIR, 'credentials.json'),
                '/app/credentials.json',
                os.path.join(os.getcwd(), 'credentials.json')
            ]
            
            print("Checking possible credential paths:")
            credentials_found = False
            client_config = None
            
            # First check if the environment variable is set
            oauth_creds = os.environ.get('OAUTH_CREDENTIALS')
            if oauth_creds:
                print("Found OAUTH_CREDENTIALS in environment, attempting to use it directly")
                try:
                    client_config = json.loads(oauth_creds)
                    print("Successfully parsed credentials from environment")
                    credentials_found = True
                except json.JSONDecodeError as e:
                    print(f"Error parsing credentials from environment: {str(e)}")
            
            # If environment variable didn't work, try file paths
            if not credentials_found:
                for path in possible_paths:
                    print(f"Trying path: {path}")
                    if os.path.exists(path):
                        print(f"Found credentials at: {path}")
                        try:
                            with open(path, 'r') as f:
                                content = f.read()
                                print(f"File contents length: {len(content)}")
                                client_config = json.loads(content)
                                print(f"Successfully loaded credentials from: {path}")
                                credentials_found = True
                                break
                        except json.JSONDecodeError as e:
                            print(f"JSON parsing error for {path}: {str(e)}")
                        except Exception as e:
                            print(f"Error reading {path}: {str(e)}")
                    else:
                        print(f"Path does not exist: {path}")
            
            if not credentials_found:
                print("\nCredentials not found in any location")
                print(f"Current directory: {os.getcwd()}")
                print(f"BASE_DIR: {BASE_DIR}")
                print(f"Directory contents of {BASE_DIR}: {os.listdir(BASE_DIR)}")
                print(f"Directory contents of /app: {os.listdir('/app')}")
                print("Environment variables:", list(os.environ.keys()))
                error_msg = "OAuth credentials file not found"
                logger.error(error_msg)
                return self._get_error_html(error_msg)
            
            if not client_config:
                error_msg = "Invalid credentials format"
                logger.error(error_msg)
                return self._get_error_html(error_msg)
            
            if 'web' not in client_config:
                error_msg = "Invalid credentials format - missing 'web' configuration"
                logger.error(error_msg)
                print("Error: Missing 'web' key in credentials")
                print(f"Available keys: {list(client_config.keys())}")
                return self._get_error_html(error_msg)
            
            print("\nCredentials loaded successfully")
            print(f"Client config keys: {list(client_config.keys())}")
            print(f"Web config keys: {list(client_config['web'].keys())}")
            print(f"Redirect URI from config: {OAUTH_REDIRECT_URI}")
            
            # Create flow using client config
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=OAUTH_REDIRECT_URI
            )
            print("Successfully created OAuth flow")
            
            # Fetch token using the callback URL
            flow.fetch_token(authorization_response=request_url)
            print("Successfully fetched token")
            
            # Get credentials and store them
            creds = flow.credentials
            token_data = json.loads(creds.to_json())
            print("Successfully generated token data")
            
            # Get user phone from temp file
            temp_user_file = os.path.join(TEMP_DIR, 'temp_user.txt')
            print(f"Looking for temp user file at: {temp_user_file}")
            if os.path.exists(temp_user_file):
                with open(temp_user_file, 'r') as f:
                    phone = f.read().strip()
                print(f"Found phone number: {phone}")
                self.user_state.store_tokens(phone, token_data)
                os.remove(temp_user_file)
                print("Successfully stored tokens and cleaned up temp file")
                return self._get_success_html()
            
            error_msg = "User session expired. Please try again."
            logger.error("No temp user file found")
            print(f"Temp file not found at {temp_user_file}")
            print(f"TEMP_DIR contents: {os.listdir(TEMP_DIR)}")
            return self._get_error_html(error_msg)
            
        except Exception as e:
            logger.error(f"Error in OAuth callback: {str(e)}")
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Traceback: {error_trace}")
            print(f"OAuth Callback Error: {str(e)}")
            print(f"Traceback: {error_trace}")
            return self._get_error_html(str(e))

    def handle_auth(self, phone):
        """Handle authentication"""
        try:
            return self.user_state.is_authorized(phone)
        except Exception as e:
            logger.error(f"Auth error: {str(e)}")
            return False