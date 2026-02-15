"""Configuration manager for LLM providers.

Reads configuration from ~/.flow/config.toml and environment variables.
Environment variables take precedence over config file values.
"""

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Mapping, Optional, cast

# Provider type alias
ProviderType = Literal["gemini", "openai", "ollama"]

# Default config file location
DEFAULT_CONFIG_PATH = Path.home() / ".flow" / "config.toml"


@dataclass
class GeminiConfig:
    """Configuration for Gemini provider."""

    api_key: str = ""
    default_model: str = "gemini-2.0-flash"
    timeout: float = 30.0  # Request timeout in seconds


@dataclass
class OpenAIConfig:
    """Configuration for OpenAI provider."""

    api_key: str = ""
    default_model: str = "gpt-4o-mini"
    base_url: str = ""  # Optional, for Azure/custom endpoints
    timeout: float = 30.0  # Request timeout in seconds


@dataclass
class OllamaConfig:
    """Configuration for Ollama provider."""

    base_url: str = "http://localhost:11434"
    default_model: str = "llama3.2"
    timeout: float = 120.0  # Request timeout in seconds (higher for local models)


@dataclass
class LLMConfig:
    """Main LLM configuration."""

    provider: ProviderType = "gemini"
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)


@dataclass
class FirstRunState:
    """First-run onboarding handoff state."""

    first_value_pending: bool
    first_value_completed_at: Optional[str]


def _load_toml(path: Path) -> dict:
    """Load and parse a TOML configuration file.

    Uses tomllib (Python 3.11+) or falls back to tomli for older versions.
    Gracefully handles missing files and missing TOML libraries.

    Args:
        path: Path to the TOML file.

    Returns:
        Parsed TOML content as dict, or empty dict if file doesn't exist
        or TOML library is unavailable.
    """
    if not path.exists():
        return {}

    try:
        # Python 3.11+ has tomllib in stdlib
        import tomllib

        with open(path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        # Fall back to tomli for older Python
        try:
            import tomli

            with open(path, "rb") as f:
                return tomli.load(f)
        except ImportError:
            # No TOML library available, return empty
            return {}


def load_config(config_path: Optional[Path] = None) -> LLMConfig:
    """Load LLM configuration from file and environment.

    Configuration sources (in order of precedence):
    1. Environment variables (FLOW_*)
    2. Config file (~/.flow/config.toml)
    3. Default values

    Args:
        config_path: Optional path to config file. Defaults to ~/.flow/config.toml.

    Returns:
        LLMConfig with merged configuration.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    file_config = _load_toml(path)

    # Extract LLM section
    llm_config = file_config.get("llm", {})

    # Build configuration with defaults
    config = LLMConfig()

    # Provider selection
    config.provider = _get_provider_type(
        os.environ.get("FLOW_LLM_PROVIDER") or llm_config.get("provider", "gemini")
    )

    # Gemini config
    gemini_section = llm_config.get("gemini", {})
    config.gemini = GeminiConfig(
        api_key=(
            os.environ.get("FLOW_GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or gemini_section.get("api_key", "")
        ),
        default_model=(
            os.environ.get("FLOW_GEMINI_MODEL")
            or gemini_section.get("default_model", "gemini-2.0-flash")
        ),
        timeout=float(
            os.environ.get("FLOW_GEMINI_TIMEOUT") or gemini_section.get("timeout", 30.0)
        ),
    )

    # OpenAI config
    openai_section = llm_config.get("openai", {})
    config.openai = OpenAIConfig(
        api_key=(
            os.environ.get("FLOW_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or openai_section.get("api_key", "")
        ),
        default_model=(
            os.environ.get("FLOW_OPENAI_MODEL")
            or openai_section.get("default_model", "gpt-4o-mini")
        ),
        base_url=(
            os.environ.get("FLOW_OPENAI_BASE_URL") or openai_section.get("base_url", "")
        ),
        timeout=float(
            os.environ.get("FLOW_OPENAI_TIMEOUT") or openai_section.get("timeout", 30.0)
        ),
    )

    # Ollama config
    ollama_section = llm_config.get("ollama", {})
    config.ollama = OllamaConfig(
        base_url=(
            os.environ.get("FLOW_OLLAMA_BASE_URL")
            or ollama_section.get("base_url", "http://localhost:11434")
        ),
        default_model=(
            os.environ.get("FLOW_OLLAMA_MODEL")
            or ollama_section.get("default_model", "llama3.2")
        ),
        timeout=float(
            os.environ.get("FLOW_OLLAMA_TIMEOUT")
            or ollama_section.get("timeout", 120.0)
        ),
    )

    return config


def _get_provider_type(value: str) -> ProviderType:
    """Validate and normalize a provider type string.

    Args:
        value: Provider name string (case-insensitive).

    Returns:
        Validated ProviderType literal. Defaults to "gemini"
        if value is not a valid provider.
    """
    value = value.lower().strip()
    if value in ("gemini", "openai", "ollama"):
        return cast(ProviderType, value)
    # Default to gemini for invalid values
    return "gemini"


def get_example_config() -> str:
    """Return example config.toml content with documented options.

    Useful for creating an initial config file or displaying
    configuration help to users.

    Returns:
        Multi-line string containing a complete example TOML configuration
        with comments explaining each option.
    """
    return """# Flow GTD - LLM Configuration
# Place this file at ~/.flow/config.toml

[llm]
# Available providers: "gemini", "openai", "ollama"
provider = "gemini"

[llm.gemini]
# API key (or set FLOW_GEMINI_API_KEY / GOOGLE_API_KEY env var)
api_key = ""
default_model = "gemini-3-flash-preview"
timeout = 30.0  # Request timeout in seconds

[llm.openai]
# API key (or set FLOW_OPENAI_API_KEY / OPENAI_API_KEY env var)
api_key = ""
default_model = "gpt-4o-mini"
timeout = 30.0  # Request timeout in seconds
# Optional: custom base URL for Azure OpenAI or other compatible endpoints
# base_url = "https://your-resource.openai.azure.com/"

[llm.ollama]
# Local Ollama server URL
base_url = "http://localhost:11434"
default_model = "llama3.2"
timeout = 120.0  # Higher timeout for local models
"""


def is_onboarding_completed(config_path: Optional[Path] = None) -> bool:
    """Check if onboarding has been completed.

    Args:
        config_path: Optional path to config file. Defaults to ~/.flow/config.toml.

    Returns:
        True if config file exists and onboarding_completed is True.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return False

    file_config = _load_toml(path)
    return file_config.get("onboarding_completed", False)


def save_config(
    provider: ProviderType,
    credentials: Mapping[str, str],
    config_path: Optional[Path] = None,
    onboarding_completed: bool = True,
    first_value_pending: bool = True,
    first_value_completed_at: str = "",
) -> None:
    """Write configuration to TOML file with secure permissions.

    Args:
        provider: The LLM provider type ("gemini", "openai", "ollama").
        credentials: Provider-specific credentials dict.
            For gemini/openai: {"api_key": "..."}
            For ollama: {"base_url": "..."}
        config_path: Optional path to config file. Defaults to ~/.flow/config.toml.
        onboarding_completed: Whether to mark onboarding as completed.
        first_value_pending: Whether first capture value is still pending.
        first_value_completed_at: ISO timestamp when first capture was completed.
    """
    path = config_path or DEFAULT_CONFIG_PATH

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build TOML content
    lines = [
        "# Flow GTD - LLM Configuration",
        "# Generated by onboarding wizard",
        "",
        f"onboarding_completed = {str(onboarding_completed).lower()}",
        f"first_value_pending = {str(first_value_pending).lower()}",
        f'first_value_completed_at = "{first_value_completed_at}"',
        "",
        "[llm]",
        f'provider = "{provider}"',
        "",
    ]

    # Gemini section
    gemini_api_key = credentials.get("api_key", "") if provider == "gemini" else ""
    lines.extend(
        [
            "[llm.gemini]",
            f'api_key = "{gemini_api_key}"',
            'default_model = "gemini-2.0-flash"',
            "timeout = 30.0",
            "",
        ]
    )

    # OpenAI section
    openai_api_key = credentials.get("api_key", "") if provider == "openai" else ""
    openai_base_url = credentials.get("base_url", "") if provider == "openai" else ""
    lines.extend(
        [
            "[llm.openai]",
            f'api_key = "{openai_api_key}"',
            'default_model = "gpt-4o-mini"',
            f'base_url = "{openai_base_url}"',
            "timeout = 30.0",
            "",
        ]
    )

    # Ollama section
    ollama_base_url = (
        credentials.get("base_url", "http://localhost:11434")
        if provider == "ollama"
        else "http://localhost:11434"
    )
    lines.extend(
        [
            "[llm.ollama]",
            f'base_url = "{ollama_base_url}"',
            'default_model = "llama3.2"',
            "timeout = 120.0",
        ]
    )

    # Write file
    content = "\n".join(lines)
    path.write_text(content)

    # Set secure permissions (owner read/write only)
    os.chmod(path, 0o600)


def _upsert_top_level_key(content: str, key: str, value_repr: str) -> str:
    """Set a top-level TOML key without rewriting section contents."""
    section_match = re.search(r"(?m)^\[", content)
    if section_match:
        top_level_block = content[: section_match.start()]
        section_block = content[section_match.start() :]
    else:
        top_level_block = content
        section_block = ""

    key_pattern = re.compile(rf"(?m)^{re.escape(key)}\s*=.*$")
    replacement = f"{key} = {value_repr}"
    if key_pattern.search(top_level_block):
        updated_top_level = key_pattern.sub(replacement, top_level_block, count=1)
        return f"{updated_top_level}{section_block}"

    joiner = "" if not top_level_block or top_level_block.endswith("\n") else "\n"
    return f"{top_level_block}{joiner}{replacement}\n{section_block}"


def read_first_run_state(config_path: Optional[Path] = None) -> FirstRunState:
    """Read persisted first-run state from config."""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return FirstRunState(first_value_pending=False, first_value_completed_at=None)

    file_config = _load_toml(path)
    pending_value = file_config.get("first_value_pending", False)
    completed_at_value = file_config.get("first_value_completed_at", "")

    first_value_pending = pending_value if isinstance(pending_value, bool) else False
    first_value_completed_at = (
        completed_at_value if isinstance(completed_at_value, str) and completed_at_value else None
    )

    return FirstRunState(
        first_value_pending=first_value_pending,
        first_value_completed_at=first_value_completed_at,
    )


def mark_first_value_completed(config_path: Optional[Path] = None) -> None:
    """Mark first-run value capture as complete."""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return

    content = path.read_text()
    timestamp = datetime.now(timezone.utc).isoformat()
    content = _upsert_top_level_key(content, "first_value_pending", "false")
    content = _upsert_top_level_key(
        content,
        "first_value_completed_at",
        f'"{timestamp}"',
    )
    path.write_text(content)
    os.chmod(path, 0o600)
