# -*- coding: utf-8 -*-
"""Fetch all reviews for one shard of the manifest. Resumable via state file.

Usage: python scripts/fetch_reviews_shard.py <shard_number 0-7>
State: data/reviews_mining/shard_{N}_state.json
Output: data/reviews_mining/raw/{room_id}.json
Prints DONE marker when the shard is complete.
"""
import json
import os
import sys
import io
import time
import urllib.request
import urllib.error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BASE = "https://api.jajiga.com/api/room/{id}/reviews?page={page}&per_page={pp}"
PER_PAGE = 50
SLEEP = 1.6
SHARD = int(sys.argv[1]) if len(sys.argv) > 1 else 0

MANIFEST = "data/reviews_mining/manifest.json"
RAW_DIR = "data/reviews_mining/raw"
STATE = f"data/reviews_mining/shard_{SHARD}_state.json"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def load_state(rooms):
    st = {"done": [], "failed": {}, "fetched_reviews": 0}
    if os.path.exists(STATE):
        old = json.load(open(STATE, encoding="utf-8"))
        st["done"] = old.get("done", [])
        st["fetched_reviews"] = old.get("fetched_reviews", 0)
        # failed rooms are NOT final: on each resume run, retry them
        st["failed"] = {}
    return st


def save_state(st):
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)


def fetch_room(rid):
    """Fetch all pages for one room. Returns list of reviews."""
    all_items, page, total = [], 1, None
    while True:
        d = fetch(BASE.format(id=rid, page=page, pp=PER_PAGE))
        items = d.get("items") or []
        if total is None:
            total = (d.get("pagination") or {}).get("total")
        if not items:
            break
        all_items.extend(items)
        if total and len(all_items) >= total:
            break
        if page > 400:  # hard safety cap
            break
        page += 1
        time.sleep(SLEEP)
    return all_items, total


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    rooms = [m for m in manifest if m["shard"] == SHARD]
    st = load_state(rooms)
    os.makedirs(RAW_DIR, exist_ok=True)
    print(f"[shard {SHARD}] {len(rooms)} rooms | already done: {len(st['done'])} | failed: {len(st['failed'])}")

    for i, m in enumerate(rooms, 1):
        rid = str(m["room_id"])
        if rid in st["done"] or rid in st["failed"]:
            continue
        try:
            items, api_total = fetch_room(rid)
            json.dump(items, open(f"{RAW_DIR}/{rid}.json", "w", encoding="utf-8"),
                      ensure_ascii=False)
            st["done"].append(rid)
            st["fetched_reviews"] += len(items)
            print(f"[shard {SHARD}] {i}/{len(rooms)} room {rid}: {len(items)} reviews "
                  f"(api_total={api_total}) | shard total={st['fetched_reviews']}")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                print(f"[shard {SHARD}] room {rid}: HTTP {e.code} -> backoff 30s")
                time.sleep(30)
                try:
                    items, api_total = fetch_room(rid)
                    json.dump(items, open(f"{RAW_DIR}/{rid}.json", "w", encoding="utf-8"),
                              ensure_ascii=False)
                    st["done"].append(rid)
                    st["fetched_reviews"] += len(items)
                    print(f"[shard {SHARD}] {i}/{len(rooms)} room {rid}: {len(items)} reviews (retry OK)")
                except Exception as e2:
                    st["failed"][rid] = str(e2)[:120]
                    print(f"[shard {SHARD}] room {rid}: FAILED {e2}")
            else:
                st["failed"][rid] = f"HTTP {e.code}"
                print(f"[shard {SHARD}] room {rid}: HTTP {e.code} marked failed")
        except Exception as e:
            st["failed"][rid] = str(e)[:120]
            print(f"[shard {SHARD}] room {rid}: FAILED {e}")
        save_state(st)
        time.sleep(SLEEP)

    print(f"[shard {SHARD}] DONE done={len(st['done'])} failed={len(st['failed'])} "
          f"reviews={st['fetched_reviews']}")
    if st["failed"]:
        print(f"[shard {SHARD}] failed rooms: {list(st['failed'])[:20]}")


if __name__ == "__main__":
    main()
