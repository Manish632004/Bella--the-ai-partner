"""
BELLA - Configuration
Loads settings from .env and provides typed config for all modules.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
# __file__ = bella/core/config.py → .parent.parent.parent = project root
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")


class Config:
    """Central configuration — reads from environment variables."""

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M")

    # Server
    HOST: str = os.getenv("BELLA_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("BELLA_PORT", "8000"))

    # Paths
    PROJECT_ROOT: Path = _project_root
    TEMPLATES_DIR: Path = _project_root / "bella" / "templates"
    STATIC_DIR: Path = _project_root / "bella" / "static"

    # System prompt for Phase 1 (plain chat, no tools yet)
    SYSTEM_PROMPT: str = (
        "You are BELLA, a helpful, privacy-first personal AI assistant. "
        "You run entirely on the user's local hardware. Be concise, friendly, "
        "and direct. If you don't know something, say so honestly. "
        "Format responses in clean markdown when helpful."
    )


config = Config()
