"""
Intent Detector for WhatsApp Commands
------------------------------------
This module handles the detection of command intents from natural language.
"""

import logging

logger = logging.getLogger(__name__)

class IntentDetector:
    """
    Detects command intents from natural language.
    """
    
    # Command phrases for exact matching
    HELP_PHRASES = ["help", "commands", "?", "menu", "options"]
    LIST_PHRASES = ["list", "documents", "files", "show", "view", "show documents", "view documents"]
    FIND_PHRASES = ["find", "search", "locate", "get"]
    ASK_PHRASES = ["ask", "question", "tell me", "explain", "summarize", "how", "what", "why", "when", "where", "who", "which", "is", "are", "can", "do", "does", "will", "should"]
    
    def detect_intent(self, text):
        """
        Detect the intent of a command.
        
        Args:
            text: The command text
            
        Returns:
            str: The detected intent (help, list, find, ask, or None)
        """
        print(f"[DEBUG] Intent detector processing: '{text}'")
        
        # Normalize text
        text = text.strip().lower()
        
        # First check for exact command matches
        if text in self.HELP_PHRASES:
            print(f"[DEBUG] Exact match found for 'help' command: '{text}'")
            return "help"
            
        if text in self.LIST_PHRASES:
            print(f"[DEBUG] Exact match found for 'list' command: '{text}'")
            return "list"
            
        # Check for prefix matches (e.g., "find document about...")
        for prefix in self.FIND_PHRASES:
            if text.startswith(prefix):
                print(f"[DEBUG] Prefix match found for 'find' command: '{text}'")
                return "find"
                
        for prefix in self.ASK_PHRASES:
            if text.startswith(prefix):
                print(f"[DEBUG] Prefix match found for 'ask' command: '{text}'")
                return "ask"
                
        # Check for natural language patterns
        if any(phrase in text for phrase in self.HELP_PHRASES):
            print(f"[DEBUG] Natural language match for 'help' command: '{text}'")
            return "help"
            
        if any(phrase in text for phrase in self.LIST_PHRASES):
            print(f"[DEBUG] Natural language match for 'list' command: '{text}'")
            return "list"
            
        if any(phrase in text for phrase in self.FIND_PHRASES):
            print(f"[DEBUG] Natural language match for 'find' command: '{text}'")
            return "find"
            
        if any(phrase in text for phrase in self.ASK_PHRASES):
            print(f"[DEBUG] Natural language match for 'ask' command: '{text}'")
            return "ask"
            
        # No intent detected
        print(f"[DEBUG] No intent detected for: '{text}'")
        return None 