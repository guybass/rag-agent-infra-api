# RAG Agent Infrastructure API Documentation

## Multi-Index Semantic Layer for DevOps/SRE/Platform Engineers

**Version:** 2.0.0

This API provides a comprehensive semantic layer for AI agents working with AWS infrastructure and Terraform. It supports hierarchical storage, semantic search, and real-time context retrieval across multiple index groups.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Authentication](#authentication)
3. [Core Endpoints](#core-endpoints)
4. [Sessions API](#sessions-api)
5. [Memory API](#memory-api)
6. [Decisions API](#decisions-api)
7. [Terraform Files API](#terraform-files-api)
8. [Terraform Search API](#terraform-search-api)
9. [Context State API](#context-state-api)
10. [Context Live API](#context-live-api)
11. [Context General API](#context-general-api)
12. [Unified Search API](#unified-search-api)

---

## Architecture Overview

### Index Groups

```
ChromaDB Client
├── TERRAFORM (Semantic + File System)
│   └── terraform__{user}__{account}__{project}
│       ├── Metadata: environment, category, resource_kind, resource_types
│       └── File System: /terraform_data/{user}/{account}/{project}/{env}/...
│
├── SESSIONS (Redis - Ephemeral)
│   └── session:{user}:{session_id}
│       ├── messages, context, state, decisions
│       └── TTL-based expiration
│
├── MEMORY (ChromaDB - Persistent)
│   ├── memory__session__{user}    (session-specific)
│   ├── memory__longterm__{user}   (cross-session)
│   └── memory__decisions__{user}  (agent decisions - INDEXED!)
│
└── CONTEXT (ChromaDB + AWS Live)
    ├── context__state__{user}__{account}  (terraform.tfstate)
    ├── context__live__{user}__{account}   (live AWS API)
    └── context__general__{user}           (general context)
```

### Collection Naming Convention

All ChromaDB collections follow the pattern:
```
{index_group}__{subindex}__{user_id}__{account_id}__{project_id}
```

---

## Authentication

All endpoints require authentication via API key or JWT token.

**Header:** `Authorization: Bearer <token>` or `X-API-Key: <api_key>`

The authenticated user's ID is extracted from the token and used for data isolation.

---

## Core Endpoints

### Health Check

#### `GET /health`

**Description:** Basic health check for the API.

**Internal Logic:**
1. Returns immediate success response
2. No database or service checks

**Response:**
```json
{
  "status": "healthy"
}
```

---

## Sessions API

Base Path: `/api/v1/sessions`

Sessions are ephemeral conversation contexts stored in Redis with automatic TTL expiration.

### Create Session

#### `POST /`

**Description:** Create a new session for an AI agent conversation.

**Internal Logic:**
1. Generate unique session ID using UUID4
2. Create `SessionData` object with:
   - `session_id`: Generated UUID
   - `user_id`: From authentication
   - `model_id`: LLM model identifier
   - `provider`: LLM provider (bedrock, openai, anthropic)
   - `created_at`: Current timestamp
   - `ttl_seconds`: Session lifetime (default 3600)
3. Serialize session to JSON
4. Store in Redis with key pattern: `session:{user_id}:{session_id}`
5. Set Redis TTL for automatic expiration

**Request Body:**
```json
{
  "model_id": "anthropic.claude-3-sonnet",
  "provider": "bedrock",
  "initial_context": {"project": "infrastructure"},
  "ttl_seconds": 3600
}
```

**Response:**
```json
{
  "session": {
    "session_id": "uuid",
    "user_id": "user123",
    "model_id": "anthropic.claude-3-sonnet",
    "provider": "bedrock",
    "created_at": "2024-01-15T10:30:00Z",
    "messages": [],
    "context": {"project": "infrastructure"},
    "state": {},
    "ttl_seconds": 3600
  }
}
```

---

### List Sessions

#### `GET /`

**Description:** List all active sessions for the authenticated user.

**Internal Logic:**
1. Scan Redis for keys matching pattern: `session:{user_id}:*`
2. For each key, retrieve session data
3. Calculate remaining TTL using Redis TTL command
4. Build summary objects with message counts
5. Sort by last activity (most recent first)

**Query Parameters:**
- `limit` (int, default=50): Maximum sessions to return

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "uuid",
      "model_id": "anthropic.claude-3-sonnet",
      "provider": "bedrock",
      "created_at": "2024-01-15T10:30:00Z",
      "last_activity": "2024-01-15T11:00:00Z",
      "message_count": 15,
      "ttl_remaining": 1800
    }
  ],
  "total": 1
}
```

---

### Get Session

#### `GET /{session_id}`

**Description:** Retrieve a specific session with all messages.

**Internal Logic:**
1. Build Redis key: `session:{user_id}:{session_id}`
2. Fetch session JSON from Redis
3. Deserialize to `SessionData` object
4. Return 404 if not found

**Response:**
```json
{
  "session": {
    "session_id": "uuid",
    "user_id": "user123",
    "model_id": "anthropic.claude-3-sonnet",
    "messages": [
      {
        "role": "user",
        "content": "Deploy EKS cluster",
        "timestamp": "2024-01-15T10:31:00Z"
      }
    ],
    "context": {},
    "state": {}
  }
}
```

---

### Delete Session

#### `DELETE /{session_id}`

**Description:** Delete a session and all its data.

**Internal Logic:**
1. Build Redis key: `session:{user_id}:{session_id}`
2. Delete key from Redis
3. Return success even if key didn't exist

**Response:**
```json
{
  "deleted": true,
  "session_id": "uuid"
}
```

---

### Add Message

#### `POST /{session_id}/messages`

**Description:** Add a message to the session conversation.

**Internal Logic:**
1. Retrieve existing session from Redis
2. Create `SessionMessage` with:
   - `role`: user/assistant/system
   - `content`: Message text
   - `timestamp`: Current time
   - `metadata`: Optional additional data
3. Append message to session's messages array
4. Update `last_activity` timestamp
5. Save updated session back to Redis
6. Reset TTL to extend session lifetime

**Request Body:**
```json
{
  "role": "user",
  "content": "What EC2 instances are running?",
  "metadata": {"intent": "query"}
}
```

**Response:**
```json
{
  "session": { ... },
  "message_added": true
}
```

---

### Get Messages

#### `GET /{session_id}/messages`

**Description:** Retrieve messages from a session with pagination.

**Internal Logic:**
1. Retrieve session from Redis
2. Apply limit and offset to messages array
3. Return paginated messages with total count

**Query Parameters:**
- `limit` (int, default=50): Messages per page
- `offset` (int, default=0): Starting position

**Response:**
```json
{
  "messages": [...],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

---

### Update Context

#### `PUT /{session_id}/context`

**Description:** Update the session's context object.

**Internal Logic:**
1. Retrieve session from Redis
2. If `merge=true`: Deep merge new context with existing
3. If `merge=false`: Replace context entirely
4. Save updated session
5. Update last_activity timestamp

**Request Body:**
```json
{
  "context": {
    "current_task": "deploying_eks",
    "environment": "production"
  },
  "merge": true
}
```

---

### Update State

#### `PUT /{session_id}/state`

**Description:** Update the session's state object (for agent state machine).

**Internal Logic:**
1. Retrieve session from Redis
2. Merge or replace state based on `merge` parameter
3. Save and update timestamps

**Request Body:**
```json
{
  "state": {
    "step": 3,
    "status": "awaiting_approval"
  },
  "merge": true
}
```

---

### Extend TTL

#### `POST /{session_id}/extend`

**Description:** Extend the session's time-to-live.

**Internal Logic:**
1. Retrieve session from Redis
2. Calculate new TTL: current_ttl + additional_seconds
3. Cap at maximum (86400 seconds / 24 hours)
4. Update Redis key's TTL using EXPIRE command

**Request Body:**
```json
{
  "additional_seconds": 3600
}
```

**Response:**
```json
{
  "extended": true,
  "new_ttl": 5400
}
```

---

## Memory API

Base Path: `/api/v1/memory`

Memory provides persistent storage for information that should survive session boundaries.

### Store Memory

#### `POST /`

**Description:** Store a memory entry for future retrieval.

**Internal Logic:**
1. Generate unique memory ID (UUID4)
2. Determine collection based on memory_type:
   - `SESSION`: `memory__session__{user_id}`
   - `LONGTERM`: `memory__longterm__{user_id}`
3. Create embedding of content using ChromaDB's embedding function
4. Build metadata object with:
   - `memory_id`, `user_id`, `session_id`
   - `memory_type`, `importance_score`
   - `tags` (stored as comma-separated string)
   - `created_at`, `accessed_at`
5. Add document to ChromaDB collection

**Request Body:**
```json
{
  "content": "User prefers Terraform modules over raw resources",
  "memory_type": "longterm",
  "session_id": "optional-session-id",
  "importance_score": 0.8,
  "metadata": {"category": "preference"},
  "tags": ["terraform", "user-preference"]
}
```

**Response:**
```json
{
  "memory": {
    "memory_id": "uuid",
    "content": "...",
    "memory_type": "longterm",
    "importance_score": 0.8,
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

---

### Search Memories

#### `POST /search`

**Description:** Semantically search memories.

**Internal Logic:**
1. Determine collections to search based on `memory_types`
2. For each collection:
   - Query ChromaDB with semantic similarity search
   - Apply metadata filters (session_id, min_importance, tags)
3. Aggregate results from all collections
4. Sort by relevance score (1 - distance)
5. Return top_k results

**Request Body:**
```json
{
  "query": "user preferences for infrastructure",
  "memory_types": ["session", "longterm"],
  "session_id": "optional-filter",
  "min_importance": 0.5,
  "tags": ["terraform"],
  "top_k": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "memory": { ... },
      "relevance_score": 0.92
    }
  ],
  "query": "user preferences for infrastructure"
}
```

---

### Get Memory

#### `GET /{memory_id}`

**Description:** Retrieve a specific memory by ID.

**Internal Logic:**
1. Search all memory collections for matching `memory_id` in metadata
2. Increment `access_count` on retrieval
3. Update `accessed_at` timestamp
4. Return memory or 404

---

### Delete Memory

#### `DELETE /{memory_id}`

**Description:** Delete a memory entry.

**Internal Logic:**
1. Find memory across collections by ID
2. Delete document from ChromaDB using ID
3. Return success/failure

---

### Update Importance

#### `PUT /{memory_id}/importance`

**Description:** Update a memory's importance score.

**Internal Logic:**
1. Find memory by ID
2. Update `importance_score` in metadata
3. Re-index document with updated metadata

**Request Body:**
```json
{
  "importance_score": 0.95
}
```

---

### Promote to Long-term

#### `POST /{memory_id}/promote`

**Description:** Promote a session memory to long-term storage.

**Internal Logic:**
1. Retrieve memory from session collection
2. Delete from session collection
3. Add to longterm collection with:
   - Updated `memory_type`: "longterm"
   - Preserved content and metadata
   - New `promoted_at` timestamp

---

### Get Session Memories

#### `GET /session/{session_id}`

**Description:** Get all memories for a specific session.

**Internal Logic:**
1. Query session memory collection
2. Filter by `session_id` in metadata
3. Return all matching memories

---

## Decisions API

Base Path: `/api/v1/memory/decisions`

Decisions track agent reasoning and outcomes for future learning.

### Store Decision

#### `POST /`

**Description:** Store an agent decision with reasoning.

**Internal Logic:**
1. Generate decision ID (UUID4)
2. Create searchable content by combining:
   - `decision_type`
   - `context`
   - `reasoning`
   - `outcome`
3. Store in `memory__decisions__{user_id}` collection
4. Build metadata with:
   - `decision_id`, `session_id`, `decision_type`
   - `confidence_score`
   - `related_resources` (JSON array)
   - `tags`
5. Index for semantic search on reasoning

**Request Body:**
```json
{
  "session_id": "uuid",
  "decision_type": "resource_selection",
  "context": "User asked for high-availability database",
  "reasoning": "Selected RDS Multi-AZ because user mentioned HA requirements and budget allows",
  "outcome": "Recommended aws_db_instance with multi_az=true",
  "confidence_score": 0.85,
  "related_resources": ["aws_db_instance", "aws_db_subnet_group"],
  "tags": ["rds", "high-availability"]
}
```

---

### Search Decisions

#### `POST /search`

**Description:** Search past decisions semantically.

**Internal Logic:**
1. Query decisions collection with semantic search
2. Filter by `decision_type`, `session_id`, `min_confidence`
3. Return ranked results by relevance

**Request Body:**
```json
{
  "query": "database high availability",
  "decision_type": "resource_selection",
  "min_confidence": 0.7,
  "top_k": 5
}
```

---

### Get Decision

#### `GET /{decision_id}`

**Description:** Retrieve a specific decision.

---

### Get Decisions by Resource

#### `GET /resource/{resource_type}`

**Description:** Get decisions related to a specific resource type.

**Internal Logic:**
1. Query decisions collection
2. Filter where `related_resources` contains `resource_type`
3. Return matching decisions

---

## Terraform Files API

Base Path: `/api/v1/terraform/files`

Manages Terraform files with both file system storage and semantic indexing.

### Upload Files

#### `POST /upload`

**Description:** Upload and index Terraform files.

**Internal Logic:**
1. Receive multipart file upload
2. Validate file extensions (.tf, .tfvars, .hcl)
3. Create directory structure:
   ```
   {terraform_storage_path}/{user_id}/{account_id}/{project_id}/{environment}/
   ```
4. Save files to filesystem
5. For each file:
   - Parse HCL using python-hcl2 (with regex fallback)
   - Extract: resources, variables, outputs, module calls, data sources
   - Determine category from file path and resource types
   - Map resources to AWS services
6. Chunk file content using RecursiveCharacterTextSplitter:
   - chunk_size: 1000
   - chunk_overlap: 200
7. Create embeddings and store in ChromaDB collection:
   - Collection: `terraform__semantic__{user_id}__{account_id}__{project_id}`
8. Index metadata:
   - `file_path`, `file_type`, `environment`, `category`
   - `resource_types`, `aws_services`, `is_module`

**Request (multipart/form-data):**
- `files`: Multiple .tf files
- `account_id`: AWS account identifier
- `project_id`: Project identifier
- `environment`: dev/staging/prod/global
- `base_path`: Optional subdirectory

**Response:**
```json
{
  "files_processed": 5,
  "chunks_created": 23,
  "hierarchy": {
    "user_id": "user123",
    "account_id": "123456789",
    "project_id": "eks-cluster",
    "environment": "prod"
  },
  "errors": []
}
```

---

### Get File Tree

#### `GET /tree`

**Description:** Get directory tree structure for Terraform files.

**Internal Logic:**
1. Build base path from user_id and optional filters
2. Walk filesystem directory recursively
3. Build tree nodes with:
   - `name`: File/directory name
   - `path`: Relative path
   - `type`: "file" or "directory"
   - `children`: Nested nodes for directories
4. Apply depth limit if specified

**Query Parameters:**
- `account_id`: Filter by account
- `project_id`: Filter by project
- `environment`: Filter by environment
- `depth`: Maximum tree depth (-1 for unlimited)

**Response:**
```json
{
  "tree": {
    "name": "root",
    "type": "directory",
    "path": "/",
    "children": [
      {
        "name": "environments",
        "type": "directory",
        "children": [
          {
            "name": "prod",
            "type": "directory",
            "children": [
              {"name": "main.tf", "type": "file", "path": "/environments/prod/main.tf"}
            ]
          }
        ]
      }
    ]
  }
}
```

---

### Get File Content

#### `GET /{file_path:path}`

**Description:** Retrieve content of a specific Terraform file.

**Internal Logic:**
1. Validate file_path is within user's directory
2. Read file from filesystem
3. Optionally parse and return structured data

**Query Parameters:**
- `account_id`: Required account context
- `project_id`: Required project context
- `parse`: Boolean, return parsed HCL structure

**Response:**
```json
{
  "path": "/environments/prod/main.tf",
  "content": "resource \"aws_eks_cluster\" ...",
  "parsed": {
    "resources": [...],
    "variables": [...],
    "outputs": [...]
  }
}
```

---

### Delete File

#### `DELETE /{file_path:path}`

**Description:** Delete a Terraform file.

**Internal Logic:**
1. Delete file from filesystem
2. Remove associated chunks from ChromaDB
3. Update parent directory if empty

---

### List Accounts

#### `GET /accounts`

**Description:** List all accounts with Terraform data.

**Internal Logic:**
1. List directories under user's terraform path
2. Return account IDs with metadata

---

### List Projects

#### `GET /accounts/{account_id}/projects`

**Description:** List projects within an account.

---

## Terraform Search API

Base Path: `/api/v1/terraform`

Semantic search across indexed Terraform configurations.

### Semantic Search

#### `POST /search`

**Description:** Search Terraform files semantically.

**Internal Logic:**
1. Build list of collections to search based on hierarchy filters
2. For each collection:
   - Perform semantic similarity search
   - Apply metadata filters:
     - `resource_types`: Filter by specific resources
     - `categories`: Filter by category (networking, compute, etc.)
     - `environments`: Filter by environment
3. Aggregate and rank results by relevance
4. Optionally include full file content

**Request Body:**
```json
{
  "query": "EKS cluster with managed node groups",
  "hierarchy": {
    "account_id": "123456789",
    "project_id": "eks-cluster"
  },
  "resource_types": ["aws_eks_cluster", "aws_eks_node_group"],
  "categories": ["compute"],
  "environments": ["prod", "staging"],
  "include_file_content": false,
  "top_k": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "content": "resource \"aws_eks_cluster\" \"main\" { ... }",
      "metadata": {
        "file_path": "/environments/prod/compute/main.tf",
        "category": "compute",
        "resource_types": ["aws_eks_cluster"],
        "environment": "prod"
      },
      "relevance_score": 0.94,
      "chunk_id": "uuid"
    }
  ],
  "query": "EKS cluster with managed node groups"
}
```

---

### List Resources

#### `GET /resources`

**Description:** List Terraform resources by type.

**Internal Logic:**
1. Query ChromaDB with metadata filter on `resource_types`
2. Extract unique resources from results
3. Group by resource type

**Query Parameters:**
- `account_id`: Required
- `project_id`: Optional
- `resource_type`: Filter specific type
- `environment`: Filter by environment

---

### List Modules

#### `GET /modules`

**Description:** List Terraform modules.

**Internal Logic:**
1. Query for documents where `is_module=true`
2. Extract module information from parsed data

---

## Context State API

Base Path: `/api/v1/context/state`

Manages Terraform state file indexing and search.

### Upload State File

#### `POST /upload`

**Description:** Upload and index a terraform.tfstate file.

**Internal Logic:**
1. Receive state file (multipart upload)
2. Validate file extension (.tfstate or .json)
3. Parse state file:
   - Support v3 and v4 state formats
   - Extract resources from modules
   - For v4: Parse `resources` array directly
   - For v3: Parse `modules[].resources`
4. Convert to `CloudResource` objects:
   - `resource_type`: Terraform type (aws_instance, etc.)
   - `resource_id`: Instance ID from state
   - `resource_name`: Logical name
   - `state_data`: Full attributes from state
5. Store in ChromaDB collection: `context__state__{user_id}__{account_id}`
6. Create embeddings from JSON-serialized state_data

**Request (multipart/form-data):**
- `file`: .tfstate file
- `account_id`: AWS account
- `project_id`: Optional project
- `environment`: Optional environment

**Response:**
```json
{
  "resources_indexed": 47,
  "account_id": "123456789",
  "source_type": "tfstate",
  "errors": []
}
```

---

### List State Resources

#### `GET /resources`

**Description:** List resources from indexed state.

**Internal Logic:**
1. Query state collection with optional filters
2. Return resource list with metadata

**Query Parameters:**
- `account_id`: Required
- `resource_type`: Optional filter
- `limit`: Max results (default 100)

**Response:**
```json
{
  "resources": [
    {
      "context_id": "uuid",
      "resource_type": "aws_instance",
      "resource_id": "i-1234567890abcdef0",
      "resource_name": "web_server",
      "region": "us-east-1",
      "state_data": {
        "instance_type": "t3.medium",
        "vpc_id": "vpc-123"
      },
      "indexed_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 47,
  "account_id": "123456789"
}
```

---

### Search State

#### `POST /search`

**Description:** Semantic search over state resources.

**Internal Logic:**
1. Query state collection with semantic search
2. Match against serialized state_data
3. Filter by resource_types if specified
4. Return ranked results

**Request Body:**
```json
{
  "query": "EC2 instances in production VPC",
  "account_id": "123456789",
  "resource_types": ["aws_instance"],
  "top_k": 10
}
```

---

## Context Live API

Base Path: `/api/v1/context/live`

Fetches and manages live AWS resource state.

### Fetch Live Resources

#### `POST /fetch`

**Description:** Fetch current resources from AWS APIs.

**Internal Logic:**
1. Initialize AWS boto3 clients with credentials:
   - Use provided credentials OR
   - Fall back to configured/IAM credentials
2. For each requested resource_type:
   - Call appropriate AWS API (describe_instances, list_clusters, etc.)
   - Handle pagination for large result sets
   - Transform to `CloudResource` objects
3. If `index_results=true`:
   - Store in ChromaDB: `context__live__{user_id}__{account_id}`
   - Create embeddings from state_data
4. Return counts by resource type

**Supported Resource Types:**
- `ec2`, `vpc`, `subnet`, `security_group`
- `eks`, `rds`, `s3`, `lambda`
- `alb`, `nlb`, `dynamodb`, `elasticache`
- `ecs`, `iam_role`, `route53`

**Request Body:**
```json
{
  "account_id": "123456789",
  "region": "us-east-1",
  "resource_types": ["ec2", "eks", "rds"],
  "index_results": true,
  "aws_access_key_id": "optional",
  "aws_secret_access_key": "optional"
}
```

**Response:**
```json
{
  "resources_fetched": 25,
  "resources_indexed": 25,
  "resource_types": {
    "ec2": 10,
    "eks": 2,
    "rds": 13
  },
  "account_id": "123456789",
  "region": "us-east-1",
  "errors": []
}
```

---

### Sync Live State

#### `POST /sync`

**Description:** Sync indexed resources with current AWS state.

**Internal Logic:**
1. Get existing indexed live resources
2. Fetch current live resources from AWS
3. Compare and categorize:
   - **Added**: Resources in live but not indexed
   - **Updated**: Resources in both (update indexed)
   - **Removed**: Resources indexed but not in live
   - **Unchanged**: Resources identical in both
4. Update ChromaDB collection accordingly
5. Return sync statistics

**Request Body:**
```json
{
  "account_id": "123456789",
  "region": "us-east-1",
  "resource_types": ["ec2", "eks"]
}
```

**Response:**
```json
{
  "synced": 15,
  "added": 3,
  "updated": 10,
  "removed": 2,
  "unchanged": 5,
  "account_id": "123456789",
  "region": "us-east-1",
  "errors": []
}
```

---

### Compare State vs Live

#### `GET /compare/{resource_type}`

**Description:** Compare Terraform state with live AWS resources.

**Internal Logic:**
1. Retrieve indexed state resources of type
2. Fetch live resources of same type
3. Build comparison:
   - **state_only**: Resources in state but not live (deleted?)
   - **live_only**: Resources in live but not state (unmanaged?)
   - **differences**: Resources with attribute differences
   - **matched**: Resources identical in both
4. Calculate drift detection status

**Query Parameters:**
- `account_id`: Required
- `region`: AWS region (default us-east-1)
- `resource_id`: Optional specific resource

**Response:**
```json
{
  "resource_type": "aws_instance",
  "account_id": "123456789",
  "region": "us-east-1",
  "state_only": [
    {"resource_id": "i-deleted", "resource_type": "aws_instance"}
  ],
  "live_only": [
    {"resource_id": "i-unmanaged", "resource_type": "aws_instance"}
  ],
  "differences": [
    {
      "resource_id": "i-12345",
      "resource_type": "aws_instance",
      "state_value": {"instance_type": "t3.small"},
      "live_value": {"instance_type": "t3.medium"},
      "differences": [
        {"key": "instance_type", "state_value": "t3.small", "live_value": "t3.medium"}
      ],
      "drift_detected": true
    }
  ],
  "matched": 8,
  "drift_detected": true
}
```

---

### List Live Resources

#### `GET /resources`

**Description:** List indexed live resources.

**Query Parameters:**
- `account_id`: Required
- `resource_type`: Optional filter
- `region`: Optional filter
- `limit`: Max results

---

## Context General API

Base Path: `/api/v1/context/general`

Stores miscellaneous context information.

### Store General Context

#### `POST /`

**Description:** Store arbitrary context information.

**Internal Logic:**
1. Generate context ID (UUID4)
2. Store in ChromaDB: `context__general__{user_id}`
3. Create embedding from content
4. Store metadata including custom fields

**Request Body:**
```json
{
  "content": "Production environment uses us-east-1 and us-west-2 for HA",
  "context_type": "architecture",
  "metadata": {
    "regions": ["us-east-1", "us-west-2"],
    "criticality": "high"
  },
  "account_id": "123456789",
  "project_id": "main-infrastructure"
}
```

---

### Search General Context

#### `POST /search`

**Description:** Search stored general context.

**Request Body:**
```json
{
  "query": "production regions",
  "top_k": 5
}
```

---

### List General Context

#### `GET /`

**Description:** List stored general context entries.

**Query Parameters:**
- `context_type`: Filter by type
- `account_id`: Filter by account
- `project_id`: Filter by project
- `limit`: Max results

---

### Get Context

#### `GET /{context_id}`

**Description:** Retrieve specific context entry.

---

### Delete Context

#### `DELETE /{context_id}`

**Description:** Delete context entry.

---

### Batch Store

#### `POST /batch`

**Description:** Store multiple context entries at once.

**Request Body:**
```json
{
  "contexts": [
    {"content": "...", "context_type": "..."},
    {"content": "...", "context_type": "..."}
  ]
}
```

---

## Unified Search API

Base Path: `/api/v1/unified`

Cross-index search and context aggregation.

### Unified Search

#### `POST /search`

**Description:** Search across all index groups simultaneously.

**Internal Logic:**
1. For each requested index group, perform parallel searches:
   - **TERRAFORM**: Semantic search on terraform collections
   - **MEMORY**: Search session + longterm memory collections
   - **DECISIONS**: Search decision collection
   - **CONTEXT**: Search state + live + general collections
2. Each search uses same query with semantic similarity
3. Aggregate results by group
4. Return unified result object

**Request Body:**
```json
{
  "query": "EKS cluster configuration with node groups",
  "index_groups": ["terraform", "memory", "context"],
  "session_id": "optional-for-session-specific-results",
  "top_k_per_group": 5
}
```

**Response:**
```json
{
  "results": {
    "terraform": [
      {"content": "...", "metadata": {...}, "relevance_score": 0.95}
    ],
    "memory": [
      {"memory": {...}, "relevance_score": 0.88}
    ],
    "decisions": [
      {"decision": {...}, "relevance_score": 0.82}
    ],
    "context": [
      {"context": {...}, "relevance_score": 0.79}
    ]
  },
  "query": "EKS cluster configuration with node groups"
}
```

---

### Build Agent Context

#### `POST /agent-context`

**Description:** Build comprehensive context for AI agent consumption.

**Internal Logic:**
1. Calculate character budget per group based on max_context_tokens
2. For each included group, retrieve and format context:
   - **SESSION**: Recent messages (last 10)
   - **MEMORY**: Relevant memories with relevance scores
   - **DECISIONS**: Past similar decisions with reasoning
   - **TERRAFORM**: Relevant terraform configurations
   - **CONTEXT**: Cloud state information
3. Format each section with headers
4. Combine into single context string
5. Track source counts for attribution

**Request Body:**
```json
{
  "session_id": "uuid",
  "query": "Deploy a new EKS cluster",
  "include_groups": ["terraform", "memory", "context"],
  "max_context_tokens": 4000
}
```

**Response:**
```json
{
  "context": "## Session Context\n[user]: Previous discussion...\n\n## Relevant Memories\n- User prefers managed node groups...\n\n## Terraform Context\n- File: /prod/eks/main.tf\n  Content: resource \"aws_eks_cluster\"...\n\n## Cloud Context\n- Resource: aws_eks_cluster/main-cluster\n  Region: us-east-1",
  "sources": {
    "sessions": 1,
    "memories": 3,
    "terraform": 5,
    "context": 4
  },
  "session_id": "uuid"
}
```

---

### Get All Stats

#### `GET /stats`

**Description:** Get statistics for all index groups.

**Internal Logic:**
1. For each index group:
   - Count collections matching user pattern
   - Sum document counts across collections
   - Gather group-specific metrics
2. Return aggregated statistics

**Response:**
```json
{
  "stats": [
    {
      "index_group": "terraform",
      "collections": 5,
      "total_documents": 234,
      "details": {
        "collection_names": ["terraform__semantic__user123__acc1__proj1", ...]
      }
    },
    {
      "index_group": "memory",
      "collections": 3,
      "total_documents": 156,
      "details": {
        "session_memories": 89,
        "longterm_memories": 45,
        "decisions": 22
      }
    },
    {
      "index_group": "context",
      "collections": 4,
      "total_documents": 512,
      "details": {
        "state_resources": 234,
        "live_resources": 198,
        "general_contexts": 80
      }
    },
    {
      "index_group": "sessions",
      "collections": 1,
      "total_documents": 8,
      "details": {
        "session_count": 8,
        "active_sessions": 5
      }
    }
  ],
  "user_id": "user123"
}
```

---

### Cleanup User Data

#### `DELETE /cleanup`

**Description:** Delete all data for the authenticated user.

**Internal Logic:**
1. Require `confirm=true` query parameter
2. List and delete all terraform collections
3. List and delete all memory collections
4. List and delete all context collections
5. Sessions expire naturally via TTL
6. Return deletion counts

**Query Parameters:**
- `confirm` (boolean, required): Must be true

**Response:**
```json
{
  "deleted": true,
  "user_id": "user123",
  "counts": {
    "terraform": 5,
    "memory": 3,
    "context": 4,
    "sessions": 0
  }
}
```

---

### Health Check

#### `GET /health`

**Description:** Health check for unified search service.

**Response:**
```json
{
  "status": "healthy",
  "service": "unified-search",
  "index_groups": ["terraform", "sessions", "memory", "context"]
}
```

---

## Error Responses

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing the issue"
}
```

**Common HTTP Status Codes:**
- `400`: Bad Request - Invalid input
- `401`: Unauthorized - Missing/invalid authentication
- `404`: Not Found - Resource doesn't exist
- `422`: Validation Error - Request body validation failed
- `500`: Internal Server Error - Server-side error

---

## Rate Limiting

Currently no rate limiting is implemented. For production deployments, consider adding rate limiting middleware.

---

## Changelog

### Version 2.0.0
- Added multi-index architecture
- Added Sessions API with Redis backend
- Added Memory and Decisions APIs
- Added Terraform file management and semantic search
- Added Context APIs for state and live AWS resources
- Added Unified Search API for cross-index queries
