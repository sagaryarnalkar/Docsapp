import os
import logging
from models.docs_app import DocsApp

logger = logging.getLogger(__name__)

class MediaHandler:
    def __init__(self, docs_app, pending_descriptions):
        self.docs_app = docs_app
        self.pending_descriptions = pending_descriptions

    def handle_media(self, phone, media_id, filename=None):
        """Handle media file from WhatsApp"""
        try:
            # Process the media file
            logger.debug(f"Processing media from {phone}")
            return True
        except Exception as e:
            logger.error(f"Error handling media: {str(e)}")
            return False

    def handle_description(self, phone, description):
        """Handle document description"""
        try:
            if phone in self.pending_descriptions:
                # Process the description
                logger.debug(f"Processing description from {phone}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error handling description: {str(e)}")
            return False