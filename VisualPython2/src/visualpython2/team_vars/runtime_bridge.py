"""Runtime bridge code generator for team-scoped variables.

Generates Python code that gets injected at the top of compiled scripts
to provide get_team_var() and set_team_var() functions. Team variables
are pre-resolved at dispatch time based on the executing user's role
permissions within the automation's team.
"""

from __future__ import annotations

import json
from typing import Any


def generate_team_vars_bridge_code(
    team_vars: dict[str, Any],
    writable_vars: list[str],
    sensitive_names: set[str] | None = None,
) -> str:
    """Generate Python code block for team variable access.

    Args:
        team_vars: Pre-resolved {name: value} dict (only vars user can read).
        writable_vars: List of variable names user has write access to.
        sensitive_names: Set of variable names marked as secret that
            should be wrapped in SensitiveValue (masks on str/repr/print).

    Returns:
        Python source code string to prepend to the compiled script.
    """
    vars_repr = json.dumps(team_vars, default=str)
    writable_repr = json.dumps(writable_vars)
    sensitive_repr = json.dumps(sorted(sensitive_names)) if sensitive_names else "[]"

    return (
        "# --- Team Variable Bridge ---\n"
        "import json as _json\n"
        "import os as _os\n"
        "from sensitive_value import SensitiveValue as _SV\n"
        f"_team_vars = _json.loads({repr(vars_repr)})\n"
        f"_team_writable = set(_json.loads({repr(writable_repr)}))\n"
        f"_team_sensitive = set(_json.loads({repr(sensitive_repr)}))\n"
        "for _k in _team_sensitive:\n"
        "    if _k in _team_vars and _team_vars[_k] is not None:\n"
        "        _team_vars[_k] = _SV(_team_vars[_k])\n"
        "\n"
        "try:\n"
        "    import redis as _redis\n"
        '    _team_redis = _redis.from_url(_os.environ.get("REDIS_URL", "redis://localhost:6379/0"))\n'
        "except ImportError:\n"
        "    _team_redis = None\n"
        "\n"
        "def get_team_var(name, default=None):\n"
        '    """Get a team variable. Returns default if not accessible."""\n'
        "    return _team_vars.get(name, default)\n"
        "\n"
        "def set_team_var(name, value):\n"
        '    """Set a team variable. Returns True on success."""\n'
        "    if name not in _team_writable:\n"
        '        raise PermissionError(f"No write access to team variable: {name}")\n'
        "    _raw = value.unwrap() if hasattr(value, 'unwrap') else value\n"
        "    _team_vars[name] = value\n"
        "    if _team_redis:\n"
        f"        _team_redis.hset('team_vars:' + _os.environ.get('SOAS_TEAM_ID', ''), name, _json.dumps(_raw, default=str))\n"
        "    return True\n"
        "# --- End Team Variable Bridge ---\n"
        "\n"
    )
