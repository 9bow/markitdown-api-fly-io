import os
import zipfile
import tempfile
from urllib.parse import urlparse
from typing import Optional, Tuple, Dict, Any
import mimetypes

# Initialize mimetypes
mimetypes.init()

# MIME type mappings
MIME_TYPE_MAPPINGS: Dict[str, str] = {
    # Text content types
    'text/html': '.html',
    'application/xhtml+xml': '.html',
    'application/xml': '.xml',
    'text/xml': '.xml',
    'text/plain': '.txt',
    'text/markdown': '.md',
    'text/x-markdown': '.md',
    'text/csv': '.csv',
    'text/comma-separated-values': '.csv',

    # Document content types
    'application/pdf': '.pdf',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
    'application/vnd.ms-excel': '.xls',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    'application/vnd.ms-powerpoint': '.ppt',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',

    # Data content types
    'application/json': '.json',

    # Image content types
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp'
}

# Supported file extensions
SUPPORTED_EXTENSIONS = {ext.lower() for ext in MIME_TYPE_MAPPINGS.values()}

# Default timeout in seconds
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "30"))


def safe_decode(content: bytes, size: int = 1024) -> str:
    """
    Safely decode binary content to string using multiple encodings.

    Args:
        content (bytes): Binary content to decode
        size (int): Maximum number of bytes to decode

    Returns:
        str: Decoded string content
    """
    encodings = ['utf-8', 'utf-16', 'ascii', 'iso-8859-1']
    sample = content[:size]

    for encoding in encodings:
        try:
            return sample.decode(encoding)
        except UnicodeDecodeError:
            continue

    return sample.decode('utf-8', errors='ignore')


def detect_content_type(
    content: Optional[bytes] = None,
    headers: Optional[dict] = None,
    url: Optional[str] = None,
    sample_size: int = 8192
) -> Tuple[str, str]:
    """
    Detect content type and file extension from various sources.

    Args:
        content (Optional[bytes]): Raw file content
        headers (Optional[dict]): HTTP response headers
        url (Optional[str]): Source URL of the content
        sample_size (int): Maximum size of content to sample

    Returns:
        Tuple[str, str]: Tuple containing (content_type, file_extension)
    """
    content_type = None
    extension = None

    # try HTTP headers first (case-insensitive)
    if headers:
        content_type_header = next(
            (v for k, v in headers.items() if k.lower() == 'content-type'),
            None
        )
        if content_type_header:
            content_type = content_type_header.split(';')[0].lower()
            extension = MIME_TYPE_MAPPINGS.get(content_type)

    # try URL extension if no extension found
    if not extension and url:
        path = os.path.basename(urlparse(url).path.split("?")[0])
        url_ext = os.path.splitext(path)[1].lower()
        if url_ext in SUPPORTED_EXTENSIONS:
            extension = url_ext
            if not content_type:
                content_type = next(
                    (k for k, v in MIME_TYPE_MAPPINGS.items() if v == extension),
                    None
                )

    # try content detection if available
    if content and (not extension or not content_type):
        content_sample = content[:sample_size]
        magic_sample = content_sample[:8]

        temp_path = None
        try:
            # Binary format checks
            if magic_sample.startswith(b'%PDF'):
                extension = '.pdf'
                content_type = 'application/pdf'
            elif magic_sample.startswith(b'\x89PNG\r\n\x1a\n'):
                extension = '.png'
                content_type = 'image/png'
            elif magic_sample.startswith(b'\xff\xd8\xff'):
                extension = '.jpg'
                content_type = 'image/jpeg'
            elif content_sample.startswith(b'PK'):
                # Office documents check
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content_sample)
                    temp_path = temp_file.name
                    temp_file.flush()
                    os.fsync(temp_file.fileno())

                try:
                    with zipfile.ZipFile(temp_path, 'r') as zf:
                        names = zf.namelist()
                        if any(name.startswith('word/') for name in names):
                            extension = '.docx'
                            content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        elif any(name.startswith('xl/') for name in names):
                            extension = '.xlsx'
                            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                        elif any(name.startswith('ppt/') for name in names):
                            extension = '.pptx'
                            content_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
                except zipfile.BadZipFile:
                    pass

            # Text format checks
            else:
                text_content = safe_decode(content_sample)
                text_content_lower = text_content.lower()

                if text_content.lstrip().startswith('{') or text_content.lstrip().startswith('['):
                    extension = '.json'
                    content_type = 'application/json'
                elif text_content.lstrip().startswith('<'):
                    if '<html' in text_content_lower or '<!doctype html' in text_content_lower:
                        extension = '.html'
                        content_type = 'text/html'
                    else:
                        extension = '.xml'
                        content_type = 'text/xml'
                elif ',' in text_content or ';' in text_content:
                    # Simple CSV detection
                    if not text_content.lstrip().startswith('<'):
                        extension = '.csv'
                        content_type = 'text/csv'

        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass

    # fallback to mimetypes if still uncertain
    if extension and not content_type:
        content_type = mimetypes.guess_type(f"file{extension}")[0]
    elif content_type and not extension:
        ext = mimetypes.guess_extension(content_type)
        if ext in SUPPORTED_EXTENSIONS:
            extension = ext

    # default fallback
    if not content_type:
        content_type = 'application/octet-stream'

    return content_type, extension or ''


def is_supported_filetype(ext: str) -> bool:
    """
    Check if the file extension is supported.

    Args:
        ext (str): File extension to check (with or without leading dot)

    Returns:
        bool: True if supported, False otherwise
    """
    return ext.lower().strip().lstrip('.') in {ext.lstrip('.') for ext in SUPPORTED_EXTENSIONS}


def get_extension_from_url(url: str) -> str:
    """
    Extract file extension from URL.

    Args:
        url (str): URL to extract extension from

    Returns:
        str: Extracted file extension (with leading dot) or empty string
    """
    path = os.path.basename(urlparse(url).path.split("?")[0])
    _, ext = os.path.splitext(path)
    return ext.lower()
