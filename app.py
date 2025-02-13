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

# Configure logging to both file and stdout
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

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

@app.route("/whatsapp-webhook", methods=['GET', 'POST'])
async def whatsapp_route():
    try:
        print("\n=== WhatsApp Webhook Called ===")
        print(f"Method: {request.method}")
        print(f"Headers: {dict(request.headers)}")

        if request.method == "GET":
            print("=== Verification Request ===")
            print(f"Args: {dict(request.args)}")

            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")

            print(f"Mode: {mode}")
            print(f"Token: {token}")
            print(f"Challenge: {challenge}")

            # Get verify token from environment variable
            VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', 'sagar')

            if mode and token:
                if mode == "subscribe" and token == VERIFY_TOKEN:
                    print("Verification successful!")
                    return challenge
                else:
                    print("Verification failed - token mismatch")
                    print(f"Expected token: {VERIFY_TOKEN}")
                    print(f"Received token: {token}")
                    return "Forbidden", 403
        else:
            print("\n=== Processing Incoming Message ===")
            
            # 1. Get and log raw data
            raw_data = request.get_data()
            print(f"Raw data ({len(raw_data)} bytes): {raw_data}")
            
            try:
                # 2. Try to decode the data
                decoded_data = raw_data.decode('utf-8')
                print(f"Decoded data: {decoded_data}")
                
                # 3. Parse JSON
                data = json.loads(decoded_data)
                print(f"Parsed JSON: {json.dumps(data, indent=2)}")
                
                # 4. Extract message details
                entry = data.get('entry', [{}])[0]
                changes = entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                messages = value.get('messages', [])
                
                if not messages:
                    print("No messages found in payload")
                    return "No messages", 200
                
                # 5. Get message details
                message = messages[0]
                print(f"\nMessage Details:")
                print(f"Type: {message.get('type')}")
                print(f"From: {message.get('from')}")
                if message.get('type') == 'text':
                    print(f"Text: {message.get('text', {}).get('body')}")
                elif message.get('type') == 'document':
                    print(f"Document: {message.get('document')}")
                
                # 6. Process message
                try:
                    result = await whatsapp_handler.handle_incoming_message(data)
                    print(f"Handler result: {result}")
                    return "OK", 200
                except Exception as e:
                    print(f"Error in message handler: {str(e)}")
                    import traceback
                    print(f"Handler traceback: {traceback.format_exc()}")
                    return "Handler error", 500
                    
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {str(e)}")
                return "Invalid JSON", 400
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                import traceback
                print(f"Traceback: {traceback.format_exc()}")
                return "Server error", 500

    except Exception as e:
        print(f"Top-level error: {str(e)}")
        import traceback
        print(f"Top-level traceback: {traceback.format_exc()}")
        return "Server error", 500

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