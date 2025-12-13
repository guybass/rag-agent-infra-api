from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Any, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class IndexGroup(str, Enum):
    TERRAFORM = "terraform"
    SESSIONS = "sessions"
    MEMORY = "memory"
    CONTEXT = "context"


class MemoryType(str, Enum):
    SESSION = "session"
    LONGTERM = "longterm"
    DECISION = "decision"


class ContextSourceType(str, Enum):
    TFSTATE = "tfstate"
    LIVE_API = "live_api"
    MANUAL = "manual"
    GENERAL = "general"


class TerraformCategory(str, Enum):
    NETWORKING = "networking"
    COMPUTE = "compute"
    DATABASE = "database"
    STORAGE = "storage"
    SECURITY = "security"
    LOAD_BALANCING = "load-balancing"
    DNS = "dns"
    MESSAGING = "messaging"
    MONITORING = "monitoring"
    GLOBAL = "global"


class TerraformEnvironment(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"
    GLOBAL = "global"


# ============================================================================
# Terraform Models
# ============================================================================

class TerraformHierarchy(BaseModel):
    """Hierarchical identifier for terraform resources."""
    user_id: str
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    environment: Optional[str] = None
    category: Optional[str] = None
    resource_kind: Optional[str] = None


class TerraformMetadata(BaseModel):
    """Metadata for terraform file indexing."""
    user_id: str
    account_id: str
    project_id: str
    environment: str
    category: str
    resource_kind: str
    file_type: str
    file_path: str
    is_module: bool = False
    resource_types: List[str] = []
    aws_services: List[str] = []
    module_source: Optional[str] = None
    dependencies: List[str] = []
    indexed_at: datetime = Field(default_factory=datetime.utcnow)


class TerraformResource(BaseModel):
    """Extracted terraform resource definition."""
    resource_type: str
    resource_name: str
    provider: str = "aws"
    attributes: Dict[str, Any] = {}
    file_path: str
    line_number: Optional[int] = None


class TerraformModuleCall(BaseModel):
    """Module call extracted from terraform file."""
    module_name: str
    source: str
    variables: Dict[str, Any] = {}
    file_path: str


class TerraformParseResult(BaseModel):
    """Result of parsing a terraform file."""
    file_path: str
    file_type: str
    resources: List[TerraformResource] = []
    variables: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []
    module_calls: List[TerraformModuleCall] = []
    data_sources: List[Dict[str, Any]] = []
    locals: Dict[str, Any] = {}
    providers: List[Dict[str, Any]] = []


class TerraformSearchResult(BaseModel):
    """Search result for terraform queries."""
    content: str
    metadata: TerraformMetadata
    relevance_score: float
    chunk_id: str


class TerraformTreeNode(BaseModel):
    """Node in terraform file tree."""
    name: str
    path: str
    type: Literal["file", "directory"]
    children: List["TerraformTreeNode"] = []
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Session Models
# ============================================================================

class SessionMessage(BaseModel):
    """Message in a session."""
    role: Literal["user", "assistant", "system"]
    content: str
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SessionData(BaseModel):
    """Session data stored in Redis."""
    session_id: str
    user_id: str
    model_id: str
    provider: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    messages: List[SessionMessage] = []
    context: Dict[str, Any] = {}
    state: Dict[str, Any] = {}
    ttl_seconds: int = 3600


class SessionSummary(BaseModel):
    """Summary info for a session."""
    session_id: str
    model_id: str
    provider: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    ttl_remaining: Optional[int] = None


# ============================================================================
# Memory Models
# ============================================================================

class MemoryEntry(BaseModel):
    """Memory entry for ChromaDB."""
    memory_id: str
    user_id: str
    session_id: Optional[str] = None
    memory_type: MemoryType
    content: str
    metadata: Dict[str, Any] = {}
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    accessed_at: datetime = Field(default_factory=datetime.utcnow)
    access_count: int = 0


class AgentDecision(BaseModel):
    """Agent decision record."""
    decision_id: str
    user_id: str
    session_id: str
    decision_type: str
    context: str
    reasoning: str
    outcome: str
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    related_resources: List[str] = []
    tags: List[str] = []


class MemorySearchResult(BaseModel):
    """Search result for memory queries."""
    memory: MemoryEntry
    relevance_score: float


class DecisionSearchResult(BaseModel):
    """Search result for decision queries."""
    decision: AgentDecision
    relevance_score: float


# ============================================================================
# Context Models
# ============================================================================

class CloudResource(BaseModel):
    """Generic cloud resource representation."""
    resource_type: str
    resource_id: str
    resource_arn: Optional[str] = None
    resource_name: Optional[str] = None
    region: str
    state_data: Dict[str, Any] = {}
    tags: Dict[str, str] = {}


class CloudContext(BaseModel):
    """Cloud context from state or live API."""
    context_id: str
    user_id: str
    account_id: str
    source_type: ContextSourceType
    resource: CloudResource
    project_id: Optional[str] = None
    environment: Optional[str] = None
    indexed_at: datetime = Field(default_factory=datetime.utcnow)
    state_captured_at: Optional[datetime] = None


class StateResource(BaseModel):
    """Resource extracted from terraform state."""
    resource_type: str
    resource_name: str
    resource_mode: str = "managed"
    provider: str
    instances: List[Dict[str, Any]] = []


class StateDiff(BaseModel):
    """Difference between state and live."""
    resource_id: str
    resource_type: str
    state_value: Dict[str, Any]
    live_value: Dict[str, Any]
    differences: List[Dict[str, Any]]
    drift_detected: bool


class ContextSearchResult(BaseModel):
    """Search result for context queries."""
    context: CloudContext
    relevance_score: float


# ============================================================================
# API Request/Response Models
# ============================================================================

# Terraform Requests
class TerraformUploadRequest(BaseModel):
    """Request to upload terraform files."""
    account_id: str
    project_id: str
    environment: str = "dev"
    base_path: str = ""


class TerraformSearchRequest(BaseModel):
    """Request to search terraform files."""
    query: str = Field(..., min_length=1)
    hierarchy: Optional[TerraformHierarchy] = None
    resource_types: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    environments: Optional[List[str]] = None
    include_file_content: bool = False
    top_k: int = Field(default=10, ge=1, le=50)


class TerraformTreeRequest(BaseModel):
    """Request to get terraform file tree."""
    account_id: Optional[str] = None
    project_id: Optional[str] = None
    environment: Optional[str] = None
    depth: int = Field(default=-1, ge=-1)


class TerraformUploadResponse(BaseModel):
    """Response from terraform upload."""
    files_processed: int
    chunks_created: int
    hierarchy: TerraformHierarchy
    errors: List[str] = []


# Session Requests
class SessionCreateRequest(BaseModel):
    """Request to create a session."""
    model_id: str
    provider: str = "bedrock"
    initial_context: Optional[Dict[str, Any]] = None
    ttl_seconds: int = Field(default=3600, ge=60, le=86400)


class SessionMessageRequest(BaseModel):
    """Request to add a message to session."""
    role: Literal["user", "assistant", "system"]
    content: str
    metadata: Optional[Dict[str, Any]] = None


class SessionUpdateContextRequest(BaseModel):
    """Request to update session context."""
    context: Dict[str, Any]
    merge: bool = True


class SessionUpdateStateRequest(BaseModel):
    """Request to update session state."""
    state: Dict[str, Any]
    merge: bool = True


class SessionExtendRequest(BaseModel):
    """Request to extend session TTL."""
    additional_seconds: int = Field(default=3600, ge=60, le=86400)


class SessionResponse(BaseModel):
    """Response with session data."""
    session: SessionData


class SessionListResponse(BaseModel):
    """Response with list of sessions."""
    sessions: List[SessionSummary]
    total: int


# Memory Requests
class MemoryStoreRequest(BaseModel):
    """Request to store memory."""
    content: str = Field(..., min_length=1)
    memory_type: MemoryType = MemoryType.SESSION
    session_id: Optional[str] = None
    importance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None
    tags: List[str] = []


class MemorySearchRequest(BaseModel):
    """Request to search memories."""
    query: str = Field(..., min_length=1)
    memory_types: List[MemoryType] = [MemoryType.SESSION, MemoryType.LONGTERM, MemoryType.DECISION]
    session_id: Optional[str] = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: Optional[List[str]] = None
    top_k: int = Field(default=10, ge=1, le=50)


class MemoryUpdateImportanceRequest(BaseModel):
    """Request to update memory importance."""
    importance_score: float = Field(..., ge=0.0, le=1.0)


class MemoryResponse(BaseModel):
    """Response with memory entry."""
    memory: MemoryEntry


class MemoryListResponse(BaseModel):
    """Response with list of memories."""
    memories: List[MemoryEntry]
    total: int


class MemorySearchResponse(BaseModel):
    """Response from memory search."""
    results: List[MemorySearchResult]
    query: str


# Decision Requests
class DecisionStoreRequest(BaseModel):
    """Request to store a decision."""
    session_id: str
    decision_type: str
    context: str
    reasoning: str
    outcome: str
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    related_resources: List[str] = []
    tags: List[str] = []


class DecisionSearchRequest(BaseModel):
    """Request to search decisions."""
    query: str = Field(..., min_length=1)
    decision_type: Optional[str] = None
    session_id: Optional[str] = None
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    top_k: int = Field(default=10, ge=1, le=50)


class DecisionResponse(BaseModel):
    """Response with decision."""
    decision: AgentDecision


class DecisionListResponse(BaseModel):
    """Response with list of decisions."""
    decisions: List[AgentDecision]
    total: int


class DecisionSearchResponse(BaseModel):
    """Response from decision search."""
    results: List[DecisionSearchResult]
    query: str


# Context Requests
class StateUploadRequest(BaseModel):
    """Request to upload state file."""
    account_id: str
    project_id: Optional[str] = None
    environment: Optional[str] = None


class AWSLiveFetchRequest(BaseModel):
    """Request to fetch live AWS resources."""
    account_id: str
    region: str
    resource_types: List[str]
    filters: Optional[Dict[str, Any]] = None


class AWSSyncRequest(BaseModel):
    """Request to sync with live AWS."""
    account_id: str
    region: str
    resource_types: Optional[List[str]] = None


class LiveFetchRequest(BaseModel):
    """Request to fetch live AWS resources."""
    account_id: str
    region: str = "us-east-1"
    resource_types: List[str] = []
    index_results: bool = True
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None


class LiveFetchResponse(BaseModel):
    """Response from live fetch."""
    resources_fetched: int
    resources_indexed: int
    resource_types: Dict[str, int]
    account_id: str
    region: str
    errors: List[str] = []


class LiveSyncRequest(BaseModel):
    """Request to sync live state with indexed state."""
    account_id: str
    region: str = "us-east-1"
    resource_types: Optional[List[str]] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None


class LiveSyncResponse(BaseModel):
    """Response from live sync."""
    synced: int
    added: int
    updated: int
    removed: int
    unchanged: int
    account_id: str
    region: str
    errors: List[str] = []


class StateVsLiveComparison(BaseModel):
    """Comparison between state and live resources."""
    resource_type: str
    account_id: str
    region: str
    state_only: List[Dict[str, Any]] = []
    live_only: List[Dict[str, Any]] = []
    differences: List[StateDiff] = []
    matched: int = 0
    drift_detected: bool = False


class GeneralContextRequest(BaseModel):
    """Request to store general context."""
    content: str = Field(..., min_length=1)
    context_type: str = "general"
    metadata: Optional[Dict[str, Any]] = None
    account_id: Optional[str] = None
    project_id: Optional[str] = None


class GeneralContextResponse(BaseModel):
    """Response from storing general context."""
    context_id: str
    indexed_at: datetime


class ContextSearchRequest(BaseModel):
    """Request to search context."""
    query: str = Field(..., min_length=1)
    account_id: Optional[str] = None
    source_type: Optional[ContextSourceType] = None
    resource_types: Optional[List[str]] = None
    top_k: int = Field(default=10, ge=1, le=50)


class GeneralContextStoreRequest(BaseModel):
    """Request to store general context."""
    context_type: str
    content: str = Field(..., min_length=1)
    metadata: Optional[Dict[str, Any]] = None


class ContextUploadResponse(BaseModel):
    """Response from context upload."""
    resources_indexed: int
    account_id: str
    source_type: str
    errors: List[str] = []


class ContextSearchResponse(BaseModel):
    """Response from context search."""
    results: List[ContextSearchResult]
    query: str


class ContextCompareResponse(BaseModel):
    """Response from state vs live comparison."""
    resource_id: str
    diff: StateDiff


# Unified Search Requests
class UnifiedSearchRequest(BaseModel):
    """Request to search across index groups."""
    query: str = Field(..., min_length=1)
    index_groups: List[IndexGroup] = [IndexGroup.TERRAFORM, IndexGroup.MEMORY, IndexGroup.CONTEXT]
    session_id: Optional[str] = None
    top_k_per_group: int = Field(default=5, ge=1, le=20)


class AgentContextRequest(BaseModel):
    """Request to build agent context."""
    session_id: str
    query: str = Field(..., min_length=1)
    include_groups: List[IndexGroup] = [IndexGroup.TERRAFORM, IndexGroup.MEMORY, IndexGroup.CONTEXT]
    max_context_tokens: int = Field(default=4000, ge=500, le=16000)


class UnifiedSearchResult(BaseModel):
    """Result from unified search."""
    terraform: List[TerraformSearchResult] = []
    memory: List[MemorySearchResult] = []
    decisions: List[DecisionSearchResult] = []
    context: List[ContextSearchResult] = []


class UnifiedSearchResponse(BaseModel):
    """Response from unified search."""
    results: UnifiedSearchResult
    query: str


class AgentContextResponse(BaseModel):
    """Response with built agent context."""
    context: str
    sources: Dict[str, int]
    session_id: str


class IndexGroupStats(BaseModel):
    """Statistics for an index group."""
    index_group: str
    collections: int
    total_documents: int
    details: Dict[str, Any] = {}


class AllStatsResponse(BaseModel):
    """Response with all index group stats."""
    stats: List[IndexGroupStats]
    user_id: str


# Fix forward reference
TerraformTreeNode.model_rebuild()
