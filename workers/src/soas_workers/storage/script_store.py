"""Read/write automation scripts on disk."""

import hashlib
import os

from soas_workers.config import config


def get_script_full_path(script_filename: str) -> str:
    return os.path.join(config.AUTOMATIONS_DIR, script_filename)


def script_exists(script_filename: str) -> bool:
    return os.path.exists(get_script_full_path(script_filename))


def read_script(script_filename: str) -> str:
    with open(get_script_full_path(script_filename)) as f:
        return f.read()


def write_script(script_filename: str, content: str) -> str:
    """Write script and return its SHA-256 hash."""
    os.makedirs(config.AUTOMATIONS_DIR, exist_ok=True)
    path = get_script_full_path(script_filename)
    with open(path, "w") as f:
        f.write(content)
    return hashlib.sha256(content.encode()).hexdigest()
