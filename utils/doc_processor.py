# utils/doc_processor.py
import json
from openai import OpenAI
from .text_extractor import extract_text

class DocProcessor:
    def __init__(self, api_key):
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com/v1"
        )

    def process_document(self, file_path):
        """Main processing method to be called from existing code"""
        try:
            text = extract_text(file_path)
            return self._generate_embeddings(text[:3000])
        except Exception as e:
            print(f"Document processing failed: {str(e)}")
            return None

    def _generate_embeddings(self, text):
        """Generate embeddings using DeepSeek"""
        response = self.client.embeddings.create(
            input=text,
            model="deepseek-text-embedding"
        )
        return json.dumps(response.data[0].embedding)