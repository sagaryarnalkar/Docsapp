#!/usr/bin/env python3
"""
Direct Fix for WhatsApp API URL Issue

This script directly fixes the WhatsApp API URL construction issue
in the message_sender.py file based on the error logs.
"""

import os
import re
import shutil
import sys

def fix_message_sender():
    """Fix the WhatsApp API URL construction in message_sender.py"""
    # Possible locations of the message_sender.py file
    possible_paths = [
        "routes/handlers/whatsapp/message_sender.py",
        "routes/handlers/message_sender.py",
        "routes/whatsapp/message_sender.py",
        "whatsapp/message_sender.py"
    ]
    
    # Find the file
    file_path = None
    for path in possible_paths:
        if os.path.exists(path):
            file_path = path
            break
    
    if not file_path:
        print("❌ Could not find message_sender.py file.")
        print("Please specify the path to the file:")
        file_path = input("> ")
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return False
    
    print(f"Found message_sender.py at: {file_path}")
    
    # Create backup
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup at: {backup_path}")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the file contains the issue
    if "graph.facebook.com/{access_token}" in content or "graph.facebook.com/{self.access_token}" in content:
        print("✅ Found the issue: Token in URL")
        
        # Fix the URL construction
        fixed_content = re.sub(
            r'url\s*=\s*f["\']https://graph\.facebook\.com/\{(?:self\.)?access_token\}/\{(?:self\.)?phone_number_id\}/messages["\']',
            'url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"',
            content
        )
        
        # Check if headers are defined with Authorization
        if '"Authorization"' not in fixed_content:
            # Find where to add the Authorization header
            if 'headers = {' in fixed_content:
                # Add to existing headers
                fixed_content = re.sub(
                    r'(headers\s*=\s*\{[^\}]*)',
                    r'\1"Authorization": f"Bearer {self.access_token}",',
                    fixed_content
                )
            else:
                # Add new headers definition after URL
                fixed_content = re.sub(
                    r'(url\s*=\s*f["\']https://graph\.facebook\.com/[^"\']*["\'])',
                    r'\1\n        headers = {\n            "Content-Type": "application/json",\n            "Authorization": f"Bearer {self.access_token}"\n        }',
                    fixed_content
                )
        
        # Make sure headers are passed to the request
        if 'requests.post(url,' in fixed_content and 'headers=' not in fixed_content:
            fixed_content = re.sub(
                r'requests\.post\(url,',
                r'requests.post(url, headers=headers,',
                fixed_content
            )
        
        # Write the fixed content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print("✅ Fixed the WhatsApp API URL construction issue!")
        return True
    else:
        print("⚠️ Could not find the exact issue pattern in the file.")
        print("Please check the file manually and look for URL construction with token in URL.")
        return False

def main():
    """Main function"""
    print("Direct Fix for WhatsApp API URL Issue")
    print("====================================")
    
    if fix_message_sender():
        print("\n✅ Successfully fixed the WhatsApp API URL issue!")
        print("Please commit and push these changes to your repository.")
        print("Render will automatically deploy the updated code.")
    else:
        print("\n⚠️ Could not automatically fix the issue.")
        print("Please check the whatsapp_url_fix.md file for manual fix instructions.")

if __name__ == "__main__":
    main() 