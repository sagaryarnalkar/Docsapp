# DocsApp WhatsApp Bot

A WhatsApp bot that helps manage and retrieve documents stored in Google Drive.

## Setup

1. Copy the example environment files:
```bash
cp .env.example .env
cp config.example.py config.py
```

2. Update the configuration files with your credentials:
- WhatsApp Business API credentials
- Google OAuth credentials
- Other environment-specific settings

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running with Docker

1. Build and run using Docker Compose:
```bash
docker-compose up --build
```

## Development

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

## Environment Variables

Required environment variables:
- `WHATSAPP_API_VERSION`: WhatsApp API version (default: v17.0)
- `WHATSAPP_PHONE_NUMBER_ID`: Your WhatsApp Phone Number ID
- `WHATSAPP_ACCESS_TOKEN`: Your WhatsApp Access Token
- `WHATSAPP_BUSINESS_ACCOUNT_ID`: Your WhatsApp Business Account ID
- `OAUTH_REDIRECT_URI`: OAuth redirect URI for Google Drive integration

## Directory Structure

- `app.py`: Main application file
- `models/`: Database models and business logic
  - `docs_app.py`: Main document handling logic
  - `rag/`: Retrieval-augmented generation components
  - `auth/`: Authentication components
- `routes/`: API routes and handlers
  - `handlers/`: Message handling components
    - `whatsapp/`: WhatsApp-specific handlers
      - `document/`: Document processing modules
      - `commands/`: Command processing modules
- `utils/`: Utility functions
- `config.py`: Application configuration
- `.env`: Environment variables 

## Architecture

### WhatsApp Document Processing

The WhatsApp document processing system uses a modular architecture:

```
WhatsAppHandler
      |
      ↓
WhatsAppDocumentProcessor (compatibility layer)
      |
      ↓
DocumentProcessor (core processing logic)
     / \
    /   \
   ↓     ↓
DocumentDownloader   DocumentTracker
```

For more details, see [WhatsApp Document Processing README](routes/handlers/whatsapp/document/README.md). 