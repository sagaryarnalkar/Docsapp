"""
List Command Handler for WhatsApp
------------------------------
This module handles the 'list' command to display the user's documents.
"""

import logging
import traceback
import time
import hashlib
import uuid
import json
from ..commands.base_command import BaseCommandHandler

logger = logging.getLogger(__name__)

class ListCommandHandler(BaseCommandHandler):
    """
    Handler for the 'list' command.
    
    This command lists all documents stored by the user.
    """
    
    async def handle(self, from_number):
        """
        Handle the 'list' command.
        
        Args:
            from_number: The user's phone number
            
        Returns:
            tuple: (message, status_code)
        """
        # Generate a unique ID for this command execution
        command_id = self.generate_command_id("list", from_number)
        print(f"\n==================================================")
        print(f"[DEBUG] LIST COMMAND EXECUTION START - {command_id}")
        print(f"[DEBUG] From: {from_number}")
        print(f"[DEBUG] Time: {int(time.time())}")
        print(f"[DEBUG] List handler: {self}")
        print(f"[DEBUG] List handler docs_app: {self.docs_app}")
        print(f"[DEBUG] List handler type(docs_app): {type(self.docs_app)}")
        print(f"[DEBUG] List handler message_sender: {self.message_sender}")
        print(f"==================================================")
        
        try:
            print(f"[DEBUG] {command_id} - Starting docs_app.get_user_documents")
            print(f"[DEBUG] {command_id} - docs_app methods: {dir(self.docs_app)}")
            
            # Try to print some information about the docs_app object
            try:
                print(f"[DEBUG] {command_id} - docs_app.__dict__: {self.docs_app.__dict__}")
            except Exception as dict_err:
                print(f"[DEBUG] {command_id} - Error accessing docs_app.__dict__: {str(dict_err)}")
            
            # Safely attempt to get documents, with very detailed error handling
            documents = []
            try:
                print(f"[DEBUG] {command_id} - About to call docs_app.get_user_documents({from_number})")
                documents = self.docs_app.get_user_documents(from_number)
                print(f"[DEBUG] {command_id} - Retrieved documents: {documents}")
                print(f"[DEBUG] {command_id} - Document count: {len(documents)}")
                print(f"[DEBUG] {command_id} - Document types: {[type(doc) for doc in documents]}")
            except AttributeError as attr_err:
                print(f"[DEBUG] {command_id} - AttributeError calling get_user_documents: {str(attr_err)}")
                print(f"[DEBUG] {command_id} - AttributeError traceback: {traceback.format_exc()}")
                documents = []
            except TypeError as type_err:
                print(f"[DEBUG] {command_id} - TypeError calling get_user_documents: {str(type_err)}")
                print(f"[DEBUG] {command_id} - TypeError traceback: {traceback.format_exc()}")
                documents = []
            except Exception as doc_err:
                print(f"[DEBUG] {command_id} - General exception calling get_user_documents: {str(doc_err)}")
                print(f"[DEBUG] {command_id} - Exception traceback: {traceback.format_exc()}")
                documents = []
            
            # Build the response message
            print(f"[DEBUG] {command_id} - Building response message")
            if documents:
                print(f"[DEBUG] {command_id} - Documents found: {len(documents)}")
                message = "📄 *Your Documents:*\n\n"
                for i, doc in enumerate(documents, 1):
                    # Safely extract document info with error handling
                    try:
                        doc_id = doc.get('id', 'unknown-id')
                        doc_name = doc.get('name', 'Unnamed Document')
                        doc_type = doc.get('type', 'Unknown Type')
                        doc_date = doc.get('upload_date', 'Unknown Date')
                        
                        message += f"{i}. *{doc_name}*\n"
                        message += f"   Type: {doc_type}\n"
                        message += f"   ID: {doc_id}\n"
                        message += f"   Date: {doc_date}\n\n"
                    except Exception as format_err:
                        print(f"[DEBUG] {command_id} - Error formatting document {i}: {str(format_err)}")
                        message += f"{i}. Error displaying document\n\n"
            else:
                print(f"[DEBUG] {command_id} - No documents found")
                message = "📂 You don't have any documents stored yet. Send a document to store it."
            
            # Add a unique timestamp to prevent duplicate message detection
            timestamp = int(time.time())
            message += f"\n\n_List generated at: {timestamp}_"
            
            # Send the response and record the result
            print(f"[DEBUG] {command_id} - Sending list response")
            success = await self.send_response(from_number, message, "list_result", command_id)
            print(f"[DEBUG] {command_id} - Send result: {success}")
            
            if success:
                print(f"[DEBUG] {command_id} - List command completed successfully")
                return "List command processed successfully", 200
            else:
                print(f"[DEBUG] {command_id} - Failed to send list response")
                # Try sending a direct error message as fallback
                try:
                    error_message = "❌ Sorry, I couldn't retrieve your document list. Please try again later."
                    await self.send_error_message(from_number, error_message, command_id)
                except Exception as send_err:
                    print(f"[DEBUG] {command_id} - Failed to send error message: {str(send_err)}")
                return "Failed to send list response", 500
                
        except Exception as e:
            print(f"[DEBUG] {command_id} - List command failed with error: {str(e)}")
            print(f"[DEBUG] {command_id} - Traceback: {traceback.format_exc()}")
            
            # Try to send an error message
            try:
                error_message = f"❌ Sorry, an error occurred while getting your documents. Please try again."
                await self.send_error_message(from_number, error_message, command_id)
            except Exception as send_err:
                print(f"[DEBUG] {command_id} - Failed to send error message: {str(send_err)}")
                print(f"[DEBUG] {command_id} - Error message traceback: {traceback.format_exc()}")
                
                # Last resort - try direct message send
                try:
                    print(f"[DEBUG] {command_id} - Attempting direct message send as last resort")
                    await self.message_sender.send_message(
                        from_number,
                        "❌ Error retrieving your documents. Please try again.",
                        message_type="error",
                        bypass_deduplication=True
                    )
                except Exception as direct_err:
                    print(f"[DEBUG] {command_id} - Direct message also failed: {str(direct_err)}")
                
            return "Error processing list command", 500 