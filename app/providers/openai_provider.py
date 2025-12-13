from typing import AsyncGenerator
from openai import AsyncOpenAI

from app.providers.base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM Provider."""

    def __init__(self, model_id: str | None = None, api_key: str | None = None):
        super().__init__(model_id)
        self.client = AsyncOpenAI(api_key=api_key)

    @property
    def default_model_id(self) -> str:
        return "gpt-4-turbo-preview"

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response using OpenAI."""
        full_prompt = self.format_rag_prompt(prompt, context)

        response = await self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content

    async def generate_stream(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using OpenAI."""
        full_prompt = self.format_rag_prompt(prompt, context)

        stream = await self.client.chat.completions.create(
            model=self.model_id,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
