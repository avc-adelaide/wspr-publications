#!/usr/bin/env python3
"""Convert a BibTeX file of conference papers to a CSV for publication tracking.

The output columns mirror the format of wspr-papers-journal.csv so that the
same HTML generation and Scholar-sync tooling can be applied to both files.

Usage examples:
  python3 scripts/bib_to_csv.py external/aurora-conf-papers.bib aurora-conf-papers.csv
  python3 scripts/bib_to_csv.py --sort year external/aurora-conf-papers.bib aurora-conf-papers.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Minimal BibTeX parser
# ---------------------------------------------------------------------------

def _strip_braces(value: str) -> str:
    """Remove outermost { } wrappers and normalise internal whitespace."""
    value = value.strip()
    if value.startswith("{") and value.endswith("}"):
        value = value[1:-1]
    # Collapse runs of whitespace (including newlines from multi-line values)
    value = re.sub(r"\s+", " ", value).strip()
    # Remove escaped backslashes left over from bib URL escaping
    value = value.replace("\\", "")
    return value


def _parse_bib(text: str) -> list[dict[str, str]]:
    """Parse *all* @inproceedings entries from *text*.

    Returns a list of dicts mapping lowercased field names → stripped values,
    plus the special key ``_citekey`` for the entry cite key.

    Duplicate cite keys are silently deduplicated: the first occurrence wins.
    """
    entries: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    # Match each @inproceedings{...} block.  We look for the closing lone "}"
    # that sits on a line by itself (which is how BibDesk/standard bib files
    # are formatted).
    entry_pattern = re.compile(
        r"@inproceedings\{([^,\s]+)\s*,\s*(.*?)\n\}",
        re.DOTALL | re.IGNORECASE,
    )

    for m in entry_pattern.finditer(text):
        citekey = m.group(1).strip()
        if citekey in seen_keys:
            continue
        seen_keys.add(citekey)

        body = m.group(2)
        fields: dict[str, str] = {"_citekey": citekey}

        # Extract field = {value} or field = {multi
        #   line value},
        # We also handle field = value, (no braces) for simple cases.
        field_pattern = re.compile(
            r"(\w+)\s*=\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
            re.DOTALL,
        )
        for fm in field_pattern.finditer(body):
            key = fm.group(1).lower()
            val = _strip_braces("{" + fm.group(2) + "}")
            # For fields that may appear multiple times (e.g. url, keyword),
            # keep only the first occurrence.
            if key not in fields:
                fields[key] = val

        entries.append(fields)

    return entries


# ---------------------------------------------------------------------------
# Author helpers
# ---------------------------------------------------------------------------

def _first_author_last_name(author_field: str) -> str:
    """Return the last name of the first author.

    BibTeX author strings are typically "Last, First and Last2, First2 ..."
    or "First Last and First2 Last2 ...".
    """
    if not author_field:
        return ""
    first = author_field.split(" and ")[0].strip()
    if "," in first:
        return first.split(",")[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


# ---------------------------------------------------------------------------
# Conference name helpers
# ---------------------------------------------------------------------------

def _best_conference(fields: dict[str, str]) -> str:
    """Return the best available short conference name."""
    # Prefer the dedicated `conference` field (common in Aurora bib files),
    # then fall back to `booktitle`.
    return fields.get("conference", "") or fields.get("booktitle", "")


# ---------------------------------------------------------------------------
# Main conversion logic
# ---------------------------------------------------------------------------

def bib_to_rows(
    bib_path: Path,
    sort_by: str = "year",
) -> tuple[list[str], list[dict[str, str]]]:
    """Parse *bib_path* and return (headers, rows) ready for CSV writing."""
    text = bib_path.read_text(encoding="utf-8-sig")
    entries = _parse_bib(text)

    if sort_by == "year":
        entries.sort(key=lambda e: (e.get("year", "0"), e.get("_citekey", "")))
    elif sort_by == "author":
        entries.sort(
            key=lambda e: (
                _first_author_last_name(e.get("author", "")),
                e.get("year", "0"),
            )
        )
    # else: preserve original order

    headers = [
        "Index",
        "First Author Last Name",
        "Year",
        "Cite key",
        "Title",
        "Conference",
        "DOI",
        "Scholar ID",
    ]

    rows: list[dict[str, str]] = []
    for idx, entry in enumerate(entries, start=1):
        rows.append(
            {
                "Index": str(idx),
                "First Author Last Name": _first_author_last_name(
                    entry.get("author", "")
                ),
                "Year": entry.get("year", ""),
                "Cite key": entry.get("_citekey", ""),
                "Title": entry.get("title", ""),
                "Conference": _best_conference(entry),
                "DOI": entry.get("doi", ""),
                "Scholar ID": "",
            }
        )

    return headers, rows


def write_csv(
    out_path: Path, headers: list[str], rows: list[dict[str, str]]
) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a BibTeX conference-papers file to a publication CSV."
    )
    parser.add_argument(
        "bib",
        help="Input BibTeX file path (e.g. external/aurora-conf-papers.bib)",
    )
    parser.add_argument(
        "out",
        help="Output CSV file path (e.g. aurora-conf-papers.csv)",
    )
    parser.add_argument(
        "--sort",
        choices=["year", "author", "none"],
        default="year",
        help="Sort order for output rows (default: year)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bib_path = Path(args.bib)
    out_path = Path(args.out)

    if not bib_path.exists():
        print(f"ERROR: BibTeX file not found: {bib_path}", file=sys.stderr)
        return 2

    headers, rows = bib_to_rows(bib_path, sort_by=args.sort)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out_path, headers, rows)
    print(f"Wrote {out_path} from {bib_path} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
