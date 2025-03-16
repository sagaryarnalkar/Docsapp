#!/usr/bin/env python3
"""
WhatsApp API URL Fix Script

This script finds and fixes the WhatsApp API URL construction issue
where the token is being placed in the URL instead of the Authorization header.
"""

import os
import re
import glob
import shutil
import sys

def find_message_sender_files():
    """Find files that might contain WhatsApp message sending code"""
    print("Searching for WhatsApp message sender files...")
    
    # Patterns to search for
    patterns = [
        r"graph\.facebook\.com",
        r"send_message.*whatsapp",
        r"whatsapp.*api"
    ]
    
    # Directories to search in
    search_dirs = [
        "routes/handlers/whatsapp",
        "routes/handlers",
        "routes",
        "."
    ]
    
    found_files = []
    
    for directory in search_dirs:
        if not os.path.exists(directory):
            continue
            
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            for pattern in patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    found_files.append(file_path)
                                    print(f"Found potential WhatsApp code in: {file_path}")
                                    break
                    except Exception as e:
                        print(f"Error reading {file_path}: {str(e)}")
    
    return found_files

def check_and_fix_file(file_path):
    """Check if a file has the URL construction issue and fix it"""
    print(f"\nChecking {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Look for URL construction with token in URL
        url_pattern = r'url\s*=\s*f[\"\']https://graph\.facebook\.com/([^/{}]+|{[^}]+})/([^/{}]+|{[^}]+})/messages[\"\']'
        matches = re.findall(url_pattern, content)
        
        if not matches:
            print(f"No URL construction pattern found in {file_path}")
            return False
        
        fixed_content = content
        fixed = False
        
        for match in matches:
            first_part, second_part = match
            print(f"Found URL: graph.facebook.com/{first_part}/{second_part}/messages")
            
            # Check if token is in URL
            if "token" in first_part.lower() or "EAA" in first_part or "{access_token}" in first_part:
                print(f"⚠️ Found token in URL in {file_path}")
                
                # Create the original pattern to replace
                original_pattern = f'url\\s*=\\s*f["\']https://graph\\.facebook\\.com/{re.escape(first_part)}/{re.escape(second_part)}/messages["\']'
                
                # Create the replacement
                if "api_version" in content:
                    replacement = 'url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"'
                else:
                    replacement = 'url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"'
                
                # Replace the URL construction
                fixed_content = re.sub(original_pattern, replacement, fixed_content)
                
                # Check if headers are defined with Authorization
                headers_pattern = r'headers\s*=\s*{[^}]*"Authorization"[^}]*}'
                if not re.search(headers_pattern, fixed_content):
                    # Find where to insert headers
                    url_line_pattern = r'(url\s*=\s*f["\']https://graph\.facebook\.com/[^"\']*["\'])'
                    url_match = re.search(url_line_pattern, fixed_content)
                    if url_match:
                        url_line = url_match.group(1)
                        indent = re.match(r'(\s*)', url_line).group(1)
                        headers_def = f'\n{indent}headers = {{\n{indent}    "Content-Type": "application/json",\n{indent}    "Authorization": f"Bearer {{access_token}}"\n{indent}}}'
                        fixed_content = fixed_content.replace(url_line, f"{url_line}{headers_def}")
                
                fixed = True
        
        if fixed:
            # Create backup
            backup_path = f"{file_path}.bak"
            shutil.copy2(file_path, backup_path)
            print(f"Created backup at {backup_path}")
            
            # Write fixed content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(fixed_content)
            
            print(f"✅ Fixed URL construction in {file_path}")
            return True
        else:
            print(f"No issues found in {file_path}")
            return False
            
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        return False

def main():
    """Main function"""
    print("WhatsApp API URL Fix Script")
    print("==========================")
    
    # Find potential message sender files
    files = find_message_sender_files()
    
    if not files:
        print("\nNo potential WhatsApp message sender files found.")
        print("Please check your project structure and try again.")
        return
    
    # Check and fix each file
    fixed_files = []
    for file_path in files:
        if check_and_fix_file(file_path):
            fixed_files.append(file_path)
    
    # Summary
    if fixed_files:
        print("\n✅ Fixed the following files:")
        for file in fixed_files:
            print(f"  - {file}")
        print("\nPlease commit and push these changes to your repository.")
        print("Render will automatically deploy the updated code.")
    else:
        print("\nNo files were fixed. The issue might be more complex.")
        print("Please check the logs for more information.")

if __name__ == "__main__":
    main() 