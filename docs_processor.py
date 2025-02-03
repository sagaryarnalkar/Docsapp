import base64
import os
import json
import logging
import time
from typing import Dict, List
from PIL import Image
import requests
import pdf2image
import io
from openai import OpenAI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocsProcessor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.api_base = "https://api.cloud.deepseek.com"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def process_file(self, file_path: str) -> Dict:
        """Process any file type (PDF, Image, etc)"""
        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            
            if file_extension == '.pdf':
                return self._process_pdf(file_path)
            elif file_extension in ['.png', '.jpg', '.jpeg']:
                return self._process_image(file_path)
            else:
                return {"status": "error", "message": f"Unsupported file type: {file_extension}"}
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _process_pdf(self, pdf_path: str) -> Dict:
        """Process PDF by converting to images first"""
        try:
            # Convert PDF to images using specific Poppler path
            poppler_path = r"C:\Docsapp\Poppler\poppler-24.08.0\Library\bin"
            if not os.path.exists(poppler_path):
                return {"status": "error", "message": f"Poppler path not found: {poppler_path}"}
                
            images = pdf2image.convert_from_path(
                pdf_path,
                poppler_path=poppler_path
            )
            
            all_content = []
            for i, image in enumerate(images):
                # Convert PIL image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                
                # Convert to base64
                base64_image = base64.b64encode(img_byte_arr).decode('utf-8')
                
                # Process each page
                response = requests.post(
                    f"{self.api_base}/v1/chat/completions",
                    headers=self.headers,
                    json={
                        "model": "deepseek-vl-7b-chat",
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"Please analyze page {i+1} of this document and extract all important information."
                                    },
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "data": base64_image
                                        }
                                    }
                                ]
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1000
                    }
                )
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    all_content.append(f"Page {i+1}: {content}")
                else:
                    error_msg = f"API Error on page {i+1}: {response.text}"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}
                
            return {
                "status": "success",
                "doc_id": os.path.basename(pdf_path),
                "content": "\n\n".join(all_content)
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return {"status": "error", "message": str(e)}

    def _process_image(self, image_path: str) -> Dict:
        """Process single image file"""
        try:
            with open(image_path, "rb") as file:
                base64_content = base64.b64encode(file.read()).decode('utf-8')
            
            response = requests.post(
                f"{self.api_base}/v1/chat/completions",
                headers=self.headers,
                json={
                    "model": "deepseek-vl-7b-chat",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Please analyze this document and extract all important information."
                                },
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "data": base64_content
                                    }
                                }
                            ]
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                return {
                    "status": "success",
                    "doc_id": os.path.basename(image_path),
                    "content": content
                }
            else:
                error_msg = f"API Error: {response.text}"
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}
                
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return {"status": "error", "message": str(e)}

    def query_document(self, question: str, doc_id: str = None) -> str:
        """Query about the document"""
        try:
            response = requests.post(
                f"{self.api_base}/v1/chat/completions",
                headers=self.headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful assistant that answers questions about documents based on previous analysis."
                        },
                        {
                            "role": "user",
                            "content": f"Based on the document analysis, please answer: {question}"
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                return f"Error: API request failed with status {response.status_code}"
            
        except Exception as e:
            logger.error(f"Error querying document: {str(e)}")
            return f"Error: {str(e)}"

def main():
    # Test the processor
    api_key = "your-api-key"  # Replace with your API key
    processor = DocsProcessor(api_key)
    
    # Test document processing
    test_file = "test_files/sample.png"  # Replace with your test file
    result = processor.process_file(test_file)
    print(f"\nProcessing result: {result}")
    
    if result["status"] == "success":
        # Test querying
        question = "What type of document is this?"
        answer = processor.query_document(question, result["doc_id"])
        print(f"\nQ: {question}")
        print(f"A: {answer}")

if __name__ == "__main__":
    main() 