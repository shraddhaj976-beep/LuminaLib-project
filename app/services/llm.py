from abc import ABC, abstractmethod

import httpx

from app.core.config import settings


class LLMClient(ABC):
    @abstractmethod
    async def summarize(self, text: str) -> str: ...

    @abstractmethod
    async def generate_tags(self, text: str) -> list[str]: ...

    @abstractmethod
    async def aggregate_reviews(self, reviews: list[str], prompt: str | None = None) -> str: ...


class MockLLM(LLMClient):
    def __init__(self):
        self.base = settings.mock_llm_url

    async def summarize(self, text: str) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base}/summarize", json={"text": text})
            return r.json()["summary"]

    async def generate_tags(self, text: str) -> list[str]:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{self.base}/tags", json={"text": text})
            data = r.json()
            tags = data.get("tags")
            if isinstance(tags, list):
                return tags
            return ["general"]

    async def aggregate_reviews(self, reviews: list[str], prompt: str | None = None) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base}/aggregate",
                json={"reviews": reviews, "prompt": prompt},
            )
            return r.json()["analysis"]


def get_llm() -> LLMClient:
    if settings.llm_provider == "mock":
        return MockLLM()
    # else implement real LLM adapter (ollama/openai)
    raise NotImplementedError("LLM provider not implemented")
