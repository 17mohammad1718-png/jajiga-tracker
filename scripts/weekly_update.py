#!/usr/bin/env python3
"""
Jajiga weekly tracker update — API-based (no browser needed).

Workflow:
  1. Load data/all-cabins.json (source of truth)
  2. Discover the full بابلکنار cottage catalog via api.jajiga.com/api/search
     (pagination trick: ?page=N goes INSIDE the `url` param, not the `page` query param)
  3. Filter catalog to the 4 target villages by title suffix
  4. Fetch fresh details for all known + new rooms via api.jajiga.com/api/room/{id}
  5. Merge (preserve non-scraper fields), save JSON, print change report

Usage:
    python scripts/weekly_update.py             # apply updates + report
    python scripts/weekly_update.py --dry-run   # report only, no save
    python scripts/weekly_update.py --skip-discover  # only refresh known cabins
"""

import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "all-cabins.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}
BASE = "https://www.jajiga.com"
sys.path.insert(0, SCRIPT_DIR)
from normalize_titles import normalize_title
API = "https://api.jajiga.com"

CATALOG_URL = "/s/babolkenar/cottage"  # all cottages in Babolkenar
PER_PAGE = 18  # API max

# Village detection from title suffix (both spellings, with/without ZWNJ/space)
VILLAGE_PATTERNS = {
    "سیدکلا":    ["سیدکلا", "سید کلا"],
    "قرآن تالار": ["قرآن تالار", "قران تالار", "قرآن تلار", "قران تلار"],
    "گونه کلا":  ["گونه کلا", "گونهکلا", "گونه كلا"],
    "شیردارکلا": ["شیردارکلا", "شیردار کلا"],
}
# Known out-of-region trap: a "سیدکلا" in سوادکوه (not Babolkenar)
EXCLUDE_TITLE = "سوادکوه"

DELAY_MIN, DELAY_MAX = 2.0, 4.0  # seconds between requests (rate-limit safe)
MAX_RETRIES = 3
QUIET = False  # set via --quiet in main()

# Fields the scraper owns; EVERYTHING else is preserved (manual edits survive)
SCRAPER_FIELDS = {
    "title", "url", "price", "price_source", "rating", "reviews",
    "guests", "rooms", "floor", "standard_capacity", "extra_capacity",
    "active", "success_books", "last_scrape_status", "last_scrape_attempt",
}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def http_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_room(rid):
    """Room details. Retries with exponential backoff (Jajiga rate-limits hard)."""
    url = f"{API}/api/room/{rid}"
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            raw = http_json(url)
            top = raw.get("data", raw) if isinstance(raw, dict) else raw
            if not isinstance(top, dict) or not top.get("title"):
                raise ValueError("empty/invalid room payload")
            return top
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep((2 ** attempt) * 5)  # 5, 10, 20s backoff
    raise last_err


def search_page(url_path_with_page):
    """One catalog search page. `page=N` must be inside the url param."""
    api_url = (
        f"{API}/api/search?per_page={PER_PAGE}&page=1"
        f"&url={urllib.parse.quote(f'{BASE}{url_path_with_page}', safe='')}"
        f"&with[]=rooms"
    )
    return http_json(api_url)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def discover_catalog():
    """Sweep the whole Babolkenar cottage catalog. Returns {id: {title, price}}."""
    found = {}
    page = 1
    while True:
        url = CATALOG_URL + (f"?page={page}" if page > 1 else "")
        r = search_page(url)
        items = r.get("rooms", {}).get("items", [])
        total = r.get("rooms", {}).get("pagination", {}).get("total") or 0
        new = 0
        for it in items:
            rid = it.get("id")
            if rid and rid not in found:
                found[rid] = {
                    "title": it.get("title", ""),
                    "price": it.get("price") or it.get("min_price"),
                }
                new += 1
        if not QUIET:
            print(f"  catalog page {page}: {len(items)} items, {new} new "
                  f"(unique={len(found)}, total={total})", flush=True)
        if len(items) < PER_PAGE or page * PER_PAGE >= total or new == 0:
            break
        page += 1
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
    return found


def detect_village(title):
    if EXCLUDE_TITLE in title:
        return None
    for vname, pats in VILLAGE_PATTERNS.items():
        for p in pats:
            if p in title:
                return vname
    return None


# ---------------------------------------------------------------------------
# Merge / save
# ---------------------------------------------------------------------------
def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    data["meta"]["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def merge_room(cabin, top):
    """Update a cabin dict from API data; returns list of change descriptions."""
    changes = []
    ratings = top.get("ratings") if isinstance(top.get("ratings"), dict) else {}
    host = top.get("host") if isinstance(top.get("host"), dict) else {}

    new_price = top.get("min_price")
    if new_price is not None:
        if cabin.get("price") != new_price:
            changes.append(f"price {cabin.get('price'):,} -> {new_price:,}")
        cabin["price"] = new_price
        cabin["price_source"] = "api_min_price"

    new_rating = ratings.get("total")
    if new_rating is not None and cabin.get("rating") != new_rating:
        changes.append(f"rating {cabin.get('rating')} -> {new_rating}")
        cabin["rating"] = new_rating

    new_reviews = ratings.get("count")
    if new_reviews is not None and cabin.get("reviews") != new_reviews:
        changes.append(f"reviews {cabin.get('reviews')} -> {new_reviews}")
        cabin["reviews"] = new_reviews

    new_guests = top.get("max_guest_number") or top.get("guest_number")
    if new_guests and cabin.get("guests") != new_guests:
        changes.append(f"guests {cabin.get('guests')} -> {new_guests}")
        cabin["guests"] = new_guests

    new_rooms = top.get("bedrooms")
    if new_rooms and cabin.get("rooms") != new_rooms:
        changes.append(f"rooms {cabin.get('rooms')} -> {new_rooms}")
        cabin["rooms"] = new_rooms

    new_floor = top.get("floor_area")
    if new_floor and cabin.get("floor") != new_floor:
        changes.append(f"floor {cabin.get('floor')} -> {new_floor}")
        cabin["floor"] = new_floor

    new_books = top.get("success_books")
    if new_books is not None:
        if cabin.get("success_books") != new_books:
            changes.append(f"success_books {cabin.get('success_books')} -> {new_books}")
        cabin["success_books"] = new_books

    new_active = top.get("status") == "active"
    if cabin.get("active") != new_active:
        changes.append(f"active {cabin.get('active')} -> {new_active}")
        cabin["active"] = new_active
    if not new_active:
        cabin["price"] = 0
        cabin["price_source"] = "inactive"

    # host: only fill when missing/placeholder (never overwrite manual edits)
    if host.get("name") and (not cabin.get("host") or cabin.get("host") == "نام میزبان"):
        cabin["host"] = host["name"]

    cabin["title"] = normalize_title(top.get("title") or cabin.get("title"))
    cabin["url"] = f"{BASE}/room/{cabin['id']}"
    cabin["last_scrape_status"] = "ok"
    cabin["last_scrape_attempt"] = datetime.now(timezone.utc).isoformat()
    return changes


def new_cabin(rid, top, village):
    ratings = top.get("ratings") if isinstance(top.get("ratings"), dict) else {}
    host = top.get("host") if isinstance(top.get("host"), dict) else {}
    active = top.get("status") == "active"
    return {
        "id": rid,
        "title": normalize_title(top.get("title") or "نامشخص"),
        "price": top.get("min_price") if active else 0,
        "price_source": "api_min_price" if active else "inactive",
        "rooms": top.get("bedrooms") or 0,
        "floor": top.get("floor_area") or 0,
        "guests": top.get("max_guest_number") or top.get("guest_number") or 0,
        "rating": ratings.get("total") or 0,
        "reviews": ratings.get("count") or 0,
        "url": f"{BASE}/room/{rid}",
        "active": active,
        "success_books": top.get("success_books") or 0,
        "host": host.get("name") or "",
        "last_scrape_status": "ok",
        "last_scrape_attempt": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    dry_run = "--dry-run" in sys.argv
    skip_discover = "--skip-discover" in sys.argv
    quiet = "--quiet" in sys.argv
    global QUIET
    QUIET = quiet

    def log(msg):
        if not quiet:
            print(msg, flush=True)

    data = load_data()
    villages = data["villages"]
    known_ids = {
        c["id"] for cabins in villages.values() for c in cabins
    }
    log(f"Loaded {len(known_ids)} known cabins")

    # 1) Discovery
    new_ids = set()
    if skip_discover:
        log("Discovery skipped (--skip-discover)")
    else:
        log("Catalog sweep:")
        catalog = discover_catalog()
        matched = {rid: it for rid, it in catalog.items() if detect_village(it["title"])}
        new_ids = set(matched) - known_ids
        log(f"Catalog: {len(catalog)} items, {len(matched)} in target villages, "
            f"{len(new_ids)} new")
    time.sleep(random.uniform(1.0, 2.0))

    # 2) Fetch all rooms (known + new)
    all_ids = sorted(known_ids | new_ids)
    log(f"Fetching {len(all_ids)} rooms...")
    fresh = {}
    for i, rid in enumerate(all_ids, 1):
        try:
            fresh[rid] = fetch_room(rid)
        except Exception as e:
            log(f"  [{i}/{len(all_ids)}] {rid} ERROR: {e}")
            continue
        if i % 5 == 0 or i == len(all_ids):
            log(f"  [{i}/{len(all_ids)}] done")
        if i < len(all_ids):
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    # 3) Merge
    report = {"price_changes": [], "new": [], "status_changes": [], "errors": []}
    for rid, top in fresh.items():
        vname = None
        for v, cabins in villages.items():
            for c in cabins:
                if c["id"] == rid:
                    vname = v
                    break
            if vname:
                break
        if vname is None:
            # new listing — assign village from title
            title = top.get("title", "")
            vname = detect_village(title)
            if vname is None:
                report["errors"].append((rid, "village not detectable"))
                continue
            if vname not in villages:
                villages[vname] = []
            cabin = new_cabin(rid, top, vname)
            villages[vname].append(cabin)
            report["new"].append((vname, rid, cabin["title"][:45], cabin["price"]))
            log(f"  NEW {vname} | {rid} | {cabin['title'][:45]} | {cabin['price']:,}")
        else:
            cabin = None
            for c in villages[vname]:
                if c["id"] == rid:
                    cabin = c
                    break
            if cabin is None:
                continue
            changes = merge_room(cabin, top)
            if changes:
                report["price_changes"].append((vname, rid, cabin["title"][:45], changes))
                log(f"  CHG {vname} | {rid} | {cabin['title'][:40]} | "
                    + "; ".join(changes))

    # 4) Remove inactive cabins
    removed = []
    for vname in list(villages.keys()):
        before = len(villages[vname])
        villages[vname] = [c for c in villages[vname] if c.get("active", True)]
        after = len(villages[vname])
        for c in villages[vname][after:] if after < before else []:
            removed.append((vname, c["id"], c["title"][:45]))
        if before != after:
            log(f"  Removed {before - after} inactive from {vname}")

    # 5) Recompute meta
    total = sum(len(v) for v in villages.values())
    prices = [c["price"] for cabins in villages.values() for c in cabins if c.get("price")]
    data["meta"]["total_cabins"] = total
    if prices:
        data["meta"]["price_range"] = (
            f"{min(prices):,} - {max(prices):,} تومان/شب"
        )

    print("\n" + "=" * 60)
    print(f"REPORT: {total} total cabins | {len(fresh)} fetched | "
          f"{len(report['new'])} new | {len(report['price_changes'])} changed | "
          f"{len(removed)} removed | {len(report['errors'])} errors")
    for v, rid, t, changes in report["price_changes"]:
        print(f"  CHG {v} {rid}: {'; '.join(changes)}")
    for v, rid, t, p in report["new"]:
        print(f"  NEW {v} {rid}: {t} | {p:,}")
    for v, rid, t in removed:
        print(f"  REM {v} {rid}: {t}")
    for e in report["errors"]:
        print(f"  ERR {e}")
    print("=" * 60)

    if dry_run:
        print("\nDRY RUN — no changes saved.")
    else:
        save_data(data)
        print(f"\nSaved to {DATA_FILE}")


if __name__ == "__main__":
    main()
