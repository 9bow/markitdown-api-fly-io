import os
import zipfile
import tempfile
from urllib.parse import urlparse
from typing import Optional

# Load configuration from environment variables (with defaults)
SUPPORTED_EXTENSIONS = {
    ".pdf", ".ppt", ".pptx", ".docx", ".xlsx", ".csv", ".json", ".xml",
    ".png", ".jpg", ".jpeg"
}

TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "30"))    # Default 30 seconds

def is_supported_filetype(ext: str) -> bool:
    """Check if the file extension is supported"""
    return ext.lower() in SUPPORTED_EXTENSIONS

def get_extension_from_url(url: str) -> str:
    """Extract file extension from URL"""
    path = os.path.basename(urlparse(url).path.split("?")[0])
    _, ext = os.path.splitext(path)
    return ext.lower()

def guess_extension_from_content(file_bytes: bytes) -> Optional[str]:
    """Guess file extension based on content"""
    # PDF
    if file_bytes.startswith(b'%PDF'):
        return ".pdf"

    # PNG
    if file_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return ".png"

    # JPEG
    if file_bytes.startswith(b'\xff\xd8\xff'):
        return ".jpg"

    # Office documents
    if file_bytes[0:2] == b'PK':
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name

                with zipfile.ZipFile(temp_path, 'r') as zf:
                    names = zf.namelist()
                    if any(name.startswith('word/') for name in names):
                        return ".docx"
                    elif any(name.startswith('xl/') for name in names):
                        return ".xlsx"
                    elif any(name.startswith('ppt/') for name in names):
                        return ".pptx"
        except:
            pass
        finally:
            if 'temp_path' in locals():
                os.unlink(temp_path)

    # JSON
    stripped = file_bytes.strip()
    if stripped.startswith(b'{') or stripped.startswith(b'['):
        return ".json"

    # XML
    if stripped.startswith(b'<'):
        return ".xml"

    # CSV estimation
    try:
        text_sample = file_bytes[:1024].decode('utf-8', errors='ignore')
        if (',' in text_sample or ';' in text_sample) and not text_sample.startswith('<'):
            return ".csv"
    except:
        pass

    return None
