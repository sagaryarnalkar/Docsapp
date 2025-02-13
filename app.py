from flask import Flask, send_from_directory, request, jsonify
import logging
import os
import sys
# Add these to your imports
import json
import requests
from datetime import timedelta, datetime
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

# At the very top of the file, after imports
VERSION = "v1.0.1"  # Increment this each time we deploy

print("\n" + "="*50)
print(f"STARTING DOCSAPP SERVER VERSION {VERSION}")
print(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*50 + "\n")

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
    try:
        print("\n" + "="*50)
        print(f"PROCESSING REQUEST - SERVER VERSION {VERSION}")
        print(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Method: {request.method}")
        print(f"URL: {request.url}")
        print(f"Headers: {dict(request.headers)}")
        print("="*50 + "\n")
        
        # Log request body for POST requests
        if request.method == 'POST':
            try:
                raw_data = request.get_data()
                print(f"Raw request data length: {len(raw_data)} bytes")
                print(f"Raw request data: {raw_data.decode('utf-8')}")
            except Exception as e:
                print(f"Error reading request data: {str(e)}")
        
        if request.form:
            print(f"Form Data: {dict(request.form)}")
        if request.args:
            print(f"Query Args: {dict(request.args)}")
            
        # Don't return anything to allow request to continue to route
    except Exception as e:
        print(f"Error in before_request: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

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
        print("\n=== Starting test_whatsapp_handler ===")
        print(f"Incoming data: {json.dumps(data, indent=2)}")
        
        # Extract the message
        print("\nStep 1: Getting entry")
        entry = data.get('entry', [{}])[0]
        print(f"Entry: {json.dumps(entry, indent=2)}")
        
        print("\nStep 2: Getting changes")
        changes = entry.get('changes', [{}])[0]
        print(f"Changes: {json.dumps(changes, indent=2)}")
        
        print("\nStep 3: Getting value")
        value = changes.get('value', {})
        print(f"Value: {json.dumps(value, indent=2)}")
        
        print("\nStep 4: Getting messages")
        messages = value.get('messages', [])
        print(f"Messages: {json.dumps(messages, indent=2)}")
        
        if not messages:
            print("No messages found - returning False")
            return False
            
        print("\nStep 5: Getting first message")
        message = messages[0]
        print(f"Message: {json.dumps(message, indent=2)}")
        
        if message.get('type') != 'text':
            print(f"Not a text message: {message.get('type')} - returning False")
            return False
            
        # Get the text and sender
        print("\nStep 6: Getting text and sender")
        text = message.get('text', {}).get('body', '')
        from_number = message.get('from')
        print(f"Text: {text}")
        print(f"From: {from_number}")
        
        # Double the text
        print("\nStep 7: Creating response")
        response_text = text + text
        print(f"Response text: {response_text}")
        
        # Prepare WhatsApp API request
        print("\nStep 8: Preparing API request")
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
        
        print(f"URL: {url}")
        print(f"Headers (excluding auth): {json.dumps({k:v for k,v in headers.items() if k != 'Authorization'}, indent=2)}")
        print(f"Request data: {json.dumps(response_data, indent=2)}")
        
        print("\nStep 9: Sending request")
        response = requests.post(url, headers=headers, json=response_data)
        print(f"Response Status: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        print("\nStep 10: Handler completed - returning True")
        return True
        
    except Exception as e:
        print(f"\n=== Error in test handler ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False

@app.route("/whatsapp-webhook", methods=['GET', 'POST'])
async def whatsapp_route():
    """Handle WhatsApp webhook requests"""
    try:
        print("\n=== WhatsApp Webhook Route Started ===")
        print(f"Processing {request.method} request at {datetime.now()}")

        if request.method == "GET":
            print("\nProcessing GET request (verification)")
            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            
            print(f"Verification Request:")
            print(f"Mode: {mode}")
            print(f"Token: {token}")
            print(f"Challenge: {challenge}")
            
            VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'sagar')
            print(f"Expected token: {VERIFY_TOKEN}")
            
            if mode == "subscribe" and token == VERIFY_TOKEN:
                print("Verification successful - returning challenge")
                return challenge
                
            print("Verification failed - returning 403")
            return "Forbidden", 403

        elif request.method == "POST":
            print("\n=== Processing POST Request ===")
            try:
                # Get raw data first
                print("\nStep 1: Getting raw data")
                raw_data = request.get_data()
                print(f"Raw data length: {len(raw_data)} bytes")
                decoded_data = raw_data.decode('utf-8')
                print(f"Raw data: {decoded_data}")
                
                # Parse JSON
                print("\nStep 2: Parsing JSON")
                data = request.get_json()
                print(f"Parsed data: {json.dumps(data, indent=2)}")
                
                # Call test handler
                print("\nStep 3: Calling test handler")
                success = await test_whatsapp_handler(data)
                print(f"Handler result: {success}")
                
                if success:
                    print("Handler succeeded - returning 200")
                    return jsonify({"status": "success"}), 200
                else:
                    print("Handler failed - returning 500")
                    return jsonify({"status": "error", "message": "Handler failed"}), 500
                
            except Exception as e:
                print("\n=== Error processing message ===")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                import traceback
                print(f"Traceback:\n{traceback.format_exc()}")
                return jsonify({"status": "error", "message": str(e)}), 500

    except Exception as e:
        print("\n=== Webhook Error ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

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