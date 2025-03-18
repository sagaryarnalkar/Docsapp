import os
import binascii

def check_file_encoding():
    print("Checking file encoding and line endings...")
    
    target_line_range = range(140, 155)
    line_num = 0
    
    with open("models/docs_app.py", "rb") as file:
        for line in file:
            line_num += 1
            if line_num in target_line_range:
                # Convert to hex to see any special characters
                hex_line = binascii.hexlify(line).decode()
                decoded_line = line.decode('utf-8', errors='replace').rstrip()
                print(f"Line {line_num}: {decoded_line}")
                print(f"Hex: {hex_line}")
                # Check line endings
                if line.endswith(b'\r\n'):
                    print("  Line ending: CRLF (Windows)")
                elif line.endswith(b'\n'):
                    print("  Line ending: LF (Unix)")
                elif line.endswith(b'\r'):
                    print("  Line ending: CR (Mac)")
                else:
                    print("  No line ending")
                
                # Check indentation
                leading_space_count = len(decoded_line) - len(decoded_line.lstrip())
                print(f"  Leading spaces: {leading_space_count}")
                print()

if __name__ == "__main__":
    check_file_encoding() 