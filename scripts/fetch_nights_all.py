#!/usr/bin/env python3
"""fetch_nights.py — فچ تقویم قیمت شبانه (api/nights) برای همه اقامتگاه‌های رُستر
خروجی: data/competitive/nights/{id}.json  (payload کامل + fetched_at)
قابل ازسرگیری. پیسینگ ملایم: 0.3-0.7s jitter، retry ×4.
"""
import json, os, random, time, urllib.request

ROOT = r"H:/projects/jajiga-tracker"
OUT = os.path.join(ROOT, "data", "competitive", "nights")
os.makedirs(OUT, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept": "application/json"}

roster = json.load(open(os.path.join(ROOT, "data", "competitive", "roster.json"), encoding="utf-8"))
ids = sorted({e["id"] for e in roster["main"] + roster["other"] + roster["around"]})

todo = [i for i in ids if not os.path.exists(os.path.join(OUT, f"{i}.json"))]
print(f"total {len(ids)} | already done {len(ids)-len(todo)} | to fetch {len(todo)}", flush=True)

ok = err = 0
t0 = time.time()
for n, rid in enumerate(todo, 1):
    got = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"https://api.jajiga.com/api/nights?room_id={rid}", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = json.loads(r.read().decode("utf-8"))
            nights = raw.get("nights") or []
            if nights:
                got = {"room_id": rid, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "nights": nights}
                break
            # خالی = تقویم خالی؛ بعد از retry ها به عنوان empty ثبت می‌شود
            got = {"room_id": rid, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "nights": [], "note": "empty payload"}
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                got = {"room_id": rid, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                       "nights": [], "note": "http 404"}
                break
            time.sleep((2 ** attempt) * 3)
        except Exception:
            time.sleep((2 ** attempt) * 3)
    if got is None:
        got = {"room_id": rid, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "nights": [], "note": "failed after retries"}
        err += 1
    else:
        ok += 1
    with open(os.path.join(OUT, f"{rid}.json"), "w", encoding="utf-8") as f:
        json.dump(got, f, ensure_ascii=False)
    time.sleep(random.uniform(0.3, 0.7))
    if n % 25 == 0 or n == len(todo):
        el = time.time() - t0
        print(f"[{n}/{len(todo)}] ok={ok} err={err} elapsed={el:.0f}s", flush=True)

print(f"DONE ok={ok} err={err}", flush=True)
