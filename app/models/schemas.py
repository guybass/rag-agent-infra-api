from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class LLMProvider(str, Enum):
    BEDROCK = "bedrock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The user's question")
    provider: LLMProvider = Field(default=LLMProvider.BEDROCK, description="LLM provider to use")
    model_id: Optional[str] = Field(default=None, description="Override default model ID")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")
    temperature: float = Field(default=0.7, ge=0, le=1, description="LLM temperature")
    max_tokens: int = Field(default=1024, ge=1, le=4096, description="Maximum response tokens")


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    provider: str
    model_id: str


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    chunks_created: int
    message: str


class DocumentListResponse(BaseModel):
    documents: list[dict]
    total: int


class DocumentDeleteResponse(BaseModel):
    document_id: str
    message: str


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    results: list[dict]
    query: str
