
class ResponseBuilder:
    @staticmethod
    def create_response(message_text):
        """Create a WhatsApp response with the given message"""
        response = MessagingResponse()
        msg = response.message()
        msg.body(message_text)
        return str(response)

    @staticmethod
    def get_help_message():
        """Get the help message text"""
        return """📚 Here's how to use DocsApp:
1. Send any document with a description to store it
2. Type 'find <description>' to retrieve your document
3. Type 'list' to see all your documents
4. Type 'delete <number>' to delete a document
5. Type 'help' to see this message again

Tips:
- When sending a document, include a good description
- Documents are stored in 'DocsApp Files' folder in your Drive
- You can search using keywords from both filename and description"""

    @staticmethod
    def get_welcome_message():
        """Get the default welcome message"""
        return """What would you like to do?
1. Send any document with a description to store it
2. Type 'find <description>' to retrieve documents
3. Type 'list' to see all your documents
4. Type 'help' for more information"""

    @staticmethod
    def get_auth_message(auth_url):
        """Get the authorization message with the OAuth URL"""
        return f"""Welcome to DocsApp! 🚀

Please authorize access to your Google Drive:
{auth_url}

After authorization:
1. Send any document with a description to store it
2. Type 'find <description>' to retrieve documents
3. Type 'list' to see all your documents
4. Type 'help' for more information"""