from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseLLMProvider(ABC):
    """Base class for all LLM providers."""

    def __init__(self, model_id: str | None = None):
        self.model_id = model_id or self.default_model_id

    @property
    @abstractmethod
    def default_model_id(self) -> str:
        """Return the default model ID for this provider."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response given a prompt and context."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        pass

    def format_rag_prompt(self, query: str, context: str) -> str:
        """Format the RAG prompt with context."""
        return f"""You are a helpful assistant that answers questions based on the provided context.
Use only the information from the context to answer the question. If the context doesn't contain
enough information to answer the question, say so.

Context:
{context}

Question: {query}

Answer:"""
