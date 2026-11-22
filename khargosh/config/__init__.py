"""Configuration (D43).

    config.toml   your settings (data)
    schema.py     the shape of the settings (Pydantic classes)
    loader.py     reads config.toml and returns a checked Config object

Other modules import from here, for example:
    from khargosh.config import Config, load_config
"""

from khargosh.config.loader import CONFIG_DIR, REPO_ROOT, load_config
from khargosh.config.schema import (
    AgentSettings,
    BashSettings,
    Config,
    ModelSettings,
    Models,
    ObservabilitySettings,
    ToolSettings,
)

__all__ = [
    "CONFIG_DIR",
    "REPO_ROOT",
    "load_config",
    "AgentSettings",
    "BashSettings",
    "Config",
    "ModelSettings",
    "Models",
    "ObservabilitySettings",
    "ToolSettings",
]
