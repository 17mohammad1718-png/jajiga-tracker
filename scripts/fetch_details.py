#!/usr/bin/env python3
"""fetch_details.py — فچ api/room/{id} برای همه اقامتگاه‌های رُستر (main+other+around)
قابل ازسرگیری: هر JSON خام در data/competitive/details/{id}.json ذخیره می‌شود؛
موجودها رد می‌شوند. retry ×4 با backoff (TLS-reset های ایران گذرا هستند).
"""
import json, os, random, sys, time, urllib.request

ROOT = r"H:/projects/jajiga-tracker"
OUT = os.path.join(ROOT, "data", "competitive", "details")
os.makedirs(OUT, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept": "application/json"}

roster = json.load(open(os.path.join(ROOT, "data", "competitive", "roster.json"), encoding="utf-8"))
ids = [e["id"] for e in roster["main"]] + [e["id"] for e in roster["other"]] + [e["id"] for e in roster["around"]]
ids = sorted(set(ids))

todo = [i for i in ids if not os.path.exists(os.path.join(OUT, f"{i}.json"))]
print(f"total {len(ids)} | already done {len(ids)-len(todo)} | to fetch {len(todo)}", flush=True)

ok = err = 0
t0 = time.time()
for n, rid in enumerate(todo, 1):
    path = os.path.join(OUT, f"{rid}.json")
    got = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"https://api.jajiga.com/api/room/{rid}", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                got = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                got = {"_http_error": 404}
                break
            time.sleep((2 ** attempt) * 3)
        except Exception:
            time.sleep((2 ** attempt) * 3)
    if got is None:
        got = {"_http_error": "failed"}
        err += 1
    else:
        ok += 1
    with open(path, "w", encoding="utf-8") as f:
        json.dump(got, f, ensure_ascii=False)
    time.sleep(random.uniform(0.35, 0.8))
    if n % 25 == 0 or n == len(todo):
        el = time.time() - t0
        eta = el / n * (len(todo) - n)
        print(f"[{n}/{len(todo)}] ok={ok} err={err} elapsed={el:.0f}s eta={eta:.0f}s", flush=True)

print(f"DONE ok={ok} err={err}", flush=True)
