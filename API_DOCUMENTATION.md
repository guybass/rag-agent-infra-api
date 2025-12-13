# RAG Agent Infrastructure API Documentation

## Multi-Index Semantic Layer for DevOps/SRE/Platform Engineers

**Version:** 2.0.0
**Base URL:** `http://localhost:8000`

This API provides a comprehensive semantic layer for AI agents working with AWS infrastructure and Terraform. It supports hierarchical storage, semantic search, and real-time context retrieval across multiple index groups.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Health Check](#health-check)
3. [Sessions API](#sessions-api)
4. [Memory API](#memory-api)
5. [Decisions API](#decisions-api)
6. [Terraform Files API](#terraform-files-api)
7. [Terraform Search API](#terraform-search-api)
8. [Context State API](#context-state-api)
9. [Context Live API](#context-live-api)
10. [Context General API](#context-general-api)
11. [Unified Search API](#unified-search-api)
12. [Documents API](#documents-api)
13. [Chat API](#chat-api)
14. [Error Responses](#error-responses)

---

## Authentication

All protected endpoints require authentication via one of these methods:

### API Key (Recommended)
```bash
curl -X GET "http://localhost:8000/api/v1/sessions/" \
  -H "X-API-Key: your-api-key"
```

### JWT Bearer Token
```bash
curl -X GET "http://localhost:8000/api/v1/sessions/" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Health Check

### GET /health
Check if the service is running.

**Authentication:** None required

**Example:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy"
}
```

### GET /
Get service information.

**Example:**
```bash
curl -X GET "http://localhost:8000/"
```

**Response:**
```json
{
  "message": "RAG Agent Infrastructure API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

---

## Sessions API

Base Path: `/api/v1/sessions`

Sessions are ephemeral conversation contexts stored in Redis with automatic TTL expiration.

### Create Session
**POST** `/api/v1/sessions/`

Create a new agent session.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "claude-3-sonnet",
    "provider": "anthropic",
    "initial_context": {
      "user_name": "John",
      "project": "infrastructure-migration"
    },
    "ttl_seconds": 7200
  }'
```

**Response:**
```json
{
  "session": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "model_id": "claude-3-sonnet",
    "provider": "anthropic",
    "context": {
      "user_name": "John",
      "project": "infrastructure-migration"
    },
    "state": {},
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "expires_at": "2024-01-15T12:30:00Z",
    "is_active": true
  }
}
```

---

### List Sessions
**GET** `/api/v1/sessions/`

List all sessions with optional filters.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_id` | string | - | Filter by model |
| `active_only` | boolean | true | Filter active sessions |

**Example:**
```bash
# List all active sessions
curl -X GET "http://localhost:8000/api/v1/sessions/" \
  -H "X-API-Key: your-api-key"

# Filter by model
curl -X GET "http://localhost:8000/api/v1/sessions/?model_id=claude-3-sonnet&active_only=true" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "model_id": "claude-3-sonnet",
      "provider": "anthropic",
      "created_at": "2024-01-15T10:30:00Z",
      "is_active": true,
      "message_count": 5
    }
  ],
  "total": 1
}
```

---

### Get Session
**GET** `/api/v1/sessions/{session_id}`

Get details of a specific session.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "session": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "user123",
    "model_id": "claude-3-sonnet",
    "provider": "anthropic",
    "messages": [
      {
        "role": "user",
        "content": "How do I create an EKS cluster?",
        "timestamp": "2024-01-15T10:35:00Z"
      },
      {
        "role": "assistant",
        "content": "To create an EKS cluster...",
        "timestamp": "2024-01-15T10:35:05Z"
      }
    ],
    "context": {},
    "state": {}
  }
}
```

---

### Delete Session
**DELETE** `/api/v1/sessions/{session_id}`

Delete a session.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "message": "Session deleted",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Add Message
**POST** `/api/v1/sessions/{session_id}/messages`

Add a message to the session history.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000/messages" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "How do I create an EKS cluster?",
    "metadata": {
      "timestamp": "2024-01-15T10:35:00Z"
    }
  }'
```

**Response:**
```json
{
  "message": "Message added",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Get Messages
**GET** `/api/v1/sessions/{session_id}/messages`

Retrieve messages from a session.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 50 | Messages per page (1-500) |
| `offset` | int | 0 | Starting position |

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000/messages?limit=20&offset=0" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "How do I create an EKS cluster?",
      "metadata": {},
      "timestamp": "2024-01-15T10:35:00Z"
    },
    {
      "role": "assistant",
      "content": "To create an EKS cluster...",
      "metadata": {},
      "timestamp": "2024-01-15T10:35:05Z"
    }
  ],
  "total": 2,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Update Context
**PUT** `/api/v1/sessions/{session_id}/context`

Update session context.

**Example:**
```bash
curl -X PUT "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000/context" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "current_task": "eks-setup",
      "aws_region": "us-west-2"
    },
    "merge": true
  }'
```

**Response:**
```json
{
  "message": "Context updated",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Update State
**PUT** `/api/v1/sessions/{session_id}/state`

Update session state.

**Example:**
```bash
curl -X PUT "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000/state" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "state": {
      "step": 3,
      "resources_created": ["vpc", "subnet"]
    },
    "merge": true
  }'
```

**Response:**
```json
{
  "message": "State updated",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Extend Session TTL
**POST** `/api/v1/sessions/{session_id}/extend`

Extend the session expiration time.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/sessions/550e8400-e29b-41d4-a716-446655440000/extend" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "additional_seconds": 3600
  }'
```

**Response:**
```json
{
  "message": "Session extended",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "additional_seconds": 3600
}
```

---

## Memory API

Base Path: `/api/v1/memory`

Memory provides persistent storage for information that should survive session boundaries.

### Store Memory
**POST** `/api/v1/memory/`

Store a new memory entry.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/memory/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "User prefers Terraform modules for infrastructure provisioning over raw resources",
    "memory_type": "longterm",
    "importance_score": 0.85,
    "metadata": {
      "source": "conversation",
      "topic": "infrastructure"
    },
    "tags": ["terraform", "preferences", "infrastructure"]
  }'
```

**Response:**
```json
{
  "memory": {
    "memory_id": "mem_xyz789",
    "content": "User prefers Terraform modules for infrastructure provisioning over raw resources",
    "memory_type": "longterm",
    "importance_score": 0.85,
    "metadata": {
      "source": "conversation",
      "topic": "infrastructure"
    },
    "tags": ["terraform", "preferences", "infrastructure"],
    "created_at": "2024-01-15T10:40:00Z"
  }
}
```

---

### Search Memories
**POST** `/api/v1/memory/search`

Semantic search across memories.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/memory/search" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What does the user prefer for infrastructure?",
    "memory_types": ["longterm", "session"],
    "min_importance": 0.5,
    "tags": ["infrastructure"],
    "top_k": 5
  }'
```

**Response:**
```json
{
  "results": [
    {
      "memory_id": "mem_xyz789",
      "content": "User prefers Terraform modules for infrastructure provisioning",
      "memory_type": "longterm",
      "importance_score": 0.85,
      "relevance_score": 0.92,
      "tags": ["terraform", "preferences"]
    }
  ],
  "total": 1
}
```

---

### Get Memory
**GET** `/api/v1/memory/{memory_id}`

Get a specific memory by ID.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/memory/mem_xyz789?memory_type=longterm" \
  -H "X-API-Key: your-api-key"
```

---

### Delete Memory
**DELETE** `/api/v1/memory/{memory_id}`

Delete a memory entry.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/memory/mem_xyz789" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "message": "Memory deleted",
  "memory_id": "mem_xyz789"
}
```

---

### Update Importance
**PUT** `/api/v1/memory/{memory_id}/importance`

Update the importance score of a memory.

**Example:**
```bash
curl -X PUT "http://localhost:8000/api/v1/memory/mem_xyz789/importance" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "importance_score": 0.95
  }'
```

**Response:**
```json
{
  "message": "Importance updated",
  "memory_id": "mem_xyz789",
  "new_score": 0.95
}
```

---

### Promote to Long-term
**POST** `/api/v1/memory/{memory_id}/promote`

Promote a session memory to long-term storage.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/memory/mem_session123/promote" \
  -H "X-API-Key: your-api-key"
```

---

### Get Session Memories
**GET** `/api/v1/memory/session/{session_id}`

Get all memories for a specific session.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/memory/session/550e8400-e29b-41d4-a716-446655440000?limit=50" \
  -H "X-API-Key: your-api-key"
```

---

### Cleanup Session Memories
**DELETE** `/api/v1/memory/session/{session_id}/cleanup`

Clean up session memories, optionally keeping important ones.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `keep_important` | boolean | true | Keep important memories |
| `importance_threshold` | float | 0.7 | Threshold (0.0-1.0) |

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/memory/session/550e8400-e29b-41d4-a716-446655440000/cleanup?keep_important=true&importance_threshold=0.7" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "message": "Session memories cleaned up",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted_count": 15,
  "kept_important": true
}
```

---

## Decisions API

Base Path: `/api/v1/memory/decisions`

Decisions track agent reasoning and outcomes for future learning.

### Store Decision
**POST** `/api/v1/memory/decisions/`

Store an agent decision for future reference.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/memory/decisions/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "decision_type": "resource_selection",
    "context": "User asked about creating a managed Kubernetes cluster",
    "reasoning": "Chose EKS over self-managed K8s due to user preference for managed services and AWS ecosystem",
    "outcome": "Recommended aws_eks_cluster resource",
    "confidence_score": 0.9,
    "related_resources": ["aws_eks_cluster", "aws_eks_node_group"],
    "tags": ["kubernetes", "aws", "eks"]
  }'
```

**Response:**
```json
{
  "decision": {
    "decision_id": "dec_qrs456",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "decision_type": "resource_selection",
    "context": "User asked about creating a managed Kubernetes cluster",
    "reasoning": "Chose EKS over self-managed K8s due to user preference for managed services",
    "outcome": "Recommended aws_eks_cluster resource",
    "confidence_score": 0.9,
    "related_resources": ["aws_eks_cluster", "aws_eks_node_group"],
    "tags": ["kubernetes", "aws", "eks"],
    "created_at": "2024-01-15T10:45:00Z"
  }
}
```

---

### Search Decisions
**POST** `/api/v1/memory/decisions/search`

Search past decisions semantically.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/memory/decisions/search" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "kubernetes cluster recommendations",
    "decision_type": "resource_selection",
    "min_confidence": 0.7,
    "top_k": 5
  }'
```

---

### Get Decision
**GET** `/api/v1/memory/decisions/{decision_id}`

Get a specific decision by ID.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/memory/decisions/dec_qrs456" \
  -H "X-API-Key: your-api-key"
```

---

### Get Decisions for Resource
**GET** `/api/v1/memory/decisions/resource/{resource_id}`

Get all decisions related to a specific resource.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/memory/decisions/resource/aws_eks_cluster?limit=20" \
  -H "X-API-Key: your-api-key"
```

---

## Terraform Files API

Base Path: `/api/v1/terraform/files`

Manages Terraform files with both file system storage and semantic indexing.

### Upload Files
**POST** `/api/v1/terraform/files/upload`

Upload Terraform files for indexing.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/terraform/files/upload" \
  -H "X-API-Key: your-api-key" \
  -F "files=@main.tf" \
  -F "files=@variables.tf" \
  -F "files=@outputs.tf" \
  -F "account_id=123456789012" \
  -F "project_id=my-infrastructure" \
  -F "environment=production" \
  -F "base_path=terraform/eks"
```

**Response:**
```json
{
  "files_processed": 3,
  "chunks_created": 15,
  "hierarchy": {
    "account_id": "123456789012",
    "project_id": "my-infrastructure",
    "environment": "production",
    "base_path": "terraform/eks"
  }
}
```

---

### Get File Tree
**GET** `/api/v1/terraform/files/tree`

Get hierarchical view of uploaded Terraform files.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `account_id` | string | - | Filter by account |
| `project_id` | string | - | Filter by project |
| `environment` | string | - | Filter by environment |
| `depth` | int | -1 | Max tree depth (-1 unlimited) |

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/terraform/files/tree?account_id=123456789012&project_id=my-infrastructure&depth=3" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "name": "terraform",
  "type": "directory",
  "children": [
    {
      "name": "eks",
      "type": "directory",
      "children": [
        {"name": "main.tf", "type": "file"},
        {"name": "variables.tf", "type": "file"},
        {"name": "outputs.tf", "type": "file"}
      ]
    }
  ]
}
```

---

### Get File Content
**GET** `/api/v1/terraform/files/content/{file_path}`

Get the content of a specific Terraform file.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/terraform/files/content/terraform/eks/main.tf?account_id=123456789012&project_id=my-infrastructure" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "file_path": "terraform/eks/main.tf",
  "content": "resource \"aws_eks_cluster\" \"main\" {\n  name = var.cluster_name\n  ...\n}",
  "account_id": "123456789012",
  "project_id": "my-infrastructure"
}
```

---

### Delete File
**DELETE** `/api/v1/terraform/files/content/{file_path}`

Delete a specific Terraform file.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/terraform/files/content/terraform/eks/old-module.tf?account_id=123456789012&project_id=my-infrastructure" \
  -H "X-API-Key: your-api-key"
```

---

### List Accounts
**GET** `/api/v1/terraform/files/accounts`

List all accounts with uploaded files.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/terraform/files/accounts" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "accounts": ["123456789012", "987654321098"],
  "total": 2
}
```

---

### List Projects
**GET** `/api/v1/terraform/files/accounts/{account_id}/projects`

List projects for an account.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/terraform/files/accounts/123456789012/projects" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "account_id": "123456789012",
  "projects": ["my-infrastructure", "data-platform"],
  "total": 2
}
```

---

### Get Project Stats
**GET** `/api/v1/terraform/files/stats`

Get statistics for a project.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/terraform/files/stats?account_id=123456789012&project_id=my-infrastructure" \
  -H "X-API-Key: your-api-key"
```

---

### Delete Project
**DELETE** `/api/v1/terraform/files/project`

Delete all files for a project.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/terraform/files/project?account_id=123456789012&project_id=my-infrastructure" \
  -H "X-API-Key: your-api-key"
```

---

## Terraform Search API

Base Path: `/api/v1/terraform`

Semantic search across indexed Terraform configurations.

### Semantic Search
**POST** `/api/v1/terraform/search`

Perform semantic search across Terraform code.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/terraform/search" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "EKS cluster with managed node groups",
    "hierarchy": {
      "account_id": "123456789012",
      "project_id": "my-infrastructure"
    },
    "resource_types": ["aws_eks_cluster", "aws_eks_node_group"],
    "include_file_content": true,
    "top_k": 10
  }'
```

**Response:**
```json
[
  {
    "content": "resource \"aws_eks_cluster\" \"main\" {\n  name = var.cluster_name\n  role_arn = aws_iam_role.eks.arn\n  ...\n}",
    "metadata": {
      "file_path": "terraform/eks/main.tf",
      "resource_type": "aws_eks_cluster",
      "resource_name": "main"
    },
    "relevance_score": 0.94,
    "chunk_id": "chunk_abc123"
  }
]
```

---

### Find Resources
**GET** `/api/v1/terraform/resources`

Find resources by type.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/terraform/resources?resource_type=aws_eks_cluster&account_id=123456789012&top_k=20" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "resource_type": "aws_eks_cluster",
  "results": [
    {
      "resource_name": "main",
      "file_path": "terraform/eks/main.tf",
      "content": "resource \"aws_eks_cluster\" \"main\" {...}"
    }
  ],
  "total": 1
}
```

---

### List Modules
**GET** `/api/v1/terraform/modules`

List Terraform modules.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/terraform/modules?account_id=123456789012&category=networking" \
  -H "X-API-Key: your-api-key"
```

---

## Context State API

Base Path: `/api/v1/context/state`

Manages Terraform state file indexing and search.

### Upload State File
**POST** `/api/v1/context/state/upload`

Upload a Terraform state file for indexing.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/context/state/upload" \
  -H "X-API-Key: your-api-key" \
  -F "file=@terraform.tfstate" \
  -F "account_id=123456789012" \
  -F "project_id=my-infrastructure" \
  -F "environment=production"
```

**Response:**
```json
{
  "resources_indexed": 45,
  "account_id": "123456789012",
  "source_type": "terraform_state"
}
```

---

### List State Resources
**GET** `/api/v1/context/state/resources`

List resources from state files.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/context/state/resources?account_id=123456789012&resource_type=aws_instance&limit=50" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "resources": [
    {
      "resource_type": "aws_instance",
      "resource_id": "i-0abc123def456",
      "name": "web-server",
      "attributes": {
        "instance_type": "t3.medium",
        "ami": "ami-12345678"
      }
    }
  ],
  "total": 5,
  "account_id": "123456789012"
}
```

---

### Search State
**POST** `/api/v1/context/state/search`

Semantic search across state resources.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/context/state/search" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "EC2 instances running in production",
    "account_id": "123456789012",
    "resource_types": ["aws_instance"],
    "top_k": 10
  }'
```

---

## Context Live API

Base Path: `/api/v1/context/live`

Fetches and manages live AWS resource state.

### Fetch Live Resources
**POST** `/api/v1/context/live/fetch`

Fetch live AWS resources and optionally index them.

**Supported Resource Types:**
- `ec2`, `vpc`, `subnet`, `security_group`
- `eks`, `rds`, `s3`, `lambda`
- `alb`, `nlb`, `dynamodb`, `elasticache`
- `ecs`, `iam_role`, `route53`

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/context/live/fetch" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "123456789012",
    "region": "us-west-2",
    "resource_types": ["ec2", "eks", "rds", "s3"],
    "index_results": true,
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }'
```

**Response:**
```json
{
  "resources_fetched": 127,
  "resources_indexed": 127,
  "resource_types": {
    "ec2": 45,
    "eks": 3,
    "rds": 12,
    "s3": 67
  }
}
```

---

### Sync Live State
**POST** `/api/v1/context/live/sync`

Sync and update the index with current live state.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/context/live/sync" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "123456789012",
    "region": "us-west-2",
    "resource_types": ["ec2", "rds"]
  }'
```

**Response:**
```json
{
  "synced": true,
  "added": 5,
  "updated": 12,
  "removed": 2,
  "unchanged": 108
}
```

---

### Compare State vs Live
**GET** `/api/v1/context/live/compare/{resource_type}`

Compare Terraform state with live AWS resources to detect drift.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/context/live/compare/aws_instance?account_id=123456789012&region=us-west-2" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "state_only": ["i-old123456"],
  "live_only": ["i-new789012"],
  "differences": [
    {
      "resource_id": "i-abc123",
      "diffs": {
        "instance_type": {
          "state": "t3.small",
          "live": "t3.medium"
        }
      }
    }
  ],
  "matched": 40,
  "drift_detected": true
}
```

---

### List Live Resources
**GET** `/api/v1/context/live/resources`

List indexed live resources.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/context/live/resources?account_id=123456789012&resource_type=ec2&region=us-west-2&limit=100" \
  -H "X-API-Key: your-api-key"
```

---

## Context General API

Base Path: `/api/v1/context/general`

Stores miscellaneous context information.

### Store General Context
**POST** `/api/v1/context/general/`

Store arbitrary context information.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/context/general/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Production EKS cluster requires minimum 3 nodes for high availability. Use m5.large instances for worker nodes.",
    "context_type": "best_practice",
    "metadata": {
      "source": "architecture_review",
      "author": "platform-team"
    },
    "account_id": "123456789012",
    "project_id": "my-infrastructure"
  }'
```

**Response:**
```json
{
  "context_id": "ctx_lmn789",
  "indexed_at": "2024-01-15T11:00:00Z"
}
```

---

### Search General Context
**POST** `/api/v1/context/general/search`

Semantic search across general context.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/context/general/search" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "EKS cluster node requirements",
    "account_id": "123456789012",
    "top_k": 5
  }'
```

---

### List General Context
**GET** `/api/v1/context/general/`

List stored context entries.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/context/general/?context_type=best_practice&account_id=123456789012&limit=50" \
  -H "X-API-Key: your-api-key"
```

---

### Get Context
**GET** `/api/v1/context/general/{context_id}`

Get a specific context entry.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/context/general/ctx_lmn789" \
  -H "X-API-Key: your-api-key"
```

---

### Delete Context
**DELETE** `/api/v1/context/general/{context_id}`

Delete a context entry.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/context/general/ctx_lmn789" \
  -H "X-API-Key: your-api-key"
```

---

### Batch Store Context
**POST** `/api/v1/context/general/batch`

Store multiple context entries at once.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/context/general/batch" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "content": "Use AWS EKS for managed Kubernetes",
      "context_type": "recommendation",
      "account_id": "123456789012"
    },
    {
      "content": "RDS instances should have Multi-AZ enabled",
      "context_type": "best_practice",
      "account_id": "123456789012"
    }
  ]'
```

**Response:**
```json
{
  "stored": 2,
  "context_ids": ["ctx_abc123", "ctx_def456"]
}
```

---

## Unified Search API

Base Path: `/api/v1/unified`

Cross-index search and context aggregation.

### Unified Search
**POST** `/api/v1/unified/search`

Search across all index groups simultaneously.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/unified/search" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to configure EKS cluster networking",
    "index_groups": ["terraform", "memory", "context"],
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "top_k_per_group": 5
  }'
```

**Response:**
```json
{
  "results": {
    "terraform": [
      {
        "content": "resource \"aws_eks_cluster\" ...",
        "relevance_score": 0.92
      }
    ],
    "memory": [
      {
        "content": "User prefers VPC CNI for EKS networking",
        "relevance_score": 0.88
      }
    ],
    "context": [
      {
        "content": "EKS networking best practices...",
        "relevance_score": 0.85
      }
    ]
  }
}
```

---

### Build Agent Context
**POST** `/api/v1/unified/agent-context`

Build optimized context for an AI agent.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/unified/agent-context" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "Create an EKS cluster with Fargate",
    "include_groups": ["terraform", "memory", "context"],
    "max_context_tokens": 4000
  }'
```

**Response:**
```json
{
  "context": "Based on your infrastructure and preferences:\n\n## Relevant Terraform Code\n...\n\n## Related Memories\n...\n\n## Best Practices\n...",
  "sources": {
    "terraform": 3,
    "memory": 2,
    "context": 2
  },
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### Get All Stats
**GET** `/api/v1/unified/stats`

Get statistics for all index groups.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/unified/stats" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "stats": [
    {
      "index_group": "terraform",
      "document_count": 150,
      "chunk_count": 450
    },
    {
      "index_group": "memory",
      "document_count": 75,
      "chunk_count": 75
    },
    {
      "index_group": "context",
      "document_count": 30,
      "chunk_count": 60
    }
  ]
}
```

---

### Cleanup User Data
**DELETE** `/api/v1/unified/cleanup`

Delete all data for the current user.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/unified/cleanup?confirm=true" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "deleted": true,
  "user_id": "user_123",
  "counts": {
    "terraform": 150,
    "memory": 75,
    "context": 30,
    "sessions": 5
  }
}
```

---

### Health Check
**GET** `/api/v1/unified/health`

Check unified search service health.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/unified/health" \
  -H "X-API-Key: your-api-key"
```

---

## Documents API

Base Path: `/api/v1/documents`

Upload and manage documents for RAG.

### Upload Document
**POST** `/api/v1/documents/upload`

Upload and index a document (PDF, DOCX, TXT, MD, CSV).

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "X-API-Key: your-api-key" \
  -F "file=@architecture-guide.pdf"
```

**Response:**
```json
{
  "document_id": "doc_uvw123",
  "filename": "architecture-guide.pdf",
  "chunks_created": 25
}
```

---

### Upload Text
**POST** `/api/v1/documents/upload-text`

Upload raw text for indexing.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload-text" \
  -H "X-API-Key: your-api-key" \
  -F "text=This is the content to be indexed. It contains important information about our infrastructure." \
  -F "source_name=infrastructure-notes"
```

**Response:**
```json
{
  "document_id": "doc_xyz456",
  "filename": "infrastructure-notes",
  "chunks_created": 1
}
```

---

### List Documents
**GET** `/api/v1/documents/`

List all uploaded documents.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/documents/" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "documents": [
    {
      "document_id": "doc_uvw123",
      "filename": "architecture-guide.pdf",
      "uploaded_at": "2024-01-15T11:30:00Z",
      "chunks": 25
    }
  ]
}
```

---

### Delete Document
**DELETE** `/api/v1/documents/{document_id}`

Delete a document and its chunks.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/doc_uvw123" \
  -H "X-API-Key: your-api-key"
```

---

### Get Stats
**GET** `/api/v1/documents/stats`

Get document collection statistics.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/documents/stats" \
  -H "X-API-Key: your-api-key"
```

---

## Chat API

Base Path: `/api/v1/chat`

RAG-enhanced chat with LLM providers.

### Chat
**POST** `/api/v1/chat/`

Send a message and get a RAG-enhanced response.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat/" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I create an EKS cluster with managed node groups?",
    "provider": "bedrock",
    "model_id": "anthropic.claude-3-sonnet-20240229-v1:0",
    "top_k": 5,
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

**Response:**
```json
{
  "answer": "To create an EKS cluster with managed node groups, you can use the following Terraform configuration...",
  "sources": [
    {
      "content": "resource \"aws_eks_cluster\" ...",
      "file_path": "terraform/eks/main.tf",
      "relevance_score": 0.94
    }
  ],
  "provider": "bedrock",
  "model_id": "anthropic.claude-3-sonnet-20240229-v1:0"
}
```

---

### Chat Stream
**POST** `/api/v1/chat/stream`

Stream a chat response using Server-Sent Events.

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat/stream" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "Explain the VPC module structure",
    "provider": "anthropic",
    "model_id": "claude-3-sonnet",
    "temperature": 0.5
  }'
```

**Response (Server-Sent Events):**
```
data: {"chunk": "The VPC module"}
data: {"chunk": " is structured"}
data: {"chunk": " to provide..."}
data: {"done": true, "sources": [...]}
```

---

### Query Documents
**POST** `/api/v1/chat/query`

Query documents without generating a response (retrieval only).

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/chat/query" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "S3 bucket configuration",
    "top_k": 10
  }'
```

**Response:**
```json
{
  "results": [
    {
      "content": "resource \"aws_s3_bucket\" \"main\" {...}",
      "metadata": {
        "file_path": "terraform/storage/s3.tf"
      },
      "relevance_score": 0.91
    }
  ]
}
```

---

### List Providers
**GET** `/api/v1/chat/providers`

List available LLM providers.

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/chat/providers" \
  -H "X-API-Key: your-api-key"
```

**Response:**
```json
{
  "providers": ["bedrock", "openai", "anthropic"],
  "default": "bedrock"
}
```

---

## Error Responses

All endpoints return consistent error responses:

### 400 Bad Request
```json
{
  "detail": "Invalid request: missing required field 'query'"
}
```

### 401 Unauthorized
```json
{
  "detail": "Missing authentication credentials"
}
```

### 403 Forbidden
```json
{
  "detail": "Invalid API key"
}
```

### 404 Not Found
```json
{
  "detail": "Session not found: sess_invalid123"
}
```

### 413 Payload Too Large
```json
{
  "detail": "File size exceeds maximum limit of 50MB"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "importance_score"],
      "msg": "ensure this value is less than or equal to 1.0",
      "type": "value_error.number.not_le"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "An unexpected error occurred. Please try again later."
}
```

---

## Quick Reference

### Endpoint Summary

| Category | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| **Health** | GET | `/health` | Service health check |
| **Health** | GET | `/` | Service info |
| **Sessions** | POST | `/api/v1/sessions/` | Create session |
| **Sessions** | GET | `/api/v1/sessions/` | List sessions |
| **Sessions** | GET | `/api/v1/sessions/{id}` | Get session |
| **Sessions** | DELETE | `/api/v1/sessions/{id}` | Delete session |
| **Sessions** | POST | `/api/v1/sessions/{id}/messages` | Add message |
| **Sessions** | GET | `/api/v1/sessions/{id}/messages` | Get messages |
| **Sessions** | PUT | `/api/v1/sessions/{id}/context` | Update context |
| **Sessions** | PUT | `/api/v1/sessions/{id}/state` | Update state |
| **Sessions** | POST | `/api/v1/sessions/{id}/extend` | Extend TTL |
| **Memory** | POST | `/api/v1/memory/` | Store memory |
| **Memory** | POST | `/api/v1/memory/search` | Search memories |
| **Memory** | GET | `/api/v1/memory/{id}` | Get memory |
| **Memory** | DELETE | `/api/v1/memory/{id}` | Delete memory |
| **Memory** | PUT | `/api/v1/memory/{id}/importance` | Update importance |
| **Memory** | POST | `/api/v1/memory/{id}/promote` | Promote to long-term |
| **Memory** | GET | `/api/v1/memory/session/{id}` | Get session memories |
| **Memory** | DELETE | `/api/v1/memory/session/{id}/cleanup` | Cleanup session |
| **Decisions** | POST | `/api/v1/memory/decisions/` | Store decision |
| **Decisions** | POST | `/api/v1/memory/decisions/search` | Search decisions |
| **Decisions** | GET | `/api/v1/memory/decisions/{id}` | Get decision |
| **Decisions** | GET | `/api/v1/memory/decisions/resource/{id}` | Get by resource |
| **Terraform** | POST | `/api/v1/terraform/files/upload` | Upload files |
| **Terraform** | GET | `/api/v1/terraform/files/tree` | Get file tree |
| **Terraform** | GET | `/api/v1/terraform/files/content/{path}` | Get file |
| **Terraform** | DELETE | `/api/v1/terraform/files/content/{path}` | Delete file |
| **Terraform** | GET | `/api/v1/terraform/files/accounts` | List accounts |
| **Terraform** | GET | `/api/v1/terraform/files/accounts/{id}/projects` | List projects |
| **Terraform** | GET | `/api/v1/terraform/files/stats` | Get stats |
| **Terraform** | DELETE | `/api/v1/terraform/files/project` | Delete project |
| **Terraform** | POST | `/api/v1/terraform/search` | Semantic search |
| **Terraform** | GET | `/api/v1/terraform/resources` | Find resources |
| **Terraform** | GET | `/api/v1/terraform/modules` | List modules |
| **Context** | POST | `/api/v1/context/state/upload` | Upload state |
| **Context** | GET | `/api/v1/context/state/resources` | List resources |
| **Context** | POST | `/api/v1/context/state/search` | Search state |
| **Context** | POST | `/api/v1/context/live/fetch` | Fetch live |
| **Context** | POST | `/api/v1/context/live/sync` | Sync state |
| **Context** | GET | `/api/v1/context/live/compare/{type}` | Compare drift |
| **Context** | GET | `/api/v1/context/live/resources` | List live |
| **Context** | POST | `/api/v1/context/general/` | Store context |
| **Context** | POST | `/api/v1/context/general/search` | Search context |
| **Context** | GET | `/api/v1/context/general/` | List contexts |
| **Context** | GET | `/api/v1/context/general/{id}` | Get context |
| **Context** | DELETE | `/api/v1/context/general/{id}` | Delete context |
| **Context** | POST | `/api/v1/context/general/batch` | Batch store |
| **Unified** | POST | `/api/v1/unified/search` | Cross-index search |
| **Unified** | POST | `/api/v1/unified/agent-context` | Build agent context |
| **Unified** | GET | `/api/v1/unified/stats` | Get all stats |
| **Unified** | DELETE | `/api/v1/unified/cleanup` | Cleanup user data |
| **Unified** | GET | `/api/v1/unified/health` | Health check |
| **Documents** | POST | `/api/v1/documents/upload` | Upload document |
| **Documents** | POST | `/api/v1/documents/upload-text` | Upload text |
| **Documents** | GET | `/api/v1/documents/` | List documents |
| **Documents** | DELETE | `/api/v1/documents/{id}` | Delete document |
| **Documents** | GET | `/api/v1/documents/stats` | Get stats |
| **Chat** | POST | `/api/v1/chat/` | Chat |
| **Chat** | POST | `/api/v1/chat/stream` | Stream chat |
| **Chat** | POST | `/api/v1/chat/query` | Query documents |
| **Chat** | GET | `/api/v1/chat/providers` | List providers |

---

## Interactive Documentation

Access the interactive API documentation at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
