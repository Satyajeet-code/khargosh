# Khargosh (खरगोश)

A personal coding agent, similar to Claude Code. It is a learning project for agentic AI.
It is not for public use.

The design decisions and the reasons for them are in [decisions_taken.md](decisions_taken.md) and [decisions_rejected.md](decisions_rejected.md).

## Status: version 1

| Component | Status |
|---|---|
| Agent loop (#2) | Done: outer loop (you) and inner loop (the agent) |
| Model client (#1) | Done: LiteLLM, many providers |
| Tools | One tool: `bash`, with a y/n approval for each command. **No sandbox.** |
| Observability | Langfuse Cloud, with secret filtering |
| Memory, context management, subagents, evals | Not yet |

## Files

```
.env.example             the names of the API keys (copy to .env)
requirements.txt         exact versions of all packages
khargosh/
  main.py                TerminalApp: the outer loop, the only class that reads input and prints
  loop.py                AgentLoop: the inner loop (the agent loop); owns the message history
  model.py               ModelClient: the only file that imports LiteLLM
  tools.py               the tool definitions (what the model reads)
  tool_handle.py         ToolRunner: runs the tool calls (checks, y/n approval, the bash command)
  schemas.py             data shapes inside the program: ModelReply, TurnResult, StopReason
  prompts.py             the system prompt
  observability.py       the only file that imports Langfuse
  config/
    config.toml          your settings (models, max_steps, bash limits)
    schema.py            the shape of the settings (Pydantic classes)
    loader.py            reads config.toml and returns a checked Config object
```

To use another config file, put it in `khargosh/config/` and name it when you start:

```bash
KHARGOSH_CONFIG=config.gemini.toml python -m khargosh
```

## Set up

Use a separate conda environment only for this project (D18).

```bash
conda create -n khargosh python=3.12
conda activate khargosh
pip install -r requirements.txt
cp .env.example .env      # then add your keys to .env
```

## Run

From the repository folder:

```bash
python -m khargosh
```

The agent works in the folder where you start it. To use it on another project:

```bash
cd /path/to/other/project
PYTHONPATH=/path/to/this/repo python -m khargosh
```

Type `/exit` or press Ctrl+D to quit. Ctrl+C stops the agent at once.

## Safety

- The `bash` tool runs commands on your computer, as your user. Read each command before you approve it.
- The model sees all command output. Do not let it read files with secrets.
- Traces go to Langfuse Cloud. A filter removes text that looks like an API key, but it cannot find every secret.
