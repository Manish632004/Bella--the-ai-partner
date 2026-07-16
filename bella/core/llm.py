"""
BELLA - Ollama LLM Client
Handles all communication with the local Ollama instance.
Uses httpx for async HTTP to Ollama's OpenAI-compatible API.
"""

import httpx
from typing import AsyncGenerator
from bella.core.config import config


class OllamaClient:
    """Async client for Ollama's /api/chat endpoint."""

    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL
        self.model = config.OLLAMA_MODEL
        # Long timeout for CPU inference — 14B on CPU can take time
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(connect=10.0, read=300.0, write=10.0, pool=10.0),
        )

    async def check_health(self) -> bool:
        """Verify Ollama is running and the model is available."""
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            available = [m["name"] for m in models]
            if self.model in available or any(self.model in n for n in available):
                return True
            print(f"[BELLA] Model '{self.model}' not found. Available: {available}")
            return False
        except httpx.HTTPError as e:
            print(f"[BELLA] Ollama health check failed: {e}")
            return False

    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> str:
        """
        Send a chat completion request to Ollama (non-streaming).
        
        Args:
            messages: List of {"role": "...", "content": "..."} dicts.
            stream: If False, returns the full response. Streaming handled separately.
        
        Returns:
            The assistant's response text.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": 4096,       # Context window
                "temperature": 0.7,
                "top_p": 0.9,
            },
        }

        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    async def chat_stream(
        self,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion from Ollama, yielding tokens as they arrive.
        This keeps the UI responsive while the CPU crunches through 14B params.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": 4096,
                "temperature": 0.7,
                "top_p": 0.9,
            },
        }

        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                import json
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done", False):
                    return

    async def close(self):
        """Clean up the HTTP client."""
        await self._client.aclose()


# Module-level singleton
llm = OllamaClient()
