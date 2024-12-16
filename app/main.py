import os
import tempfile
from typing import Optional

import requests
from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, HTTPException, Security, Depends, Form, File
from fastapi.security import HTTPBearer, APIKeyHeader
from fastapi.security.http import HTTPAuthorizationCredentials
from fastapi.openapi.utils import get_openapi
from markitdown import MarkItDown

from utils import (
    is_supported_filetype,
    get_extension_from_url,
    guess_extension_from_content,
    TIMEOUT_SECONDS
)

# Load environment variables
API_KEY = os.getenv("API_KEY", "DEFAULT_API_KEY_FOR_MARKITDOWN_API")  # Read from FLY secrets
API_VER = os.getenv("VERSION", "0.0.1")                               # Read from .env file
MAX_FILE_SIZE = int(os.getenv("MAX_DOWNLOAD_SIZE", "52428800"))       # Read from .env file

# Initialize MarkItDown and FastAPI
markitdown = MarkItDown()
app = FastAPI(
    title="MarkItDown API",
    docs_url=None,    # Disable default /docs
    redoc_url=None    # Disable default /redoc
)

# Response Models
class ConversionResult(BaseModel):
    result: str

class HealthResponse(BaseModel):
    status: str
    version: str

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)

# API key or Bearer token verification
async def get_auth_token(
    api_key: str = Security(api_key_header),
    bearer: HTTPAuthorizationCredentials = Security(bearer_auth)
) -> str:
    """
    Verify either API key from header or Bearer token.
    Returns the valid token/key or raises 401 if neither is valid.
    """
    # Check API Key header first
    if api_key == API_KEY:
        return api_key

    # Then check Bearer token
    if bearer and bearer.credentials == API_KEY:
        return bearer.credentials

    # If neither is valid, raise 401
    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer or X-API-Key"}
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "healthy",
        "version": API_VER,
    }

# OpenAPI schema endpoint with authentication
@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint(auth_token: str = Depends(get_auth_token)):
    return get_openapi(
        title="MarkItDown API",
        version=API_VER,
        description="REST API service for converting documents to Markdown",
        routes=app.routes,
    )

# File conversion endpoint (url/file -> md)
@app.post("/convert", response_model=ConversionResult)
async def convert(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    auth_token: str = Depends(get_auth_token)
):
    # Validate input: either file or url must be provided
    if not file and not url:
        raise HTTPException(
            status_code=400,
            detail="Either file or url must be provided"
        )

    # Validate input: only one of file or url should be provided
    if file and url:
        raise HTTPException(
            status_code=400,
            detail="Only one of file or url should be provided"
        )

    try:
        # Handle file upload
        if file:
            content = await file.read()
            if len(content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB"
                )
            file_ext = os.path.splitext(file.filename)[1].lower()

        # Handle URL download
        elif url:
            file_ext = get_extension_from_url(url)

            try:
                response = requests.get(
                    url,
                    timeout=TIMEOUT_SECONDS,
                    allow_redirects=True,
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

            content_length = int(response.headers.get('content-length', 0))
            if content_length > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024:.2f}MB"
                )

            content = response.content

        # Verify file format
        if not file_ext or not is_supported_filetype(file_ext):
            detected_ext = guess_extension_from_content(content)
            if not detected_ext or not is_supported_filetype(detected_ext):
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported or invalid file format"
                )
            file_ext = detected_ext

        # Save to temporary file and convert
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        # Convert to Markdown
        try:
            result = markitdown.convert(temp_path)
            return ConversionResult(result=result.text_content)
        finally:
            os.unlink(temp_path)

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))