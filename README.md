# MarkItDown API

A REST API service that converts documents and web content to Markdown. Supports various file formats using [Microsoft's MarkItDown](https://github.com/microsoft/markitdown) and web content extraction using [Trafilatura](https://github.com/adbar/trafilatura) and [python-readability](https://github.com/buriy/python-readability).

## Features

- Document-to-Markdown conversion via file upload or URL
  - Office documents (DOCX, XLSX, PPTX)
  - PDF files
  - Images (PNG, JPEG, GIF, WebP)
  - Data files (CSV, JSON, XML)
- Web content extraction and conversion
  - Primary extraction using Trafilatura
  - Fallback to python-readability for robust content extraction
  - Intelligent character encoding detection
  - Clean Markdown output with preserved formatting
- Rich metadata for conversion results
- API Key-based authentication and OpenAPI documentation
- Robust content type detection and handling

## Installation & Development

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

### Clone & Local Setup

1. Clone the repository
```bash
git clone https://github.com/9bow/markitdown-api-fly-io.git
cd markitdown-api-fly-io
```

2. Create and activate virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure environment variables
```bash
# Create .env file with the following variables (via .env.template)
cp .env.example .env
# Update the following variables in .env
VERSION=0.0.1
MAX_DOWNLOAD_SIZE=52428800  # 50MB in bytes
TIMEOUT_SECONDS=30
```

5. Run development server
```bash
cd app/
uvicorn main:app --reload
```

### Deployment (via Fly.io)

1. Install Fly.io CLI
```bash
curl -L https://fly.io/install.sh | sh
```

2. Login and deploy
```bash
flyctl auth login
flyctl launch
flyctl secrets set API_KEY="your-secure-api-key"
flyctl deploy
```

## API Usage

### Authentication

All API endpoints require authentication using either:
- API key in the `X-API-Key` header
- Bearer token in the `Authorization` header

### Endpoints

#### Health Check
```bash
curl -X GET \
  -H "X-API-Key: your-secure-api-key" \
  http://localhost:8000/health
```

#### Convert Document
```bash
# via file upload
curl -X POST \
  -H "X-API-Key: your-secure-api-key" \
  -F "file=@document.pdf" \
  http://localhost:8000/convert

# via file URL
curl -X POST \
  -H "X-API-Key: your-secure-api-key" \
  -F "url=https://example.com/document.pdf" \
  http://localhost:8000/convert
```

### Response Format

Successful conversions return a JSON object with the following structure:
```json
{
  "result": "# Converted Markdown Content...",
  "metadata": {
    "content_type": "application/pdf",
    "file_size": 12345,
    "processing_time": 0.532,
    "original_url": "https://example.com/document.pdf",
    "conversion_method": "markitdown"
  }
}
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:
- 400: Bad Request (invalid input)
  - Unsupported file format
  - Invalid URL
  - Missing file/URL
- 401: Unauthorized (invalid API key)
- 408: Request Timeout
- 413: Payload Too Large (file size exceeds limit)
- 500: Internal Server Error

## Content Type Support

### Documents
- PDF (`.pdf`)
- Microsoft Word (`.docx`)
- Microsoft Excel (`.xlsx`)
- Microsoft PowerPoint (`.pptx`)

### Web Content
- HTML pages (`.html`, `.htm`)
- XML documents (`.xml`)

### Data Files
- CSV (`.csv`)
- JSON (`.json`)
- XML (`.xml`)

### Images
- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- GIF (`.gif`)
- WebP (`.webp`)

## Development

### Running Tests
```bash
pytest
```

### Type Checking
```bash
mypy app/
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.