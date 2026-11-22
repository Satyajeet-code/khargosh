"""The agent loop, component #2 (D6, D7, D9, D28).

`AgentLoop` is the INNER loop: it works on one user request until the model
stops asking for tools. It owns the message history of one agent, so a
subagent later is simply another AgentLoop with its own history.

It never calls input() or print(). It talks to the user only through the
functions that main.py gives it: `show` here, and `approve` inside the
ToolRunner. So an eval runner can use the same class later, with no user (R18).
"""

from __future__ import annotations

from typing import Any

from khargosh import observability
from khargosh.model import ModelClient
from khargosh.schemas import ShowFn, StopReason, TurnResult
from khargosh.tool_handle import ToolRunner
from khargosh.tools import TOOLS


class AgentLoop:
    def __init__(
        self,
        model: ModelClient,
        tools: ToolRunner,
        *,
        system_prompt: str,
        max_steps: int,
        show: ShowFn,
    ) -> None:
        self.model = model
        self.tools = tools
        self.max_steps = max_steps
        self.show = show
        # The full history. We only append to it, never change old items (Question E).
        self.messages: list[Any] = [{"role": "system", "content": system_prompt}]

    @observability.observe(name="agent-turn", as_type="agent")
    async def run_turn(self, user_text: str) -> TurnResult:
        """Add the user's message, then run the inner loop until the model is finished."""
        self.messages.append({"role": "user", "content": user_text})
        result = TurnResult()

        for step in range(1, self.max_steps + 1):
            result.steps = step
            reply = await self.model.complete(self.messages, TOOLS)

            # Rule from D15: append the FULL message, unchanged (it can carry thinking blocks).
            self.messages.append(reply.message)
            result.add_usage(reply)

            if reply.reasoning:
                self.show(f"[thinking] {self._shorten(reply.reasoning, 300)}")

            if reply.finish_reason == "content_filter":  # LiteLLM reports a model refusal like this
                result.text = reply.text or "The model declined this request."
                result.stop = StopReason.REFUSAL
                return result

            if not reply.tool_calls:  # no tool requests: the model is finished
                result.text = reply.text
                if reply.finish_reason == "length":
                    result.stop = StopReason.LENGTH  # the answer was cut at max_tokens
                return result

            if reply.text:
                self.show(reply.text)  # text that the model wrote before its tool calls

            # The model can ask for several tools in one reply. EVERY tool call needs a result.
            # Each result is one "tool" message. LiteLLM groups them into one user turn for Claude.
            for call in reply.tool_calls:
                output = await self.tools.execute(call)
                self.messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

        result.text = f"I stopped after {self.max_steps} steps (max_steps in config.toml). The task may not be finished."
        result.stop = StopReason.STEP_LIMIT
        return result

    @staticmethod
    def _shorten(text: str, limit: int) -> str:
        text = " ".join(text.split())
        return text if len(text) <= limit else text[: limit - 3] + "..."
