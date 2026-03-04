"""Runtime bridge code generator for per-user secrets.

Generates Python code that gets injected at the top of compiled scripts
to provide get_user_secret() function. User secrets are pre-resolved and
decrypted at dispatch time based on the triggering user.
"""

from __future__ import annotations

import json


def generate_user_secrets_bridge_code(
    user_secrets: dict[str, str],
) -> str:
    """Generate Python code block for user secret access.

    Args:
        user_secrets: Pre-resolved {name: decrypted_value} dict.

    Returns:
        Python source code string to prepend to the compiled script.
    """
    secrets_repr = json.dumps(user_secrets, default=str)

    return (
        "# --- User Secrets Bridge ---\n"
        "import json as _json\n"
        f"_user_secrets = _json.loads({repr(secrets_repr)})\n"
        "\n"
        "def get_user_secret(name, default=None):\n"
        '    """Get a user secret by name. Returns default if not found."""\n'
        "    return _user_secrets.get(name, default)\n"
        "# --- End User Secrets Bridge ---\n"
        "\n"
    )
