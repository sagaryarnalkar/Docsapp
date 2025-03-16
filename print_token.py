#!/usr/bin/env python
"""
Print WhatsApp Access Token
--------------------------
This script prints the WhatsApp access token from environment variables
with partial masking for security.
"""

import os
from dotenv import load_dotenv

def print_token_info():
    """Print information about the WhatsApp access token."""
    # Load environment variables
    load_dotenv()
    
    # Get WhatsApp API credentials
    api_version = os.environ.get('WHATSAPP_API_VERSION', 'Not set')
    phone_number_id = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'Not set')
    access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN', 'Not set')
    business_account_id = os.environ.get('WHATSAPP_BUSINESS_ACCOUNT_ID', 'Not set')
    
    print("\n=== WhatsApp API Configuration ===")
    print(f"API Version: {api_version}")
    print(f"Phone Number ID: {phone_number_id}")
    print(f"Business Account ID: {business_account_id}")
    
    # Print token with masking
    if access_token != 'Not set':
        token_length = len(access_token)
        if token_length > 20:
            # Show first 10 and last 5 characters
            masked_token = f"{access_token[:10]}...{access_token[-5:]}"
            print(f"Access Token: {masked_token} (Length: {token_length} characters)")
            
            # Check if token starts with EAA (Meta token format)
            if access_token.startswith('EAA'):
                print("✅ Token format appears correct (starts with EAA)")
            else:
                print("⚠️ Token format may be incorrect (doesn't start with EAA)")
                
            # Print full token with warning
            print("\n⚠️ SECURITY WARNING: Full token shown below for debugging only ⚠️")
            print(f"Full Token: {access_token}")
        else:
            print(f"Access Token: {access_token} (WARNING: Token seems too short)")
    else:
        print("Access Token: Not set")
    
    # Check if token is in .env file
    try:
        with open('.env', 'r') as f:
            env_content = f.read()
            if 'WHATSAPP_ACCESS_TOKEN=' in env_content:
                print("\n✅ Token is defined in .env file")
                
                # Check if token is a placeholder
                if 'EXPIRED_TOKEN' in env_content or 'YOUR_ACCESS_TOKEN' in env_content:
                    print("⚠️ Token in .env file appears to be a placeholder")
            else:
                print("\n⚠️ Token is not defined in .env file")
    except Exception as e:
        print(f"\n⚠️ Could not check .env file: {str(e)}")
    
    print("\n=== Environment Variables ===")
    print("Note: The token in environment variables is what's actually used by the application")
    print("If you're using Render, the token should be set in the environment variables section")
    print("of your service configuration, not in the .env file.")

if __name__ == "__main__":
    print_token_info() 