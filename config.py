import os

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

# Google OAuth Configuration
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# Create necessary directories
for directory in [TEMP_DIR, LOGS_DIR, DATA_DIR, DB_DIR]:
    os.makedirs(directory, exist_ok=True)

# Twilio Configuration
TWILIO_ACCOUNT_SID = 'ACc02f635df0f15ee3e7f85279cf406b4c'
TWILIO_AUTH_TOKEN = 'b176c8500f7189f0555c0359c9b11bfe'
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'

print("=== WhatsApp Configuration ===")
print(f"Version: {WHATSAPP_API_VERSION}")
print(f"Phone ID: {WHATSAPP_PHONE_NUMBER_ID}")
print(f"Access Token: {WHATSAPP_ACCESS_TOKEN}")
print(f"Business Account ID: {WHATSAPP_BUSINESS_ACCOUNT_ID}")