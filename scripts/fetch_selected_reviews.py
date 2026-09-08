#!/usr/bin/env python3
"""fetch_selected_reviews.py v2 — 50 نظر جدید هر اتاق انتخابی، API-first.
API متن کامل پاسخ میزبان را می‌دهد؛ corpus فقط پرچم پاسخ دارد → corpus فقط fallback.
خروجی: data/competitive/selected_reviews/{id}.json
"""
import json, os, time, urllib.request

ROOT = r"H:/projects/jajiga-tracker"
OUT = os.path.join(ROOT, "data", "competitive", "selected_reviews")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept": "application/json"}

sel = json.load(open(os.path.join(ROOT, "data", "competitive", "selected_rooms.json"), encoding="utf-8"))
selected = sel["selected"]

corpus = json.load(open(os.path.join(ROOT, "data", "reviews_mining", "corpus.json"), encoding="utf-8"))
by_room = {}
for r in corpus:
    by_room.setdefault(str(r["room_id"]), []).append(r)

def api_all(rid, cap=50):
    out, page = [], 1
    while len(out) < cap:
        d = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    f"https://api.jajiga.com/api/room/{rid}/reviews?page={page}&per_page=50",
                    headers=UA)
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read().decode("utf-8"))
                break
            except Exception as e:
                print(f"  retry {rid} p{page} a{attempt}: {str(e)[:50]}", flush=True)
                time.sleep(3 * (attempt + 1))
        if d is None:
            return out, "api_error"
        items = d.get("items") or []
        if not items:
            break
        out.extend(items)
        page += 1
        time.sleep(0.8)
    return out[:cap], "ok"

report = []
for rid in selected:
    fresh, status = api_all(rid)
    src = "api"
    if len(fresh) < 50:
        # fallback: از corpus قدیمی‌تر پر کن (بدون دوبلی)
        api_ids = {r.get("id") for r in fresh}
        old = [r for r in by_room.get(str(rid), []) if r.get("review_id") not in api_ids]
        # مرتب‌سازی نزولی بر اساس تاریخ
        old.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        need = 50 - len(fresh)
        if old:
            src = "api+corpus"
        fresh = fresh + old[:need]
    with open(os.path.join(OUT, f"{rid}.json"), "w", encoding="utf-8") as f:
        json.dump({"room_id": rid, "reviews": fresh, "source": src}, f, ensure_ascii=False, indent=1)
    print(f"{rid}: n={len(fresh)} ({src}) {status}", flush=True)
    report.append({"room_id": rid, "count": len(fresh), "source": src, "status": status})
    time.sleep(0.5)

json.dump(report, open(os.path.join(OUT, "_report.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("DONE")
