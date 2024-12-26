import os
import tempfile
from typing import Optional
from datetime import datetime

import requests
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, HTTPException, Security, Depends, Form, File
from fastapi.security import HTTPBearer, APIKeyHeader
from fastapi.security.http import HTTPAuthorizationCredentials
from fastapi.openapi.utils import get_openapi
from markitdown import MarkItDown
from readability import Document
import html2text
import trafilatura
import chardet

from utils import (
    detect_content_type,
    is_supported_filetype,
    TIMEOUT_SECONDS
)


# Load environment variables
API_KEY = os.getenv("API_KEY", "DEFAULT_API_KEY_FOR_MARKITDOWN_API")  # Read from FLY secrets
API_VER = os.getenv("VERSION", "0.0.1")                               # Read from .env file
MAX_FILE_SIZE = int(os.getenv("MAX_DOWNLOAD_SIZE", "52428800"))       # Read from .env file (50MB)

# Initialize FastAPI and dependencies
app = FastAPI(
    title="MarkItDown API",
    docs_url=None,    # Disable default /docs
    redoc_url=None    # Disable default /redoc
)

# Initialize conversion tools
markitdown = MarkItDown()
html_converter = html2text.HTML2Text()
html_converter.ignore_links = False
html_converter.ignore_images = False
html_converter.ignore_tables = False


# Response Models
class ConversionMetadata(BaseModel):
    """Metadata about the conversion process"""
    content_type: str
    file_size: int
    processing_time: float
    original_url: Optional[str] = None
    conversion_method: str

class EnhancedConversionResult(BaseModel):
    """Enhanced conversion result with metadata"""
    result: str
    metadata: ConversionMetadata

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str


# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

async def get_auth_token(
    api_key: str = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials = Security(bearer_auth)
) -> str:
    """
    Verify either API key from header or Bearer token.

    Args:
        api_key (str): API key from X-API-Key header
        bearer (HTTPAuthorizationCredentials): Bearer token credentials

    Returns:
        str: Valid authentication token

    Raises:
        HTTPException: If authentication fails
    """
    if api_key == API_KEY:
        return api_key

    if bearer and bearer.credentials == API_KEY:
        return bearer.credentials

    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer or X-API-Key"}
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns:
        dict: Health status and API version
    """
    return {
        "status": "healthy",
        "version": API_VER,
    }


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint(auth_token: str = Depends(get_auth_token)):
    """
    OpenAPI schema endpoint with authentication.

    Args:
        auth_token (str): Authenticated token from get_auth_token dependency

    Returns:
        dict: OpenAPI schema
    """
    return get_openapi(
        title="MarkItDown API",
        version=API_VER,
        description="REST API service for converting documents to Markdown",
        routes=app.routes,
    )


@app.post("/convert", response_model=EnhancedConversionResult)
async def convert(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    auth_token: str = Depends(get_auth_token)
):
    """
    Convert files or web content to Markdown.

    Args:
        file (Optional[UploadFile]): Uploaded file to convert
        url (Optional[str]): URL of content to convert
        auth_token (str): Authenticated token from get_auth_token dependency

    Returns:
        EnhancedConversionResult: Converted content with metadata

    Raises:
        HTTPException: For various error conditions
    """
    start_time = datetime.now()

    # Input validation
    if not file and not url:
        raise HTTPException(
            status_code=400,
            detail="Either file or url must be provided"
        )
    if file and url:
        raise HTTPException(
            status_code=400,
            detail="Only one of file or url should be provided"
        )

    try:
        # Handle file upload
        if file:
            content = await file.read()
            file_size = len(content)
            original_url = None

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024:.1f}MB"
                )

            content_type, file_ext = detect_content_type(
                content=content,
                headers={'content-type': file.content_type},
                url=file.filename
            )

        # Handle URL download
        else:
            try:
                response = requests.get(
                    url,
                    timeout=TIMEOUT_SECONDS,
                    allow_redirects=True,
                    headers={'User-Agent': 'Mozilla/5.0'},
                    stream=True
                )
                response.raise_for_status()
            except requests.Timeout:
                raise HTTPException(
                    status_code=408,
                    detail="Request timeout"
                )
            except requests.RequestException as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download file: {str(e)}"
                )

            content = response.content
            file_size = len(content)

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024:.1f}MB"
                )

            content_type, file_ext = detect_content_type(
                content=content,
                headers=response.headers,
                url=url
            )
            original_url = url

        # Process content based on detected type
        conversion_method = "default"

        # Handle HTML content
        if content_type.startswith('text/html'):
            # Web content extraction
            try:
                # Try trafilatura first
                extracted = trafilatura.extract(
                    content.decode('utf-8'),
                    include_links=True,
                    include_images=True,
                    include_tables=True,
                    output_format='markdown'
                )

                if extracted:
                    conversion_method = "trafilatura"
                    result = extracted
                else:
                    # Fallback to python-readability
                    # Detect encoding
                    encoding_detect = chardet.detect(content)
                    encoding = encoding_detect['encoding'] or 'utf-8'

                    # Create document
                    doc = Document(content.decode(encoding))

                    # Get title and clean content
                    title = doc.title()
                    article = doc.summary(html_partial=True)  # Get clean HTML

                    # Convert to markdown
                    result = f"# {title}\n\n" if title else ""
                    result += html_converter.handle(article)
                    conversion_method = "readability"

            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to extract web content: {str(e)}"
                )

        else:
            # Verify file format support for non-HTML content
            if not file_ext or not is_supported_filetype(file_ext):
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported or invalid file format: {content_type}"
                )

            # Standard file conversion using temporary file
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name
                    temp_file.flush()
                    os.fsync(temp_file.fileno())

                conversion_result = markitdown.convert(temp_path)
                result = conversion_result.text_content
                conversion_method = "markitdown"

            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.unlink(temp_path)
                    except:
                        pass

        processing_time = (datetime.now() - start_time).total_seconds()

        return EnhancedConversionResult(
            result=result,
            metadata=ConversionMetadata(
                content_type=content_type,
                file_size=file_size,
                processing_time=processing_time,
                original_url=original_url,
                conversion_method=conversion_method
            )
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))
