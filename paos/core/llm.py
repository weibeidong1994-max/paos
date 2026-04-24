import logging
from typing import Any

from openai import AsyncOpenAI, OpenAI

from paos.config.settings import settings
from paos.core.fallback import queue_request

logger = logging.getLogger(__name__)


class LLMClient:
    """统一 LLM 客户端封装，当前支持 OpenAI 兼容 API

    所有参数均从配置中心读取，代码中无硬编码。
    当外部 LLM 不可用时，支持 Agent Fallback 机制。
    """

    def __init__(self) -> None:
        self.provider = settings.llm.provider
        self.api_key = settings.llm.api_key
        self.model = settings.llm.model
        self.base_url = settings.llm.base_url
        self.temperature = settings.llm.temperature
        self.max_tokens = settings.llm.max_tokens
        self.fallback_enabled = settings.llm.fallback.enabled

        if self.provider == "openai":
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            self._async_client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def chat_completion(self, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        """同步调用 LLM"""
        if not self.api_key:
            logger.error("LLM API key is not configured.")
            if self.fallback_enabled:
                req_id = queue_request("chat_completion", system_prompt, user_content)
                return f"[FALLBACK_QUEUED:{req_id}]"
            return "[ERROR: LLM API key not configured. Set it in config/default.yaml or environment variable OPENAI_API_KEY.]"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.exception("LLM chat completion failed")
            if self.fallback_enabled:
                req_id = queue_request("chat_completion", system_prompt, user_content)
                return f"[FALLBACK_QUEUED:{req_id}]"
            return f"[ERROR: {e}]"

    async def achat_completion(self, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        """异步调用 LLM"""
        if not self.api_key:
            logger.error("LLM API key is not configured.")
            if self.fallback_enabled:
                req_id = queue_request("chat_completion", system_prompt, user_content)
                return f"[FALLBACK_QUEUED:{req_id}]"
            return "[ERROR: LLM API key not configured. Set it in config/default.yaml or environment variable OPENAI_API_KEY.]"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        try:
            response = await self._async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.exception("LLM async chat completion failed")
            if self.fallback_enabled:
                req_id = queue_request("chat_completion", system_prompt, user_content)
                return f"[FALLBACK_QUEUED:{req_id}]"
            return f"[ERROR: {e}]"


llm_client = LLMClient()
