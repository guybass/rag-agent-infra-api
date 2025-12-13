from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from typing import Optional

from app.models.schemas import (
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentDeleteResponse,
)
from app.services.vector_store import VectorStoreService
from app.services.document_processor import DocumentProcessor
from app.api.deps import get_vector_store, verify_api_key_or_token
from app.config import get_settings

router = APIRouter()
settings = get_settings()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """
    Upload and process a document for RAG.

    Supported formats: PDF, DOCX, TXT, MD, CSV
    """
    # Validate file size
    max_size = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read()

    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB",
        )

    # Reset file position
    await file.seek(0)

    # Process the document
    processor = DocumentProcessor()

    try:
        document_id, chunks, metadatas = processor.process_file(
            file.file,
            file.filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}",
        )

    # Add to vector store
    chunks_created = vector_store.add_documents(
        texts=chunks,
        metadatas=metadatas,
        document_id=document_id,
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=file.filename,
        chunks_created=chunks_created,
        message="Document uploaded and processed successfully",
    )


@router.post("/upload-text", response_model=DocumentUploadResponse)
async def upload_text(
    text: str = Form(...),
    source_name: str = Form(default="direct_input"),
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """Upload raw text directly for RAG processing."""
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    processor = DocumentProcessor()
    document_id, chunks, metadatas = processor.process_text(text, source_name)

    chunks_created = vector_store.add_documents(
        texts=chunks,
        metadatas=metadatas,
        document_id=document_id,
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=source_name,
        chunks_created=chunks_created,
        message="Text processed and stored successfully",
    )


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """List all documents in the vector store."""
    document_ids = vector_store.get_document_ids()

    documents = []
    for doc_id in document_ids:
        metadata = vector_store.get_document_metadata(doc_id)
        if metadata:
            documents.append({
                "document_id": doc_id,
                "filename": metadata.get("filename", "unknown"),
                "file_type": metadata.get("file_type", "unknown"),
                "total_chunks": metadata.get("total_chunks", 0),
            })

    return DocumentListResponse(documents=documents, total=len(documents))


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """Delete a document and all its chunks from the vector store."""
    # Check if document exists
    metadata = vector_store.get_document_metadata(document_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Document not found")

    vector_store.delete_document(document_id)

    return DocumentDeleteResponse(
        document_id=document_id,
        message="Document deleted successfully",
    )


@router.get("/stats")
async def get_stats(
    vector_store: VectorStoreService = Depends(get_vector_store),
    auth: dict = Depends(verify_api_key_or_token),
):
    """Get vector store statistics."""
    return vector_store.get_collection_stats()
