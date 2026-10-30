#!/usr/bin/env python3
"""Fill in the secrets backend/.env needs, without touching anything you already set.

Creates backend/.env from .env.example if it does not exist, then generates a value for each
secret that is empty or still a placeholder. Existing values (your API keys!) are never changed,
and no secret is ever printed.
"""

from __future__ import annotations

import base64
import os
import re
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # the repository root
TARGET = ROOT / "backend" / ".env"  # the git-ignored file the API reads
EXAMPLE = ROOT / ".env.example"  # the template with every setting documented

# Each secret and how to generate a fresh value for it.
GENERATORS = {
    # Key-encryption key for firm data keys (32 random bytes, URL-safe base64), as "id:key".
    "AICFO_LOCAL_KEKS": lambda: "k1:" + base64.urlsafe_b64encode(os.urandom(32)).decode(),
    # Signs session tokens.
    "AICFO_JWT_SECRET": lambda: secrets.token_urlsafe(48),
    # Lets n8n call the API.
    "AICFO_AUTOMATION_TOKEN": lambda: secrets.token_urlsafe(32),
}


def needs_value(current: str) -> bool:
    """True if the setting is empty or still the template placeholder."""
    return not current.strip() or "REPLACE_ME" in current


def main() -> int:
    if not TARGET.exists():  # first run: start from the template
        shutil.copy(EXAMPLE, TARGET)
        print(f"created {TARGET.relative_to(ROOT)} from .env.example")
    lines = TARGET.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()  # settings found in the file
    changed: list[str] = []  # settings we generated
    for i, line in enumerate(lines):
        m = re.match(r"^(AICFO_[A-Z0-9_]+)=(.*)$", line)  # a KEY=value line
        if not m or m.group(1) not in GENERATORS:
            continue
        key, value = m.groups()
        seen.add(key)
        if needs_value(value):
            lines[i] = f"{key}={GENERATORS[key]()}"  # replace only the empty/placeholder value
            changed.append(key)
    for key, make in GENERATORS.items():  # settings missing from the file entirely
        if key not in seen:
            lines.append(f"{key}={make()}")
            changed.append(key)
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    TARGET.chmod(0o600)  # only you can read it
    print("generated:", ", ".join(changed) if changed else "nothing (all secrets already set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
