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
import uuid  # Add at top with other imports

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

# Add after app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

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
        # Generate unique request ID
        request.request_id = str(uuid.uuid4())
        print(f"\n{'='*50}")
        print(f"REQUEST ID: {request.request_id}")
        print(f"PROCESSING REQUEST - SERVER VERSION {VERSION}")
        print(f"TIME: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Method: {request.method}")
        print(f"URL: {request.url}")
        print(f"Headers: {dict(request.headers)}")
        print(f"{'='*50}\n")
        
        # Log request body for POST requests
        if request.method == 'POST':
            try:
                raw_data = request.get_data()
                print(f"[{request.request_id}] Raw request data length: {len(raw_data)} bytes")
                print(f"[{request.request_id}] Raw request data: {raw_data.decode('utf-8')}")
            except Exception as e:
                print(f"[{request.request_id}] Error reading request data: {str(e)}")
        
        if request.form:
            print(f"[{request.request_id}] Form Data: {dict(request.form)}")
        if request.args:
            print(f"[{request.request_id}] Query Args: {dict(request.args)}")
            
    except Exception as e:
        print(f"Error in before_request: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

@app.after_request
def after_request(response):
    """Log after request processing"""
    try:
        request_id = getattr(request, 'request_id', 'NO_ID')
        print(f"\n[{request_id}] === After Request ===")
        print(f"[{request_id}] Response Status: {response.status_code}")
        print(f"[{request_id}] Response Headers: {dict(response.headers)}")
        return response
    except Exception as e:
        print(f"Error in after_request: {str(e)}")
        return response

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

@app.route("/whatsapp-webhook", methods=['GET', 'POST'])
async def whatsapp_route():
    """Handle WhatsApp webhook requests"""
    request_id = getattr(request, 'request_id', 'NO_ID')
    try:
        print(f"\n[{request_id}] === WhatsApp Webhook Route Started ===")
        print(f"[{request_id}] Processing {request.method} request at {datetime.now()}")

        if request.method == "GET":
            print(f"\n[{request_id}] Processing GET request (verification)")
            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")
            
            print(f"[{request_id}] Verification Request:")
            print(f"[{request_id}] Mode: {mode}")
            print(f"[{request_id}] Token: {token}")
            print(f"[{request_id}] Challenge: {challenge}")
            
            VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'sagar')
            print(f"[{request_id}] Expected token: {VERIFY_TOKEN}")
            
            if mode == "subscribe" and token == VERIFY_TOKEN:
                print(f"[{request_id}] Verification successful - returning challenge")
                return challenge
                
            print(f"[{request_id}] Verification failed - returning 403")
            return "Forbidden", 403

        elif request.method == "POST":
            print(f"\n[{request_id}] === Processing POST Request ===")
            try:
                # Get raw data first
                print(f"\n[{request_id}] Step 1: Getting raw data")
                raw_data = request.get_data()
                print(f"[{request_id}] Raw data length: {len(raw_data)} bytes")
                decoded_data = raw_data.decode('utf-8')
                print(f"[{request_id}] Raw data: {decoded_data}")
                
                # Parse JSON
                print(f"\n[{request_id}] Step 2: Parsing JSON")
                data = request.get_json()
                print(f"[{request_id}] Parsed data: {json.dumps(data, indent=2)}")
                
                # Call WhatsApp handler
                print(f"\n[{request_id}] Step 3: Calling WhatsApp handler")
                result = await whatsapp_handler.handle_incoming_message(data)
                print(f"[{request_id}] Handler result: {result}")
                
                # Handle different types of responses
                if isinstance(result, tuple):
                    message, status_code = result
                    
                    # Special handling for authorization needed
                    if message == "Authorization needed" and status_code == 200:
                        return jsonify({
                            "status": "success",
                            "message": "Authorization request sent",
                            "request_id": request_id
                        }), 200
                    
                    # Handle other responses
                    return jsonify({
                        "status": "success" if status_code == 200 else "error",
                        "message": message,
                        "request_id": request_id
                    }), status_code
                else:
                    return jsonify({
                        "status": "success",
                        "request_id": request_id
                    }), 200
                
            except Exception as e:
                print(f"\n[{request_id}] === Error processing message ===")
                print(f"[{request_id}] Error type: {type(e).__name__}")
                print(f"[{request_id}] Error message: {str(e)}")
                import traceback
                print(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
                
                # Send error message to user
                try:
                    data = request.get_json()
                    entry = data.get('entry', [{}])[0]
                    changes = entry.get('changes', [{}])[0]
                    value = changes.get('value', {})
                    messages = value.get('messages', [])
                    if messages:
                        from_number = messages[0].get('from')
                        if from_number:
                            await whatsapp_handler.send_message(
                                from_number,
                                "❌ Sorry, there was an error processing your request. Please try again later."
                            )
                except Exception as send_error:
                    print(f"Error sending error message: {str(send_error)}")
                
                return jsonify({
                    "status": "error", 
                    "message": str(e),
                    "request_id": request_id
                }), 500

    except Exception as e:
        print(f"\n[{request_id}] === Webhook Error ===")
        print(f"[{request_id}] Error type: {type(e).__name__}")
        print(f"[{request_id}] Error message: {str(e)}")
        import traceback
        print(f"[{request_id}] Traceback:\n{traceback.format_exc()}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "request_id": request_id
        }), 500

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