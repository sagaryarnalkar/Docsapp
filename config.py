import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Directory Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/docsapp')
LOGS_DIR = os.getenv('LOGS_DIR', '/tmp/docsapp/logs')
DATA_DIR = os.getenv('DATA_DIR', '/tmp/docsapp/data')
DB_DIR = os.getenv('DB_DIR', '/tmp/docsapp/db')

# WhatsApp Configuration
WHATSAPP_API_VERSION = os.getenv('WHATSAPP_API_VERSION', 'v17.0')
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID')

# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
GOOGLE_CLOUD_LOCATION = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '/etc/secrets/google-credentials.json')

# OAuth Configuration
OAUTH_REDIRECT_URI = os.getenv('OAUTH_REDIRECT_URI', 'https://docsapp-20br.onrender.com/oauth2callback')

# Google OAuth Configuration
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# Create necessary directories
for directory in [TEMP_DIR, LOGS_DIR, DATA_DIR, DB_DIR]:
    os.makedirs(directory, exist_ok=True)

# Debug logging of configuration
if os.getenv('DEBUG'):
    print("\n=== Configuration Debug ===")
    print(f"GOOGLE_CLOUD_PROJECT: {GOOGLE_CLOUD_PROJECT}")
    print(f"GOOGLE_CLOUD_LOCATION: {GOOGLE_CLOUD_LOCATION}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {GOOGLE_APPLICATION_CREDENTIALS}")
    print(f"OAUTH_REDIRECT_URI: {OAUTH_REDIRECT_URI}")
    print("=========================\n") 