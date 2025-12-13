from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "healthy"}


@router.get("/")
async def root():
    return {
        "message": "RAG Agent Infrastructure API",
        "version": "1.0.0",
        "docs": "/docs",
    }
