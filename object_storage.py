from replit.object_storage import Client
from flask import Response
import uuid

class ObjectStorageService:
    def __init__(self):
        # Replit Client handles authentication automatically
        self.client = Client()
    
    def upload_thumbnail(self, file_obj, file_extension):
        """Upload a thumbnail to object storage and return the object path."""
        object_id = str(uuid.uuid4())
        object_name = f"thumbnails/{object_id}{file_extension}"
        
        # Read the file data
        file_data = file_obj.read()
        
        # Upload using Replit's SDK
        self.client.upload_from_bytes(object_name, file_data)
        
        return f'/objects/{object_id}{file_extension}'
    
    def get_object_file(self, object_path):
        """Get a file from the object storage."""
        if not object_path.startswith('/objects/'):
            raise ValueError("Invalid object path")
        
        parts = object_path[1:].split('/')
        if len(parts) < 2:
            raise ValueError("Invalid object path")
        
        entity_id = '/'.join(parts[1:])
        object_name = f"thumbnails/{entity_id}"
        
        # Check if file exists
        if not self.client.exists(object_name):
            raise FileNotFoundError("Object not found")
        
        # Return the object data
        return self.client.download_as_bytes(object_name)
    
    def download_object(self, file_data, response):
        """Stream an object to a Flask response."""
        try:
            response.headers['Content-Type'] = 'image/jpeg'
            response.headers['Cache-Control'] = 'public, max-age=3600'
            response.data = file_data
            return response
        except Exception as e:
            raise Exception(f"Error downloading file: {str(e)}")
