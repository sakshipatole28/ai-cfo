#!/usr/bin/env python3
"""Validate the n8n workflows in infra/n8n/workflows (CI guard, standard library only).

Checks: valid JSON with nodes and connections; every connection points to an existing node;
URLs come from $env (no hard-coded hosts); calls to the AI CFO API send the automation
token; no embedded credentials or secret-looking strings.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "infra" / "n8n" / "workflows"
SECRET = re.compile(r"(gsk_[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}|sk-[A-Za-z0-9]{20,}|eyJ[\w-]{20,}\.)")


def check(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        wf = json.loads(text)
    except json.JSONDecodeError as exc:
        return [f"{path.name}: invalid JSON ({exc})"]
    nodes = {n["name"]: n for n in wf.get("nodes", [])}
    if not nodes or "connections" not in wf:
        errors.append(f"{path.name}: needs nodes and connections")
    for src, outs in wf.get("connections", {}).items():
        if src not in nodes:
            errors.append(f"{path.name}: connection from unknown node {src!r}")
        for branch in outs.get("main", []):
            for edge in branch:
                if edge["node"] not in nodes:
                    errors.append(f"{path.name}: connection to unknown node {edge['node']!r}")
    for name, n in nodes.items():
        if n.get("credentials"):
            errors.append(f"{path.name}: {name} embeds credentials; use $env or n8n credentials")
        if n["type"] == "n8n-nodes-base.httpRequest":
            url = str(n["parameters"].get("url", ""))
            if not url.startswith("={{ $env."):
                errors.append(f"{path.name}: {name} URL must come from $env, got {url!r}")
            headers = n["parameters"].get("headerParameters", {}).get("parameters", [])
            if "AICFO_API_URL" in url and not any(h["name"] == "Authorization" for h in headers):
                errors.append(f"{path.name}: {name} calls the API without the automation token")
    if SECRET.search(text):
        errors.append(f"{path.name}: contains a secret-looking string")
    return errors


def main() -> int:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else WORKFLOWS
    files = sorted(folder.glob("*.json"))
    errors = [e for f in files for e in check(f)]
    for e in errors:
        print(f"ERROR {e}")
    print(f"checked {len(files)} n8n workflows: {'ok' if not errors else 'FAILED'}")
    return 1 if errors or not files else 0


if __name__ == "__main__":
    sys.exit(main())
