"""
WhatsApp Handler Package
-----------------------
This package contains components for handling WhatsApp messages and interactions.
It provides a modular approach to processing different types of WhatsApp messages
and commands.

The main entry point is the WhatsAppHandler class which orchestrates all WhatsApp
interactions.
"""

from .handler import WhatsAppHandler, WhatsAppHandlerError

__all__ = ['WhatsAppHandler', 'WhatsAppHandlerError'] 