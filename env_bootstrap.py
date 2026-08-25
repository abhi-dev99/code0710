"""
Environment bootstrap — single source of truth for loading .env.

Every entry point (API, tests, training scripts) calls load_env() before
constructing LLMClient / touching settings. Idempotent: real environment
variables always win over .env values (setdefault).
"""
from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_LOADED = False


def load_env() -> bool:
    """Load KEY=VALUE pairs from <repo>/.env into os.environ (setdefault).
    Returns True if a .env file was found."""
    global _LOADED
    if _LOADED:
        return True
    env_path = _ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    _LOADED = True
    return True
