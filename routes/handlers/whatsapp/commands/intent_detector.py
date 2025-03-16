"""
Intent Detector
------------
This module handles detecting command intents from natural language.
"""

import logging

logger = logging.getLogger(__name__)

class IntentDetector:
    """
    Detects command intents from natural language.
    
    This class is responsible for:
    1. Detecting exact command matches
    2. Detecting command prefixes
    3. Detecting natural language command intents
    """
    
    def __init__(self):
        """Initialize the intent detector."""
        # Define natural language phrases for each command
        self.help_phrases = ['help me', 'what can you do', 'how does this work', 'commands', 'instructions']
        self.list_phrases = ['show me', 'list', 'documents', 'files', 'what do i have']
        self.find_phrases = ['find', 'search', 'look for', 'where is']
        self.ask_phrases = ['ask', 'question', 'tell me about', 'what is', 'how to']
        
    def detect_intent(self, text):
        """
        Detect command intent from natural language.
        
        Args:
            text: The user's message
            
        Returns:
            dict: The detected command intent with type and parameters, or None if no intent was detected
        """
        logger.info(f"[DEBUG] Detecting intent for: '{text}'")
        
        # Normalize text
        text = text.strip().lower()
        
        # Check for exact matches
        if text == 'help':
            logger.info("[DEBUG] Detected exact match for 'help' command")
            return {'type': 'help'}
        elif text == 'list' or text == 'show documents' or text == 'show my documents':
            logger.info("[DEBUG] Detected exact match for 'list' command")
            return {'type': 'list'}
            
        # Check for prefix matches
        if text.startswith('find '):
            query = text[5:].strip()
            logger.info(f"[DEBUG] Detected 'find' command with query: '{query}'")
            return {'type': 'find', 'query': query}
        elif text.startswith('/ask '):
            question = text[5:].strip()
            logger.info(f"[DEBUG] Detected '/ask' command with question: '{question}'")
            return {'type': 'ask', 'question': question}
        elif text.startswith('delete '):
            document_id = text[7:].strip()
            logger.info(f"[DEBUG] Detected 'delete' command with document ID: '{document_id}'")
            return {'type': 'delete', 'document_id': document_id}
            
        # Check for natural language matches
        
        # Check for help intent
        if any(phrase in text for phrase in self.help_phrases):
            logger.info("[DEBUG] Detected natural language 'help' command")
            return {'type': 'help'}
            
        # Check for list intent
        if any(phrase in text for phrase in self.list_phrases):
            logger.info("[DEBUG] Detected natural language 'list' command")
            return {'type': 'list'}
            
        # Check for find intent with query
        for phrase in self.find_phrases:
            if phrase in text:
                # Extract the query after the phrase
                query_start = text.find(phrase) + len(phrase)
                query = text[query_start:].strip()
                if query:
                    logger.info(f"[DEBUG] Detected natural language 'find' command with query: '{query}'")
                    return {'type': 'find', 'query': query}
                    
        # Check for ask intent with question
        for phrase in self.ask_phrases:
            if phrase in text:
                # Extract the question after the phrase
                question_start = text.find(phrase) + len(phrase)
                question = text[question_start:].strip()
                if question:
                    logger.info(f"[DEBUG] Detected natural language 'ask' command with question: '{question}'")
                    return {'type': 'ask', 'question': question}
                    
        logger.info("[DEBUG] No command intent detected")
        return None 