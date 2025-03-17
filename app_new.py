"""Main Application Module (Refactored)
--------------------------------
This is the main entry point for the DocsApp application.
It initializes the Flask application and sets up all necessary components.
"""


from flask import Flask, send_from_directory
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration
from config import TEMP_DIR, BASE_DIR

# Import utility modules
from utils.logging_config import setup_logging
from utils.startup_checks import run_startup_checks
from utils.logger import get_logger

# Import middleware
from middleware import setup_middleware

# Import route modules
from routes.health import register_health_routes
from routes.auth import register_auth_routes
from routes.api import register_api_routes
from routes.webhook import register_webhook_routes

# Import debug routes if in development mode
if os.getenv("FLASK_ENV") == "development":
    from routes.debug_routes import register_debug_routes

# Import models and handlers
from models.user_state import UserState
from models.docs_app import DocsApp
from routes.handlers.auth_handler import AuthHandler
from routes.handlers.media_handler import MediaHandler
from routes.handlers.document_handler import DocumentHandler
from routes.handlers.command_handler import CommandHandler
from routes.handlers.whatsapp.whatsapp_handler import WhatsAppHandler

# Application version
VERSION = "v1.1.0"  # Increment this each time we deploy

# Set up logger
logger = get_logger(__name__)

def create_app():
    """
    Create and configure the Flask application.
    
    Returns:
        app: The configured Flask application
    """
    # Set up logging
    setup_logging(VERSION)
    
    # Run startup checks
    startup_results = run_startup_checks()
    
    # Create Flask app
    app = Flask(__name__)
    
    # Configure app
    app.config['VERSION'] = VERSION
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit
    
    # Set up middleware
    setup_middleware(app)
    
    # Initialize all required objects
    user_state = UserState()
    docs_app = DocsApp()
    pending_descriptions = {}
    user_documents = {}
    
    # Initialize all handlers
    auth_handler = AuthHandler(user_state)
    media_handler = MediaHandler(docs_app, pending_descriptions)
    document_handler = DocumentHandler(docs_app, user_documents)
    command_handler = CommandHandler(media_handler, document_handler)
    whatsapp_handler = WhatsAppHandler(docs_app, pending_descriptions, user_state)
    
    # Register routes
    register_health_routes(app)
    register_auth_routes(app, auth_handler)
    register_api_routes(app, whatsapp_handler)
    register_webhook_routes(app, whatsapp_handler)
    
    # Register debug routes if in development mode
    if os.getenv("FLASK_ENV") == "development":
        register_debug_routes(app)
    
    # Add route for serving temporary files
    @app.route('/temp/<path:filename>')
    def serve_file(filename):
        """
        Serve a temporary file.
        
        Args:
            filename: The filename to serve
            
        Returns:
            The file content
        """
        return send_from_directory(TEMP_DIR, filename)
    
    # Add route for home page
    @app.route("/")
    def home():
        """
        Home page.
        
        Returns:
            HTML response with basic information
        """
        return f"""
        <html>
            <head>
                <title>DocsApp WhatsApp Bot</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    h1 {{ color: #333; }}
                    .container {{ max-width: 800px; margin: 0 auto; }}
                    .info {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
                    .version {{ font-size: 0.8em; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>DocsApp WhatsApp Bot</h1>
                    <div class="info">
                        <p>This is the DocsApp WhatsApp Bot server.</p>
                        <p>The server is running and ready to process WhatsApp messages.</p>
                        <p class="version">Version: {VERSION}</p>
                    </div>
                </div>
            </body>
        </html>
        """
    
    return app

# Create the application
app = create_app()

if __name__ == "__main__":
    # Run the application
    debug_mode = os.getenv("FLASK_ENV") == "development"
    app.run(debug=debug_mode, host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
