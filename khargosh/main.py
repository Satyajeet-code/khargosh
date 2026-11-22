"""The terminal interface: the OUTER loop (D6, D28).

`TerminalApp` is the only class that reads the keyboard and prints for the user.
It builds the parts (model client, tools, agent loop) and connects them.

Note on input(): input() blocks the program while it waits for you. That is
acceptable in version 1, because nothing else must run while you type (D36).
The message queue (R23, D31) will change this with prompt_toolkit.

Ctrl+C stops Khargosh. The history is only in memory (D10), so the session ends.
"""

from __future__ import annotations

import asyncio
import os
import signal
import uuid

from dotenv import load_dotenv

from khargosh import observability
from khargosh.config import REPO_ROOT, Config, load_config
from khargosh.loop import AgentLoop
from khargosh.model import ModelClient, ModelError
from khargosh.prompts import build_system_prompt
from khargosh.schemas import StopReason, TurnResult
from khargosh.tool_handle import ToolRunner


class TerminalApp:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.session_id = uuid.uuid4().hex  # groups the turns of this session in Langfuse

    async def run(self) -> None:
        tracing = observability.init(self.config.observability.enabled)  # before the first traced call
        agent = AgentLoop(
            ModelClient(self.config.models.primary),
            ToolRunner(self.config.tools, show=self.show, approve=self.approve),
            system_prompt=build_system_prompt(os.getcwd()),
            max_steps=self.config.agent.max_steps,
            show=self.show,
        )

        print(f"Khargosh | model: {self.config.models.primary.model} | tracing: {'on' if tracing else 'off'}")
        print(f"Working directory: {os.getcwd()}")
        print("Type /exit to quit.")

        try:
            while True:
                try:
                    text = input("\nyou> ").strip()
                except EOFError:  # Ctrl+D
                    break
                if text in ("/exit", "/quit"):
                    break
                if not text:
                    continue

                try:
                    with observability.session(self.session_id):
                        result = await agent.run_turn(text)
                except ModelError as error:
                    print(f"\n[model error] {error}")
                    continue

                print(f"\nkhargosh> {result.text}")
                print(self.summary(result))
        finally:
            observability.shutdown()

    @staticmethod
    def show(text: str) -> None:
        print(f"  {text}".replace("\n", "\n  "))

    @staticmethod
    def approve(description: str) -> bool:
        print(f"\n  {description}")
        answer = input("  Run this? [y/n] ").strip().lower()
        return answer in ("y", "yes")

    @staticmethod
    def summary(result: TurnResult) -> str:
        cost = "unknown" if result.cost_usd is None else f"${result.cost_usd:.4f}"
        line = f"  [{result.steps} step(s) | {result.input_tokens} in / {result.output_tokens} out tokens | cost {cost}]"
        if result.stop == StopReason.LENGTH:
            line += "\n  [warning: the answer was cut at max_tokens]"
        return line


def main() -> None:
    load_dotenv(REPO_ROOT / ".env", override=True)
    app = TerminalApp(load_config())
    try:
        asyncio.run(_run(app))
    except KeyboardInterrupt:
        print("\nStopped.")


async def _run(app: TerminalApp) -> None:
    # asyncio.run() installs its own Ctrl+C handler. That handler only cancels the
    # async task, so it does not interrupt a blocking input(). The default handler
    # raises KeyboardInterrupt at once, also while input() waits.
    signal.signal(signal.SIGINT, signal.default_int_handler)
    await app.run()
