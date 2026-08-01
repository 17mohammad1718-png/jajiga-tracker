#!/usr/bin/env python3
"""
probe_jajiga.py — live probe of api.jajiga.com for Claude analysis.

Runs on YOUR machine (has internet), prints compact JSON for pasting back.
Claude's sandbox cannot reach jajiga; this is the relay.

Usage:
    python scripts/probe_jajiga.py                  # default probes
    python scripts/probe_jajiga.py --room 3297585   # one room, deep detail
"""
import json
import sys
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
API = "https://api.jajiga.com"


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def probe_room(rid):
    print(f"\n{'=' * 60}\nROOM {rid}\n{'=' * 60}")
    try:
        raw = get(f"{API}/api/room/{rid}")
        top = raw.get("data", raw) if isinstance(raw, dict) else raw
        # Trim to the interesting fields; keep structure
        keys = ["id", "title", "status", "min_price", "extra_price",
                "success_books", "bedrooms", "floor_area", "guest_number",
                "max_guest_number", "ratings", "host", "geo", "features",
                "discounts", "current_discount", "cancellation_policy",
                "is_instant", "is_plus", "is_clean", "is_new", "units_count"]
        out = {k: top.get(k) for k in keys if k in top}
        print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])
    except Exception as e:
        print(f"ERROR: {e}")


def probe_nights(rid):
    print(f"\n{'=' * 60}\nNIGHTS {rid}\n{'=' * 60}")
    try:
        raw = get(f"{API}/api/nights?room_id={rid}")
        room = raw.get("room", {})
        nights = raw.get("nights", [])
        print("room meta:", json.dumps(room, ensure_ascii=False))
        print(f"nights count: {len(nights)}")
        if nights:
            print("first 3 nights:", json.dumps(nights[:3], ensure_ascii=False))
            print("last 2 nights:", json.dumps(nights[-2:], ensure_ascii=False))
            unav = sum(1 for n in nights if n.get("is_unavailable"))
            print(f"unavailable count: {unav}")
    except Exception as e:
        print(f"ERROR: {e}")


def probe_search():
    print(f"\n{'=' * 60}\nSEARCH /s/babolkenar/cottage\n{'=' * 60}")
    try:
        url = "https://www.jajiga.com/s/babolkenar/cottage"
        api_url = (
            f"{API}/api/search?per_page=18&page=1"
            f"&url={urllib.request.quote(url, safe='')}&with[]=rooms"
        )
        raw = get(api_url)
        meta = raw.get("meta", {})
        rooms = raw.get("rooms", {})
        print("meta:", json.dumps(meta, ensure_ascii=False)[:600])
        items = rooms.get("items", [])
        print(f"items: {len(items)}")
        pag = rooms.get("pagination", {})
        print("pagination:", json.dumps(pag, ensure_ascii=False))
        if items:
            print("sample item:", json.dumps(items[0], ensure_ascii=False)[:500])
    except Exception as e:
        print(f"ERROR: {e}")


def main():
    if "--room" in sys.argv:
        rid = sys.argv[sys.argv.index("--room") + 1]
        probe_room(rid)
        probe_nights(rid)
        return
    probe_search()
    probe_room("3297585")      # user's own cabin (Swiss Chalet, Seyd Kola)
    probe_nights("3297585")
    probe_room("3245625")      # busiest cabin from R&D docs
    probe_nights("3245625")


if __name__ == "__main__":
    main()
