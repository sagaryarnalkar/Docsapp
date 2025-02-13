from flask import Flask, send_from_directory, request, jsonify
import logging
import os
import sys
# Add these to your imports
import json
import requests
from datetime import timedelta
from config import TEMP_DIR, BASE_DIR
# Remove webhook imports since we handle it in this file now
# from routes.webhook import handle_webhook, handle_oauth_callback
from models.user_state import UserState
from models.docs_app import DocsApp
from routes.handlers import AuthHandler, MediaHandler, DocumentHandler, CommandHandler
from routes.handlers.whatsapp_handler import WhatsAppHandler
from dotenv import load_dotenv

# At the top with your other imports
from config import (
    TEMP_DIR,
    BASE_DIR,
    WHATSAPP_API_VERSION,
    WHATSAPP_PHONE_NUMBER_ID,
    WHATSAPP_ACCESS_TOKEN,
    WHATSAPP_BUSINESS_ACCOUNT_ID
)

# Ensure logs directory exists
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Set up file logging
log_file = os.path.join(LOG_DIR, 'docsapp.log')

# Configure logging to both file and stdout with immediate flush
class UnbufferedLogger:
    def __init__(self, stream):
        self.stream = stream
    def write(self, data):
        self.stream.write(data)
        self.stream.flush()
    def writelines(self, datas):
        self.stream.writelines(datas)
        self.stream.flush()
    def __getattr__(self, attr):
        return getattr(self.stream, attr)

sys.stdout = UnbufferedLogger(sys.stdout)
sys.stderr = UnbufferedLogger(sys.stderr)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def log_debug(message):
    """Force immediate logging output"""
    print(f"[DEBUG] {message}", flush=True)
    sys.stdout.flush()
    logger.debug(message)

# Add direct stdout logging for critical debug info
print("=== Application Starting ===")
print(f"Log file location: {log_file}")
print(f"Temp directory: {TEMP_DIR}")
print(f"Base directory: {BASE_DIR}")

app = Flask(__name__)

# Initialize all required objects
user_state = UserState()
docs_app = DocsApp()
pending_descriptions = {}
user_documents = {}

# Initialize all handlers
auth_handler = AuthHandler(user_state)
media_handler = MediaHandler(docs_app, pending_descriptions)
document_handler = DocumentHandler(docs_app, user_documents)
command_handler = CommandHandler(media_handler, document_handler)
whatsapp_handler = WhatsAppHandler(docs_app, pending_descriptions, user_state)  # Pass user_state

@app.before_request
def before_request():
    """Log details of every incoming request"""
    print("\n=== New Request ===")
    print(f"Method: {request.method}")
    print(f"URL: {request.url}")
    print(f"Headers: {dict(request.headers)}")
    if request.form:
        print(f"Form Data: {dict(request.form)}")
    if request.args:
        print(f"Query Args: {dict(request.args)}")

@app.route("/")
def home():
    print("Home route accessed")
    return """
    <html>
        <body style="display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif; background-color: #f5f5f5;">
            <div style="text-align: center; padding: 20px; background-color: white; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h1>DocsApp WhatsApp Bot</h1>
                <p>Status: Running ✅</p>
                <p>Send a message to +14155238886 on WhatsApp to get started!</p>
            </div>
        </body>
    </html>
    """

async def test_whatsapp_handler(data):
    """Simple test handler that doubles the input text"""
    try:
        log_debug("\n=== Starting test_whatsapp_handler ===")
        
        # Extract the message
        log_debug("Step 1: Extracting entry from data")
        entry = data.get('entry', [{}])[0]
        log_debug(f"Entry: {json.dumps(entry, indent=2)}")
        
        log_debug("\nStep 2: Extracting changes")
        changes = entry.get('changes', [{}])[0]
        log_debug(f"Changes: {json.dumps(changes, indent=2)}")
        
        log_debug("\nStep 3: Extracting value")
        value = changes.get('value', {})
        log_debug(f"Value: {json.dumps(value, indent=2)}")
        
        log_debug("\nStep 4: Extracting messages")
        messages = value.get('messages', [])
        log_debug(f"Messages: {json.dumps(messages, indent=2)}")
        
        if not messages:
            log_debug("No messages found - returning False")
            return False
            
        log_debug("\nStep 5: Getting first message")
        message = messages[0]
        log_debug(f"Message: {json.dumps(message, indent=2)}")
        
        if message.get('type') != 'text':
            log_debug(f"Not a text message: {message.get('type')} - returning False")
            return False
            
        # Get the text and sender
        log_debug("\nStep 6: Extracting text and sender")
        text = message.get('text', {}).get('body', '')
        from_number = message.get('from')
        log_debug(f"Text: {text}")
        log_debug(f"From: {from_number}")
        
        # Double the text
        log_debug("\nStep 7: Creating response text")
        response_text = text + text
        log_debug(f"Response text: {response_text}")
        
        # Prepare WhatsApp API request
        log_debug("\nStep 8: Preparing WhatsApp API request")
        url = f'https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages'
        headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        response_data = {
            'messaging_product': 'whatsapp',
            'to': from_number,
            'type': 'text',
            'text': {'body': response_text}
        }
        
        log_debug(f"URL: {url}")
        log_debug(f"Headers (excluding auth): {json.dumps({k:v for k,v in headers.items() if k != 'Authorization'}, indent=2)}")
        log_debug(f"Request data: {json.dumps(response_data, indent=2)}")
        
        log_debug("\nStep 9: Sending WhatsApp API request")
        response = requests.post(url, headers=headers, json=response_data)
        log_debug(f"Response Status: {response.status_code}")
        log_debug(f"Response Body: {response.text}")
        
        log_debug("\nStep 10: Handler completed successfully - returning True")
        return True
        
    except Exception as e:
        log_debug("\n=== Error in test handler ===")
        log_debug(f"Error type: {type(e).__name__}")
        log_debug(f"Error message: {str(e)}")
        import traceback
        log_debug(f"Traceback:\n{traceback.format_exc()}")
        return False

@app.route("/whatsapp-webhook", methods=['GET', 'POST'])
async def whatsapp_route():
    try:
        log_debug("\n=== WhatsApp Webhook Called ===")
        log_debug(f"Method: {request.method}")
        log_debug(f"URL: {request.url}")
        log_debug(f"Headers: {dict(request.headers)}")

        if request.method == "GET":
            log_debug("\nProcessing GET request (verification)")
            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            
            log_debug(f"Verification Request:")
            log_debug(f"Mode: {mode}")
            log_debug(f"Token: {token}")
            log_debug(f"Challenge: {challenge}")
            
            VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'sagar')
            log_debug(f"Expected token: {VERIFY_TOKEN}")
            
            if mode == "subscribe" and token == VERIFY_TOKEN:
                log_debug("Verification successful - returning challenge")
                return challenge
                
            log_debug("Verification failed - returning 403")
            return "Forbidden", 403

        else:
            log_debug("\nProcessing POST request (incoming message)")
            try:
                # Log request details
                log_debug("\nStep 1: Getting request details")
                log_debug(f"Content-Type: {request.content_type}")
                raw_data = request.get_data()
                log_debug(f"Raw data length: {len(raw_data)} bytes")
                decoded_data = raw_data.decode('utf-8')
                log_debug(f"Decoded data: {decoded_data}")
                
                # Parse JSON
                log_debug("\nStep 2: Parsing JSON data")
                data = request.get_json()
                log_debug(f"Parsed JSON: {json.dumps(data, indent=2)}")
                
                # Call test handler
                log_debug("\nStep 3: Calling test handler")
                success = await test_whatsapp_handler(data)
                log_debug(f"Handler result: {success}")
                
                if success:
                    log_debug("Handler succeeded - returning 200")
                    return "OK", 200
                else:
                    log_debug("Handler failed - returning 500")
                    return "Handler failed", 500
                
            except Exception as e:
                log_debug("\n=== Error processing message ===")
                log_debug(f"Error type: {type(e).__name__}")
                log_debug(f"Error message: {str(e)}")
                import traceback
                log_debug(f"Traceback:\n{traceback.format_exc()}")
                return "Error", 500

    except Exception as e:
        log_debug("\n=== Webhook Error ===")
        log_debug(f"Error type: {type(e).__name__}")
        log_debug(f"Error message: {str(e)}")
        import traceback
        log_debug(f"Traceback:\n{traceback.format_exc()}")
        return "Error", 500

@app.route("/oauth2callback")
def oauth2callback():
    """Handle OAuth callback from Google"""
    try:
        # Get authorization code from query parameters
        code = request.args.get('code')
        state = request.args.get('state')
        
        if code:
            # Store the authorization code
            user_state.store_auth_code(code, state)
            return "Authorization successful! You can close this window and return to WhatsApp."
        return "Authorization failed!"

    except Exception as e:
        logger.error(f"Error in oauth2callback: {str(e)}")
        return str(e), 500

@app.route('/temp/<path:filename>')
def serve_file(filename):
    print(f"Serving file: {filename}")
    return send_from_directory(TEMP_DIR, filename)

# Add this route to test WhatsApp sending
@app.route("/test-whatsapp")
def test_whatsapp():
    output = []
    try:
        # Debug environment variables
        output.append("=== Environment Variables Debug ===")
        output.append(f"WHATSAPP_API_VERSION: {os.getenv('WHATSAPP_API_VERSION')}")
        output.append(f"WHATSAPP_PHONE_NUMBER_ID: {os.getenv('WHATSAPP_PHONE_NUMBER_ID')}")
        output.append(f"WHATSAPP_BUSINESS_ACCOUNT_ID: {os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID')}")
        output.append(f"Access Token Length: {len(os.getenv('WHATSAPP_ACCESS_TOKEN', ''))} characters")
        
        test_phone = '919823623966'  # Your number
        url = f'https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages'
        
        output.append("\n=== Request Configuration ===")
        output.append(f"Target Phone: {test_phone}")
        output.append(f"API URL: {url}")

        headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }

        data = {
            'messaging_product': 'whatsapp',
            'to': test_phone,
            'type': 'text',
            'text': {'body': "🔄 Test message from DocsApp! If you receive this, the WhatsApp integration is working."}
        }

        output.append("\n=== Request Details ===")
        output.append(f"Headers (without auth): {json.dumps({k:v for k,v in headers.items() if k != 'Authorization'}, indent=2)}")
        output.append(f"Request Data: {json.dumps(data, indent=2)}")

        # Print debug info before making request
        print("\n=== Making WhatsApp API Request ===")
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        print(f"Data: {json.dumps(data, indent=2)}")

        response = requests.post(url, headers=headers, json=data)

        output.append("\n=== Response Details ===")
        output.append(f"Response Status: {response.status_code}")
        output.append(f"Response Headers: {dict(response.headers)}")
        output.append(f"Response Body: {response.text}")

        # Print debug info after response
        print("\n=== WhatsApp API Response ===")
        print(f"Status: {response.status_code}")
        print(f"Body: {response.text}")

        html_output = "<br>".join(output).replace("\n", "<br>")
        return f"<pre>{html_output}</pre>"

    except Exception as e:
        import traceback
        error_info = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}\n\nDebug Info:\n" + "\n".join(output)
        print(f"\n=== Test WhatsApp Error ===\n{error_info}")
        return f"<pre>{error_info}</pre>"

@app.route("/test_log")
def test_log():
    print("=== Testing Logging ===")
    print("If you see this in the logs, logging is working")
    return "Test logged. Check error logs."

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route("/test-webhook", methods=['GET'])
async def test_webhook():
    """Test route to simulate a WhatsApp message"""
    try:
        # Simulate a WhatsApp text message
        test_data = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "14155238886",
                            "phone_number_id": WHATSAPP_PHONE_NUMBER_ID
                        },
                        "messages": [{
                            "from": "919850132361",
                            "id": "wamid.test123",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {
                                "body": "help"
                            }
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        print("\n=== Testing Webhook Handler ===")
        print(f"Test Data: {json.dumps(test_data, indent=2)}")

        result = await whatsapp_handler.handle_incoming_message(test_data)
        return jsonify({
            "status": "success",
            "result": result,
            "message": "Test completed"
        })

    except Exception as e:
        print(f"Test Error: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

if __name__ == "__main__":
    app.run(debug=True)