"""
Google Cloud Storage integration for Memori.
This module handles uploading and downloading files to/from GCS.
"""

from google.cloud import storage
from google.oauth2 import service_account
import os
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CloudStorage:
    """Handle Google Cloud Storage operations for audio files and other media."""
    
    def __init__(self, bucket_name=None, credentials_path=None):
        """
        Initialize the CloudStorage client.
        
        Args:
            bucket_name: The name of the GCS bucket to use
            credentials_path: Path to the service account credentials JSON file
        """
        self.bucket_name = bucket_name or os.environ.get('GCS_BUCKET_NAME')
        credentials_path = credentials_path or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        
        if not self.bucket_name:
            logger.warning("No GCS bucket specified, using local storage instead")
            self.client = None
            self.bucket = None
            return
            
        try:
            if credentials_path and os.path.exists(credentials_path):
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                self.client = storage.Client(credentials=credentials)
            else:
                # Use application default credentials
                self.client = storage.Client()
                
            self.bucket = self.client.bucket(self.bucket_name)
            logger.info(f"Connected to GCS bucket: {self.bucket_name}")
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
            self.client = None
            self.bucket = None
    
    def is_available(self):
        """Check if GCS storage is available."""
        return self.client is not None and self.bucket is not None
    
    def upload_file(self, local_path, destination_path=None):
        """
        Upload a file to GCS bucket.
        
        Args:
            local_path: Path to the local file
            destination_path: Path in the bucket (defaults to filename)
            
        Returns:
            Public URL of the uploaded file or None if failed
        """
        if not self.is_available():
            logger.warning("GCS storage not available, skipping upload")
            return None
            
        try:
            local_path = Path(local_path)
            destination_path = destination_path or local_path.name
            
            blob = self.bucket.blob(destination_path)
            blob.upload_from_filename(str(local_path))
            
            logger.info(f"Uploaded {local_path} to GCS as {destination_path}")
            return blob.public_url
        except Exception as e:
            logger.error(f"Failed to upload to GCS: {e}")
            return None
    
    def download_file(self, gcs_path, local_path):
        """
        Download a file from GCS bucket.
        
        Args:
            gcs_path: Path to the file in the bucket
            local_path: Local path to save the file
            
        Returns:
            Path to the downloaded file or None if failed
        """
        if not self.is_available():
            logger.warning("GCS storage not available, skipping download")
            return None
            
        try:
            blob = self.bucket.blob(gcs_path)
            local_path = Path(local_path)
            
            # Ensure the directory exists
            os.makedirs(local_path.parent, exist_ok=True)
            
            blob.download_to_filename(str(local_path))
            logger.info(f"Downloaded {gcs_path} from GCS to {local_path}")
            return str(local_path)
        except Exception as e:
            logger.error(f"Failed to download from GCS: {e}")
            return None
    
    def list_files(self, prefix=None):
        """
        List files in the bucket with optional prefix.
        
        Args:
            prefix: Filter by prefix (folder)
            
        Returns:
            List of file names or empty list if failed
        """
        if not self.is_available():
            logger.warning("GCS storage not available, cannot list files")
            return []
            
        try:
            blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
            return [blob.name for blob in blobs]
        except Exception as e:
            logger.error(f"Failed to list files in GCS: {e}")
            return []
    
    def delete_file(self, gcs_path):
        """
        Delete a file from the bucket.
        
        Args:
            gcs_path: Path to the file in the bucket
            
        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            logger.warning("GCS storage not available, cannot delete file")
            return False
            
        try:
            blob = self.bucket.blob(gcs_path)
            blob.delete()
            logger.info(f"Deleted {gcs_path} from GCS")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file from GCS: {e}")
            return False

# Singleton instance for easy import
storage_client = CloudStorage()

def init_cloud_storage(bucket_name=None, credentials_path=None):
    """
    Initialize cloud storage with the given configuration.
    
    Args:
        bucket_name: The name of the GCS bucket to use
        credentials_path: Path to the service account credentials JSON file
        
    Returns:
        CloudStorage instance
    """
    global storage_client
    storage_client = CloudStorage(bucket_name, credentials_path)
    return storage_client
