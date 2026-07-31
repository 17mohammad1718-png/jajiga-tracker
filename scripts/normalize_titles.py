#!/usr/bin/env python3
"""Normalize cabin titles: remove village names and 'در بابلکنار' from titles,
since villages have their own column in the dashboard.

Rules (from skill):
- Strip: سیدکلا, سید کلا, قرآن تالار, قران تالار, قرآن تلار, قران تلار,
         گونه کلا, گونهکلا, شیردارکلا, شیردار کلا
- Strip: در بابلکنار, در در بابلکنار (double در typo)
- Strip trailing/leading dashes and spaces left after removal
- KEEP distinctive suffixes: - ۲, - ط بالا, - ط۳, - ۳ خوابه, - واحد ۴, - همکف
- Also strip 'در سوادکوه' prefix if present (room 3178917 title starts with it)
"""
import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "all-cabins.json")

# Village name patterns to strip (order: longest first to avoid partial matches)
VILLAGE_SUFFIXES = [
    "شیردارکلا", "شیردار کلا",
    "قرآن تالار", "قران تالار", "قرآن تلار", "قران تلار",
    "سیدکلا", "سید کلا",
    "گونه کلا", "گونهکلا",
]

# Infixes to strip (order: longest first)
STRIP_INFIXES = [
    "در در بابلکنار",  # double در typo
    "در بابلکنار",
    "در سوادکوه",
    "در سیدکلا بابلکنار",  # compound
    "در گونه کلا",         # compound
    "در شیردارکلا",        # compound
    "در قرآن تالار",       # compound
]

# Additional cleanup: orphan "در" left after village removal
# e.g. "کلبه جنگلی استخردار در - ۳ خوابه" -> "کلبه جنگلی استخردار - ۳ خوابه"
ORPHAN_FIXES = [
    (" در - ", " - "),      # orphan در before dash
    (" در -", " -"),        # orphan در before dash (no trailing space)
    (" در  ", " "),         # orphan در followed by double space
]


def normalize_title(title):
    """Remove village names, در بابلکنار, and clean up punctuation."""
    t = title.strip()

    # Strip infixes (در بابلکنار, etc.)
    for infix in STRIP_INFIXES:
        t = t.replace(infix, " ").replace("  ", " ")

    # Strip village suffixes (after - or space)
    for vs in VILLAGE_SUFFIXES:
        t = t.replace(f" - {vs}", "")
        t = t.replace(f"  {vs}", "")
        t = t.replace(f"- {vs}", "")
        t = t.replace(vs, "")

    # Fix orphan "در" left after village removal
    for old, new in ORPHAN_FIXES:
        t = t.replace(old, new)

    # Handle ZWNJ variants (U+200C): re-strip with ZWNJ in patterns
    # e.g. "قرآن‌ تالار" has ZWNJ between ئ and space
    zwnj_villages = [vs.replace(" ", "\u200c ") for vs in VILLAGE_SUFFIXES]
    for vs in zwnj_villages:
        t = t.replace(f" - {vs}", "")
        t = t.replace(f"  {vs}", "")
        t = t.replace(f"- {vs}", "")
        t = t.replace(vs, "")
    # Also strip ZWNJ from "در بابلکنار" variants
    t = t.replace("در\u200c بابلکنار", " ")
    t = t.replace("در بابلکنار\u200c ", " ")

    # Strip trailing/leading dashes and spaces
    t = re.sub(r'\s*-\s*$', '', t)       # trailing " - "
    t = re.sub(r'^\s*-\s*', '', t)       # leading "- "
    t = re.sub(r'\s{2,}', ' ', t)        # multiple spaces -> single
    t = t.strip()

    # Final cleanup: "استخردار بابلکنار" -> "استخردار"
    # (بَلـ is a substring, so it only matches when followed by more text)
    if "بَل" not in t:  # no "بل" in the actual cabin name
        t = t.replace(" بابلکنار", "")

    return t


def main():
    data = json.load(open(DATA_FILE, encoding="utf-8"))
    changed = 0
    for vname, cabins in data["villages"].items():
        for c in cabins:
            old = c.get("title", "")
            new = normalize_title(old)
            if old != new:
                c["title"] = new
                changed += 1
                print(f"  {c['id']} | {old}")
                print(f"    -> {new}")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nNormalized {changed}/{sum(len(v) for v in data['villages'].values())} titles")
    print(f"Saved to {DATA_FILE}")


if __name__ == "__main__":
    main()
