#!/usr/bin/env python3
"""fetch_review_bounds.py — تاریخ اولین و آخرین نظر قابل مشاهده برای هر اقامتگاه
روش: per_page=50 → page 1 (جدیدترین) + صفحه آخر (قدیمی‌ترین). 2 کال به‌ازای هر اتاق.
خروجی: data/competitive/review_bounds.json  {id: {first, last, total}}
قابل ازسرگیری.
"""
import json, math, os, time, urllib.request

ROOT = r"H:/projects/jajiga-tracker"
OUT_FILE = os.path.join(ROOT, "data", "competitive", "review_bounds.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept": "application/json"}

bounds = {}
if os.path.exists(OUT_FILE):
    bounds = json.load(open(OUT_FILE, encoding="utf-8"))

roster = json.load(open(os.path.join(ROOT, "data", "competitive", "roster.json"), encoding="utf-8"))
ids = sorted({e["id"] for e in roster["main"] + roster["other"] + roster["around"]})
todo = [i for i in ids if str(i) not in bounds]
print(f"total {len(ids)} | done {len(bounds)} | to fetch {len(todo)}", flush=True)

def get(rid, page):
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                f"https://api.jajiga.com/api/room/{rid}/reviews?page={page}&per_page=50", headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                print(f"  err {rid} p{page}: {str(e)[:50]}", flush=True)
                return None
            time.sleep(3 * (attempt + 1))

ok = err = 0
t0 = time.time()
for n, rid in enumerate(todo, 1):
    d1 = get(rid, 1)
    if not d1:
        bounds[str(rid)] = {"error": "fetch_failed"}
        err += 1
        continue
    items = d1.get("items") or []
    total = (d1.get("pagination") or {}).get("total")
    if not items:
        bounds[str(rid)] = {"first": "", "last": "", "total": 0}
        ok += 1
    else:
        last_date = items[0].get("created_at", "")[:10]     # جدیدترین
        pages = max(1, math.ceil((total or len(items)) / 50))
        first_date = last_date
        if pages > 1:
            dN = get(rid, pages)
            if dN and (dN.get("items") or []):
                first_date = dN["items"][-1].get("created_at", "")[:10]  # قدیمی‌ترین صفحه آخر
        else:
            first_date = items[-1].get("created_at", "")[:10]
        bounds[str(rid)] = {"first": first_date, "last": last_date, "total": total}
        ok += 1
    if n % 25 == 0 or n == len(todo):
        json.dump(bounds, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        el = time.time() - t0
        print(f"[{n}/{len(todo)}] ok={ok} err={err} elapsed={el:.0f}s eta={el/n*(len(todo)-n):.0f}s", flush=True)
    time.sleep(0.4)

json.dump(bounds, open(OUT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"DONE ok={ok} err={err}", flush=True)
