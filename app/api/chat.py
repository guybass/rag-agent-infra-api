from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json

from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    QueryRequest,
    QueryResponse,
    LLMProvider,
)
from app.services.vector_store import VectorStoreService
from app.providers.factory import LLMProviderFactory
from app.api.deps import get_vector_store, verify_api_key_or_token

router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """
    Chat with the RAG system.

    Retrieves relevant context from the vector store and generates
    a response using the specified LLM provider.
    """
    # Retrieve relevant context
    results = vector_store.query(
        query_text=request.query,
        top_k=request.top_k,
    )

    if not results["documents"]:
        raise HTTPException(
            status_code=404,
            detail="No relevant documents found. Please upload documents first.",
        )

    # Format context from retrieved documents
    context_parts = []
    sources = []

    for i, (doc, metadata, distance) in enumerate(
        zip(results["documents"], results["metadatas"], results["distances"])
    ):
        context_parts.append(f"[{i+1}] {doc}")
        sources.append({
            "chunk_index": i + 1,
            "filename": metadata.get("filename", "unknown"),
            "relevance_score": 1 - distance,  # Convert distance to similarity
        })

    context = "\n\n".join(context_parts)

    # Get LLM provider
    try:
        provider = LLMProviderFactory.get_provider(
            provider=request.provider,
            model_id=request.model_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error initializing LLM provider: {str(e)}",
        )

    # Generate response
    try:
        answer = await provider.generate(
            prompt=request.query,
            context=context,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating response: {str(e)}",
        )

    return ChatResponse(
        answer=answer,
        sources=sources,
        provider=provider.provider_name,
        model_id=provider.model_id,
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """
    Chat with streaming response.

    Returns a Server-Sent Events stream with the response chunks.
    """
    # Retrieve relevant context
    results = vector_store.query(
        query_text=request.query,
        top_k=request.top_k,
    )

    if not results["documents"]:
        raise HTTPException(
            status_code=404,
            detail="No relevant documents found. Please upload documents first.",
        )

    # Format context
    context_parts = []
    sources = []

    for i, (doc, metadata, distance) in enumerate(
        zip(results["documents"], results["metadatas"], results["distances"])
    ):
        context_parts.append(f"[{i+1}] {doc}")
        sources.append({
            "chunk_index": i + 1,
            "filename": metadata.get("filename", "unknown"),
            "relevance_score": 1 - distance,
        })

    context = "\n\n".join(context_parts)

    # Get LLM provider
    provider = LLMProviderFactory.get_provider(
        provider=request.provider,
        model_id=request.model_id,
    )

    async def generate():
        # Send sources first
        yield f"data: {json.dumps({'type': 'sources', 'data': sources})}\n\n"

        # Stream the response
        async for chunk in provider.generate_stream(
            prompt=request.query,
            context=context,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        ):
            yield f"data: {json.dumps({'type': 'content', 'data': chunk})}\n\n"

        # Send completion signal
        yield f"data: {json.dumps({'type': 'done', 'provider': provider.provider_name, 'model_id': provider.model_id})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request: QueryRequest,
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """
    Query the vector store without LLM generation.

    Returns the most relevant document chunks for the query.
    """
    results = vector_store.query(
        query_text=request.query,
        top_k=request.top_k,
    )

    formatted_results = []
    for doc, metadata, distance in zip(
        results["documents"], results["metadatas"], results["distances"]
    ):
        formatted_results.append({
            "content": doc,
            "metadata": metadata,
            "relevance_score": 1 - distance,
        })

    return QueryResponse(results=formatted_results, query=request.query)


@router.get("/providers")
async def list_providers(auth: dict = Depends(verify_api_key_or_token)):
    """List available LLM providers."""
    return {
        "providers": LLMProviderFactory.available_providers(),
        "default": LLMProvider.BEDROCK.value,
    }
