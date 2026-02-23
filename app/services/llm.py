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


class OllamaLLM(LLMClient):
    def __init__(self):
        self.base = settings.ollama_url.rstrip("/")
        self.model = settings.ollama_model

    async def _generate(self, prompt: str) -> str:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip()

    async def summarize(self, text: str) -> str:
        prompt = (
            "Summarize the following book content in 5-7 sentences. "
            "Focus on key themes and takeaways.\n\n"
            f"{text}"
        )
        return await self._generate(prompt)

    async def generate_tags(self, text: str) -> list[str]:
        prompt = (
            "Extract 3-8 concise topic tags from the following content. "
            "Return tags as a comma-separated list, no extra text.\n\n"
            f"{text}"
        )
        raw = await self._generate(prompt)
        tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        return tags or ["general"]

    async def aggregate_reviews(self, reviews: list[str], prompt: str | None = None) -> str:
        if not prompt:
            prompt = (
                "Aggregate the following reviews into a concise consensus summary "
                "covering overall sentiment, common praise, and common criticisms."
            )
        full_prompt = prompt + "\n\n" + "\n".join([f"- {r}" for r in reviews])
        return await self._generate(full_prompt)


def get_llm() -> LLMClient:
    if settings.llm_provider == "mock":
        return MockLLM()
    if settings.llm_provider == "ollama":
        return OllamaLLM()
    raise NotImplementedError("LLM provider not implemented")
