import os
from openai import OpenAI

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
WHATSAPP_ACCESS_TOKEN = 'EAAQDY035EjEBO9EgDWB4Um2ZBtMRxbb6mAtCnN3hBmuu6oUZA2ZCWRMqpi34kwhLRoWvS1x2ykKut8aYIWajoDlO3BvNUORu4QBEvMTDfZA5BIQjD19xZAgvS3psKU81nsJM8U0Na3BkMZAc8s4FDybqoZAPM00zFIZAkqeppm3GC2W6rHQwHWvp5y2QZCDK8Jc0EOk3PKXb3GNHAPtrfqBIUuMBx'
WHATSAPP_BUSINESS_ACCOUNT_ID = '563839283474834'

# Google Drive API setup
SCOPES = ['https://www.googleapis.com/auth/drive.file']
OAUTH_REDIRECT_URI = 'https://sagary.pythonanywhere.com/oauth2callback'

#Deepseek key - sk-54cd5e49a0a24fa6a9ff77c8a4ceb6f8
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL")
)

print("=== WhatsApp Configuration ===")
print(f"Version: {WHATSAPP_API_VERSION}")
print(f"Phone ID: {WHATSAPP_PHONE_NUMBER_ID}")
print(f"Access Token: {WHATSAPP_ACCESS_TOKEN}")
print(f"Business Account ID: {WHATSAPP_BUSINESS_ACCOUNT_ID}")