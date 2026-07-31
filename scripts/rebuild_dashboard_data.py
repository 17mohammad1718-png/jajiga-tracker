"""
rebuild_dashboard_data.py
-------------------------
Regenerates the `const ALL_CABINS = [...]` block in dashboard.html
from data/all-cabins.json (the single source of truth).

Idempotent — safe to run multiple times.
Stdlib only, no external dependencies.

Usage:
    python scripts/rebuild_dashboard_data.py
"""

import json
import os
import sys
import re

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(PROJECT_ROOT, "data", "all-cabins.json")
HTML_PATH = os.path.join(PROJECT_ROOT, "dashboard.html")


def load_json():
    """Load and parse the JSON data file."""
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def deduplicate_cabins(cabin_list):
    """Remove duplicate IDs, keeping the first occurrence.
    
    This preserves data integrity — if a cabin appears twice
    with different data, the first (presumably older/more reliable) wins.
    """
    seen_ids = set()
    unique = []
    for cabin in cabin_list:
        cid = cabin["id"]
        if cid not in seen_ids:
            seen_ids.add(cid)
            unique.append(cabin)
    return unique


def cabins_to_js_array(cabins):
    """Convert cabin list to JavaScript ALL_CABINS array string.
    Includes ALL fields from the JSON record, except scrape metadata
    (last_scrape_status, last_scrape_attempt) which the UI doesn't consume."""
    EXCLUDED = {"last_scrape_status", "last_scrape_attempt", "_note"}
    lines = []
    for c in cabins:
        parts = []
        for k, v in c.items():
            if k in EXCLUDED:
                continue
            if k == "title":
                # Escape single quotes in titles
                v = str(v).replace("'", "\\'")
            if isinstance(v, str):
                parts.append(f'{k}:"{v}"')
            elif isinstance(v, bool):
                parts.append(f'{k}:{"true" if v else "false"}')
            elif v is None:
                parts.append(f'{k}:null')
            else:
                parts.append(f'{k}:{v}')
        line = "  {" + ",".join(parts) + "}"
        lines.append(line)
    return "const ALL_CABINS = [\n" + ",\n".join(lines) + "\n];"


def rebuild_html(html, js_array):
    """Replace the ALL_CABINS block in the HTML file."""
    # Match the ALL_CABINS declaration block
    # Pattern handles both "const ALL_CABINS = [" ... "];" forms
    pattern = r"const ALL_CABINS = \[.*?\];"
    replacement = js_array
    new_html, count = re.subn(pattern, replacement, html, flags=re.DOTALL)
    if count == 0:
        print("ERROR: Could not find ALL_CABINS block in dashboard.html", file=sys.stderr)
        sys.exit(1)
    if count > 1:
        print(f"WARNING: Replaced {count} ALL_CABINS blocks (expected 1)", file=sys.stderr)
    return new_html


def main():
    print(f"Reading JSON: {JSON_PATH}")
    data = load_json()

    # Flatten all cabins across villages, tagging each with its village name
    all_cabins = []
    for village, cabins in data["villages"].items():
        for cabin in cabins:
            cabin_copy = dict(cabin)
            cabin_copy["village"] = village
            all_cabins.append(cabin_copy)

    print(f"Total cabins before dedup: {len(all_cabins)}")
    unique = deduplicate_cabins(all_cabins)
    print(f"Total cabins after dedup:  {len(unique)}")
    removed = len(all_cabins) - len(unique)
    if removed:
        print(f"  → Removed {removed} duplicate(s)")

    js_array = cabins_to_js_array(unique)

    print(f"Reading HTML: {HTML_PATH}")
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    new_html = rebuild_html(html, js_array)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"✅ dashboard.html updated ({len(unique)} cabins)")

    # Verify: check that previously-zeroed entries now have real values
    zero_ids = [3154396, 3264357, 3304015, 3199443, 3224492, 3305898, 3283844]
    for cid in zero_ids:
        found = next((c for c in unique if c["id"] == cid), None)
        if found:
            price = found.get("price", 0)
            rating = found.get("rating", 0)
            reviews = found.get("reviews", 0)
            status = "✅" if price > 0 else "⚠️  still zero"
            print(f"  id={cid}: price={price:,}, rating={rating}, reviews={reviews} {status}")
        else:
            print(f"  id={cid}: ❌ NOT FOUND in deduped data")


if __name__ == "__main__":
    main()
