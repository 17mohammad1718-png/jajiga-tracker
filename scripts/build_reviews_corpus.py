# -*- coding: utf-8 -*-
"""Merge all fetched reviews into one deduplicated corpus.

Sources: data/reviews_mining/raw/*.json + legacy data/reviews/*_reviews.json
Output:  data/reviews_mining/corpus.json  (list of standardized review dicts)
Also prints summary stats. Idempotent — safe to re-run after more fetching.
"""
import glob
import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

RAW_DIR = "data/reviews_mining/raw"
LEGACY_DIR = "data/reviews"
OUT = "data/reviews_mining/corpus.json"


def main():
    # room -> province/city/title map from manifest + sweep
    meta = {}
    try:
        for m in json.load(open("data/reviews_mining/manifest.json", encoding="utf-8")):
            meta[str(m["room_id"])] = {"title": m.get("title"), "province": m.get("province"),
                                       "city": m.get("city")}
    except FileNotFoundError:
        pass
    try:
        sweep = json.load(open("data/top_rooms_sweep.json", encoding="utf-8"))
        for r in (sweep if isinstance(sweep, list) else sweep.get("rooms") or []):
            meta.setdefault(str(r["id"]), {"title": r.get("title"), "province": r.get("province"),
                                           "city": r.get("city")})
    except FileNotFoundError:
        pass

    corpus, seen, files_used = {}, set(), 0
    sources = sorted(glob.glob(f"{RAW_DIR}/*.json")) + sorted(glob.glob(f"{LEGACY_DIR}/*_reviews.json"))
    for f in sources:
        rid = os.path.basename(f).replace("_reviews.json", "").replace(".json", "")
        try:
            items = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"WARN bad file {f}: {e}")
            continue
        files_used += 1
        for it in items or []:
            rv_id = str(it.get("id"))
            key = f"{rid}:{rv_id}"
            if key in seen:
                continue
            seen.add(key)
            created = (it.get("created_at") or "")[:10]  # strip microseconds before any date use
            user = it.get("user") or {}
            corpus[key] = {
                "review_id": rv_id,
                "room_id": rid,
                "title": meta.get(rid, {}).get("title"),
                "province": meta.get(rid, {}).get("province"),
                "city": meta.get(rid, {}).get("city"),
                "content": (it.get("content") or "").strip(),
                "rating": it.get("rating"),
                "created_at": created,
                "user_name": user.get("name"),
                "host_reply": bool(it.get("host_reply")),
            }

    out = list(corpus.values())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"files merged: {files_used}")
    print(f"unique reviews: {len(out)}")
    rooms = {r["room_id"] for r in out}
    print(f"rooms with reviews: {len(rooms)}")
    provs = {}
    for r in out:
        p = r["province"] or "?"
        provs[p] = provs.get(p, 0) + 1
    print("by province:", {k: v for k, v in sorted(provs.items(), key=lambda x: -x[1])[:8]})
    empty = sum(1 for r in out if not r["content"])
    print(f"empty-content reviews: {empty}")


if __name__ == "__main__":
    main()
