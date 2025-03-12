"""
Embedding Generator for RAG

This module handles the generation of embeddings for text chunks using Google Vertex AI
with fallback mechanisms and error handling.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any, Union
import numpy as np

# Google Cloud imports
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel

# Setup logging
logger = logging.getLogger(__name__)

class EmbeddingGeneratorError(Exception):
    """Exception raised for errors in embedding generation."""
    pass

class EmbeddingGenerator:
    """
    Handles the generation of embeddings for text.
    
    This class is responsible for:
    - Generating embeddings using Vertex AI
    - Providing fallback mechanisms for embedding generation
    - Handling batching and rate limiting
    - Managing error handling and retries
    """
    
    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        model_name: str = "textembedding-gecko@latest",
        fallback_model_name: str = "textembedding-gecko@001",
        batch_size: int = 5,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        """
        Initialize the embedding generator.
        
        Args:
            project_id: Google Cloud project ID
            location: Google Cloud location
            model_name: Name of the embedding model to use
            fallback_model_name: Name of the fallback embedding model
            batch_size: Maximum number of texts to embed in a single request
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.project_id = project_id
        self.location = location
        self.model_name = model_name
        self.fallback_model_name = fallback_model_name
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize embedding models
        self._embedding_model = None
        self._fallback_model = None
        
        # Try to initialize the models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize the embedding models."""
        try:
            # Initialize Vertex AI
            aiplatform.init(project=self.project_id, location=self.location)
            
            # Try to initialize the primary model
            try:
                self._embedding_model = TextEmbeddingModel.from_pretrained(self.model_name)
                logger.info(f"Successfully initialized embedding model: {self.model_name}")
            except Exception as e:
                logger.warning(f"Failed to initialize primary embedding model: {e}")
                self._embedding_model = None
            
            # Try to initialize the fallback model if needed
            if self._embedding_model is None:
                try:
                    self._fallback_model = TextEmbeddingModel.from_pretrained(self.fallback_model_name)
                    logger.info(f"Successfully initialized fallback embedding model: {self.fallback_model_name}")
                except Exception as e:
                    logger.error(f"Failed to initialize fallback embedding model: {e}")
                    self._fallback_model = None
                    raise EmbeddingGeneratorError(f"Failed to initialize embedding models: {e}")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding generator: {e}")
            raise EmbeddingGeneratorError(f"Failed to initialize embedding generator: {e}")
    
    @property
    def embedding_model(self):
        """Get the embedding model, initializing if needed."""
        if self._embedding_model is None and self._fallback_model is None:
            self._initialize_models()
        return self._embedding_model or self._fallback_model
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to generate embeddings for
            
        Returns:
            List of embedding vectors (as lists of floats)
        """
        if not texts:
            return []
        
        try:
            # Process in batches to avoid rate limits
            all_embeddings = []
            
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i:i + self.batch_size]
                batch_embeddings = await self._generate_batch_embeddings(batch)
                all_embeddings.extend(batch_embeddings)
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise EmbeddingGeneratorError(f"Failed to generate embeddings: {e}")
    
    async def _generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts with retries.
        
        Args:
            texts: Batch of text strings
            
        Returns:
            List of embedding vectors for the batch
        """
        for attempt in range(self.max_retries):
            try:
                # Try with primary model first
                if self._embedding_model:
                    try:
                        embeddings = self._embedding_model.get_embeddings(texts)
                        return [embedding.values for embedding in embeddings]
                    except Exception as e:
                        logger.warning(f"Primary model embedding generation failed: {e}")
                        if self._fallback_model is None:
                            raise
                
                # Fall back to fallback model if available
                if self._fallback_model:
                    embeddings = self._fallback_model.get_embeddings(texts)
                    return [embedding.values for embedding in embeddings]
                
                # If we get here with no models, raise an error
                raise EmbeddingGeneratorError("No embedding models available")
                
            except Exception as e:
                logger.warning(f"Embedding generation attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    # Wait before retrying
                    time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
                else:
                    logger.error(f"All embedding generation attempts failed: {e}")
                    raise EmbeddingGeneratorError(f"Failed to generate embeddings after {self.max_retries} attempts: {e}")
    
    def normalize_embeddings(self, embeddings: List[List[float]]) -> List[List[float]]:
        """
        Normalize embedding vectors to unit length.
        
        Args:
            embeddings: List of embedding vectors
            
        Returns:
            List of normalized embedding vectors
        """
        try:
            normalized = []
            for embedding in embeddings:
                # Convert to numpy array for easier normalization
                vec = np.array(embedding)
                # Calculate L2 norm
                norm = np.linalg.norm(vec)
                # Normalize
                if norm > 0:
                    normalized_vec = vec / norm
                else:
                    normalized_vec = vec
                # Convert back to list
                normalized.append(normalized_vec.tolist())
            return normalized
        except Exception as e:
            logger.error(f"Failed to normalize embeddings: {e}")
            raise EmbeddingGeneratorError(f"Failed to normalize embeddings: {e}")
    
    def calculate_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (between -1 and 1)
        """
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Calculate dot product
            dot_product = np.dot(vec1, vec2)
            
            # Calculate magnitudes
            mag1 = np.linalg.norm(vec1)
            mag2 = np.linalg.norm(vec2)
            
            # Calculate cosine similarity
            if mag1 > 0 and mag2 > 0:
                similarity = dot_product / (mag1 * mag2)
            else:
                similarity = 0.0
                
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            raise EmbeddingGeneratorError(f"Failed to calculate similarity: {e}") 