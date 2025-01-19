import os
import requests
import mimetypes
from datetime import datetime
from twilio.rest import Client
from config import TEMP_DIR, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN

class MediaHandler:
    def __init__(self, docs_app_instance, pending_descriptions):
        self.docs_app = docs_app_instance
        self.pending_descriptions = pending_descriptions
        self.client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        self.timeout = 30

    def get_extension_from_mime(self, mime_type):
        """Get file extension from MIME type"""
        if mime_type == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
            return '.xlsx'
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            return '.docx'
        elif mime_type == 'application/pdf':
            return '.pdf'
        elif mime_type == 'image/jpeg':
            return '.jpg'
        elif mime_type == 'image/png':
            return '.png'
        else:
            return mimetypes.guess_extension(mime_type) or '.txt'

    def handle_media_upload(self, request_values, user_phone, description):
        debug_info = ["=== Debug Info ==="]
        try:
            num_media = int(request_values.get('NumMedia', '0'))
            debug_info.append(f"Number of media files: {num_media}")

            # Log ALL request values for complete visibility
            debug_info.append("\nAll Request Values:")
            for key, value in sorted(request_values.items()):
                debug_info.append(f"{key}: {value}")

            success_count = 0
            failed_count = 0

            for media_index in range(num_media):
                try:
                    media_url = request_values.get(f'MediaUrl{media_index}')
                    mime_type = request_values.get(f'MediaContentType{media_index}', '')
                    message_type = request_values.get('MessageType', '')
                    profile_name = request_values.get('ProfileName', '')
                    wa_id = request_values.get('WaId', '')

                    debug_info.append(f"\nProcessing Media #{media_index + 1}:")
                    debug_info.append(f"Message Type: {message_type}")
                    debug_info.append(f"MIME Type: {mime_type}")
                    debug_info.append(f"Profile Name: {profile_name}")
                    debug_info.append(f"WhatsApp ID: {wa_id}")

                    # Extract additional media details
                    media_caption = request_values.get('Caption', '')
                    media_filename = request_values.get('OriginalMediaFilename', '')
                    document_id = request_values.get('DocumentId', '')

                    debug_info.append("Additional Media Details:")
                    debug_info.append(f"Caption: {media_caption}")
                    debug_info.append(f"Original Media Filename: {media_filename}")
                    debug_info.append(f"Document ID: {document_id}")

                    print("\n=== PROCESSING MEDIA FILE ===")
                    print("Raw Data:")
                    raw_data = request_values.get('raw_data', b'')
                    if raw_data:
                        try:
                            print("Raw Data (decoded):", raw_data.decode('utf-8', errors='ignore'))
                        except:
                            print("Could not decode raw data")

                    print("\nHeaders:")
                    raw_headers = request_values.get('raw_headers', {})
                    for header, value in raw_headers.items():
                        print(f"{header}: {value}")
                        if 'file' in header.lower() or 'name' in header.lower():
                            print(f"Potential filename header: {header}: {value}")

                    # Try to get file info from the URL
                    media_url_info = requests.head(
                        media_url,
                        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                        headers={'Accept': '*/*'}
                    )
                    print("\nMedia URL Headers:")
                    for header, value in media_url_info.headers.items():
                        print(f"{header}: {value}")

                    # Get filename from all possible sources
                    filename_candidates = {
                        'MediaFileName': request_values.get(f'MediaFileName{media_index}'),
                        'FileName': request_values.get('FileName'),
                        'Caption': media_caption,
                        'DocumentFileName': request_values.get('DocumentFileName'),
                        'OriginalName': request_values.get('OriginalName'),
                        'Body': request_values.get('Body', '').split('\n')[0] if request_values.get('Body') else None
                    }

                    debug_info.append("\nFilename Candidates:")
                    for source, name in filename_candidates.items():
                        debug_info.append(f"{source}: {name}")

                    # Try to get filename from candidates
                    original_filename = None
                    for name in filename_candidates.values():
                        if name and ('xlsx' in name.lower() or 'pdf' in name.lower() or 'doc' in name.lower()):
                            original_filename = name
                            debug_info.append(f"Selected filename from candidates: {original_filename}")
                            break

                    # If no filename found, generate one
                    if not original_filename:
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        extension = self.get_extension_from_mime(mime_type)
                        original_filename = f"Document_{timestamp}{extension}"
                        debug_info.append(f"Generated filename: {original_filename}")

                    # Download and store file
                    response_twilio = requests.get(
                        media_url,
                        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                        timeout=self.timeout,
                        headers={
                            'Accept': '*/*',
                            'User-Agent': 'WhatsApp/2.23.13.76',
                            'Accept-Encoding': 'gzip, deflate',
                            'Accept-Language': 'en-US'
                        }
                    )

                    debug_info.append(f"\nDownload Status: {response_twilio.status_code}")

                    if response_twilio.status_code == 200:
                        temp_path = os.path.join(TEMP_DIR, f'download_{datetime.now().timestamp()}_{media_index}')
                        debug_info.append(f"Temp Path: {temp_path}")

                        with open(temp_path, 'wb') as f:
                            f.write(response_twilio.content)

                        if self.docs_app.store_document(user_phone, temp_path, description or "", original_filename):
                            success_count += 1
                            debug_info.append("Document stored successfully")
                        else:
                            failed_count += 1
                            debug_info.append("Failed to store document")

                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                            debug_info.append("Temp file cleaned up")
                    else:
                        failed_count += 1
                        debug_info.append(f"Download failed: {response_twilio.text}")

                except Exception as e:
                    failed_count += 1
                    debug_info.append(f"Error processing media: {str(e)}")

            response = self._build_media_response(
                success_count, failed_count, num_media, description, original_filename
            )

            # Add debug info to response
            debug_text = "\n\n--- Debug Info ---\n" + "\n".join(debug_info)
            return response + debug_text

        except Exception as e:
            debug_info.append(f"Main handler error: {str(e)}")
            return "❌ Error processing documents.\n\n" + "\n".join(debug_info)

    def _build_media_response(self, success_count, failed_count, total_media, description, filename=None):
        if success_count > 0:
            if not description:
                if total_media == 1:
                    msg = f"Document '{filename}' stored without any description - "
                    msg += "you can reply to the document with a description that will help find it later."
                    return msg
                else:
                    return f"{success_count} documents stored without any description - you can reply to each document with a description that will help find it later."
            else:
                response_text = f"✅ Successfully stored {success_count} document(s)"
                if failed_count > 0:
                    response_text += f"\n❌ Failed to store {failed_count} document(s)"
                return response_text
        else:
            return "❌ Sorry, there was an error processing your documents. Please try again."