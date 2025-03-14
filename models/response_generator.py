"""
Response Generator using Gemini
------------------------------
This module uses Google's Gemini model to generate natural language responses
for unknown commands.
"""

import logging
from typing import Dict, Any, Optional
from google.oauth2 import service_account
import vertexai
from vertexai.generative_models import GenerativeModel
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """
    Generates natural language responses using Gemini.
    
    This class is responsible for:
    1. Generating conversational responses
    2. Providing context-aware replies
    3. Handling error cases gracefully
    """
    
    def __init__(self):
        """Initialize the response generator with Gemini."""
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
            logger.info("✅ Successfully initialized Gemini model for response generation")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini model: {str(e)}")
            self.is_available = False
    
    async def generate_response(self, user_message: str, context: Dict[str, Any]) -> str:
        """
        Generate a natural language response using Gemini.
        
        Args:
            user_message: The user's message text
            context: Context information for the response
            
        Returns:
            The generated response text
        """
        if not self.is_available or not self.model:
            logger.warning("Gemini model not available for response generation")
            return "I'm sorry, I couldn't understand your request. Please try using one of the standard commands like 'help', 'list', or '/ask'."
        
        try:
            # Create a structured prompt for response generation
            prompt = f"""
            You are a helpful WhatsApp document management assistant. Generate a natural, conversational response to the user's message.

            User message: "{user_message}"
            
            Context:
            - User has {context.get('document_count', 0)} documents stored
            - Last command: {context.get('last_command', 'None')}
            - Command understood: {context.get('command_understood', False)}
            
            Guidelines:
            1. Be concise but helpful
            2. If you don't understand the request, suggest using standard commands
            3. Don't make up information about documents
            4. Always mention the available commands if the user seems confused
            5. Keep responses under 200 characters when possible
            6. Available commands are: 'help', 'list', 'find [text]', '/ask [question]'
            
            Your response:
            """
            
            # Generate response from Gemini
            response = self.model.generate_content(prompt)
            return response.text.strip()
                
        except Exception as e:
            logger.error(f"Error generating response with Gemini: {str(e)}")
            return "I'm sorry, I couldn't process your request right now. Please try using one of the standard commands like 'help', 'list', or '/ask'." 