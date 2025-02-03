import pytesseract
from PIL import Image
import pdfplumber
import logging

logger = logging.getLogger(__name__)

def extract_text_from_image(image_path):
    """Extract text from image using pytesseract"""
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from image: {str(e)}")
        return ""

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF using pdfplumber"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        return ""

def extract_text(file_path, file_type):
    """Extract text based on file type"""
    if file_type.lower() in ['.jpg', '.jpeg', '.png', '.bmp']:
        return extract_text_from_image(file_path)
    elif file_type.lower() == '.pdf':
        return extract_text_from_pdf(file_path)
    else:
        logger.error(f"Unsupported file type: {file_type}")
        return ""
