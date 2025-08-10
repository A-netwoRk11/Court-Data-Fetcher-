import os
import logging
import requests
import hashlib
from pathlib import Path
import PyPDF2

logger = logging.getLogger(__name__)

class PDFHandler:
    """
    Service for downloading and handling PDF documents
    """
    
    def __init__(self):
        self.download_folder = os.getenv('UPLOAD_FOLDER', 'downloads')
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE', 10485760))  
        
        
        Path(self.download_folder).mkdir(parents=True, exist_ok=True)
        
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'Accept': 'application/pdf,application/octet-stream,*/*',
        })
    
    def download_pdf(self, url, document_id):
        """
        Download PDF from URL and save locally
        
        Args:
            url (str): PDF URL to download
            document_id (int): Document ID for naming
            
        Returns:
            str: Local file path if successful, None if failed
        """
        try:
            logger.info(f"Downloading PDF from {url}")
            
            
            filename = f"document_{document_id}.pdf"
            file_path = os.path.join(self.download_folder, filename)
            
            
            if os.path.exists(file_path):
                if self._validate_pdf(file_path):
                    logger.info(f"PDF already exists and is valid: {file_path}")
                    return file_path
                else:
                    logger.warning(f"Existing PDF is invalid, re-downloading: {file_path}")
                    os.remove(file_path)
            
            
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and 'octet-stream' not in content_type:
                logger.warning(f"Unexpected content type: {content_type}")
            
            
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_file_size:
                logger.error(f"File too large: {content_length} bytes")
                return None
            
            
            total_size = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
                        
                        
                        if total_size > self.max_file_size:
                            logger.error(f"File size exceeded limit during download")
                            f.close()
                            os.remove(file_path)
                            return None
            
            
            if self._validate_pdf(file_path):
                logger.info(f"PDF downloaded successfully: {file_path} ({total_size} bytes)")
                return file_path
            else:
                logger.error(f"Downloaded file is not a valid PDF")
                os.remove(file_path)
                return None
            
        except requests.RequestException as e:
            logger.error(f"Network error downloading PDF: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error downloading PDF: {str(e)}")
            return None
    
    def _validate_pdf(self, file_path):
        """
        Validate that file is a proper PDF
        
        Args:
            file_path (str): Path to PDF file
            
        Returns:
            bool: True if valid PDF, False otherwise
        """
        try:
            if not os.path.exists(file_path):
                return False
            
            
            if os.path.getsize(file_path) == 0:
                return False
            
            
            with open(file_path, 'rb') as f:
                
                header = f.read(4)
                if header != b'%PDF':
                    return False
                
                
                f.seek(0)
                try:
                    reader = PyPDF2.PdfReader(f)
                    
                    page_count = len(reader.pages)
                    if page_count > 0:
                        return True
                except Exception:
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating PDF {file_path}: {str(e)}")
            return False
    
    def get_pdf_info(self, file_path):
        """
        Get information about a PDF file
        
        Args:
            file_path (str): Path to PDF file
            
        Returns:
            dict: PDF information
        """
        try:
            info = {
                'valid': False,
                'pages': 0,
                'size_bytes': 0,
                'checksum': None,
                'created': None,
                'title': None,
                'author': None
            }
            
            if not os.path.exists(file_path):
                return info
            
            
            stat = os.stat(file_path)
            info['size_bytes'] = stat.st_size
            info['created'] = stat.st_ctime
            
            
            info['checksum'] = self._calculate_checksum(file_path)
            
            
            try:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    info['pages'] = len(reader.pages)
                    info['valid'] = True
                    
                    
                    metadata = reader.metadata
                    if metadata:
                        info['title'] = str(metadata.get('/Title', '')) if metadata.get('/Title') else None
                        info['author'] = str(metadata.get('/Author', '')) if metadata.get('/Author') else None
                        
            except Exception as e:
                logger.warning(f"Could not extract PDF metadata: {str(e)}")
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting PDF info: {str(e)}")
            return info
    
    def _calculate_checksum(self, file_path):
        """Calculate SHA-256 checksum of file"""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating checksum: {str(e)}")
            return None
    
    def cleanup_old_files(self, days_old=30):
        """
        Clean up PDF files older than specified days
        
        Args:
            days_old (int): Delete files older than this many days
        """
        try:
            import time
            cutoff_time = time.time() - (days_old * 24 * 60 * 60)
            
            deleted_count = 0
            for file_path in Path(self.download_folder).glob('*.pdf'):
                if file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old PDF: {file_path}")
                    except Exception as e:
                        logger.error(f"Error deleting {file_path}: {str(e)}")
            
            logger.info(f"Cleanup completed: {deleted_count} files deleted")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return 0
