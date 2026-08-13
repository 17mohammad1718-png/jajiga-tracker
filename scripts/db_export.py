#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db_export.py — export the unified jajiga.db back to a single lossless JSON
(jajiga_master.json). This is the file the master dashboard and any future
tooling read from. Does NOT modify the database or any source file.

Output shape:
  meta       — build + export metadata
  regions    — village list with counts
  hosts      — 346 full host records (raw)
  rooms      — 467 merged room records (flat + sources + tracked)
  nights     — {source: {room_id: [night,...]}}
  snapshots  — {kind: [{date, fetched_at, data}]}
  revenue    — 33 revenue records
  state      — parsed state blobs
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(ROOT, "jajiga.db")
OUT_PATH = os.path.join(ROOT, "jajiga_master.json")
VERSION = "1.0.0"


def main():
    if not os.path.exists(DB_PATH):
        print("jajiga.db not found — run scripts/db_build.py first", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    meta = {r["key"]: r["value"] for r in cur.execute("SELECT key,value FROM meta")}
    regions = [dict(r) for r in cur.execute("SELECT * FROM regions ORDER BY sort_order, name")]
    hosts = []
    for r in cur.execute("SELECT * FROM hosts"):
        raw = json.loads(r["raw"]) if r["raw"] else {}
        hosts.append(raw)
    rooms = []
    for r in cur.execute("SELECT * FROM rooms"):
        raw = json.loads(r["raw"]) if r["raw"] else {}
        raw["sources"] = r["sources"].split(",") if r["sources"] else []
        raw["tracked"] = bool(r["tracked"])
        raw["updated_at"] = r["updated_at"]
        rooms.append(raw)

    nights = {"radar": {}, "revenue": {}}
    for r in cur.execute("SELECT * FROM nights ORDER BY room_id, date"):
        src = r["source"]
        nights.setdefault(src, {})
        nights[src].setdefault(str(r["room_id"]), []).append({
            "date": r["date"], "price": r["price"], "discount": r["discount"],
            "is_unavailable": bool(r["is_unavailable"]), "is_instant": bool(r["is_instant"]),
            "is_peak": bool(r["is_peak"]), "is_holiday": bool(r["is_holiday"]),
            "is_weekend": bool(r["is_weekend"]),
        })

    snapshots = {"supply": [], "radar": []}
    for r in cur.execute("SELECT * FROM snapshots ORDER BY kind, date"):
        snapshots.setdefault(r["kind"], []).append({
            "date": r["date"], "fetched_at": r["fetched_at"], "data": json.loads(r["data"]),
        })

    revenue = []
    for r in cur.execute("SELECT * FROM revenue"):
        rec = json.loads(r["raw"]) if r["raw"] else {}
        rec["month"] = r["month"]
        revenue.append(rec)

    state = {}
    for r in cur.execute("SELECT key,value FROM state"):
        try:
            state[r["key"]] = json.loads(r["value"])
        except (TypeError, json.JSONDecodeError):
            state[r["key"]] = r["value"]

    con.close()

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = {
        "meta": {
            **meta,
            "exported_at": now,
            "export_version": VERSION,
            "structure_guide": {
                "regions": "list of village/region with counts",
                "hosts": "full host records (346)",
                "rooms": "merged room records (467) with sources list",
                "nights": "{source: {room_id: [night,...]}} — radar + revenue calendars",
                "snapshots": "{kind: [{date, fetched_at, data}]}",
                "revenue": "revenue estimation records",
                "state": "derived blobs (supply months, village_stats, radar_config, ...)",
            },
        },
        "regions": regions,
        "hosts": hosts,
        "rooms": rooms,
        "nights": nights,
        "snapshots": snapshots,
        "revenue": revenue,
        "state": state,
    }

    tmp = OUT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT_PATH)

    size = os.path.getsize(OUT_PATH)
    print(f"jajiga_master.json written: {OUT_PATH} ({size/1024/1024:.2f} MB)")
    print(f"  regions   {len(regions)}")
    print(f"  hosts     {len(hosts)}")
    print(f"  rooms     {len(rooms)}")
    print(f"  nights    radar {sum(len(v) for v in nights['radar'].values())} | revenue {sum(len(v) for v in nights['revenue'].values())}")
    print(f"  snapshots {sum(len(v) for v in snapshots.values())}")
    print(f"  revenue   {len(revenue)}")
    print(f"  state     {len(state)}")


if __name__ == "__main__":
    main()
