import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Directory Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERSISTENT_ROOT = "/data/docsapp"
TEMP_DIR = os.path.join(PERSISTENT_ROOT, 'temp')
LOGS_DIR = os.path.join(PERSISTENT_ROOT, 'logs')
DATA_DIR = os.path.join(PERSISTENT_ROOT, 'data')
DB_DIR = os.path.join(PERSISTENT_ROOT, 'db')

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
print("\n=== Creating Persistent Directories ===")
for directory in [TEMP_DIR, LOGS_DIR, DATA_DIR, DB_DIR]:
    try:
        os.makedirs(directory, exist_ok=True)
        print(f"Created/verified directory: {directory}")
        print(f"Contents: {os.listdir(directory)}")
    except Exception as e:
        print(f"Error with directory {directory}: {str(e)}")

# Debug logging of configuration
if os.getenv('DEBUG'):
    print("\n=== Configuration Debug ===")
    print(f"PERSISTENT_ROOT: {PERSISTENT_ROOT}")
    print(f"TEMP_DIR: {TEMP_DIR}")
    print(f"LOGS_DIR: {LOGS_DIR}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"DB_DIR: {DB_DIR}")
    print(f"GOOGLE_CLOUD_PROJECT: {GOOGLE_CLOUD_PROJECT}")
    print(f"GOOGLE_CLOUD_LOCATION: {GOOGLE_CLOUD_LOCATION}")
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {GOOGLE_APPLICATION_CREDENTIALS}")
    print(f"OAUTH_REDIRECT_URI: {OAUTH_REDIRECT_URI}")
    print("=========================\n") 