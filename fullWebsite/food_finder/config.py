"""Local environment configuration shared by the application modules."""

import os
from pathlib import Path


def _load_local_env() -> None:
    """Load simple KEY=VALUE entries without overriding deployed environment values."""
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


# Resolve from this file so `python fullWebsite/app.py` and `cd fullWebsite &&
# python app.py` both load the same untracked configuration file.
_load_local_env()
