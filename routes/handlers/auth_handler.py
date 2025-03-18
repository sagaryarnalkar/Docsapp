# routes/handlers/auth_handler.py
import os
import json
import logging
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from config import BASE_DIR, TEMP_DIR, SCOPES, OAUTH_REDIRECT_URI
from utils.response_builder import ResponseBuilder
from googleapiclient.discovery import build
from models.database import UserToken, get_session

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
            
            # Ensure 'openid' is in the auth URL
            if 'openid' not in auth_url and 'scope=' in auth_url:
                print("Adding openid scope to auth URL")
                scope_index = auth_url.find('scope=')
                if scope_index != -1:
                    # Find the end of the scope parameter
                    next_param = auth_url.find('&', scope_index)
                    if next_param != -1:
                        # Insert openid in the middle
                        auth_url = auth_url[:next_param] + '%20openid' + auth_url[next_param:]
                    else:
                        # Append to the end
                        auth_url = auth_url + '%20openid'
            
            print("\n=== Generated Auth URL ===")
            print(f"Full Auth URL: {auth_url}")
            print(f"State parameter: {state}")
            
            # Store user phone for callback in multiple locations for reliability
            temp_locations = [
                os.path.join(TEMP_DIR, 'temp_user.txt'),
                os.path.join('/tmp/docsapp', 'temp_user.txt'),
                os.path.join('/data/docsapp', 'temp_user.txt'),
                os.path.join('/app', 'temp_user.txt')
            ]
            
            print("\n=== Storing user data ===")
            for temp_file_path in temp_locations:
                try:
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
                    with open(temp_file_path, 'w') as f:
                        f.write(user_phone)
                    print(f"Stored user data at: {temp_file_path}")
                except Exception as e:
                    print(f"Failed to store at {temp_file_path}: {str(e)}")
            
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
            
            try:
                # Fetch token using the callback URL
                flow.fetch_token(authorization_response=request_url)
                print("Successfully fetched token")
            except Exception as token_error:
                # Check if it's a scope mismatch error
                error_str = str(token_error)
                if "Scope has changed" in error_str:
                    print("Detected scope mismatch error, attempting to fix...")
                    try:
                        # Extract the scopes from the error message
                        import re
                        scope_match = re.search(r'to "(.*?)"', error_str)
                        if scope_match:
                            actual_scopes = scope_match.group(1).split()
                            print(f"Actual scopes from response: {actual_scopes}")
                            
                            # Create a new flow with the actual scopes
                            new_flow = Flow.from_client_config(
                                client_config,
                                scopes=actual_scopes,
                                redirect_uri=OAUTH_REDIRECT_URI
                            )
                            
                            # Try again with the correct scopes
                            new_flow.fetch_token(authorization_response=request_url)
                            print("Successfully fetched token with corrected scopes")
                            
                            # Use the new flow instead
                            flow = new_flow
                        else:
                            # If we can't extract the scopes, re-raise the error
                            raise
                    except Exception as retry_error:
                        print(f"Failed to fix scope mismatch: {str(retry_error)}")
                        return self._get_error_html(f"Authorization failed: {str(token_error)}<br><br>Please try again and make sure to approve all requested permissions.")
                else:
                    # If it's not a scope mismatch error, re-raise
                    return self._get_error_html(f"Authorization failed: {str(token_error)}")
            
            # Get credentials and store them
            creds = flow.credentials
            token_data = json.loads(creds.to_json())
            print("Successfully generated token data")
            
            # Get user phone from temp file
            temp_user_file = os.path.join(TEMP_DIR, 'temp_user.txt')
            
            # Try alternative locations if the primary one doesn't exist
            if not os.path.exists(temp_user_file):
                alternative_paths = [
                    os.path.join('/tmp/docsapp', 'temp_user.txt'),
                    os.path.join('/data/docsapp', 'temp_user.txt'),
                    os.path.join('/app', 'temp_user.txt')
                ]
                
                for alt_path in alternative_paths:
                    if os.path.exists(alt_path):
                        print(f"Found temp user file at alternative location: {alt_path}")
                        temp_user_file = alt_path
                        break
            
            print(f"Looking for temp user file at: {temp_user_file}")
            if os.path.exists(temp_user_file):
                with open(temp_user_file, 'r') as f:
                    phone = f.read().strip()
                print(f"Found phone number: {phone}")
                self.user_state.store_tokens(phone, token_data)
                os.remove(temp_user_file)
                print("Successfully stored tokens and cleaned up temp file")
                
                # Send welcome message without depending on userinfo API
                try:
                    # Check if this is a new user or returning user
                    is_new_user = True  # Default to new user
                    
                    # Use ORM to check if this is a returning user
                    session = get_session()
                    try:
                        user_token = session.query(UserToken).filter_by(phone_number=phone).first()
                        if user_token is not None:
                            # This is a returning user
                            is_new_user = False
                    except Exception as e:
                        print(f"Error checking user status: {str(e)}")
                    finally:
                        session.close()
                    
                    # Import WhatsAppHandler here to avoid circular import
                    from routes.handlers.whatsapp_handler import WhatsAppHandler
                    import asyncio
                    
                    # Create a function to send the welcome message
                    async def send_welcome_message():
                        try:
                            # Create a temporary WhatsApp handler
                            from config import WHATSAPP_API_VERSION, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_ACCESS_TOKEN
                            handler = WhatsAppHandler(None, {}, self.user_state)
                            
                            if is_new_user:
                                welcome_msg = (
                                    f"🎉 Welcome to Docverse—You're In! 🎉\n\n"
                                    f"Great news—you're connected to Docverse via your Google Drive! Now, send us your documents, "
                                    f"and we'll index them for lightning-fast access. Your info will be readily available—ask anything "
                                    f"complex with our AI-powered search!\n\n"
                                    f"📋 *Available Commands:*\n"
                                    f"• Send any document to store it\n"
                                    f"• *list* - View your stored documents\n"
                                    f"• *find [text]* - Search for documents\n"
                                    f"• *ask [question]* - Ask questions about your documents\n"
                                    f"• *help* - Show all commands"
                                )
                            else:
                                # Get document count for returning users
                                doc_count = 0
                                try:
                                    from models.database import Document, Session
                                    session = Session()
                                    doc_count = session.query(Document).filter_by(user_phone=phone).count()
                                    session.close()
                                except Exception as e:
                                    print(f"Error getting document count: {str(e)}")
                                
                                welcome_msg = (
                                    f"👋 Welcome back to Docverse!\n\n"
                                    f"We are now connected to your Google Drive. "
                                    f"You have {doc_count} document{'s' if doc_count != 1 else ''} stored.\n\n"
                                    f"📋 *Available Commands:*\n"
                                    f"• Send any document to store it\n"
                                    f"• *list* - View your stored documents\n"
                                    f"• *find [text]* - Search for documents\n"
                                    f"• *ask [question]* - Ask questions about your documents\n"
                                    f"• *help* - Show all commands"
                                )
                            
                            await handler.send_message(phone, welcome_msg)
                            print(f"Sent welcome message to {phone}")
                        except Exception as e:
                            print(f"Error sending welcome message: {str(e)}")
                            import traceback
                            print(f"Traceback:\n{traceback.format_exc()}")
                    
                    # Schedule the welcome message to be sent
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(send_welcome_message())
                    loop.close()
                    
                except Exception as e:
                    print(f"Error sending welcome message: {str(e)}")
                    import traceback
                    print(f"Traceback:\n{traceback.format_exc()}")
            
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