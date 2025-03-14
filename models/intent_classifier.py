"""
Intent Classifier using Gemini
-----------------------------
This module uses Google's Gemini model to classify user intents when
rule-based detection fails.
"""

import logging
import json
from typing import Dict, Any, Optional, List, Tuple
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS

logger = logging.getLogger(__name__)

class IntentClassifier:
    """
    Classifies user intents using Gemini when rule-based detection fails.
    
    This class is responsible for:
    1. Initializing the Gemini model
    2. Classifying user intents
    3. Providing confidence scores for classifications
    4. Extracting parameters from user messages
    """
    
    def __init__(self):
        """Initialize the intent classifier with Gemini."""
        self.model = None
        self.is_available = False
        self.initialize_model()
        
    def initialize_model(self):
        """Initialize the Gemini model."""
        try:
            # Load credentials
            credentials = service_account.Credentials.from_service_account_file(
                GOOGLE_APPLICATION_CREDENTIALS,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            
            # Initialize Vertex AI
            vertexai.init(
                project=GOOGLE_CLOUD_PROJECT,
                location=GOOGLE_CLOUD_LOCATION,
                credentials=credentials
            )
            
            # Initialize Gemini model
            self.model = GenerativeModel("gemini-pro")
            self.is_available = True
            logger.info("✅ Successfully initialized Gemini model for intent classification")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini model: {str(e)}")
            self.is_available = False
    
    async def classify_intent(self, user_message: str) -> Dict[str, Any]:
        """
        Classify the user's intent using Gemini.
        
        Args:
            user_message: The user's message text
            
        Returns:
            Dict containing the classified intent, confidence, and extracted parameters
        """
        if not self.is_available or not self.model:
            logger.warning("Gemini model not available for intent classification")
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "parameters": {},
                "status": "error",
                "message": "Intent classification model not available"
            }
        
        try:
            # Create a structured prompt for intent classification
            prompt = f"""
            You are an intent classifier for a WhatsApp document management bot. 
            Classify the following user message into one of these intents:
            
            1. list_documents - User wants to see their documents
            2. help - User needs help or instructions
            3. find_document - User is searching for a document (extract the search query)
            4. ask_question - User is asking a question about their documents (extract the question)
            5. delete_document - User wants to delete a document (extract document identifier)
            6. unknown - Cannot determine the user's intent
            
            User message: "{user_message}"
            
            Respond in JSON format with the following structure:
            {{
                "intent": "the_intent",
                "confidence": 0.0 to 1.0,
                "parameters": {{
                    // Any extracted parameters like search_query, question, document_id, etc.
                }}
            }}
            
            Only respond with the JSON, nothing else.
            """
            
            # Generate response from Gemini
            response = self.model.generate_content(prompt)
            
            # Parse the JSON response
            try:
                result = json.loads(response.text)
                result["status"] = "success"
                return result
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract JSON from the response
                import re
                json_match = re.search(r'({.*})', response.text, re.DOTALL)
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                        result["status"] = "success"
                        return result
                    except:
                        pass
                
                logger.error(f"Failed to parse Gemini response as JSON: {response.text}")
                return {
                    "intent": "unknown",
                    "confidence": 0.0,
                    "parameters": {},
                    "status": "error",
                    "message": "Failed to parse intent classification response"
                }
                
        except Exception as e:
            logger.error(f"Error classifying intent with Gemini: {str(e)}")
            return {
                "intent": "unknown",
                "confidence": 0.0,
                "parameters": {},
                "status": "error",
                "message": f"Error classifying intent: {str(e)}"
            } 