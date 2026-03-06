"""Runtime bridge code generator for SOAS application-level variables.

Generates Python code that gets injected at the top of compiled scripts
to provide get_soas_var() and set_soas_var() functions. SOAS variables
are pre-resolved at dispatch time based on the executing user's role
permissions, so the bridge code receives a manifest of allowed variables.
"""

from __future__ import annotations

import json
from typing import Any


def generate_soas_bridge_code(
    soas_vars: dict[str, Any],
    writable_vars: list[str],
    sensitive_names: set[str] | None = None,
) -> str:
    """Generate Python code block for SOAS variable access.

    Args:
        soas_vars: Pre-resolved {name: value} dict (only vars user can read).
        writable_vars: List of variable names user has write access to.
        sensitive_names: Set of variable names (typically shared secrets) that
            should be wrapped in SensitiveValue (masks on str/repr/print).

    Returns:
        Python source code string to prepend to the compiled script.
    """
    # Serialize the vars dict as a Python literal
    vars_repr = json.dumps(soas_vars, default=str)
    writable_repr = json.dumps(writable_vars)
    sensitive_repr = json.dumps(sorted(sensitive_names)) if sensitive_names else "[]"

    return (
        "# --- SOAS Variable Bridge ---\n"
        "import json as _json\n"
        "import os as _os\n"
        "from sensitive_value import SensitiveValue as _SV\n"
        f"_soas_vars = _json.loads({repr(vars_repr)})\n"
        f"_soas_writable = set(_json.loads({repr(writable_repr)}))\n"
        f"_soas_sensitive = set(_json.loads({repr(sensitive_repr)}))\n"
        "for _k in _soas_sensitive:\n"
        "    if _k in _soas_vars and _soas_vars[_k] is not None:\n"
        "        _soas_vars[_k] = _SV(_soas_vars[_k])\n"
        "\n"
        "try:\n"
        "    import redis as _redis\n"
        '    _soas_redis = _redis.from_url(_os.environ.get("REDIS_URL", "redis://localhost:6379/0"))\n'
        "except ImportError:\n"
        "    _soas_redis = None\n"
        "\n"
        "def get_soas_var(name, default=None):\n"
        '    """Get a SOAS application variable. Returns default if not accessible."""\n'
        "    return _soas_vars.get(name, default)\n"
        "\n"
        "def set_soas_var(name, value):\n"
        '    """Set a SOAS application variable. Returns True on success."""\n'
        "    if name not in _soas_writable:\n"
        '        raise PermissionError(f"No write access to SOAS variable: {name}")\n'
        "    _raw = value.unwrap() if hasattr(value, 'unwrap') else value\n"
        "    _soas_vars[name] = value\n"
        "    if _soas_redis:\n"
        '        _soas_redis.hset("soas_vars:all", name, _json.dumps(_raw, default=str))\n'
        "    return True\n"
        "# --- End SOAS Variable Bridge ---\n"
        "\n"
    )
