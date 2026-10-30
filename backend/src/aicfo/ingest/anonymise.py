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

# Column-name patterns that mark identity columns, by kind.
IDENTITY = {
    "name": re.compile(r"^(client|investor|holder|customer|full)?\s*_?name$|^name$", re.I),
    "pan": re.compile(r"\bpan\b", re.I),
    "phone": re.compile(r"phone|mobile|contact", re.I),
    "email": re.compile(r"e-?mail", re.I),
    "address": re.compile(r"address|city|pin\s*code|pincode", re.I),
    "dob": re.compile(r"birth|\bdob\b", re.I),
}
# Folio / demat / account columns: replaced by codes rather than removed.
ACCOUNT = re.compile(r"folio|account|demat|dp\s*id|client\s*id|bo\s*id", re.I)
# A PAN number anywhere in text.
PAN_RX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
# An email address anywhere in text.
EMAIL_RX = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# An Indian mobile number anywhere in text.
PHONE_RX = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")


# What the anonymiser did, so the firm can check it.
@dataclass
class Report:
    # Rows processed.
    rows: int = 0
    # Identity columns dropped, with their kind.
    removed_columns: dict[str, str] = field(default_factory=dict)  # column -> kind
    # Account columns replaced by codes.
    coded_columns: list[str] = field(default_factory=list)
    # Other cells that contained a PAN, email or phone and were cleaned.
    scrubbed_cells: int = 0
    # Distinct clients found.
    clients: int = 0


# A stable code for a value: keyed hash, so the same value gets the same code but cannot be reversed without the key.
def _code(key: bytes, prefix: str, value: str) -> str:
    # HMAC-SHA256 with the firm's secret key.
    digest = hmac.new(key, value.strip().upper().encode(), hashlib.sha256).hexdigest()
    # Prefix and the first 8 hex characters.
    return f"{prefix}-{digest[:8].upper()}"


# What kind of column is this header?
def classify(header: str) -> str | None:
    # Account number column.
    if ACCOUNT.search(header):
        # Replace with a code.
        return "account"
    # Name, PAN, phone, email, address, birth date.
    for kind, rx in IDENTITY.items():
        # Matches this kind.
        if rx.search(header):
            # Remove the column.
            return kind
    # An ordinary financial column: keep.
    return None


# Remove identities from spreadsheet rows.
def anonymise_rows(rows: list[dict[str, str]], key: bytes) -> tuple[list[dict[str, str]], Report]:
    # A secret key is mandatory.
    if not key:
        # Refuse to run without one.
        raise ValueError("a secret key is required")
    # Start the report.
    report = Report(rows=len(rows))
    # Nothing to do.
    if not rows:
        # Empty result.
        return [], report
    # Classify every column once.
    kinds = {h: classify(h) for h in rows[0]}
    # The PAN column, if any.
    pan_col = next((h for h, k in kinds.items() if k == "pan"), None)
    # The name column, if any.
    name_col = next((h for h, k in kinds.items() if k == "name"), None)
    # Remember which columns are dropped.
    report.removed_columns = {h: k for h, k in kinds.items() if k and k != "account"}
    # …and which are coded.
    report.coded_columns = [h for h, k in kinds.items() if k == "account"]
    # Output rows and distinct client codes.
    out, clients = [], set()
    # Each row.
    for row in rows:
        # Identify the client by PAN, or by name if there is no PAN.
        ident = (row.get(pan_col or "") or row.get(name_col or "") or "").strip()
        # Turn it into a stable code.
        client_code = _code(key, "C", ident) if ident else "C-UNKNOWN"
        # Count distinct clients.
        clients.add(client_code)
        # The anonymised row starts with the client code.
        new: dict[str, str] = {"client_code": client_code}
        # Each cell.
        for h, v in row.items():
            # Its column kind.
            kind = kinds[h]
            # Account number…
            if kind == "account":
                # …replaced by a code.
                new[f"{h} (code)"] = _code(key, "A", v) if v.strip() else ""
            # Identity column…
            elif kind:
                # …dropped.
                continue  # identity column: dropped
            # Ordinary cell.
            else:
                # Blank anything that looks like a PAN, email or phone number.
                clean = PHONE_RX.sub("", EMAIL_RX.sub("", PAN_RX.sub("", v)))
                # Something was removed…
                if clean != v:
                    # …count it.
                    report.scrubbed_cells += 1
                # Keep the cleaned value.
                new[h] = clean.strip()
        # Add the row.
        out.append(new)
    # Final client count.
    report.clients = len(clients)
    # Anonymised rows and the report.
    return out, report


# Command-line entry for the firm's own computer.
def main() -> None:
    # Argument parser.
    ap = argparse.ArgumentParser(prog="python -m aicfo.ingest.anonymise")
    # Input spreadsheet.
    ap.add_argument("source", type=Path)
    # Output spreadsheet.
    ap.add_argument("target", type=Path)
    # The firm's secret key.
    ap.add_argument(
        "--key", required=True, help="secret kept by the firm; the same key gives the same codes"
    )
    # Read the command line.
    args = ap.parse_args()
    # Read the input.
    with args.source.open(newline="", encoding="utf-8-sig") as f:
        # Rows as dictionaries.
        rows = list(csv.DictReader(f))
    # Anonymise.
    out, rep = anonymise_rows(rows, args.key.encode())
    # Write the output.
    with args.target.open("w", newline="", encoding="utf-8") as f:
        # Only if there are rows.
        if out:
            # CSV writer with the new headers.
            w = csv.DictWriter(f, fieldnames=list(out[0]))
            # Header row.
            w.writeheader()
            # Data rows.
            w.writerows(out)
    # Summary.
    print(f"{rep.rows} rows, {rep.clients} clients")
    print(
        "Removed columns:",
        ", ".join(f"{c} ({k})" for c, k in rep.removed_columns.items()) or "none",
    )
    # Which columns were coded.
    print("Replaced with codes:", ", ".join(rep.coded_columns) or "none")
    # How many other cells were cleaned.
    print(f"Other cells cleaned of PAN/email/phone: {rep.scrubbed_cells}")


# Run when executed as a program.
if __name__ == "__main__":
    # Go.
    main()
