#!/usr/bin/env python3
"""fetch_rank_daily.py — daily search-rank tracker for Babolkenar villages.

For each village search URL, walks search API pages (in-url pagination — the only
pagination that works) and records the position of every tracked radar room + own
room. Output appends to data/signals/rank_history.json:
    {"2026-09-10": {"3297585": {"village": "سیدکلا", "rank": 4, "url": "..."},
                     "_villages": {"سیدکلا": {"pages": 2, "total": 33}}, ...}}

Notes:
- Rank = 1-based position in the API listing order. First run should be sanity-checked
  against the site in a browser (API order vs rendered order can differ).
- Rooms not found in any page get rank=null (worse than last page).
"""
import json
import random
import subprocess
import time
import urllib.parse
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SIG = BASE / "data" / "signals"
SIG.mkdir(parents=True, exist_ok=True)
HIST = SIG / "rank_history.json"

# village search URLs (site search slugs) — rank is measured within each
VILLAGES = {
    "سیدکلا": "https://www.jajiga.com/s/seyyedkolababolkenar/cottage",
    "قرآن تالار": "https://www.jajiga.com/s/ghorantalarbabolkenar/cottage",
    "گونه کلا": "https://www.jajiga.com/s/gunehkolababolkenar/cottage",
    "شیردارکلا": "https://www.jajiga.com/s/shirdarekolababolkenar/cottage",
    "کاردرکلا": "https://www.jajiga.com/s/kardarkolababolkenar/cottage",
    "امیرکلا": "https://www.jajiga.com/s/amirkolababolkenar/cottage",
}
API = "https://api.jajiga.com/api/search?per_page=18&url={}&with[]=rooms"


def load_tracked():
    cfg = json.load(open(BASE / "data" / "radar" / "radar-config.json", encoding="utf-8"))
    return {str(r["id"]): r for r in cfg["rooms"]}


def curl_json(url, tries=3):
    for a in range(tries):
        r = subprocess.run(["curl", "-s", "--max-time", "25", url],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0 and r.stdout.strip():
            try:
                return json.loads(r.stdout)
            except json.JSONDecodeError:
                pass
        time.sleep(10 * (a + 1))
    return None


def sweep_village(base_url, tracked_ids, max_pages=6):
    """Walk pages until no new ids; return {room_id: rank} for tracked rooms + stats."""
    found = {}
    seen = set()
    total = None
    pages = 0
    for p in range(1, max_pages + 1):
        sep = "&" if "?" in base_url else "?"
        page_url = f"{base_url}{sep}page={p}"
        api_url = API.format(urllib.parse.quote(page_url, safe=""))
        d = curl_json(api_url)
        if not d or "rooms" not in d:
            break
        items = (d.get("rooms") or {}).get("items") or []
        pag = (d.get("rooms") or {}).get("pagination") or {}
        total = pag.get("total", total)
        new = 0
        for pos, it in enumerate(items, start=(p - 1) * 18 + 1):
            rid = str(it.get("id"))
            if rid not in seen:
                seen.add(rid)
                new += 1
                if rid in tracked_ids:
                    found[rid] = pos
        pages = p
        if new == 0 or (total and len(seen) >= total):
            break
        time.sleep(random.uniform(0.6, 1.2))
    return found, {"pages": pages, "seen": len(seen), "total": total}


def main():
    tracked = load_tracked()
    tracked_ids = set(tracked.keys())
    today = date.today().isoformat()
    hist = json.load(open(HIST, encoding="utf-8")) if HIST.exists() else {}
    day = {"_villages": {}}
    for village, url in VILLAGES.items():
        found, stats = sweep_village(url, tracked_ids)
        for rid, rank in found.items():
            day[rid] = {"village": village, "rank": rank}
        day["_villages"][village] = stats
        hit = {tracked[rid]["short_label"]: r for rid, r in found.items()}
        print(f"{village}: pages={stats['pages']} seen={stats['seen']}/{stats['total']} tracked={hit}", flush=True)
        time.sleep(random.uniform(1.5, 2.5))
    hist[today] = day
    json.dump(hist, open(HIST, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"saved {today} -> {HIST}", flush=True)


if __name__ == "__main__":
    main()
