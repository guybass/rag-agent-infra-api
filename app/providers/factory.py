from app.models.schemas import LLMProvider
from app.providers.base import BaseLLMProvider
from app.providers.bedrock import BedrockProvider
from app.providers.openai_provider import OpenAIProvider
from app.providers.anthropic_provider import AnthropicProvider
from app.config import get_settings


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""

    _providers: dict[LLMProvider, type[BaseLLMProvider]] = {
        LLMProvider.BEDROCK: BedrockProvider,
        LLMProvider.OPENAI: OpenAIProvider,
        LLMProvider.ANTHROPIC: AnthropicProvider,
    }

    @classmethod
    def get_provider(
        cls,
        provider: LLMProvider | None = None,
        model_id: str | None = None,
        **kwargs,
    ) -> BaseLLMProvider:
        """
        Get an LLM provider instance.

        Args:
            provider: The LLM provider type (defaults to settings.llm_provider)
            model_id: Optional model ID override
            **kwargs: Additional provider-specific arguments (e.g., api_key)

        Returns:
            An instance of the requested LLM provider
        """
        settings = get_settings()

        # Use default provider from settings if not specified
        if provider is None:
            provider = LLMProvider(settings.llm_provider.value)

        if provider not in cls._providers:
            raise ValueError(f"Unknown provider: {provider}")

        # Inject API keys from settings if not provided in kwargs
        if provider == LLMProvider.OPENAI and "api_key" not in kwargs:
            if settings.openai_api_key:
                kwargs["api_key"] = settings.openai_api_key
        elif provider == LLMProvider.ANTHROPIC and "api_key" not in kwargs:
            if settings.anthropic_api_key:
                kwargs["api_key"] = settings.anthropic_api_key

        provider_class = cls._providers[provider]
        return provider_class(model_id=model_id, **kwargs)

    @classmethod
    def register_provider(
        cls,
        provider_type: LLMProvider,
        provider_class: type[BaseLLMProvider],
    ) -> None:
        """
        Register a new provider type.

        Args:
            provider_type: The provider type enum value
            provider_class: The provider class to register
        """
        cls._providers[provider_type] = provider_class

    @classmethod
    def available_providers(cls) -> list[str]:
        """Return list of available provider names."""
        return [p.value for p in cls._providers.keys()]
