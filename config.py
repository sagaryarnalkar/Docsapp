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
TWILIO_AUTH_TOKEN = 'b176c8500f7189f0555c0359c9b11bfe'
TWILIO_WHATSAPP_NUMBER = 'whatsapp:+14155238886'

# WhatsApp API Configuration
WHATSAPP_API_VERSION = 'v17.0'
WHATSAPP_PHONE_NUMBER_ID = '571053722749385'
WHATSAPP_ACCESS_TOKEN = 'EAAQDY035EjEBOxB4r4obxoGq9K6TUwFDZB84yt8Q2xsnb4zZCd68uz6VpWyeH5784x3OLdvivv0UUXhVEVJ6ULS6IVMz7hE5MZBdkyZBlrRUcuTiQhhwEsXTK3mjUpqwZBnR2VhbB94HwaD7dEiEYnn2gjcpNgZBrSlaV3dpWH3zEqy7Eul0Eof4j9ZAMSm9ZAZA4OVP42kZAoTwhTlZBUQgzfdQVQY'
WHATSAPP_BUSINESS_ACCOUNT_ID = '563839283474834'

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive.file']
OAUTH_REDIRECT_URI = 'https://sagary.pythonanywhere.com/oauth2callback'

print("=== WhatsApp Configuration ===")
print(f"Version: {WHATSAPP_API_VERSION}")
print(f"Phone ID: {WHATSAPP_PHONE_NUMBER_ID}")
print(f"Access Token: {WHATSAPP_ACCESS_TOKEN}")
print(f"Business Account ID: {WHATSAPP_BUSINESS_ACCOUNT_ID}")