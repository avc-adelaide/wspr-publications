#!/usr/bin/env python3
"""Export Google Scholar publications and compare them with repository CSV files.

Usage examples:
  python3 scripts/scholar_sync.py --user-id kxCnpPEAAAAJ
  python3 scripts/scholar_sync.py --user-id kxCnpPEAAAAJ --update-scholar-id
  python3 scripts/scholar_sync.py --scholar-json reports/scholar-publications.json
"""

from __future__ import annotations

import argparse
import csv
import difflib
import glob
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ScholarPub:
    title: str
    scholar_id: str
    year: str
    venue: str
    source: str


def normalize_title(value: str) -> str:
    value = (value or "").strip().lower()
    value = value.replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", value)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Scholar publications and compare them against repository CSVs."
    )
    parser.add_argument(
        "--user-id",
        default="",
        help="Google Scholar user id, e.g. kxCnpPEAAAAJ.",
    )
    parser.add_argument(
        "--scholar-json",
        default="",
        help="Path to cached scholar export JSON. If provided, no network fetch is attempted.",
    )
    parser.add_argument(
        "--csv-glob",
        default="*.csv",
        help="Glob pattern for publication CSV files (default: *.csv).",
    )
    parser.add_argument(
        "--export-json",
        default="reports/scholar-publications.json",
        help="Output path for exported scholar publications JSON.",
    )
    parser.add_argument(
        "--missing-report",
        default="reports/scholar-missing.csv",
        help="Output path for missing-publications report CSV.",
    )
    parser.add_argument(
        "--update-scholar-id",
        action="store_true",
        help="Add/update a 'Scholar ID' column in matching CSV rows.",
    )
    parser.add_argument(
        "--fuzzy-cutoff",
        type=float,
        default=0.94,
        help="Fuzzy-match threshold for title matching (0..1, default: 0.94).",
    )
    return parser.parse_args()


def load_scholar_from_json(json_path: Path) -> list[ScholarPub]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    pubs: list[ScholarPub] = []
    for row in data:
        pubs.append(
            ScholarPub(
                title=str(row.get("title", "")).strip(),
                scholar_id=str(row.get("scholar_id", "")).strip(),
                year=str(row.get("year", "")).strip(),
                venue=str(row.get("venue", "")).strip(),
                source=str(row.get("source", "json")).strip() or "json",
            )
        )
    return [p for p in pubs if p.title]


def load_scholar_live(user_id: str) -> list[ScholarPub]:
    if not user_id:
        raise ValueError("Missing --user-id for live Scholar fetch.")
    try:
        from scholarly import scholarly  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Package 'scholarly' is required for live fetch. "
            "Install with: pip install scholarly"
        ) from exc

    author = scholarly.search_author_id(user_id)
    author = scholarly.fill(author, sections=["publications"])

    pubs: list[ScholarPub] = []
    for p in author.get("publications", []):
        bib = p.get("bib", {}) or {}
        title = str(bib.get("title", "")).strip()
        if not title:
            continue
        pubs.append(
            ScholarPub(
                title=title,
                scholar_id=str(p.get("author_pub_id", "")).strip(),
                year=str(bib.get("pub_year", "")).strip(),
                venue=str(bib.get("venue", "")).strip(),
                source="live",
            )
        )
    return pubs


def export_scholar_json(pubs: list[ScholarPub], export_path: Path) -> None:
    ensure_parent(export_path)
    payload = [
        {
            "title": p.title,
            "scholar_id": p.scholar_id,
            "year": p.year,
            "venue": p.venue,
            "source": p.source,
        }
        for p in pubs
    ]
    export_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_csv_files(pattern: str) -> list[Path]:
    files = [Path(p) for p in sorted(glob.glob(pattern))]
    return [p for p in files if p.is_file()]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
    return headers, rows


def write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def build_repo_title_index(
    csv_files: list[Path],
) -> tuple[dict[str, list[tuple[Path, int]]], dict[Path, tuple[list[str], list[dict[str, str]]]]]:
    by_title: dict[str, list[tuple[Path, int]]] = {}
    loaded: dict[Path, tuple[list[str], list[dict[str, str]]]] = {}

    for path in csv_files:
        headers, rows = read_csv(path)
        loaded[path] = (headers, rows)
        if "Title" not in headers:
            continue
        for idx, row in enumerate(rows):
            norm = normalize_title(row.get("Title", ""))
            if not norm:
                continue
            by_title.setdefault(norm, []).append((path, idx))
    return by_title, loaded


def find_match(
    scholar_norm: str, repo_keys: list[str], cutoff: float
) -> str | None:
    if scholar_norm in repo_keys:
        return scholar_norm
    maybe = difflib.get_close_matches(scholar_norm, repo_keys, n=1, cutoff=cutoff)
    return maybe[0] if maybe else None


def write_missing_report(path: Path, missing: list[ScholarPub]) -> None:
    ensure_parent(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["scholar_id", "title", "year", "venue", "source"]
        )
        writer.writeheader()
        for p in missing:
            writer.writerow(
                {
                    "scholar_id": p.scholar_id,
                    "title": p.title,
                    "year": p.year,
                    "venue": p.venue,
                    "source": p.source,
                }
            )


def update_scholar_ids(
    loaded_csv: dict[Path, tuple[list[str], list[dict[str, str]]]],
    repo_index: dict[str, list[tuple[Path, int]]],
    scholar_pubs: list[ScholarPub],
    cutoff: float,
) -> int:
    updated_cells = 0
    repo_keys = list(repo_index.keys())

    for p in scholar_pubs:
        if not p.scholar_id:
            continue
        match = find_match(normalize_title(p.title), repo_keys, cutoff)
        if not match:
            continue
        for path, row_idx in repo_index[match]:
            headers, rows = loaded_csv[path]
            if "Scholar ID" not in headers:
                headers.append("Scholar ID")
                for row in rows:
                    row.setdefault("Scholar ID", "")
            current = rows[row_idx].get("Scholar ID", "").strip()
            if current != p.scholar_id:
                rows[row_idx]["Scholar ID"] = p.scholar_id
                updated_cells += 1
    return updated_cells


def main() -> int:
    args = parse_args()

    # Load Scholar publications.
    if args.scholar_json:
        scholar_path = Path(args.scholar_json)
        if not scholar_path.exists():
            print(f"ERROR: scholar json not found: {scholar_path}", file=sys.stderr)
            return 2
        scholar_pubs = load_scholar_from_json(scholar_path)
    else:
        try:
            scholar_pubs = load_scholar_live(args.user_id)
        except Exception as exc:
            print(f"ERROR: live Scholar fetch failed: {exc}", file=sys.stderr)
            return 2
        export_scholar_json(scholar_pubs, Path(args.export_json))

    if not scholar_pubs:
        print("No Scholar publications found.")
        return 0

    # Load repo CSVs and compare.
    csv_files = read_csv_files(args.csv_glob)
    if not csv_files:
        print(f"ERROR: no CSV files matched pattern: {args.csv_glob}", file=sys.stderr)
        return 2

    repo_index, loaded_csv = build_repo_title_index(csv_files)
    repo_keys = list(repo_index.keys())

    missing: list[ScholarPub] = []
    matched = 0
    for pub in scholar_pubs:
        norm = normalize_title(pub.title)
        if not norm:
            continue
        found = find_match(norm, repo_keys, args.fuzzy_cutoff)
        if found:
            matched += 1
        else:
            missing.append(pub)

    write_missing_report(Path(args.missing_report), missing)

    updated_cells = 0
    if args.update_scholar_id:
        updated_cells = update_scholar_ids(
            loaded_csv, repo_index, scholar_pubs, args.fuzzy_cutoff
        )
        for path, (headers, rows) in loaded_csv.items():
            if "Scholar ID" in headers:
                write_csv(path, headers, rows)

    print(f"Scholar publications: {len(scholar_pubs)}")
    print(f"Matched in repo CSVs: {matched}")
    print(f"Missing in repo CSVs: {len(missing)}")
    print(f"Missing report: {args.missing_report}")
    if not args.scholar_json:
        print(f"Scholar export cache: {args.export_json}")
    if args.update_scholar_id:
        print(f"Updated Scholar ID cells: {updated_cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
