"""Run the tool calls that the model makes (D27, D30, D37, D45, D46).

`ToolRunner` holds the three things that every tool needs: the tool settings,
`show` (print a progress line), and `approve` (ask the user y/n). They are
stored one time, so the methods do not pass them along.

The order for each tool call:
    execute()       find the handler by the tool's name, convert the JSON arguments to a dictionary
    handle_bash()   check the arguments, ask the user y/n, run the command
    run_bash()      run the command with a time limit; stop it and its child processes if needed

No method here raises for a bad tool call. The model must get a result for
EVERY tool call, so a problem becomes an "ERROR: ..." result that the model can
read and fix. (The OpenAI message format has no error flag, D37.)

Safety in version 1:
- There is no sandbox. Commands run on your computer, as your user.
- You approve each command before it runs.
- A command cannot read from the keyboard (stdin is empty), so it cannot hang on a question.
- A command that runs too long is stopped.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
from typing import Any

from khargosh import observability
from khargosh.config import ToolSettings
from khargosh.schemas import ApproveFn, ShowFn
from khargosh.tools import TOOLS


class ToolRunner:
    def __init__(self, settings: ToolSettings, show: ShowFn, approve: ApproveFn) -> None:
        self.settings = settings
        self.show = show
        self.approve = approve
        # Tool name -> the method that handles it. The names must match the definitions in tools.py.
        self._handlers = {
            "bash": self.handle_bash,
        }
        self._check_handlers()  # stops at start-up if tools.py and this file do not match

    async def execute(self, call: Any) -> str:
        """Run one tool call and return the text for the model."""
        name = call.function.name  # a plain string, for example "bash"
        handler = self._handlers.get(name)
        if handler is None:
            return f"ERROR: unknown tool {name!r}. Available tools: {', '.join(self._handlers)}."

        # call.function.arguments is a STRING that contains JSON, for example '{"command": "ls -la"}'.
        try:
            arguments = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError as error:
            return f"ERROR: the tool arguments are not valid JSON ({error})."
        if not isinstance(arguments, dict):
            return "ERROR: the tool arguments must be a JSON object."

        return await handler(arguments)

    async def handle_bash(self, arguments: dict[str, Any]) -> str:
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            return "ERROR: 'command' must be a non-empty string."

        if not self.approve(f"$ {command}"):  # D30
            self.show("[declined]")
            return "The user declined this action. Do not try it again. Ask the user how to continue."

        output = await self.run_bash(command)
        self.show(_preview(output))
        return output

    @observability.observe(name="bash", as_type="tool")
    async def run_bash(self, command: str) -> str:
        timeout_seconds = self.settings.bash.timeout_seconds
        process = await asyncio.create_subprocess_shell(
            command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            # A new process group, so we can stop the command AND every child process it starts.
            start_new_session=True,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            _kill(process)
            await process.wait()
            return f"ERROR: the command did not finish in {timeout_seconds} seconds and was stopped."
        except asyncio.CancelledError:  # Ctrl+C while the command runs
            _kill(process)
            raise

        text = stdout.decode("utf-8", errors="replace")
        return f"exit code: {process.returncode}\n{_truncate(text, self.settings.bash.max_output_chars)}"

    def _check_handlers(self) -> None:
        """Stop if a definition has no handler, or a handler has no definition."""
        defined = {tool["function"]["name"] for tool in TOOLS}
        missing = defined - self._handlers.keys()
        extra = self._handlers.keys() - defined
        if missing or extra:
            raise RuntimeError(f"tools.py and tool_handle.py do not match. No handler: {missing}. No definition: {extra}.")


def _kill(process: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)  # Linux and macOS
    except ProcessLookupError:
        pass  # the process already stopped


def _truncate(text: str, limit: int) -> str:
    """Keep the start and the end. Errors are often at the end of the output."""
    if len(text) <= limit:
        return text
    half = limit // 2
    omitted = len(text) - 2 * half
    return f"{text[:half]}\n\n... [{omitted} characters omitted] ...\n\n{text[-half:]}"


def _preview(output: str, lines: int = 8) -> str:
    """A short view of the output for the terminal. The model gets the full output."""
    all_lines = output.splitlines()
    shown = "\n".join(all_lines[:lines])
    if len(all_lines) > lines:
        shown += f"\n... ({len(all_lines) - lines} more lines)"
    return shown
