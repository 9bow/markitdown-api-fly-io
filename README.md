# MarkItDown API

A REST API service that converts document files (PDF, Office documents, etc.) to Markdown using [Microsoft's MarkItDown](https://github.com/microsoft/markitdown).

## Features

- Document-to-Markdown conversion via file upload or URL using [MarkItDown library](https://github.com/microsoft/markitdown)
- API Key-based authentication and OpenAPI documentation
- Support for multiple file formats (PDF, Office documents, images, and more)

## Installation & Development

### Clone & Local Setup

1. Clone the repository
```bash
git clone https://github.com/9bow/markitdown-api-fly-io.git
cd markitdown-api-fly-io
```

2. Install dependencies
```bash
pip install -r requirements.txt
```

3. Configure environment variables
```bash
# Create .env file with the following variables (via .env.template)
cp .env.example .env
# Update the following variables in .env
VERSION=0.0.1
MAX_DOWNLOAD_SIZE=52428800  # 50MB in bytes
TIMEOUT_SECONDS=30
```

4. Run development server
```bash
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

All API endpoints require an API key to be sent in the `X-API-Key` header or `BEARER` token in the `Authorization` header.

### Endpoints

#### Health Check
```bash
curl -X GET \
  -H "X-API-Key: your-api-key" \
  http://localhost:8000/health
```

#### Convert File
```bash
# via file upload
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf" \
  http://localhost:8000/convert

# via file URL
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -F "url=https://example.com/document.pdf" \
  http://localhost:8000/convert
```

## Error Handling

The API returns appropriate HTTP status codes and error messages:
- 400: Bad Request (invalid input)
- 401: Unauthorized (invalid API key)
- 408: Request Timeout
- 413: Payload Too Large
- 500: Internal Server Error
