#!/usr/bin/env python3
"""build_market_signals.py — compute the 4 analysis signals from existing data.

Signal sources:
  4. Holiday-premium map    <- data/radar/snapshots/*.json (per-night cycle prices)
  5. Discount + repricing   <- snapshots (price changes between consecutive snapshots)
  6. Amenity ROI            <- data/signals/market_sweep_<today>.json (features x price x books)
  10. Badge effect          <- sweep (is_instant/is_plus/is_clean x success_books)

Output: data/signals/signals_computed.json (consumed by the dashboard builder)
"""
import json
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RD = BASE / "data" / "radar"
SIG = BASE / "data" / "signals"
WINDOW_DAYS = 45


def load_snapshots():
    snaps = []
    for f in sorted((RD / "snapshots").glob("*.json")):
        d = json.load(open(f, encoding="utf-8"))
        snaps.append({"date": f.stem, "fetched_at": d.get("fetched_at"), "rooms": d["rooms"]})
    return snaps


def night_price(n):
    return n.get("price") if not n.get("is_unavailable") else None


def pct(a, b):
    return round((a / b - 1) * 100, 1) if b else None


# ---------- Signal 4: holiday premium ----------
def holiday_premium_v2(snaps):
    """Premium vs each room's own non-weekend median (per room, per date)."""
    today = date.today()
    end = today + timedelta(days=WINDOW_DAYS)
    # room -> date -> list of (price, weekend flag) across snapshots
    hist = {}
    for s in snaps:
        for rid, r in s["rooms"].items():
            if r.get("meta", {}).get("own"):
                continue
            for n in r.get("nights", []):
                dt = n["date"]
                if today.isoformat() <= dt <= end.isoformat():
                    p = night_price(n)
                    if p:
                        hist.setdefault(rid, {}).setdefault(dt, []).append((p, bool(n.get("is_weekend"))))
    per_date_premiums = {}
    for rid, days in hist.items():
        base_prices = [p for ps in days.values() for p, wk in ps if not wk]
        if len(base_prices) < 3:
            continue
        base = sorted(base_prices)[len(base_prices)//2]
        for dt, ps in days.items():
            p = sorted(x for x, _ in ps)[len(ps)//2]
            prem = pct(p, base)
            if prem is not None:
                per_date_premiums.setdefault(dt, []).append(prem)
    rows = {}
    for dt, prems in sorted(per_date_premiums.items()):
        d = date.fromisoformat(dt)
        rows[dt] = {
            "weekday": d.weekday(),
            "is_weekend": d.weekday() >= 4,  # Fri=4, Sat=5 (Iranian weekend)
            "avg_premium": round(sum(prems)/len(prems), 1),
            "median_premium": sorted(prems)[len(prems)//2],
            "n_rooms": len(prems),
        }
    return rows


# ---------- Signal 5: discount census + repricing ----------
def repricing(snaps):
    today = date.today()
    events = []
    prev = None
    for s in snaps:
        if prev:
            for rid, r in s["rooms"].items():
                pr = prev["rooms"].get(rid)
                if not pr or r.get("meta", {}).get("own"):
                    continue
                prev_n = {n["date"]: n for n in pr.get("nights", [])}
                for n in r.get("nights", []):
                    dt = n["date"]
                    if dt < today.isoformat():
                        continue
                    p0 = night_price(prev_n.get(dt, {}))
                    p1 = night_price(n)
                    if p0 and p1 and p0 != p1:
                        events.append({
                            "room_id": int(rid) if rid.isdigit() else rid,
                            "room": r["meta"].get("title", "")[:40],
                            "date": dt,
                            "old": p0, "new": p1,
                            "change_pct": pct(p1, p0),
                            "snapshot": s["date"],
                        })
        prev = s
    return {"events": events}


def discount_census(sweep):
    from collections import Counter
    c = Counter()
    by_type = Counter()
    vals = Counter()
    for r in sweep["rooms"].values():
        for d in r.get("discounts") or []:
            t = d.get("type")
            by_type[t] += 1
            vals[(t, d.get("percent"), d.get("min_nights"))] += 1
        if r.get("current_discount_percent"):
            c["current"] += 1
    return {"rooms": len(sweep["rooms"]), "by_type": dict(by_type),
            "values": {f"{t}/{p}%/{mn}n": n for (t, p, mn), n in vals.most_common(12)},
            "current_active": c["current"]}


# ---------- Signals 6 & 10 from sweep ----------
def amenity_roi(sweep):
    """Feature -> rooms median price + avg success_books + count."""
    from collections import defaultdict
    groups = defaultdict(list)
    for r in sweep["rooms"].values():
        p = r.get("min_price")
        if not p or r.get("status") != "active":
            continue
        groups["_all"].append(r)
        for f in r.get("features") or []:
            groups[f].append(r)
    feat_names = {
        "jacuzzibathtub": "جکوزی", "swimmingpool": "استخر", "barbecue": "باربیکیو",
        "pool": "استخر", "playyard": "زمین بازی", "lounge": "فرش/نشیمن",
    }
    rows = []
    all_prices = [r["min_price"] for r in groups["_all"]]
    all_books = [r.get("success_books") or 0 for r in groups["_all"]]
    def med(v):
        s = sorted(v)
        return s[len(s)//2] if s else None
    base_p, base_b = med(all_prices), sum(all_books)/max(len(all_books), 1)
    for f, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        prices = [r["min_price"] for r in rs]
        books = [r.get("success_books") or 0 for r in rs]
        rows.append({
            "feature": f, "fa": feat_names.get(f, f),
            "n": len(rs),
            "median_price": med(prices),
            "price_premium_pct": pct(med(prices), base_p),
            "avg_books": round(sum(books)/len(rs), 1),
            "books_vs_market_pct": pct(round(sum(books)/len(rs), 1), round(base_b, 1)),
        })
    return {"base_median_price": base_p, "rows": rows}


def badge_effect(sweep):
    from collections import defaultdict
    out = {}
    combos = defaultdict(list)
    for r in sweep["rooms"].values():
        if not r.get("min_price") or r.get("status") != "active":
            continue
        key = (bool(r.get("is_instant")), bool(r.get("is_plus")), bool(r.get("is_clean")), bool(r.get("is_new")))
        combos[key].append(r)
    labels = {
        (True, True, False, False): "فوری + پلاس",
        (False, True, False, False): "فقط پلاس",
        (True, False, False, False): "فقط فوری",
        (False, False, False, False): "بدون بج",
        (False, False, False, True): "جدید",
    }
    for key, rs in sorted(combos.items(), key=lambda kv: -len(kv[1])):
        books = [r.get("success_books") or 0 for r in rs]
        prices = [r["min_price"] for r in rs]
        s = sorted(books)
        out[labels.get(key, str(key))] = {
            "n": len(rs),
            "median_books": s[len(s)//2],
            "avg_books": round(sum(books)/len(rs), 1),
            "median_price": sorted(prices)[len(prices)//2],
        }
    return out


def main():
    snaps = load_snapshots()
    hp = holiday_premium_v2(snaps)
    sw_path = SIG / f"market_sweep_{date.today().isoformat()}.json"
    sweep = json.load(open(sw_path, encoding="utf-8")) if sw_path.exists() else None
    rep = repricing(snaps)
    out = {
        "generated": date.today().isoformat(),
        "snapshots_used": [s["date"] for s in snaps],
        "holiday_premium": hp,
        "repricing_events_tail": sorted(rep["events"], key=lambda e: e["snapshot"])[-120:],
        "repricing_events_total": len(rep["events"]),
        "discount_census": discount_census(sweep),
        "amenity_roi": amenity_roi(sweep),
        "badge_effect": badge_effect(sweep),
    }
    json.dump(out, open(SIG / "signals_computed.json", "w", encoding="utf-8"), ensure_ascii=False)
    # summary print
    wk = {d: r for d, r in hp.items() if r["is_weekend"]}
    print("premium rows:", len(hp), "| weekend rows:", len(wk))
    for d, r in list(hp.items())[:40]:
        tag = "WK" if r["is_weekend"] else "  "
        print(f"  {d} {tag} avg {r['avg_premium']:>6}%  med {r['median_premium']:>6}%  n={r['n_rooms']}")
    print("repricing events:", out["repricing_events_total"])
    print("discount census:", json.dumps(out["discount_census"], ensure_ascii=False))
    print("badge_effect:", json.dumps(out["badge_effect"], ensure_ascii=False)[:800])
    print("top amenities:", json.dumps(out["amenity_roi"]["rows"][:6], ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
