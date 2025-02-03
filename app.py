from flask import Flask, send_from_directory, request
import logging
import os
import sys
# Add these to your imports
import json
import requests
from datetime import timedelta
from config import TEMP_DIR, BASE_DIR
from routes.webhook import handle_webhook, handle_oauth_callback
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

@app.route("/webhook", methods=['POST'])
def webhook():
    print("\n=== Webhook Endpoint Hit ===")
    try:
        print("Request Form Data:")
        for key, value in request.form.items():
            print(f"{key}: {value}")

        response = handle_webhook()
        print(f"Webhook Response: {response}")
        return response
    except Exception as e:
        print(f"Error in webhook route: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return "Error", 500

@app.route("/oauth2callback")
def oauth2callback():
    print("OAuth callback route accessed")
    return handle_oauth_callback()

@app.route('/temp/<path:filename>')
def serve_file(filename):
    print(f"Serving file: {filename}")
    return send_from_directory(TEMP_DIR, filename)

# Add this route to test WhatsApp sending
@app.route("/test-whatsapp")
def test_whatsapp():
    output = []
    try:
        test_phone = '919823623966'
        url = f'https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages'

        headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }

        data = {
            'messaging_product': 'whatsapp',
            'to': test_phone,
            'type': 'text',
            'text': {'body': "This is a test message from DocsApp!"}
        }

        output.append(f"URL: {url}")
        output.append(f"Headers: {headers}")
        output.append(f"Request Data: {json.dumps(data, indent=2)}")

        response = requests.post(url, headers=headers, json=data)

        output.append(f"Response Status: {response.status_code}")
        output.append(f"Response Body: {response.text}")

        html_output = "<br>".join(output).replace("\n", "<br>")
        return f"<pre>{html_output}</pre>"

    except Exception as e:
        import traceback
        return f"<pre>Error: {str(e)}\n\n{traceback.format_exc()}\n\nDebug Info:\n{chr(10).join(output)}</pre>"

@app.route("/whatsapp-webhook", methods=['GET', 'POST'])
def whatsapp_route():
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

        VERIFY_TOKEN = "sagar"

        if mode and token:
            if mode == "subscribe" and token == VERIFY_TOKEN:
                print("Verification successful!")
                return challenge
            else:
                print("Verification failed - token mismatch")
                return "Forbidden", 403
    else:
        print("=== Incoming Message ===")
        data = request.get_json()
        print(f"Request Data: {json.dumps(data, indent=2)}")

        try:
            if data.get('object') == 'whatsapp_business_account':
                result = whatsapp_handler.handle_incoming_message(data)
                print(f"Handler Result: {result}")
                return result
            return "Invalid request", 404
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return "Error", 500

@app.route("/test_log")
def test_log():
    print("=== Testing Logging ===")
    print("If you see this in the logs, logging is working")
    return "Test logged. Check error logs."

if __name__ == "__main__":
    app.run(debug=True)