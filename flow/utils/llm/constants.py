"""Constants for LLM module.

Centralizes magic numbers, default values, and configuration constants
for better maintainability and documentation.
"""

# =============================================================================
# Prompt Processing
# =============================================================================

# Maximum prompt length (chars) for sanitization.
# Most LLMs support 8k-32k context; 8000 is a safe default that works
# across all providers while leaving room for responses.
MAX_PROMPT_LENGTH = 8000

# =============================================================================
# Timeout Settings (seconds)
# =============================================================================

# Default timeout for cloud API providers (Gemini, OpenAI)
# Balance between user patience and allowing for network latency.
DEFAULT_API_TIMEOUT = 30.0

# Default timeout for Ollama (local inference)
# Higher timeout because local models can be slower, especially
# on first request when loading into memory.
OLLAMA_TIMEOUT = 120.0

# Validation timeout for onboarding wizard
# Short timeout for quick feedback during credential testing.
VALIDATION_TIMEOUT = 10.0

# =============================================================================
# Default Models
# =============================================================================

# Default models for each provider.
# These are stable, cost-effective choices for GTD task processing.
DEFAULT_MODELS = {
    "gemini": "gemini-3-flash-preview",  # Fast, capable, free tier available
    "openai": "gpt-4o-mini",  # Cost-effective, good for structured output
    "ollama": "llama3.2",  # Popular open model, runs well locally
}

# =============================================================================
# HTTP Client Settings
# =============================================================================

# Connection pool size for async HTTP clients
# Kept small since Flow typically makes sequential LLM requests.
HTTP_MAX_CONNECTIONS = 10

# Keep-alive timeout for connection reuse (seconds)
HTTP_KEEPALIVE_TIMEOUT = 30.0
