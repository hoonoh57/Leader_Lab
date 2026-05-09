# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def load_env_file(env_path: Optional[str] = None) -> Dict[str, str]:
    """Load simple KEY=VALUE .env file into os.environ.

    Rules:
    - Empty lines and comments are ignored.
    - Existing process env values are overwritten by the file values.
    - Quotes around values are stripped.
    """
    path_text = env_path or os.environ.get("LEADER_LAB_ENV", ".env")
    path = Path(path_text)
    result: Dict[str, str] = {}

    if not path.exists():
        return result

    text = path.read_text(encoding="utf-8-sig")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if len(value) >= 2:
            if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

        result[key] = value
        os.environ[key] = value

    return result


def env_str(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_int(key: str, default: int) -> int:
    value = os.environ.get(key)
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def env_float(key: str, default: float) -> float:
    value = os.environ.get(key)
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default
