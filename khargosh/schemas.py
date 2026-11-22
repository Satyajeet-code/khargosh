"""Data shapes that pass between the parts of Khargosh.

These are plain dataclasses, not Pydantic models. Pydantic is for data that
comes from OUTSIDE and must be checked (config.toml, in config.py). These
objects are made inside our own code, so they need no checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

# The two ways the agent talks to the user (D28). main.py supplies them.
ShowFn = Callable[[str], None]  # print a progress line
ApproveFn = Callable[[str], bool]  # ask the user to approve an action; True means yes


class StopReason(StrEnum):
    """Why the agent loop ended a turn."""

    DONE = "done"  # the model replied with no tool calls
    STEP_LIMIT = "step_limit"  # max_steps was reached (D9)
    LENGTH = "length"  # the answer was cut at max_tokens
    REFUSAL = "refusal"  # the model declined the request


@dataclass
class ModelReply:
    """One reply from the model, made by ModelClient.complete()."""

    message: Any  # the full assistant message: append it to the history unchanged (D15)
    text: str
    tool_calls: list[Any]
    finish_reason: str | None  # "stop", "tool_calls", "length", "content_filter", ...
    reasoning: str | None  # a readable summary of the model's thinking, if the provider returns one
    input_tokens: int
    output_tokens: int
    cost_usd: float | None  # None when LiteLLM does not know the price of the model


@dataclass
class TurnResult:
    """The result of one user turn, made by AgentLoop.run_turn()."""

    text: str = ""  # the final answer for the user
    steps: int = 0  # how many model calls this turn used
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = 0.0  # None if the price of any call was unknown
    stop: StopReason = StopReason.DONE

    def add_usage(self, reply: ModelReply) -> None:
        """Add the tokens and the cost of one model call to the totals of this turn."""
        self.input_tokens += reply.input_tokens
        self.output_tokens += reply.output_tokens
        if self.cost_usd is None or reply.cost_usd is None:
            self.cost_usd = None
        else:
            self.cost_usd += reply.cost_usd
