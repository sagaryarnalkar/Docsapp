import os

def fix_file():
    print("Creating a fixed version of docs_app.py...")
    
    # Read the original file
    with open("models/docs_app.py", "r", encoding="utf-8") as file:
        lines = file.readlines()
    
    # Create a new file with LF (Unix) line endings
    new_file_path = "models/docs_app.py.fixed"
    with open(new_file_path, "w", encoding="utf-8", newline='\n') as new_file:
        for line in lines:
            # Strip CRLF and add LF
            new_file.write(line.rstrip('\r\n') + '\n')
    
    print(f"Created fixed file at {new_file_path}")
    print("Now you can replace the original file with the fixed file:")
    print("cp models/docs_app.py.fixed models/docs_app.py")

if __name__ == "__main__":
    fix_file() 