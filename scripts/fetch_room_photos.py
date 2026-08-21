#!/usr/bin/env python3
"""Download all current listing photos for a Jajiga room.

Usage:
  python fetch_room_photos.py <room_id> [--out DIR] [--size large|medium|small]

- Fetches the room API, takes pictures[] (name, url, description, created_at)
- Downloads each from storage.jajiga.com (best available size, fallback chain)
- Writes manifest.json (per-photo metadata + status) and prints a summary.
Output dir default: <user home>/projects/cabin-photos/<room_id> (OUTSIDE any public repo).
"""
import argparse
import json
import os
import sys
import time
import urllib.request

API = "https://api.jajiga.com/api/room/{}"
CDN = "https://storage.jajiga.com/public/pictures/{}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.jajiga.com/",
}
SIZE_ORDER = ["large", "medium", "small"]
DELAY = 0.5  # seconds between photo downloads


def http_get(url: str, timeout: int = 25):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=timeout)


def room_pictures(room_id: int) -> list:
    with http_get(API.format(room_id)) as r:
        data = json.load(r)
    return data.get("pictures") or []


def download_best(pic: dict, out_dir: str, pref: str) -> dict:
    """Download the photo at the preferred size, falling back down the chain."""
    rel = pic.get("url", "")
    if not rel:
        return {"status": "no_url"}
    last = None
    order = [pref] + [s for s in SIZE_ORDER if s != pref]
    for size in order:
        url = CDN.format(size) + "/" + rel
        fname = pic.get("name") or rel.rsplit("/", 1)[-1]
        dest = os.path.join(out_dir, fname)
        try:
            with http_get(url) as r:
                blob = r.read()
            if len(blob) == 0:
                last = f"empty_{size}"
                continue
            with open(dest, "wb") as f:
                f.write(blob)
            return {"status": "ok", "size": size, "bytes": len(blob),
                    "file": fname, "url_full": url}
        except Exception as e:  # noqa: BLE001 - try next size
            last = f"{size}:{type(e).__name__}"
    return {"status": "fail", "error": str(last)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Download Jajiga room photos")
    ap.add_argument("room_id", type=int)
    ap.add_argument("--out", default=None, help="output dir (default: ~/projects/cabin-photos/<id>)")
    ap.add_argument("--size", default="large", choices=SIZE_ORDER)
    ap.add_argument("--no-delay", action="store_true")
    args = ap.parse_args()

    out_dir = args.out or os.path.join(
        os.path.expanduser("~"), "projects", "cabin-photos", str(args.room_id))
    os.makedirs(out_dir, exist_ok=True)

    pics = room_pictures(args.room_id)
    print(f"API: {len(pics)} pictures for room {args.room_id}")

    manifest = {"room_id": args.room_id, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "count_total": len(pics), "photos": []}
    ok = 0
    for i, pic in enumerate(pics, 1):
        res = download_best(pic, out_dir, args.size)
        ok += 1 if res.get("status") == "ok" else 0
        manifest["photos"].append({
            "index": i,
            "name": pic.get("name"),
            "description": pic.get("description", ""),
            "created_at": pic.get("created_at"),
            **res,
        })
        tag = "OK " if res.get("status") == "ok" else "ERR"
        desc = pic.get("description") or ""
        print(f"  [{i:02d}/{len(pics)}] {tag} {pic.get('created_at')}  "
              f"{desc[:30]:<32} {res.get('bytes',0)}B")
        if not args.no_delay and i < len(pics):
            time.sleep(DELAY)

    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    print(f"\nDONE: {ok}/{len(pics)} downloaded -> {out_dir}")
    return 0 if ok == len(pics) else 1


if __name__ == "__main__":
    sys.exit(main())
