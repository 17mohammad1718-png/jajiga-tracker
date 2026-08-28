# -*- coding: utf-8 -*-
"""Build fetch manifest for review mining: top-N rooms by review count, after probing per_page."""
import json
import sys
import io
import time
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BASE = "https://api.jajiga.com/api/room/{id}/reviews?page={page}&per_page={pp}"


def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def probe_per_page(room_ids):
    """Try per_page in [10, 20, 50] on a sample room: count returned items on page 1."""
    results = {}
    for rid in room_ids[:2]:
        for pp in (10, 20, 50):
            try:
                d = fetch(BASE.format(id=rid, page=1, pp=pp))
                items = len(d.get("items") or [])
                total = (d.get("pagination") or {}).get("total")
                results.setdefault(pp, []).append((items, total))
                print(f"  room {rid} per_page={pp}: got {items} items, api total={total}")
            except Exception as e:
                results.setdefault(pp, []).append((None, str(e)))
                print(f"  room {rid} per_page={pp}: ERROR {e}")
            time.sleep(1.2)
    # optimal = largest pp where items == pp (page 1 fully filled)
    optimal = 10
    for pp in (50, 20, 10):
        vals = results.get(pp) or []
        if any(isinstance(i, int) and i == pp for i, _ in vals):
            optimal = pp
            break
    print(f"OPTIMAL per_page: {optimal}")
    return optimal


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    sweep = json.load(open("data/top_rooms_sweep.json", encoding="utf-8"))
    rooms = sweep if isinstance(sweep, list) else sweep.get("rooms") or []
    # rank by review count, take top N
    rooms = sorted(rooms, key=lambda r: (r.get("reviews") or 0), reverse=True)[:top_n]
    print(f"selected rooms: {len(rooms)}")

    already = set()
    import glob, os
    for f in glob.glob("data/reviews/*_reviews.json"):
        rid = os.path.basename(f).split("_")[0]
        already.add(rid)
    for f in glob.glob("data/reviews_mining/raw/*.json"):
        rid = os.path.basename(f).replace(".json", "")
        already.add(rid)
    print(f"already fetched: {len(already)}")

    # probe with a couple of high-review rooms not yet fetched
    probe_ids = [str(r["id"]) for r in rooms if str(r["id"]) not in already][:2] or [str(rooms[0]["id"])]
    optimal = probe_per_page(probe_ids)

    manifest, total_pages, est_reviews = [], 0, 0
    for r in rooms:
        rid = str(r["id"])
        if rid in already:
            continue
        total = int(r.get("reviews") or 0)
        pages = max(1, -(-total // optimal))
        manifest.append({
            "room_id": rid,
            "title": r.get("title"),
            "province": r.get("province"),
            "city": r.get("city"),
            "card_reviews": total,
            "pages": pages,
            "shard": len(manifest) % 8,  # provisional; rebalanced later by pages
        })
        total_pages += pages
        est_reviews += total

    # rebalance shards by page count (greedy: heaviest page room to lightest shard)
    manifest.sort(key=lambda m: -m["pages"])
    shard_load = [0] * 8
    for m in manifest:
        s = shard_load.index(min(shard_load))
        m["shard"] = s
        shard_load[s] += m["pages"]
    print(f"manifest: {len(manifest)} rooms, {total_pages} pages, est ~{est_reviews} reviews")
    print(f"shard loads (pages): {shard_load}")

    est_minutes = total_pages * 1.6 / 60 / 8  # 1.6s per page across 8 agents
    print(f"est fetch time: ~{est_minutes:.0f} min at 8 agents, 1.6s/page")

    json.dump(manifest, open("data/reviews_mining/manifest.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({"per_page": optimal, "shard_loads": shard_load, "total_pages": total_pages,
               "total_rooms": len(manifest), "est_reviews": est_reviews,
               "already_fetched": sorted(already)},
              open("data/reviews_mining/probe.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("saved manifest.json + probe.json")


if __name__ == "__main__":
    main()
