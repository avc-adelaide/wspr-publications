#!/usr/bin/env python3
"""Generate a static, browseable HTML table from a CSV file."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a CSV into a static HTML table for GitHub Pages."
    )
    parser.add_argument(
        "--csv",
        default="wspr-papers-journal.csv",
        help="Input CSV path (default: wspr-papers-journal.csv)",
    )
    parser.add_argument(
        "--out",
        default="docs/index.html",
        help="Output HTML path (default: docs/index.html)",
    )
    parser.add_argument(
        "--title",
        default="WSPR Journal Publications",
        help="Page title",
    )
    return parser.parse_args()


def read_csv(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [{k: (v or "") for k, v in row.items()} for row in reader]
        return list(reader.fieldnames or []), rows


def build_html(page_title: str, headers: list[str], rows: list[dict[str, str]]) -> str:
    safe_title = html.escape(page_title)
    headers_json = json.dumps(headers, ensure_ascii=False)
    rows_json = json.dumps(rows, ensure_ascii=False)

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{safe_title}</title>
  <style>
    :root {{
      --bg: #f4f6f8;
      --card: #ffffff;
      --text: #13202b;
      --muted: #5a6773;
      --line: #d7dde3;
      --accent: #0b6e99;
      --accent-soft: #e8f5fb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Helvetica Neue", Helvetica, Arial, sans-serif;
      color: var(--text);
      background: linear-gradient(180deg, #edf2f6 0%, var(--bg) 240px);
    }}
    .wrap {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 24px;
    }}
    .header {{
      display: flex;
      gap: 16px;
      align-items: flex-end;
      justify-content: space-between;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }}
    h1 {{ margin: 0; font-size: 1.6rem; }}
    .meta {{ color: var(--muted); margin-top: 6px; font-size: 0.95rem; }}
    .controls {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }}
    input[type=\"search\"] {{
      width: min(440px, 84vw);
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      font-size: 0.95rem;
      background: #fff;
    }}
    .button {{
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 0.9rem;
      cursor: pointer;
    }}
    .button:hover {{ border-color: var(--accent); color: var(--accent); }}
    .table-card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(24, 39, 75, 0.08);
    }}
    .scroll {{ overflow: auto; max-height: 78vh; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 1100px; }}
    thead th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fbfd;
      border-bottom: 1px solid var(--line);
      text-align: left;
      font-weight: 600;
      font-size: 0.86rem;
      color: #1f3b4f;
      padding: 10px 12px;
      white-space: nowrap;
      cursor: pointer;
      user-select: none;
    }}
    tbody td {{
      border-top: 1px solid #eef2f6;
      padding: 10px 12px;
      vertical-align: top;
      font-size: 0.9rem;
      line-height: 1.35;
    }}
    tbody tr:hover {{ background: #fbfdff; }}
    .title-col {{ min-width: 450px; }}
    .doi-col {{ min-width: 210px; }}
    .muted {{ color: var(--muted); }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .count {{ margin: 10px 2px 0; color: var(--muted); font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"header\">
      <div>
        <h1>{safe_title}</h1>
        <div class=\"meta\">Sortable and searchable publication table</div>
      </div>
      <div class=\"controls\">
        <input id=\"search\" type=\"search\" placeholder=\"Search all fields\" />
        <button class=\"button\" id=\"clear\" type=\"button\">Clear</button>
      </div>
    </div>

    <div class=\"table-card\">
      <div class=\"scroll\">
        <table id=\"pubTable\">
          <thead><tr id=\"headRow\"></tr></thead>
          <tbody id=\"bodyRows\"></tbody>
        </table>
      </div>
    </div>
    <div class=\"count\" id=\"count\"></div>
  </div>

  <script>
    const headers = {headers_json};
    const allRows = {rows_json};

    const searchInput = document.getElementById("search");
    const clearButton = document.getElementById("clear");
    const headRow = document.getElementById("headRow");
    const bodyRows = document.getElementById("bodyRows");
    const count = document.getElementById("count");

    let sortKey = "Year";
    let sortAsc = false;

    function safe(text) {{
      return (text ?? "").toString();
    }}

    function compareValues(a, b) {{
      const numA = Number(a);
      const numB = Number(b);
      if (!Number.isNaN(numA) && !Number.isNaN(numB)) return numA - numB;
      return a.localeCompare(b, undefined, {{ sensitivity: "base" }});
    }}

    function headerLabel(name) {{
      if (name === sortKey) return `${{name}} ${{sortAsc ? "▲" : "▼"}}`;
      return name;
    }}

    function renderHeaders() {{
      headRow.innerHTML = "";
      headers.forEach((h) => {{
        const th = document.createElement("th");
        th.textContent = headerLabel(h);
        if (h === "Title") th.className = "title-col";
        if (h === "DOI") th.className = "doi-col";
        th.addEventListener("click", () => {{
          if (sortKey === h) sortAsc = !sortAsc;
          else {{
            sortKey = h;
            sortAsc = true;
          }}
          render();
        }});
        headRow.appendChild(th);
      }});
    }}

    function render() {{
      const q = searchInput.value.trim().toLowerCase();

      const filtered = allRows.filter((row) => {{
        if (!q) return true;
        return headers.some((h) => safe(row[h]).toLowerCase().includes(q));
      }});

      filtered.sort((ra, rb) => {{
        const av = safe(ra[sortKey]);
        const bv = safe(rb[sortKey]);
        const result = compareValues(av, bv);
        return sortAsc ? result : -result;
      }});

      bodyRows.innerHTML = "";
      for (const row of filtered) {{
        const tr = document.createElement("tr");
        for (const h of headers) {{
          const td = document.createElement("td");
          if (h === "Title") td.className = "title-col";
          if (h === "DOI") td.className = "doi-col";

          const value = safe(row[h]);
          if (h === "DOI" && value) {{
            const link = document.createElement("a");
            const url = value.startsWith("http") ? value : `https://doi.org/${{value}}`;
            link.href = url;
            link.textContent = value;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            td.appendChild(link);
          }} else {{
            td.textContent = value;
          }}
          tr.appendChild(td);
        }}
        bodyRows.appendChild(tr);
      }}

      renderHeaders();
      count.textContent = `Showing ${{filtered.length}} of ${{allRows.length}} records`;
    }}

    searchInput.addEventListener("input", render);
    clearButton.addEventListener("click", () => {{
      searchInput.value = "";
      render();
      searchInput.focus();
    }});

    render();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    csv_path = Path(args.csv)
    out_path = Path(args.out)

    headers, rows = read_csv(csv_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_html(args.title, headers, rows), encoding="utf-8")
    print(f"Wrote {out_path} from {csv_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
