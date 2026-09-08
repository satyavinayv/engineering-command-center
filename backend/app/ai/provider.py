"""
AIProvider abstraction (spec section 32 - "AI should be replaceable").
The dashboard works fully with AI disabled or misconfigured; every
caller of get_ai_provider() must handle a None return by simply not
showing AI content, never by blocking on it or erroring.
"""
from abc import ABC, abstractmethod

import httpx

from app.config import settings


class AIProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...


class MockAIProvider(AIProvider):
    """Deterministic stand-in for local dev/testing without an API key
    - lets the whole AI pipeline (caching, endpoints, frontend) be
    exercised without ever calling a real model."""

    def generate(self, prompt: str) -> str:
        return (
            "[Mock AI provider - set AI_PROVIDER=openai and OPENAI_API_KEY "
            "in .env for a real summary] Based on your current action "
            "items, review the list below and tackle P0s first."
        )


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> str:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


def get_ai_provider() -> AIProvider | None:
    """Returns None if AI is disabled or not configured - callers must
    treat that as "skip the AI section", not an error."""
    if not settings.ai_enabled:
        return None
    if settings.ai_provider == "openai" and settings.openai_api_key:
        return OpenAIProvider(settings.openai_api_key, settings.openai_model)
    return MockAIProvider()