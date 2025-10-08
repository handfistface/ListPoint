from google.cloud import storage
from google.auth import external_account
from flask import Response
import os
import uuid
import json

REPLIT_SIDECAR_ENDPOINT = "http://127.0.0.1:1106"

def get_storage_client():
    """Create and return a Google Cloud Storage client configured for Replit."""
    credentials_info = {
        "type": "external_account",
        "audience": "replit",
        "subject_token_type": "access_token",
        "token_url": f"{REPLIT_SIDECAR_ENDPOINT}/token",
        "credential_source": {
            "url": f"{REPLIT_SIDECAR_ENDPOINT}/credential",
            "format": {
                "type": "json",
                "subject_token_field_name": "access_token",
            },
        },
        "universe_domain": "googleapis.com",
    }
    
    credentials = external_account.Credentials.from_info(credentials_info)
    return storage.Client(credentials=credentials, project="")

class ObjectStorageService:
    def __init__(self):
        self.client = get_storage_client()
        self.private_object_dir = os.getenv('PRIVATE_OBJECT_DIR', '')
        if not self.private_object_dir:
            raise ValueError(
                "PRIVATE_OBJECT_DIR not set. Create a bucket in 'Object Storage' "
                "tool and set PRIVATE_OBJECT_DIR env var (e.g., /bucket-name/thumbnails)."
            )
    
    def _parse_object_path(self, path):
        """Parse an object path into bucket name and object name."""
        if not path.startswith('/'):
            path = f'/{path}'
        
        parts = path.split('/')
        if len(parts) < 3:
            raise ValueError("Invalid path: must contain at least a bucket name")
        
        bucket_name = parts[1]
        object_name = '/'.join(parts[2:])
        
        return bucket_name, object_name
    
    def upload_thumbnail(self, file_obj, file_extension):
        """Upload a thumbnail to object storage and return the object path."""
        object_id = str(uuid.uuid4())
        full_path = f"{self.private_object_dir}/uploads/{object_id}{file_extension}"
        
        bucket_name, object_name = self._parse_object_path(full_path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        blob.upload_from_file(file_obj, content_type=f'image/{file_extension.lstrip(".")}')
        
        return f'/objects/{object_id}{file_extension}'
    
    def get_object_file(self, object_path):
        """Get a file object from the object storage."""
        if not object_path.startswith('/objects/'):
            raise ValueError("Invalid object path")
        
        parts = object_path[1:].split('/')
        if len(parts) < 2:
            raise ValueError("Invalid object path")
        
        entity_id = '/'.join(parts[1:])
        object_entity_path = f"{self.private_object_dir}/uploads/{entity_id}"
        
        bucket_name, object_name = self._parse_object_path(object_entity_path)
        bucket = self.client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        if not blob.exists():
            raise FileNotFoundError("Object not found")
        
        return blob
    
    def download_object(self, blob, response):
        """Stream an object to a Flask response."""
        try:
            blob.reload()
            
            response.headers['Content-Type'] = blob.content_type or 'application/octet-stream'
            response.headers['Content-Length'] = str(blob.size)
            response.headers['Cache-Control'] = 'public, max-age=3600'
            
            response.data = blob.download_as_bytes()
            return response
        except Exception as e:
            raise Exception(f"Error downloading file: {str(e)}")
