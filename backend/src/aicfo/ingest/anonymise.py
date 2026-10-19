"""Remove identities from a holdings spreadsheet before it leaves the firm.

Run by the CA firm on their own computer:
    python -m aicfo.ingest.anonymise holdings.csv shared.csv --key "<a secret only the firm keeps>"

* Name, PAN, phone, email and address columns are removed.
* PAN (or name, when PAN is missing) becomes a client code; folio / account numbers
  become account codes. Codes come from a keyed hash (HMAC-SHA256): the same client
  gets the same code every time, but without the firm's key nobody can reverse it.
* Every remaining text cell is scanned; anything that looks like a PAN, email or
  phone number is blanked and reported.
* Financial facts are kept: ISIN, scheme, units, dates, amounts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from pathlib import Path

IDENTITY = {
    "name": re.compile(r"^(client|investor|holder|customer|full)?\s*_?name$|^name$", re.I),
    "pan": re.compile(r"\bpan\b", re.I),
    "phone": re.compile(r"phone|mobile|contact", re.I),
    "email": re.compile(r"e-?mail", re.I),
    "address": re.compile(r"address|city|pin\s*code|pincode", re.I),
    "dob": re.compile(r"birth|\bdob\b", re.I),
}
ACCOUNT = re.compile(r"folio|account|demat|dp\s*id|client\s*id|bo\s*id", re.I)
PAN_RX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
EMAIL_RX = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RX = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")


@dataclass
class Report:
    rows: int = 0
    removed_columns: dict[str, str] = field(default_factory=dict)  # column -> kind
    coded_columns: list[str] = field(default_factory=list)
    scrubbed_cells: int = 0
    clients: int = 0


def _code(key: bytes, prefix: str, value: str) -> str:
    digest = hmac.new(key, value.strip().upper().encode(), hashlib.sha256).hexdigest()
    return f"{prefix}-{digest[:8].upper()}"


def classify(header: str) -> str | None:
    if ACCOUNT.search(header):
        return "account"
    for kind, rx in IDENTITY.items():
        if rx.search(header):
            return kind
    return None


def anonymise_rows(rows: list[dict[str, str]], key: bytes) -> tuple[list[dict[str, str]], Report]:
    if not key:
        raise ValueError("a secret key is required")
    report = Report(rows=len(rows))
    if not rows:
        return [], report
    kinds = {h: classify(h) for h in rows[0]}
    pan_col = next((h for h, k in kinds.items() if k == "pan"), None)
    name_col = next((h for h, k in kinds.items() if k == "name"), None)
    report.removed_columns = {h: k for h, k in kinds.items() if k and k != "account"}
    report.coded_columns = [h for h, k in kinds.items() if k == "account"]
    out, clients = [], set()
    for row in rows:
        ident = (row.get(pan_col or "") or row.get(name_col or "") or "").strip()
        client_code = _code(key, "C", ident) if ident else "C-UNKNOWN"
        clients.add(client_code)
        new: dict[str, str] = {"client_code": client_code}
        for h, v in row.items():
            kind = kinds[h]
            if kind == "account":
                new[f"{h} (code)"] = _code(key, "A", v) if v.strip() else ""
            elif kind:
                continue  # identity column: dropped
            else:
                clean = PHONE_RX.sub("", EMAIL_RX.sub("", PAN_RX.sub("", v)))
                if clean != v:
                    report.scrubbed_cells += 1
                new[h] = clean.strip()
        out.append(new)
    report.clients = len(clients)
    return out, report


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m aicfo.ingest.anonymise")
    ap.add_argument("source", type=Path)
    ap.add_argument("target", type=Path)
    ap.add_argument(
        "--key", required=True, help="secret kept by the firm; the same key gives the same codes"
    )
    args = ap.parse_args()
    with args.source.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out, rep = anonymise_rows(rows, args.key.encode())
    with args.target.open("w", newline="", encoding="utf-8") as f:
        if out:
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
    print(f"{rep.rows} rows, {rep.clients} clients")
    print(
        "Removed columns:",
        ", ".join(f"{c} ({k})" for c, k in rep.removed_columns.items()) or "none",
    )
    print("Replaced with codes:", ", ".join(rep.coded_columns) or "none")
    print(f"Other cells cleaned of PAN/email/phone: {rep.scrubbed_cells}")


if __name__ == "__main__":
    main()
