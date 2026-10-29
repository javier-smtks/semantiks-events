"""Semantiks CUA — chat with an agent that controls your laptop.

Purpose: give a LangSmith-traced OpenAI agent a cross-OS execution layer via
the open-source [trycua/cua](https://github.com/trycua/cua) Driver. You type
"open Mail and tell me unread count"; the agent clicks, types, and reports
back — on macOS, Windows, or Linux, without a VM.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root as early as possible so every module that
# reads os.environ at import time sees the user's keys.
load_dotenv(Path.cwd() / ".env")

__version__ = "0.1.0"

from .cli import main  # noqa: E402

__all__ = ["main", "__version__"]
