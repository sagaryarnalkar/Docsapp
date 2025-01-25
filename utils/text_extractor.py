# utils/text_extractor.py
import PyPDF2
import docx
import pytesseract
from PIL import Image

def extract_text(file_path):
    if file_path.endswith('.pdf'):
        with open(file_path, 'rb') as f:
            return " ".join([page.extract_text() for page in PyPDF2.PdfReader(f).pages])
    elif file_path.endswith(('.docx', '.doc')):
        return " ".join([p.text for p in docx.Document(file_path).paragraphs])
    elif file_path.endswith(('.png', '.jpg', '.jpeg')):
        return pytesseract.image_to_string(Image.open(file_path))
    else:
        with open(file_path, 'r') as f:
            return f.read()