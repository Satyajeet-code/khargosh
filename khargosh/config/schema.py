"""The shape of the config file (D19, D43).

Each class matches one table in config.toml:

    (the whole file)     -> Config
    [agent]              -> AgentSettings
    [models.primary]     -> Models -> ModelSettings
    [models.secondary]   -> Models -> ModelSettings
    [tools.bash]         -> ToolSettings -> BashSettings
    [observability]      -> ObservabilitySettings

Pydantic checks the file against these classes at start-up. A misspelled key
or a wrong type stops the program with a clear error, instead of a strange
failure later. To add a setting, add a field here and a value in config.toml.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]


class _Strict(BaseModel):
    # "forbid" makes an unknown key an error, for example "max_step" instead of "max_steps".
    model_config = ConfigDict(extra="forbid")


class ModelSettings(_Strict):
    model: str  # LiteLLM model string, for example "anthropic/claude-opus-5-5"
    max_tokens: int = Field(default=16000, gt=0)
    reasoning_effort: ReasoningEffort | None = None
    api_base: str | None = None  # for Ollama, vLLM, or a proxy
    # Extra parameters, passed unchanged to litellm.acompletion (for example {"num_ctx": 32768}).
    extra: dict[str, Any] = Field(default_factory=dict)


class Models(_Strict):
    primary: ModelSettings
    secondary: ModelSettings | None = None  # for subagents later (D12)


class AgentSettings(_Strict):
    max_steps: int = Field(default=50, gt=0)


class BashSettings(_Strict):
    timeout_seconds: int = Field(default=120, gt=0)
    max_output_chars: int = Field(default=20000, ge=1000)


class ToolSettings(_Strict):
    bash: BashSettings = Field(default_factory=BashSettings)


class ObservabilitySettings(_Strict):
    enabled: bool = True


class Config(_Strict):
    agent: AgentSettings = Field(default_factory=AgentSettings)
    models: Models
    tools: ToolSettings = Field(default_factory=ToolSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
