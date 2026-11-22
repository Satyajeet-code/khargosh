"""Model client, component #1 (D14, D15).

This is the ONLY file that imports LiteLLM. LiteLLM translates our
OpenAI-format messages to each provider's native API.

Rule from D15: the caller appends the FULL assistant message that LiteLLM
returns. That message carries extra fields (`thinking_blocks` for Claude,
`provider_specific_fields` with thought signatures for Gemini). The
provider needs them back unchanged, or it returns a 400 error.
"""

from __future__ import annotations

import os
from typing import Any

os.environ.setdefault("LITELLM_MODE", "PRODUCTION")

import litellm 

from khargosh import observability
from khargosh.config import ModelSettings
from khargosh.schemas import ModelReply


class ModelError(Exception):
    """The model call failed, for example a wrong API key or a network error."""


class ModelClient:
    """Talks to one model, with one set of settings.

    The primary model and the secondary model (D12) are two ModelClient objects.
    """

    def __init__(self, settings: ModelSettings) -> None:
        self.settings = settings

    @observability.observe(name="llm-call", as_type="generation", capture_input=False, capture_output=False)
    async def complete(self, messages: list[Any], tools: list[dict[str, Any]]) -> ModelReply:
        """Send the full message history to the model once, and return its reply."""
        try:
            response = await litellm.acompletion(**self._build_request(messages, tools))
        except Exception as error:  # LiteLLM raises many error types; the loop only needs one
            raise ModelError(f"{type(error).__name__}: {error}") from error

        choice = response.choices[0]
        message = choice.message
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        cached_tokens = getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        input_cost, output_cost = self._cost(usage)

        observability.record_generation(
            model=self.settings.model,
            input=messages,
            output=message,
            # Langfuse wants separate buckets: "input" must not include the cached tokens.
            usage={"input": input_tokens - cached_tokens, "cache_read_input_tokens": cached_tokens, "output": output_tokens},
            cost=None if input_cost is None else {"input": input_cost, "output": output_cost},
        )

        return ModelReply(
            message=message,
            text=message.content or "",
            tool_calls=list(message.tool_calls or []),
            finish_reason=choice.finish_reason,
            reasoning=getattr(message, "reasoning_content", None),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=None if input_cost is None else input_cost + output_cost,
        )

    def _build_request(self, messages: list[Any], tools: list[dict[str, Any]]) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "tools": tools,
            "max_tokens": self.settings.max_tokens,
            "_skip_mcp_handler": True,
            **self.settings.extra,
        }
        if self.settings.reasoning_effort:
            # For Claude models with adaptive thinking, LiteLLM turns this into
            # thinking={"type": "adaptive", "display": "summarized"} plus output_config={"effort": ...}.
            request["reasoning_effort"] = self.settings.reasoning_effort
        if self.settings.api_base:
            request["api_base"] = self.settings.api_base
        return request

    def _cost(self, usage: Any) -> tuple[float | None, float | None]:
        """Return (input cost, output cost) in USD, from LiteLLM's price table."""
        if usage is None:
            return None, None
        try:
            input_cost, output_cost = litellm.cost_per_token(model=self.settings.model, usage_object=usage)
        except Exception:  # an unknown model, for example a local Ollama model, has no price
            return None, None
        return float(input_cost), float(output_cost)
