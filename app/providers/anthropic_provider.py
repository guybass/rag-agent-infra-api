from typing import AsyncGenerator
from anthropic import AsyncAnthropic

from app.providers.base import BaseLLMProvider


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude LLM Provider (direct API, not Bedrock)."""

    def __init__(self, model_id: str | None = None, api_key: str | None = None):
        super().__init__(model_id)
        self.client = AsyncAnthropic(api_key=api_key)

    @property
    def default_model_id(self) -> str:
        return "claude-3-sonnet-20240229"

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def generate(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response using Anthropic Claude."""
        full_prompt = self.format_rag_prompt(prompt, context)

        response = await self.client.messages.create(
            model=self.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        )

        return response.content[0].text

    async def generate_stream(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using Anthropic Claude."""
        full_prompt = self.format_rag_prompt(prompt, context)

        async with self.client.messages.stream(
            model=self.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": full_prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text
