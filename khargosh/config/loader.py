"""Load config.toml and turn it into a checked Config object (D43).

Two steps:
1. tomllib converts the TOML text to a plain Python dictionary.
2. Config.model_validate() checks the dictionary against the schema
   (schema.py) and returns a Config object.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from khargosh.config.schema import Config

# This folder: it holds config.toml and any other config files (for example config.gemini.toml).
CONFIG_DIR = Path(__file__).resolve().parent

# The repository root: the folder that contains .env.
# We do not use the current directory, because Khargosh works in YOUR project
# folder, and that folder does not contain Khargosh's files.
REPO_ROOT = CONFIG_DIR.parent.parent


def load_config(path: str | Path | None = None) -> Config:
    """Load a config file. The default is config.toml in this folder.

    The KHARGOSH_CONFIG environment variable can name another file. A plain file
    name, for example "config.gemini.toml", is looked up in this folder.
    """
    config_path = Path(path or os.environ.get("KHARGOSH_CONFIG") or CONFIG_DIR / "config.toml")
    if not config_path.is_absolute() and not config_path.exists():
        config_path = CONFIG_DIR / config_path

    with config_path.open("rb") as file:
        data = tomllib.load(file)  # step 1: TOML text -> dictionary
    return Config.model_validate(data)  # step 2: dictionary -> checked Config object
