#!/usr/bin/env python3
"""Fail if broker order-placement APIs appear in source code.

AI CFO is read-only by design. Usage: check_no_order_apis.py [paths...]
(default: backend/src frontend/src).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FORBIDDEN = re.compile(
    r"""(
        /v\d+/orders\b | /orders/(regular|amo|modify|cancel|place)\b |
        /super/orders | /forever/orders | /positions/exit | /killswitch |
        \b(place|modify|cancel)_?(super_|forever_|slice_)?order\b |
        \bexit_all_positions\b
    )""",
    re.IGNORECASE | re.VERBOSE,
)
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx"}


def scan(roots: list[Path]) -> list[str]:
    hits: list[str] = []
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in files:
            if path.suffix not in SUFFIXES or not path.is_file():
                continue
            for lineno, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
                if FORBIDDEN.search(line):
                    hits.append(f"{path}:{lineno}: {line.strip()}")
    return hits


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or [Path("backend/src"), Path("frontend/src")]
    hits = scan([r for r in roots if r.exists()])
    if hits:
        print("Forbidden broker order API usage found (AI CFO is read-only):")
        print("\n".join(hits))
        return 1
    print("OK: no broker order APIs found.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
