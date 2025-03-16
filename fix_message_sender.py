#!/usr/bin/env python3
"""
Direct Fix for WhatsApp Message Sender

This script directly fixes the WhatsApp API URL construction issue
in the message_sender.py file by searching for all possible locations
and applying the fix.
"""

import os
import re
import glob
import shutil

def find_all_message_sender_files():
    """Find all possible message_sender.py files in the project"""
    print("Searching for all possible message_sender.py files...")
    
    # Use glob to find all Python files
    all_py_files = glob.glob("**/*.py", recursive=True)
    
    # Filter for potential message sender files
    potential_files = []
    for file_path in all_py_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if "graph.facebook.com" in content and "messages" in content:
                    potential_files.append(file_path)
                    print(f"Found potential file: {file_path}")
        except Exception as e:
            print(f"Error reading {file_path}: {str(e)}")
    
    return potential_files

def fix_file(file_path):
    """Fix the WhatsApp API URL construction in a file"""
    print(f"\nAttempting to fix {file_path}...")
    
    try:
        # Create backup
        backup_path = f"{file_path}.bak"
        shutil.copy2(file_path, backup_path)
        print(f"Created backup at {backup_path}")
        
        # Read the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for the specific URL pattern with token in URL
        if "graph.facebook.com" in content:
            print(f"Found graph.facebook.com in {file_path}")
            
            # Try different patterns to match the URL construction
            patterns = [
                # Pattern 1: Direct token in URL
                (r'url\s*=\s*f["\']https://graph\.facebook\.com/([^/{}]+|{[^}]+})/([^/{}]+|{[^}]+})/messages["\']', 
                 lambda m: f'url = f"https://graph.facebook.com/v22.0/{m.group(2)}/messages"'),
                
                # Pattern 2: Self token in URL
                (r'url\s*=\s*f["\']https://graph\.facebook\.com/{self\.access_token}/{self\.phone_number_id}/messages["\']',
                 'url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"'),
                
                # Pattern 3: Variables in URL
                (r'url\s*=\s*f["\']https://graph\.facebook\.com/{access_token}/{phone_number_id}/messages["\']',
                 'url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"'),
                
                # Pattern 4: Direct string concatenation - removed due to syntax issues
                (r'url\s*=\s*["\'"]https://graph\.facebook\.com/["\'"] \+ .*? \+ ["\'"]messages["\'"]',
                 'url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"')
            ]
            
            fixed_content = content
            fixed = False
            
            for pattern, replacement in patterns:
                if re.search(pattern, content):
                    print(f"Found matching pattern: {pattern}")
                    if callable(replacement):
                        # Use the replacement function
                        fixed_content = re.sub(pattern, replacement, fixed_content)
                    else:
                        # Use the replacement string
                        fixed_content = re.sub(pattern, replacement, fixed_content)
                    fixed = True
            
            # Add headers if not present
            if fixed and "Authorization" not in fixed_content:
                # Find where to add headers
                url_pattern = r'(url\s*=\s*f["\']https://graph\.facebook\.com/[^"\']*["\'])'
                url_match = re.search(url_pattern, fixed_content)
                
                if url_match:
                    url_line = url_match.group(1)
                    indent = re.match(r'(\s*)', url_line).group(1)
                    
                    # Check if we're in a class method
                    if "self." in url_line:
                        headers_def = f'\n{indent}headers = {{\n{indent}    "Content-Type": "application/json",\n{indent}    "Authorization": f"Bearer {{self.access_token}}"\n{indent}}}'
                    else:
                        headers_def = f'\n{indent}headers = {{\n{indent}    "Content-Type": "application/json",\n{indent}    "Authorization": f"Bearer {{access_token}}"\n{indent}}}'
                    
                    fixed_content = fixed_content.replace(url_line, f"{url_line}{headers_def}")
            
            # Make sure headers are passed to the request
            if fixed and "requests.post" in fixed_content:
                # Check if headers are passed to requests.post
                if re.search(r'requests\.post\(url,\s*[^)]*headers\s*=', fixed_content):
                    print("Headers are already passed to requests.post")
                else:
                    # Add headers to requests.post
                    fixed_content = re.sub(
                        r'requests\.post\(url,',
                        r'requests.post(url, headers=headers,',
                        fixed_content
                    )
            
            if fixed:
                # Write fixed content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(fixed_content)
                
                print(f"✅ Fixed {file_path}")
                return True
            else:
                print(f"No matching patterns found in {file_path}")
                return False
        else:
            print(f"No graph.facebook.com found in {file_path}")
            return False
    except Exception as e:
        print(f"Error fixing {file_path}: {str(e)}")
        return False

def main():
    """Main function"""
    print("Direct Fix for WhatsApp Message Sender")
    print("=====================================")
    
    # Find all potential message sender files
    files = find_all_message_sender_files()
    
    if not files:
        print("\nNo potential message sender files found.")
        return
    
    # Fix each file
    fixed_files = []
    for file_path in files:
        if fix_file(file_path):
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