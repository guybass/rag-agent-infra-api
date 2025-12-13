import json
from typing import AsyncGenerator
import boto3
from botocore.config import Config

from app.providers.base import BaseLLMProvider
from app.config import get_settings


class BedrockProvider(BaseLLMProvider):
    """AWS Bedrock LLM Provider."""

    def __init__(self, model_id: str | None = None):
        super().__init__(model_id)
        settings = get_settings()

        config = Config(
            region_name=settings.aws_region,
            retries={"max_attempts": 3, "mode": "adaptive"},
        )

        # Check if we need to assume a role
        if settings.aws_assume_role_arn:
            # Use STS to assume the specified role
            sts_client = boto3.client("sts", region_name=settings.aws_region)
            assumed_role = sts_client.assume_role(
                RoleArn=settings.aws_assume_role_arn,
                RoleSessionName="rag-agent-bedrock-session"
            )
            credentials = assumed_role["Credentials"]
            self.client = boto3.client(
                "bedrock-runtime",
                config=config,
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )
        elif settings.aws_access_key_id and settings.aws_secret_access_key:
            # Use explicit credentials from config
            self.client = boto3.client(
                "bedrock-runtime",
                config=config,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
        else:
            # Use EC2 instance role / default credential chain
            self.client = boto3.client("bedrock-runtime", config=config)

    @property
    def default_model_id(self) -> str:
        return get_settings().bedrock_model_id

    @property
    def provider_name(self) -> str:
        return "bedrock"

    async def generate(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response using AWS Bedrock."""
        full_prompt = self.format_rag_prompt(prompt, context)

        # Determine the model family and format request accordingly
        if "anthropic" in self.model_id.lower():
            return await self._generate_anthropic(full_prompt, temperature, max_tokens)
        elif "meta" in self.model_id.lower():
            return await self._generate_llama(full_prompt, temperature, max_tokens)
        elif "amazon" in self.model_id.lower():
            return await self._generate_titan(full_prompt, temperature, max_tokens)
        else:
            # Default to Anthropic format
            return await self._generate_anthropic(full_prompt, temperature, max_tokens)

    async def _generate_anthropic(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Generate using Anthropic Claude models on Bedrock."""
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        })

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    async def _generate_llama(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Generate using Meta Llama models on Bedrock."""
        body = json.dumps({
            "prompt": prompt,
            "max_gen_len": max_tokens,
            "temperature": temperature,
        })

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body["generation"]

    async def _generate_titan(
        self, prompt: str, temperature: float, max_tokens: int
    ) -> str:
        """Generate using Amazon Titan models on Bedrock."""
        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens,
                "temperature": temperature,
            },
        })

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body["results"][0]["outputText"]

    async def generate_stream(
        self,
        prompt: str,
        context: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response using AWS Bedrock."""
        full_prompt = self.format_rag_prompt(prompt, context)

        if "anthropic" in self.model_id.lower():
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {"role": "user", "content": full_prompt}
                ],
            })

            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=body,
                contentType="application/json",
                accept="application/json",
            )

            for event in response["body"]:
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk["type"] == "content_block_delta":
                    yield chunk["delta"].get("text", "")
        else:
            # For non-streaming models, yield the full response
            result = await self.generate(prompt, context, temperature, max_tokens)
            yield result
