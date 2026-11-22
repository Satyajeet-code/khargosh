"""Tool definitions: the descriptions that the model reads (D8, D45).

The model cannot see our Python code. It sees only these dictionaries.
Each sentence in a description changes how the model uses the tool.

The code that runs each tool is in tool_handle.py.
To add a tool: add its definition here AND its handler in tool_handle.py.
"""

BASH = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Run a shell command on the user's computer and return its exit code and output "
            "(stdout and stderr together). Each call starts a new shell in the user's working "
            "directory, so `cd` does not carry over to the next call: use `cd dir && command`. "
            "The command cannot read input, so do not run interactive programs. "
            "The user must approve each command before it runs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to run."},
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
}

# The definitions that we send to the model with every request.
TOOLS = [BASH]
