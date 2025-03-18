#!/usr/bin/env python
"""
Fix indentation in docs_app.py
"""

import re

def fix_indentation():
    """Fix indentation in docs_app.py file"""
    file_path = 'models/docs_app.py'
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Write the file back with fixed indentation
    with open(file_path, 'w', encoding='utf-8') as file:
        for line in lines:
            # Remove any trailing whitespace
            line = line.rstrip() + '\n'
            file.write(line)

if __name__ == "__main__":
    fix_indentation()
    print("Indentation fixed in models/docs_app.py") 