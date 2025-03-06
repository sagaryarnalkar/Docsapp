import os
import io
import logging
import time
import json
from typing import Dict, List, Optional
import vertexai
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel
from google.cloud import storage
from google.cloud import documentai
from google.api_core import retry
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from config import GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, SCOPES
from .database import Document
from .user_state import UserState
from google.cloud import aiplatform
import asyncio
from googleapiclient.errors import HttpError
from datetime import datetime
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

class RAGProcessorError(Exception):
    """Custom exception for RAG processor errors."""
    pass

class RAGProcessor:
    def __init__(self, project_id, location, credentials_path):
        """Initialize the RAG processor with Google Cloud credentials"""
        # Store both numeric and human-readable project IDs
        self.project_id = project_id
        self.location = location
        self.credentials_path = credentials_path
        
        print(f"\n=== Initializing RAG Processor ===")
        print(f"Project ID: {project_id}")
        print(f"Location: {location}")
        print(f"Credentials path: {credentials_path}")
        
        try:
            # Load credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES
            )
            print("✅ Successfully loaded service account credentials")
            
            # Initialize storage client
            self.storage_client = storage.Client(
                project=project_id, 
                credentials=self.credentials
            )
            print("✅ Successfully initialized storage client")
            
            # Initialize Vertex AI
            try:
                print("Initializing Vertex AI...")
                vertexai.init(
                    project=project_id,
                    location=location,
                    credentials=self.credentials
                )
                print("✅ Successfully initialized Vertex AI")
                self.is_available = True
            except Exception as vertex_err:
                print(f"⚠️ Warning: Could not initialize Vertex AI: {str(vertex_err)}")
                print("RAG processing will use fallback methods")
                self.is_available = True  # Still mark as available since we have fallbacks
            
            # Initialize Drive service
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            print("✅ Successfully initialized Drive service")
            
            # Set up temporary bucket for document processing
            self.temp_bucket_name = f"{project_id}-docsapp-temp"
            print(f"Temporary bucket name: {self.temp_bucket_name}")
            
            # Rate limiting
            self.last_request_time = 0
            self.min_request_interval = 1.0  # seconds
            
        except Exception as e:
            print(f"❌ Error initializing RAG processor: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            self.is_available = False
            raise RAGProcessorError(f"Failed to initialize RAG processor: {str(e)}")
        
        print("=== RAG Processor Initialized ===\n")

    def ensure_temp_bucket_exists(self):
        """Ensure temporary storage bucket exists"""
        try:
            bucket = self.storage_client.bucket(self.temp_bucket_name)
            if not bucket.exists():
                try:
                    bucket = self.storage_client.create_bucket(
                        self.temp_bucket_name,
                        location=self.location
                    )
                    logger.info(f"Created temporary bucket: {self.temp_bucket_name}")
                except Exception as e:
                    # If bucket already exists (409 error), that's fine
                    if "409" in str(e) and "already own it" in str(e):
                        logger.info(f"Bucket {self.temp_bucket_name} already exists")
                        return
                    raise  # Re-raise other exceptions
            logger.info(f"Using existing bucket: {self.temp_bucket_name}")
        except Exception as e:
            logger.error(f"Error ensuring temp bucket exists: {str(e)}")
            raise

    def _rate_limit(self):
        """Implement rate limiting for API calls"""
        current_time = time.time()
        time_since_last_call = current_time - self.last_request_time
        if time_since_last_call < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last_call)
        self.last_request_time = time.time()

    async def _extract_text(self, gcs_uri: str, mime_type: str) -> str:
        """Extract text from document in GCS"""
        print(f"\n=== Extracting Text from Document ===")
        print(f"Source: {gcs_uri}")
        print(f"MIME Type: {mime_type}")
        
        try:
            # Check if this is a local file
            if gcs_uri.startswith("local://"):
                local_file_path = gcs_uri.replace("local://", "")
                print(f"Reading from local file: {local_file_path}")
                
                with open(local_file_path, 'rb') as f:
                    content = f.read()
                
                print(f"Read {len(content)} bytes from local file")
            else:
                # Download from GCS
                bucket_name = gcs_uri.split('/')[2]
                blob_name = '/'.join(gcs_uri.split('/')[3:])
                
                print(f"Downloading from GCS bucket: {bucket_name}, blob: {blob_name}")
                
                bucket = self.storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                content = blob.download_as_bytes()
                
                print(f"Downloaded {len(content)} bytes from GCS")
            
            # For PDF files
            if mime_type == 'application/pdf':
                print("Processing as PDF")
                # Try using PyPDF2
                try:
                    print("Using PyPDF2")
                    reader = PdfReader(io.BytesIO(content))
                    text_content = ""
                    for page in reader.pages:
                        text_content += page.extract_text() + "\n"
                    print(f"PyPDF2 extracted {len(text_content)} characters")
                    return text_content
                except Exception as pdf_err:
                    print(f"PyPDF2 extraction failed: {str(pdf_err)}")
                    raise
            
            # For text-based files
            else:
                print("Processing as text file")
                # Try different encodings
                encodings = ['utf-8', 'latin-1', 'cp1252']
                for encoding in encodings:
                    try:
                        text_content = content.decode(encoding)
                        print(f"Successfully decoded using {encoding}")
                        return text_content
                    except UnicodeDecodeError:
                        continue
                
                raise Exception("Could not decode file with any supported encoding")
            
        except Exception as e:
            print(f"Error extracting text: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            raise

    async def _copy_drive_to_gcs(self, file_id: str, user_phone: str = None) -> str:
        """Copy file from Drive to GCS"""
        print("\n=== Copying File to GCS ===")
        print(f"File ID: {file_id}")
        print(f"User phone: {user_phone}")
        
        # Get a fresh Drive service with user credentials if provided
        if user_phone:
            try:
                drive_service = self._get_drive_service(user_phone)
                print(f"Using user-specific Drive service for {user_phone}")
            except Exception as e:
                print(f"Error getting user Drive service: {str(e)}")
                print("Falling back to default service account")
                drive_service = self.drive_service
        else:
            drive_service = self.drive_service
            print("Using default service account for Drive access")
        
        # Create local temp directory if it doesn't exist
        local_temp_dir = os.path.join(os.getcwd(), "data", "docsapp", "temp")
        print(f"=== Creating Persistent Directories ===")
        os.makedirs(local_temp_dir, exist_ok=True)
        print(f"Created/verified directory: {local_temp_dir}")
        print(f"Contents: {os.listdir(local_temp_dir)}")
        
        try:
            print("Fetching file from Drive")
            max_retries = 5
            retry_delay = 2  # seconds
            
            for attempt in range(max_retries):
                try:
                    # Get file metadata with more detailed logging
                    print(f"Attempt {attempt+1}/{max_retries}: Getting file metadata")
                    
                    # First check if the file exists and is accessible
                    try:
                        file_metadata = drive_service.files().get(
                            fileId=file_id,
                            supportsAllDrives=True,
                            fields='name,mimeType,size,modifiedTime'
                        ).execute()
                    except HttpError as e:
                        if e.resp.status == 404:
                            # File not found - check if it's in the user's DocsApp folder
                            print("File not found with direct ID. Checking in user's DocsApp folder...")
                            
                            # Try to find the DocsApp folder
                            folder_name = "DocsApp Files"
                            folder_query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                            folders = drive_service.files().list(q=folder_query, spaces='drive').execute()
                            
                            if not folders.get('files', []):
                                print(f"DocsApp folder not found for user {user_phone}")
                                raise Exception(f"Document not found. Please make sure you've shared the document with DocsApp or uploaded it to your DocsApp Files folder.")
                            
                            # Check files in the DocsApp folder
                            folder_id = folders['files'][0]['id']
                            print(f"Found DocsApp folder with ID: {folder_id}")
                            
                            # List files in the folder
                            files_query = f"'{folder_id}' in parents and trashed=false"
                            files = drive_service.files().list(q=files_query, spaces='drive').execute()
                            
                            if not files.get('files', []):
                                print(f"No files found in DocsApp folder for user {user_phone}")
                                raise Exception(f"No documents found in your DocsApp Files folder. Please upload a document first.")
                            
                            print(f"Found {len(files.get('files', []))} files in DocsApp folder")
                            
                            # Check if our file_id is in the list or if it's a partial match
                            for file in files.get('files', []):
                                if file['id'] == file_id or file_id in file['id']:
                                    print(f"Found matching file: {file['name']} (ID: {file['id']})")
                                    file_id = file['id']  # Update to the correct ID if it was partial
                                    file_metadata = file
                                    break
                            else:
                                print(f"File with ID {file_id} not found in DocsApp folder")
                                raise Exception(f"Document not found. Please check the document ID or upload the document again.")
                        else:
                            # Other API error
                            raise
                    
                    print(f"File metadata retrieved:")
                    print(f"  Name: {file_metadata.get('name')}")
                    print(f"  MIME Type: {file_metadata.get('mimeType')}")
                    print(f"  Size: {file_metadata.get('size', 'unknown')} bytes")
                    print(f"  Modified: {file_metadata.get('modifiedTime')}")
                    
                    # Try to use GCS if available, otherwise use local storage
                    use_local_storage = False
                    gcs_uri = None
                    
                    try:
                        # Ensure temp bucket exists
                        self.ensure_temp_bucket_exists()
                        print(f"Confirmed GCS bucket exists: {self.temp_bucket_name}")
                        
                        # Generate GCS URI with more unique naming
                        timestamp = int(time.time())
                        safe_filename = "".join(c for c in file_metadata.get('name', 'unnamed') 
                                             if c.isalnum() or c in ('-', '_', '.'))
                        # Add user identifier to filename if available
                        user_suffix = f"_{user_phone[-4:]}" if user_phone else ""
                        gcs_object_name = f"{timestamp}{user_suffix}_{safe_filename}"
                        gcs_uri = f"gs://{self.temp_bucket_name}/{gcs_object_name}"
                        
                        print(f"Will copy to GCS: {gcs_uri}")
                    except Exception as gcs_err:
                        print(f"GCS access error: {str(gcs_err)}")
                        print("Falling back to local file storage")
                        use_local_storage = True
                    
                    # Download file content with progress tracking
                    print(f"Downloading file content from Drive")
                    request = drive_service.files().get_media(
                        fileId=file_id,
                        supportsAllDrives=True
                    )
                    
                    file_content = io.BytesIO()
                    downloader = MediaIoBaseDownload(file_content, request)
                    
                    done = False
                    download_start = time.time()
                    while not done:
                        status, done = downloader.next_chunk()
                        if status:
                            progress = int(status.progress() * 100)
                            print(f"Download {progress}% complete")
                    
                    download_time = time.time() - download_start
                    file_content.seek(0)
                    file_size = file_content.getbuffer().nbytes
                    print(f"Download completed: {file_size} bytes in {download_time:.2f} seconds")
                    
                    # Use local storage if GCS is not available
                    if use_local_storage:
                        # Generate local file path
                        timestamp = int(time.time())
                        safe_filename = "".join(c for c in file_metadata.get('name', 'unnamed') 
                                             if c.isalnum() or c in ('-', '_', '.'))
                        user_suffix = f"_{user_phone[-4:]}" if user_phone else ""
                        local_filename = f"{timestamp}{user_suffix}_{safe_filename}"
                        local_file_path = os.path.join(local_temp_dir, local_filename)
                        
                        print(f"Saving to local file: {local_file_path}")
                        
                        # Write to local file
                        with open(local_file_path, 'wb') as f:
                            f.write(file_content.getbuffer())
                        
                        print(f"✅ Successfully saved file locally: {local_file_path}")
                        # Return a special URI format for local files
                        return f"local://{local_file_path}"
                    else:
                        # Upload to GCS with retry
                        print(f"Uploading to GCS bucket: {self.temp_bucket_name}")
                        upload_start = time.time()
                        
                        for upload_attempt in range(3):  # 3 upload retries
                            try:
                                bucket = self.storage_client.bucket(self.temp_bucket_name)
                                blob = bucket.blob(gcs_object_name)
                                blob.upload_from_file(file_content)
                                upload_time = time.time() - upload_start
                                print(f"Upload completed in {upload_time:.2f} seconds")
                                break
                            except Exception as upload_err:
                                print(f"Upload attempt {upload_attempt+1} failed: {str(upload_err)}")
                                if upload_attempt == 2:  # Last attempt
                                    print("All GCS upload attempts failed, falling back to local storage")
                                    file_content.seek(0)
                                    
                                    # Generate local file path
                                    local_filename = f"{timestamp}{user_suffix}_{safe_filename}"
                                    local_file_path = os.path.join(local_temp_dir, local_filename)
                                    
                                    print(f"Saving to local file: {local_file_path}")
                                    
                                    # Write to local file
                                    with open(local_file_path, 'wb') as f:
                                        f.write(file_content.getbuffer())
                                    
                                    print(f"✅ Successfully saved file locally: {local_file_path}")
                                    # Return a special URI format for local files
                                    return f"local://{local_file_path}"
                                file_content.seek(0)  # Reset file pointer for retry
                                await asyncio.sleep(2)
                        
                        # Verify the file exists in GCS
                        try:
                            print("Verifying file exists in GCS")
                            bucket = self.storage_client.bucket(self.temp_bucket_name)
                            blob = bucket.blob(gcs_object_name)
                            if blob.exists():
                                print(f"✅ Verified file exists in GCS: {gcs_uri}")
                            else:
                                print(f"⚠️ File not found in GCS after upload")
                                if attempt < max_retries - 1:
                                    print(f"Will retry entire process")
                                    continue
                                else:
                                    print("Falling back to local storage")
                                    file_content.seek(0)
                                    
                                    # Generate local file path
                                    local_filename = f"{timestamp}{user_suffix}_{safe_filename}"
                                    local_file_path = os.path.join(local_temp_dir, local_filename)
                                    
                                    print(f"Saving to local file: {local_file_path}")
                                    
                                    # Write to local file
                                    with open(local_file_path, 'wb') as f:
                                        f.write(file_content.getbuffer())
                                    
                                    print(f"✅ Successfully saved file locally: {local_file_path}")
                                    # Return a special URI format for local files
                                    return f"local://{local_file_path}"
                        except Exception as verify_err:
                            print(f"Error verifying file in GCS: {str(verify_err)}")
                            if attempt < max_retries - 1:
                                print(f"Will retry entire process")
                                continue
                            else:
                                print("Falling back to local storage")
                                file_content.seek(0)
                                
                                # Generate local file path
                                local_filename = f"{timestamp}{user_suffix}_{safe_filename}"
                                local_file_path = os.path.join(local_temp_dir, local_filename)
                                
                                print(f"Saving to local file: {local_file_path}")
                                
                                # Write to local file
                                with open(local_file_path, 'wb') as f:
                                    f.write(file_content.getbuffer())
                                
                                print(f"✅ Successfully saved file locally: {local_file_path}")
                                # Return a special URI format for local files
                                return f"local://{local_file_path}"
                        
                        print(f"✅ Successfully copied file to GCS: {gcs_uri}")
                        return gcs_uri
                    
                except HttpError as e:
                    if e.resp.status in [404, 403, 500, 503] and attempt < max_retries - 1:
                        print(f"Drive API error (status {e.resp.status}), retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})")
                        print(f"Error details: {str(e)}")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30 seconds
                    else:
                        if e.resp.status == 404:
                            print(f"File not found after {max_retries} attempts")
                            raise Exception(f"Document not found. Please check if the document exists and you have permission to access it.")
                        else:
                            print(f"Unrecoverable Drive API error: {str(e)}")
                            raise
                except Exception as other_e:
                    print(f"Unexpected error during copy attempt {attempt + 1}: {str(other_e)}")
                    import traceback
                    print(f"Traceback:\n{traceback.format_exc()}")
                    if attempt < max_retries - 1:
                        print(f"Will retry in {retry_delay} seconds")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 30)
                    else:
                        raise
                    
        except Exception as e:
            print(f"Drive access error: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            raise Exception(f"Could not access file in Drive: {str(e)}")
            
        raise Exception("Failed to copy file to GCS after maximum retries")

    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 100) -> List[Dict]:
        """Split text into overlapping chunks with metadata"""
        chunks = []
        start = 0
        
        while start < len(text):
            # Get chunk with overlap
            end = start + chunk_size
            chunk_text = text[start:end]
            
            # Add some context by not breaking mid-sentence
            if end < len(text):
                last_period = chunk_text.rfind('.')
                if last_period != -1:
                    end = start + last_period + 1
                    chunk_text = text[start:end]
            
            # Create chunk with metadata
            chunk = {
                'text': chunk_text,
                'metadata': {
                    'start_char': start,
                    'end_char': end,
                    'chunk_index': len(chunks)
                }
            }
            chunks.append(chunk)
            
            # Move start position, accounting for overlap
            start = end - overlap
            
        return chunks

    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Vertex AI's text embedding model"""
        print("=== Step 4: Generating Embeddings ===")
        print(f"Starting embedding generation at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Generating embeddings for {len(texts)} chunks")
        
        # Only use Vertex AI for embeddings
        try:
            embeddings = await self._generate_embeddings_vertex_ai(texts)
            print(f"✅ Successfully generated {len(embeddings)} embeddings")
            return embeddings
        except Exception as e:
            print(f"❌ Error generating embeddings: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            raise e
    
    async def _generate_embeddings_vertex_ai(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Vertex AI's text embedding model"""
        try:
            print("Attempting to use Vertex AI text embedding model...")
            print(f"Project ID: {self.project_id}")
            print(f"Location: {self.location}")
            print(f"Credentials path: {self.credentials_path}")
            
            # Print environment information
            import os
            print(f"GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')}")
            print(f"GOOGLE_CLOUD_PROJECT: {os.environ.get('GOOGLE_CLOUD_PROJECT')}")
            
            # Initialize Vertex AI explicitly
            print("Initializing Vertex AI...")
            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=self.credentials
            )
            print("Vertex AI initialized successfully")
            
            # Use the new text-embedding-005 model as recommended by Google
            print("Trying to load text embedding model...")
            model_id = "text-embedding-005"  # Updated from textembedding-gecko@latest
            print(f"Using model: {model_id}")
            model = TextEmbeddingModel.from_pretrained(model_id)
            print("Model loaded successfully")
            
            # Generate embeddings in batches
            embeddings = []
            batch_size = 5  # Adjust based on rate limits
            
            for i in range(0, len(texts), batch_size):
                print(f"Processing batch {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
                batch = texts[i:i + batch_size]
                batch_embeddings = model.get_embeddings(batch)
                embeddings.extend([emb.values for emb in batch_embeddings])
                print(f"Batch {i//batch_size + 1} processed successfully")
            
            print(f"Successfully generated {len(embeddings)} embeddings")
            return embeddings
            
        except Exception as e:
            print(f"Vertex AI embedding failed: {str(e)}")
            import traceback
            print(f"Detailed error traceback:\n{traceback.format_exc()}")
            
            # Try with a fallback model if the primary one fails
            try:
                print("Trying fallback model text-embedding-004...")
                model = TextEmbeddingModel.from_pretrained("text-embedding-004")
                
                embeddings = []
                batch_size = 5
                
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    batch_embeddings = model.get_embeddings(batch)
                    embeddings.extend([emb.values for emb in batch_embeddings])
                
                print(f"Successfully generated {len(embeddings)} embeddings with fallback model")
                return embeddings
            except Exception as alt_e:
                print(f"Fallback model also failed: {str(alt_e)}")
                raise e  # Raise the original error
    
    async def _store_embeddings(self, embeddings: List[List[float]], chunks: List[Dict], index_id: str = None) -> str:
        """Store embeddings in Vertex AI Vector Search"""
        try:
            # Initialize Vertex AI Vector Search client
            client = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=f"projects/{self.project_id}/locations/{self.location}/indexEndpoints/{index_id}"
            )
            
            # Prepare documents with embeddings and metadata
            documents = []
            for embedding, chunk in zip(embeddings, chunks):
                doc = {
                    'embedding': embedding,
                    'metadata': {
                        'text': chunk['text'],
                        **chunk['metadata']
                    }
                }
                documents.append(doc)
            
            # Store in vector index
            response = client.upsert_datapoints(
                embeddings=[doc['embedding'] for doc in documents],
                metadata=[doc['metadata'] for doc in documents]
            )
            
            return response.index_id
            
        except Exception as e:
            logger.error(f"Error storing embeddings: {str(e)}")
            raise

    async def _search_similar_chunks(self, query_embedding: List[float], index_id: str, top_k: int = 5) -> List[Dict]:
        """Search for similar chunks in Vector Search"""
        try:
            # Initialize Vector Search client
            client = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=f"projects/{self.project_id}/locations/{self.location}/indexEndpoints/{index_id}"
            )
            
            # Search for similar chunks
            response = client.find_neighbors(
                deployed_index_id=index_id,
                queries=[query_embedding],
                num_neighbors=top_k
            )
            
            # Get matching chunks with scores
            matches = []
            for neighbor in response.nearest_neighbors[0]:
                matches.append({
                    'text': neighbor.metadata['text'],
                    'score': neighbor.distance,
                    'metadata': neighbor.metadata
                })
            
            return matches
            
        except Exception as e:
            logger.error(f"Error searching similar chunks: {str(e)}")
            raise

    def _create_rag_prompt(self, question: str, relevant_chunks: List[Dict]) -> str:
        """Create a prompt for RAG using relevant chunks"""
        # Combine relevant chunks into context
        context = "\n\n".join([
            f"Chunk {i+1}:\n{chunk['text']}"
            for i, chunk in enumerate(relevant_chunks)
        ])
        
        return f"""Answer the following question using only the provided context. If the answer cannot be found in the context, say so explicitly.

Context:
{context}

Question: {question}

Instructions:
1. Answer based only on the provided context
2. If information is missing or unclear, say so
3. Cite specific parts of the context
4. Be concise but complete

Answer:"""

    async def process_document_async(self, file_id: str, mime_type: str, user_phone: str = None) -> Dict:
        """Process a document asynchronously using Vertex AI."""
        print(f"\n{'='*50}")
        print("STARTING DOCUMENT PROCESSING")
        print(f"{'='*50}")
        print(f"File ID: {file_id}")
        print(f"MIME Type: {mime_type}")
        print(f"User: {user_phone}")
        
        # Add timestamp for tracking processing time
        import time
        start_time = time.time()
        print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        if not self.is_available:
            print("RAG processing not available")
            return {
                "status": "error",
                "error": "RAG processing not available",
                "data_store_id": None,
                "document_id": None,
                "filename": None
            }

        try:
            self._rate_limit()
            
            # Get file metadata first
            drive_service = self._get_drive_service(user_phone)
            try:
                print(f"Getting file metadata for file ID: {file_id}")
                file_metadata = drive_service.files().get(
                    fileId=file_id, 
                    fields='name,mimeType',
                    supportsAllDrives=True
                ).execute()
                filename = file_metadata.get('name', 'Unknown Document')
                actual_mime_type = file_metadata.get('mimeType')
                print(f"Processing document: {filename}")
                print(f"Detected MIME type: {actual_mime_type}")
                
                # Use detected mime type if none was provided
                if not mime_type:
                    mime_type = actual_mime_type
                    print(f"Using detected MIME type: {mime_type}")
            except Exception as e:
                print(f"Error getting file metadata: {str(e)}")
                import traceback
                print(f"Metadata error traceback:\n{traceback.format_exc()}")
                filename = 'Unknown Document'
            
            # 1. Copy file to GCS for processing
            print("\n=== Step 1: Copying to GCS ===")
            try:
                print(f"Starting copy to GCS at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                gcs_uri = await self._copy_drive_to_gcs(file_id, user_phone)
                print(f"✅ File copied to GCS: {gcs_uri}")
                print(f"Copy completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Copy took {time.time() - start_time:.2f} seconds")
            except Exception as e:
                print(f"❌ Error copying to GCS: {str(e)}")
                import traceback
                print(f"GCS copy error traceback:\n{traceback.format_exc()}")
                return {
                    "status": "error",
                    "error": f"Failed to copy to GCS: {str(e)}",
                    "data_store_id": None,
                    "document_id": None,
                    "filename": filename
                }
            
            # 2. Extract text from document
            print("\n=== Step 2: Extracting Text ===")
            try:
                print(f"Starting text extraction at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                text_content = await self._extract_text(gcs_uri, mime_type)
                print(f"✅ Text extracted successfully ({len(text_content)} characters)")
                print(f"Extraction completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Extraction took {time.time() - start_time:.2f} seconds total")
                
                # Log a sample of the extracted text for debugging
                text_sample = text_content[:500] + "..." if len(text_content) > 500 else text_content
                print(f"Text sample: {text_sample}")
            except Exception as e:
                print(f"❌ Error extracting text: {str(e)}")
                import traceback
                print(f"Text extraction error traceback:\n{traceback.format_exc()}")
                return {
                    "status": "error",
                    "error": f"Failed to extract text: {str(e)}",
                    "data_store_id": None,
                    "document_id": None,
                    "filename": filename
                }
            
            # 3. Split text into chunks
            print("\n=== Step 3: Chunking Text ===")
            try:
                print(f"Starting text chunking at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                chunks = self._chunk_text(text_content)
                print(f"✅ Split into {len(chunks)} chunks")
                print(f"Chunking completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                # Log a sample chunk for debugging
                if chunks:
                    sample_chunk = chunks[0]['text'][:200] + "..." if len(chunks[0]['text']) > 200 else chunks[0]['text']
                    print(f"Sample chunk: {sample_chunk}")
            except Exception as e:
                print(f"❌ Error chunking text: {str(e)}")
                import traceback
                print(f"Chunking error traceback:\n{traceback.format_exc()}")
                return {
                    "status": "error",
                    "error": f"Failed to chunk text: {str(e)}",
                    "data_store_id": None,
                    "document_id": None,
                    "filename": filename
                }
            
            # 4. Generate embeddings
            print("\n=== Step 4: Generating Embeddings ===")
            try:
                print(f"Starting embedding generation at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                chunk_texts = [chunk['text'] for chunk in chunks]
                print(f"Generating embeddings for {len(chunk_texts)} chunks")
                embeddings = await self._generate_embeddings(chunk_texts)
                print(f"✅ Generated {len(embeddings)} embeddings")
                print(f"Embedding generation completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Embedding generation took {time.time() - start_time:.2f} seconds total")
            except Exception as e:
                print(f"❌ Error generating embeddings: {str(e)}")
                import traceback
                print(f"Embedding error traceback:\n{traceback.format_exc()}")
                return {
                    "status": "error",
                    "error": f"Failed to generate embeddings: {str(e)}",
                    "data_store_id": None,
                    "document_id": None,
                    "filename": filename
                }
            
            # 5. Store embeddings in Vector Search
            print("\n=== Step 5: Storing Embeddings ===")
            try:
                print(f"Starting embedding storage at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                index_id = await self._store_embeddings(embeddings, chunks)
                print(f"✅ Stored embeddings with index ID: {index_id}")
                print(f"Storage completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Total processing time: {time.time() - start_time:.2f} seconds")
            except Exception as e:
                print(f"❌ Error storing embeddings: {str(e)}")
                import traceback
                print(f"Storage error traceback:\n{traceback.format_exc()}")
                return {
                    "status": "error",
                    "error": f"Failed to store embeddings: {str(e)}",
                    "data_store_id": None,
                    "document_id": None,
                    "filename": filename
                }
            
            print(f"\n{'='*50}")
            print("DOCUMENT PROCESSING COMPLETED SUCCESSFULLY")
            print(f"Total time: {time.time() - start_time:.2f} seconds")
            print(f"{'='*50}")
            
            return {
                "status": "success",
                "data_store_id": index_id,
                "document_id": file_id,
                "filename": filename
            }
            
        except Exception as e:
            print(f"\n{'='*50}")
            print("DOCUMENT PROCESSING FAILED")
            print(f"Error: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            print(f"Total time before failure: {time.time() - start_time:.2f} seconds")
            print(f"{'='*50}")
            
            return {
                "status": "error",
                "error": str(e),
                "data_store_id": None,
                "document_id": None,
                "filename": filename if 'filename' in locals() else 'Unknown Document'
            }

    async def query_documents(self, question: str, data_store_id: str) -> Dict:
        """Query documents using Vertex AI Vector Search and LLM."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            print(f"\n=== Processing Question ===")
            print(f"Question: {question}")
            print(f"Data Store ID: {data_store_id}")
            
            # 1. Generate embedding for question
            question_embeddings = await self._generate_embeddings([question])
            question_embedding = question_embeddings[0]
            print("Generated question embedding")
            
            # 2. Search for similar chunks
            relevant_chunks = await self._search_similar_chunks(
                question_embedding, 
                data_store_id
            )
            print(f"Found {len(relevant_chunks)} relevant chunks")
            
            # 3. Create RAG prompt
            prompt = self._create_rag_prompt(question, relevant_chunks)
            
            # 4. Generate answer using Gemini Pro
            response = self.language_model.generate_content(prompt)
            print("Generated answer successfully")
            
            return {
                "status": "success",
                "answer": response.text,
                "sources": [chunk['metadata'] for chunk in relevant_chunks]
            }
            
        except Exception as e:
            print(f"Error querying documents: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Error querying documents: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def get_document_summary(self, data_store_id: str, document_id: str) -> Dict:
        """Get a comprehensive document summary using Vertex AI."""
        if not self.is_available:
            return {
                "status": "error",
                "error": "RAG processing not available"
            }

        try:
            logger.info(f"Generating summary for document: {document_id}")
            self._rate_limit()
            
            prompt = """Please provide a comprehensive summary of the document.
            Include:
            1. Main topics and key points
            2. Important findings or conclusions
            3. Any significant dates, numbers, or statistics
            4. Document structure and organization"""
            
            response = self.language_model.generate_content(prompt)
            
            return {
                "status": "success",
                "summary": response.text,
                "metadata": {}
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }

    async def process_question(self, question: str, documents: List[Document], user_phone: str = None) -> str:
        """Process a question against the given documents"""
        if not self.is_available:
            raise RAGProcessorError("RAG processing is not available")

        try:
            # Validate input
            if not question or not documents:
                raise RAGProcessorError("Question and documents are required")

            # Get Drive service for accessing documents
            drive_service = self._get_drive_service(user_phone)
            if not drive_service:
                raise RAGProcessorError("Could not access Google Drive")

            # Combine document information
            document_texts = []
            for doc in documents:
                try:
                    # Get document metadata
                    file_metadata = drive_service.files().get(
                        fileId=doc.file_id, 
                        fields='name,mimeType'
                    ).execute()

                    doc_info = [
                        f"Document: {file_metadata.get('name', doc.filename)}",
                        f"Type: {file_metadata.get('mimeType', 'unknown')}"
                    ]

                    if doc.description:
                        doc_info.append(f"Description: {doc.description}")

                    document_texts.append("\n".join(doc_info))
                except Exception as e:
                    logger.warning(f"Could not get metadata for document {doc.file_id}: {str(e)}")
                    # Still include basic information
                    document_texts.append(f"Document: {doc.filename}\nDescription: {doc.description}")
            
            if not document_texts:
                raise RAGProcessorError("No accessible documents found")

            combined_text = "\n\n".join(document_texts)
            
            # Create prompt with more context
            prompt = f"""Based on the following document information, please answer this question: {question}

Available Documents:
{combined_text}

Instructions:
1. Answer the question based only on the information provided in the documents
2. If the answer cannot be found in the documents, explicitly say so
3. If you find partial information, explain what is known and what is missing
4. If multiple documents contain relevant information, mention which document provides each piece of information

Question: {question}
"""
            
            # Generate response with controlled parameters
            response = self.language_model.generate_content(prompt)
            
            return response.text
            
        except RAGProcessorError:
            raise
        except Exception as e:
            logger.error(f"Error processing question: {str(e)}", exc_info=True)
            raise RAGProcessorError(f"Failed to process question: {str(e)}")

    def _get_drive_service(self, user_phone=None):
        """Get Google Drive service instance"""
        try:
            if user_phone:
                # Try to get user-specific credentials first
                from models.user_state import UserState
                user_state = UserState()
                user_creds = user_state.get_credentials(user_phone)
                
                if user_creds and user_creds.valid:
                    print(f"Using user credentials for {user_phone}")
                    return build('drive', 'v3', credentials=user_creds)
                else:
                    print(f"No valid user credentials found for {user_phone}, falling back to service account")
            
            # Fall back to service account credentials
            print("Using service account credentials for Drive access")
            return build('drive', 'v3', credentials=self.credentials)
        except Exception as e:
            print(f"Error getting Drive service: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            logger.error(f"Error getting Drive service: {str(e)}")
            raise RAGProcessorError(f"Failed to get Drive service: {str(e)}") 