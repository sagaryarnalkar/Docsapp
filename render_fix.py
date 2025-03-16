#!/usr/bin/env python3
"""
Render Server Fix for WhatsApp API URL Issue

This script directly fixes the WhatsApp API URL construction issue
on the Render server by modifying the message_sender.py file.
"""

import os
import re
import glob
import shutil

def find_message_sender():
    """Find the message_sender.py file on the Render server"""
    print("Searching for message_sender.py on Render server...")
    
    # Common locations for the message_sender.py file
    common_paths = [
        "routes/handlers/whatsapp/message_sender.py",
        "routes/handlers/message_sender.py",
        "routes/whatsapp/message_sender.py",
        "whatsapp/message_sender.py"
    ]
    
    # Check common paths first
    for path in common_paths:
        if os.path.exists(path):
            print(f"Found message_sender.py at common path: {path}")
            return path
    
    # If not found in common paths, search the entire project
    print("Not found in common paths, searching entire project...")
    for root, _, files in os.walk("."):
        for file in files:
            if file == "message_sender.py":
                path = os.path.join(root, file)
                print(f"Found message_sender.py at: {path}")
                return path
    
    # If still not found, search for any file that might contain the WhatsApp API URL
    print("message_sender.py not found, searching for files with WhatsApp API URL...")
    for root, _, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if "graph.facebook.com" in content and "messages" in content:
                            print(f"Found file with WhatsApp API URL: {path}")
                            return path
                except Exception as e:
                    print(f"Error reading {path}: {str(e)}")
    
    return None

def fix_message_sender(file_path):
    """Fix the WhatsApp API URL construction in the message_sender.py file"""
    print(f"Fixing WhatsApp API URL in {file_path}...")
    
    # Create backup
    backup_path = f"{file_path}.bak"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup at {backup_path}")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the file contains the issue
    if "graph.facebook.com" in content:
        print("Found graph.facebook.com in the file")
        
        # Look for the URL construction with token in URL
        token_in_url = False
        
        # Check for different patterns
        patterns = [
            r'url\s*=\s*f["\']https://graph\.facebook\.com/{[^}]*access_token[^}]*}',
            r'url\s*=\s*f["\']https://graph\.facebook\.com/EAA',
            r'url\s*=\s*["\']https://graph\.facebook\.com/["\'] \+ access_token'
        ]
        
        for pattern in patterns:
            if re.search(pattern, content):
                token_in_url = True
                print(f"Found token in URL with pattern: {pattern}")
                break
        
        if token_in_url:
            print("Fixing URL construction...")
            
            # Fix the URL construction
            fixed_content = content
            
            # Replace URL construction with token in URL
            for pattern in [
                r'url\s*=\s*f["\']https://graph\.facebook\.com/{[^}]*access_token[^}]*}/{[^}]*phone[^}]*}/messages["\']',
                r'url\s*=\s*f["\']https://graph\.facebook\.com/EAA[^/]*/[^/]*/messages["\']'
            ]:
                if re.search(pattern, fixed_content):
                    # Check if we're in a class method
                    if "self." in fixed_content:
                        replacement = 'url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"'
                    else:
                        replacement = 'url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"'
                    
                    fixed_content = re.sub(pattern, replacement, fixed_content)
            
            # Add headers if not present
            if "Authorization" not in fixed_content:
                # Find the URL line
                url_line = re.search(r'url\s*=\s*f["\']https://graph\.facebook\.com/[^"\']*["\']', fixed_content)
                
                if url_line:
                    url_line_text = url_line.group(0)
                    indent = re.match(r'(\s*)', url_line_text).group(1)
                    
                    # Check if we're in a class method
                    if "self." in fixed_content:
                        headers_def = f'\n{indent}headers = {{\n{indent}    "Content-Type": "application/json",\n{indent}    "Authorization": f"Bearer {{self.access_token}}"\n{indent}}}'
                    else:
                        headers_def = f'\n{indent}headers = {{\n{indent}    "Content-Type": "application/json",\n{indent}    "Authorization": f"Bearer {{access_token}}"\n{indent}}}'
                    
                    fixed_content = fixed_content.replace(url_line_text, f"{url_line_text}{headers_def}")
            
            # Make sure headers are passed to the request
            if "requests.post(url," in fixed_content and "headers=" not in fixed_content:
                fixed_content = fixed_content.replace(
                    "requests.post(url,",
                    "requests.post(url, headers=headers,"
                )
            
            # Write the fixed content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            print(f"✅ Fixed WhatsApp API URL in {file_path}")
            return True
        else:
            print("No token in URL found in the file")
            return False
    else:
        print("No graph.facebook.com found in the file")
        return False

def main():
    """Main function"""
    print("Render Server Fix for WhatsApp API URL Issue")
    print("==========================================")
    
    # Find the message_sender.py file
    file_path = find_message_sender()
    
    if not file_path:
        print("❌ Could not find message_sender.py or any file with WhatsApp API URL")
        return
    
    # Fix the message_sender.py file
    if fix_message_sender(file_path):
        print("\n✅ Successfully fixed the WhatsApp API URL issue!")
        print("Please restart your Render server to apply the changes.")
    else:
        print("\n❌ Could not fix the WhatsApp API URL issue")
        print("Please check the logs for more information.")

if __name__ == "__main__":
    main() 