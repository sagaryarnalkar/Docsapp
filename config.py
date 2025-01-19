import os

# Path configurations
BASE_DIR = '/home/sagary/docsapp'
TEMP_DIR = os.path.join(BASE_DIR, 'temp')
DB_DIR = os.path.join(BASE_DIR, 'data')

# Create necessary directories
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)

# Twilio Configuration
TWILIO_ACCOUNT_SID = 'ACc02f635df0f15ee3e7f85279cf406b4c'
TWILIO_AUTH_TOKEN = 'e7f8eaf4f37042c04359791bf9242eb5'
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive.file']
OAUTH_REDIRECT_URI = 'https://sagary.pythonanywhere.com/oauth2callback'