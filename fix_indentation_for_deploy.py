import re

def fix_indentation():
    # Read the file
    with open("models/docs_app.py", "r", encoding="utf-8") as file:
        lines = file.readlines()
    
    fixed_lines = []
    in_try_block = False
    try_indent = ""
    line_num = 0
    fixed_line_nums = []
    
    for line in lines:
        line_num += 1
        
        # Check for the start of the try block around line 143
        if re.match(r'(\s+)try:', line) and 140 <= line_num <= 150:
            in_try_block = True
            try_indent = re.match(r'(\s+)', line).group(1)
            inner_indent = try_indent + "    "  # Add 4 spaces for inner indentation
            fixed_lines.append(line)
            continue
        
        # Fix indentation in the try block
        if in_try_block:
            # Check if this is a line that needs indentation fixed
            if line.strip() and not line.startswith(inner_indent):
                # This line should be indented but isn't
                fixed_line = inner_indent + line.lstrip()
                fixed_lines.append(fixed_line)
                fixed_line_nums.append(line_num)
            else:
                fixed_lines.append(line)
            
            # Check for end of try block (encountering except)
            if re.match(r'(\s+)except\s+', line):
                in_try_block = False
        else:
            fixed_lines.append(line)
    
    # Save the fixed content
    with open("models/docs_app.py", "w", encoding="utf-8") as file:
        file.writelines(fixed_lines)
    
    print(f"Indentation fixed successfully! Fixed lines: {fixed_line_nums}")

if __name__ == "__main__":
    fix_indentation() 