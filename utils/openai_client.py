from openai import OpenAI
import base64
import os
from PIL import Image
import io
import pdf2image
import mimetypes
import logging
import json

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, api_key):
        logger.info("Initializing OpenAI client...")
        self.client = OpenAI(api_key=api_key)  # Removed base_url since using service account key

    def get_file_type(self, file_path):
        """Determine file type using mimetypes"""
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type

    def convert_pdf_to_images(self, pdf_path):
        """Convert PDF pages to images"""
        try:
            return pdf2image.convert_from_path(pdf_path)
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}")
            return []

    def encode_image(self, image_path_or_object):
        """Convert image to base64"""
        try:
            if isinstance(image_path_or_object, str):
                # If it's a file path
                with open(image_path_or_object, "rb") as image_file:
                    return base64.b64encode(image_file.read()).decode('utf-8')
            else:
                # If it's a PIL Image object
                img_byte_arr = io.BytesIO()
                image_path_or_object.save(img_byte_arr, format='JPEG')
                img_byte_arr = img_byte_arr.getvalue()
                return base64.b64encode(img_byte_arr).decode('utf-8')
        except Exception as e:
            logger.error(f"Error encoding image: {str(e)}")
            return None

    def process_image(self, file_path):
        """Process image using GPT-4 Vision"""
        try:
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = self.client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all important information from this document. Format it as structured JSON."
                            },
                            {
                                "type": "image_url",
                                "image_url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        ]
                    }
                ],
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return None

    def test_connection(self):
        """Test the API connection"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello!"}]
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return None

    def answer_query(self, query, context):
        """Answer questions about documents using GPT-4"""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions about user documents."},
                    {"role": "user", "content": f"Context: {context}\n\nQuestion: {query}"}
                ]
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return None 