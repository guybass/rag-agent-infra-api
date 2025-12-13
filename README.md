# RAG Agent Infrastructure API

A production-ready RAG (Retrieval-Augmented Generation) API built with FastAPI, ChromaDB, and a pluggable LLM provider factory supporting AWS Bedrock, OpenAI, and Anthropic.

## Features

- **Document Ingestion**: Upload PDF, DOCX, TXT, MD, and CSV files
- **Vector Search**: ChromaDB-powered semantic search
- **LLM Provider Factory**: Easily switch between Bedrock, OpenAI, and Anthropic
- **Streaming Responses**: Server-Sent Events for real-time chat
- **Authentication**: API Key and JWT token support
- **Docker Ready**: Production deployment with Docker Compose

## Quick Start

### Local Development

```bash
# Clone the repository
git clone <your-repo-url>
cd rag_aget_infra_api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# Run the application
python -m app.main
```

### EC2 Deployment

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Run the setup script (first time only)
sudo ./scripts/setup-ec2.sh

# Clone your repository
cd /opt/rag-agent-api
git clone <your-repo-url> .

# Configure environment
cp .env.example .env
nano .env  # Add your AWS credentials and API keys

# Deploy
sudo ./scripts/deploy.sh
```

## API Endpoints

### Health
- `GET /health` - Health check
- `GET /` - API info

### Documents
- `POST /api/v1/documents/upload` - Upload a document
- `POST /api/v1/documents/upload-text` - Upload raw text
- `GET /api/v1/documents/` - List all documents
- `DELETE /api/v1/documents/{document_id}` - Delete a document
- `GET /api/v1/documents/stats` - Collection statistics

### Chat
- `POST /api/v1/chat/` - Chat with RAG (returns complete response)
- `POST /api/v1/chat/stream` - Chat with streaming response
- `POST /api/v1/chat/query` - Query vector store without LLM
- `GET /api/v1/chat/providers` - List available LLM providers

## Authentication

All endpoints (except health) require authentication via:

1. **API Key**: Add header `X-API-Key: your-api-key`
2. **JWT Token**: Add header `Authorization: Bearer your-jwt-token`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | Required |
| `API_KEY` | API key for authentication | Required |
| `AWS_REGION` | AWS region for Bedrock | us-east-1 |
| `AWS_ACCESS_KEY_ID` | AWS access key | Optional (uses IAM role on EC2) |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key | Optional (uses IAM role on EC2) |
| `BEDROCK_MODEL_ID` | Default Bedrock model | anthropic.claude-3-sonnet-20240229-v1:0 |
| `CHROMA_PERSIST_DIRECTORY` | ChromaDB storage path | ./chroma_data |
| `CHUNK_SIZE` | Document chunk size | 1000 |
| `CHUNK_OVERLAP` | Chunk overlap | 200 |

## Usage Examples

### Upload a Document

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.pdf"
```

### Chat with RAG

```bash
curl -X POST "http://localhost:8000/api/v1/chat/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main topic of the document?",
    "provider": "bedrock",
    "top_k": 5
  }'
```

### Switch LLM Provider

```bash
curl -X POST "http://localhost:8000/api/v1/chat/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarize the key points",
    "provider": "openai",
    "model_id": "gpt-4-turbo-preview"
  }'
```

## Project Structure

```
rag_aget_infra_api/
├── app/
│   ├── api/
│   │   ├── chat.py         # Chat endpoints
│   │   ├── documents.py    # Document endpoints
│   │   ├── health.py       # Health endpoints
│   │   └── deps.py         # Dependencies & auth
│   ├── models/
│   │   └── schemas.py      # Pydantic models
│   ├── providers/
│   │   ├── base.py         # Base LLM provider
│   │   ├── bedrock.py      # AWS Bedrock provider
│   │   ├── openai_provider.py
│   │   ├── anthropic_provider.py
│   │   └── factory.py      # Provider factory
│   ├── services/
│   │   ├── vector_store.py # ChromaDB service
│   │   └── document_processor.py
│   ├── config.py           # Settings
│   └── main.py             # FastAPI app
├── scripts/
│   ├── deploy.sh           # Deployment script
│   └── setup-ec2.sh        # EC2 setup script
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## License

MIT
