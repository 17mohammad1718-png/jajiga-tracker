#!/usr/bin/env python3
"""market sweep: fetch full room detail (features/properties/badges/discounts/host stats)
for every active Babolkenar room in jajiga_master.json.
Serial fetch with 2-4s delay + retry (jajiga rate-limit rule: NO parallel requests).
Resume-safe: partial results saved to checkpoint after every room.

Output: data/signals/market_sweep_<date>.json
"""
import json
import random
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SIG = BASE / "data" / "signals"
SIG.mkdir(parents=True, exist_ok=True)
TODAY = date.today().isoformat()
OUT = SIG / f"market_sweep_{TODAY}.json"
CKPT = SIG / "sweep_checkpoint.json"
DELAY = (2.0, 4.0)


def curl_json(url, tries=3):
    """curl with retry + exponential backoff (WinError 10061 rule)."""
    for attempt in range(tries):
        r = subprocess.run(
            ["curl", "-s", "--max-time", "30", url],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if r.returncode == 0 and r.stdout.strip():
            try:
                return json.loads(r.stdout), None
            except json.JSONDecodeError:
                err = "json-decode"
        else:
            err = f"curl-rc={r.returncode}"
        wait = 15 * (attempt + 1)
        print(f"  retry {attempt+1}/3 after {err}, wait {wait}s", flush=True)
        time.sleep(wait)
    return None, err


def load_checkpoint():
    if CKPT.exists():
        ck = json.load(open(CKPT, encoding="utf-8"))
        if ck.get("date") == TODAY:
            return ck.get("results", {})
    return {}


def save_checkpoint(results, ids):
    json.dump({"date": TODAY, "results": results, "pending": ids},
              open(CKPT, "w", encoding="utf-8"), ensure_ascii=False)


def extract_room(d):
    """Slim record per room with the fields the 5 signals need."""
    host = d.get("host") or {}
    ratings = d.get("ratings") or {}
    return {
        "id": d.get("id"),
        "title": d.get("title"),
        "status": d.get("status"),
        "min_price": d.get("min_price"),
        "current_discount": d.get("current_discount"),
        "current_discount_percent": d.get("current_discount_percent"),
        "discounts": d.get("discounts"),
        "features": [f.get("name") for f in (d.get("features") or [])],
        "properties": [p.get("name") for p in (d.get("properties") or [])],
        "types": d.get("types"),
        "is_instant": d.get("is_instant"),
        "is_plus": d.get("is_plus"),
        "is_clean": d.get("is_clean"),
        "is_new": d.get("is_new"),
        "success_books": d.get("success_books"),
        "rating_total": (ratings.get("total") if isinstance(ratings, dict) else None),
        "rating_count": (ratings.get("count") if isinstance(ratings, dict) else None),
        "bedrooms": d.get("bedrooms"),
        "floor_area": d.get("floor_area"),
        "guest_number": d.get("guest_number"),
        "max_guest_number": d.get("max_guest_number"),
        "units_count": d.get("units_count"),
        "host_id": host.get("id"),
        "host_name": host.get("name"),
        "host_accept_rate": host.get("accept_rate"),
        "host_response_time": host.get("response_time"),
        "host_communication_rate": host.get("host_communication_rate"),
        "geo": d.get("geo"),
    }


def main():
    master = json.load(open(BASE / "jajiga_master.json", encoding="utf-8"))
    ids = [r["id"] for r in master["rooms"] if r.get("status") == "active"]
    print(f"sweep target: {len(ids)} active rooms -> {OUT.name}", flush=True)

    results = load_checkpoint()
    done = [i for i in ids if str(i) in results or i in results]
    print(f"resume: {len(done)} already collected", flush=True)

    t0 = time.time()
    fails = []
    for n, rid in enumerate(ids, 1):
        if str(rid) in results:
            continue
        d, err = curl_json(f"https://api.jajiga.com/api/room/{rid}")
        if d and d.get("id"):
            results[str(rid)] = extract_room(d)
        else:
            fails.append({"id": rid, "err": err})
            print(f"  FAIL {rid}: {err}", flush=True)
        if n % 10 == 0:
            save_checkpoint(results, [i for i in ids if str(i) not in results])
            el = time.time() - t0
            rem = (len(ids) - n) * (el / max(n - len(done), 1)) if n > len(done) else 0
            print(f"[{n}/{len(ids)}] {el/60:.1f}m elapsed, ~{rem/60:.0f}m left, "
                  f"{len(results)} ok, {len(fails)} fail", flush=True)
        time.sleep(random.uniform(*DELAY))

    payload = {
        "date": TODAY,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(results),
        "failed": fails,
        "rooms": results,
    }
    json.dump(payload, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    CKPT.unlink(missing_ok=True)
    print(f"DONE: {len(results)} rooms saved, {len(fails)} failed -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
