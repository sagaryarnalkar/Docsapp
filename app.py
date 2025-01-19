from flask import Flask, send_from_directory, request
import logging
import os
import sys
from datetime import timedelta
from config import TEMP_DIR, BASE_DIR
from routes.webhook import handle_webhook, handle_oauth_callback

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

@app.route("/test_log")
def test_log():
    print("=== Testing Logging ===")
    print("If you see this in the logs, logging is working")
    return "Test logged. Check error logs."

if __name__ == "__main__":
    app.run(debug=True)