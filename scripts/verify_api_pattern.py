"""Verify Jajiga API extraction pattern against stored JSON (full batch, background).
Rate-limit safe: 2-4s delays, retry with exponential backoff, sequential only.
"""
import json
import urllib.request
import time
import random
import sys

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

DATA_FILE = r"H:\projects\jajiga-tracker\data\all-cabins.json"
OUT_FILE = r"H:\projects\jajiga-tracker\data\_api_verify.json"


def fetch_room(rid, max_retries=3):
    url = f"https://api.jajiga.com/api/room/{rid}"
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            top = raw.get("data", raw) if isinstance(raw, dict) else raw
            return top
        except Exception as e:
            if attempt < max_retries:
                wait = (2 ** attempt) * 5  # 5, 10, 20s backoff
                print(f"    retry {attempt+1} for {rid} in {wait}s ({e})", flush=True)
                time.sleep(wait)
            else:
                raise


def main():
    data = json.load(open(DATA_FILE, encoding="utf-8"))
    villages = data["villages"]
    all_cabins = []
    for vname, cabins in villages.items():
        for c in cabins:
            all_cabins.append({**c, "village": vname})

    print(f"Total cabins: {len(all_cabins)}", flush=True)
    results = {}
    start = time.time()
    for i, cabin in enumerate(all_cabins, 1):
        rid = cabin["id"]
        t0 = time.time()
        try:
            top = fetch_room(rid)
            ratings = top.get("ratings") if isinstance(top.get("ratings"), dict) else {}
            host = top.get("host") if isinstance(top.get("host"), dict) else {}
            results[rid] = {
                "title": top.get("title"),
                "min_price": top.get("min_price"),
                "status": top.get("status"),
                "bedrooms": top.get("bedrooms"),
                "floor_area": top.get("floor_area"),
                "guest_number": top.get("guest_number"),
                "max_guest_number": top.get("max_guest_number"),
                "host": host.get("name"),
                "rating": ratings.get("total"),
                "reviews": ratings.get("count"),
            }
            status = "OK"
        except Exception as e:
            results[rid] = {"error": str(e)[:100]}
            status = f"ERR: {e}"
        elapsed = time.time() - t0
        if i % 5 == 0 or status.startswith("ERR"):
            print(f"  [{i}/{len(all_cabins)}] {rid} {status} ({elapsed:.1f}s)", flush=True)
        # 2-4s random delay (rate-limit safe)
        if i < len(all_cabins):
            time.sleep(random.uniform(2.0, 4.0))

    total = time.time() - start
    print(f"\nFetch complete in {total:.0f}s", flush=True)

    # Compare
    price_changes = []
    errors = []
    for cabin in all_cabins:
        rid = cabin["id"]
        fresh = results.get(rid, {})
        if "error" in fresh:
            errors.append((rid, fresh["error"]))
            continue
        old_price = cabin.get("price")
        new_price = fresh.get("min_price")
        if old_price != new_price:
            price_changes.append(
                (cabin["village"], rid, (cabin.get("title") or "")[:40], old_price, new_price)
            )

    report = {
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(all_cabins),
        "ok": len([r for r in results.values() if "error" not in r]),
        "errors": errors,
        "price_changes": price_changes,
        "raw": results,
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n=== RESULT ===")
    print(f"OK: {report['ok']}/{report['total']}, Errors: {len(errors)}")
    print(f"PRICE CHANGES: {len(price_changes)}")
    for v, rid, t, old, new in price_changes:
        print(f"  {v} | {rid} | {t} | {old:,} -> {new:,}")
    print(f"Saved to {OUT_FILE}")


if __name__ == "__main__":
    main()
