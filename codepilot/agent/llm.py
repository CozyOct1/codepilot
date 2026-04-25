from __future__ import annotations

from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from codepilot.core.config import Settings


PROVIDER_DEFAULTS = {
    "openai": {"base_url": None, "model": "gpt-4o-mini"},
    "deepseek": {"base_url": "https://api.deepseek.com", "model": "deepseek-chat"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "openai_compatible": {"base_url": None, "model": "gpt-4o-mini"},
}


@dataclass(frozen=True)
class LLMClient:
    provider: str
    model: str
    available: bool
    reason: str | None = None

    def invoke_text(self, prompt: str, timeout: int = 30) -> str | None:
        if not self.available:
            return None
        settings = self._settings
        defaults = PROVIDER_DEFAULTS.get(self.provider, PROVIDER_DEFAULTS["openai"])
        llm = ChatOpenAI(
            model=self.model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url or defaults["base_url"],
            timeout=timeout,
        )
        message = llm.invoke(prompt)
        return str(message.content)

    @property
    def _settings(self) -> Settings:
        return object.__getattribute__(self, "settings")


def get_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm_provider
    if provider == "offline":
        return LLMClient(provider=provider, model=settings.llm_model, available=False, reason="offline mode")
    defaults = PROVIDER_DEFAULTS.get(provider)
    if defaults is None:
        return LLMClient(provider=provider, model=settings.llm_model, available=False, reason="unknown provider")
    if not settings.llm_api_key:
        return LLMClient(provider=provider, model=settings.llm_model, available=False, reason="missing api key")

    model = settings.llm_model
    if model == "gpt-4o-mini" and provider in {"deepseek", "qwen"}:
        model = str(defaults["model"])

    client = LLMClient(provider=provider, model=model, available=True)
    object.__setattr__(client, "settings", settings)
    return client
