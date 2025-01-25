from config import client
import logging

def generate_embeddings(text: str, max_length: int = 3000) -> list:
    """Generate embeddings using DeepSeek API"""
    try:
        response = client.embeddings.create(
            input=text[:max_length],
            model="deepseek-text-embedding"
        )
        return response.data[0].embedding
    except Exception as e:
        logging.error(f"Embedding generation failed: {str(e)}")
        return None