#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db_build.py — build the unified jajiga.db SQLite database from all existing
jajiga-tracker data files. Idempotent: drops and recreates the schema, then
re-inserts everything from the source files. Does NOT modify any source file.

Tables:
  meta       — build metadata (version, built_at, sources)
  regions    — village/region list (tracked villages + all village_stats)
  hosts      — 346 hosts (merged hosts-babolkenar + supply hosts)
  rooms      — unified rooms table (merged supply + all_cabins + pricing)
  nights     — per-night calendar rows (radar + revenue sources)
  snapshots  — supply + radar snapshots (raw JSON)
  revenue    — revenue estimation rows (seydkola-mordad-1405)
  state      — derived state blobs (supply months, village_stats, radar config, pricing meta)
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DB_PATH = os.path.join(ROOT, "jajiga.db")
VERSION = "1.0.0"


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def load_opt(rel):
    p = os.path.join(ROOT, rel)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def load_manual_blocks():
    """روزهای «بسته میزبان» (غیرمشتری) از data/manual-blocks.json.
    Returns dict: room_id_str -> set of ISO dates."""
    try:
        data = json.load(open(os.path.join(ROOT, "data", "manual-blocks.json"), encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for rid, dates in (data or {}).items():
        if isinstance(dates, list):
            out[str(rid)] = set(d for d in dates if isinstance(d, str))
    return out


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ---------------- load sources ----------------
    # اولویت با فایل‌های تازه است (supply-data امروز، all-cabins دیروز از اسکرپر هفتگی).
    # jajiga_complete_dataset.json فقط به‌عنوان fallback برای بخش‌هایی که فایل تازه ندارند.
    def first(*paths):
        for p in paths:
            if os.path.exists(os.path.join(ROOT, p)):
                return json.load(open(os.path.join(ROOT, p), encoding="utf-8"))
        return None

    supply = first("data/supply-data.json") or (complete["supply"] if (complete := load_opt("jajiga_complete_dataset.json")) else None) or load("data/supply-data.json")
    all_cabins = first("data/all-cabins.json") or (load_opt("jajiga_complete_dataset.json") or {}).get("all_cabins") or load("data/all-cabins.json")
    hosts_db = first("data/hosts-babolkenar.json") or (load_opt("jajiga_complete_dataset.json") or {}).get("hosts_db") or load("data/hosts-babolkenar.json")
    pricing = load("data/pricing/pricing-dataset.json")
    radar_config = load("data/radar/radar-config.json")
    revenue = load("data/revenue/seydkola-mordad-1405.json")

    # snapshot files
    supply_snap_paths = sorted(
        os.path.join(DATA, "snapshots", f) for f in os.listdir(os.path.join(DATA, "snapshots")) if f.startswith("supply-")
    )
    radar_snap_paths = sorted(
        os.path.join(DATA, "radar", "snapshots", f) for f in os.listdir(os.path.join(DATA, "radar", "snapshots")) if f.endswith(".json")
    )
    radar_room_paths = sorted(
        os.path.join(DATA, "radar", f) for f in os.listdir(os.path.join(DATA, "radar"))
        if f.endswith(".json") and f != "radar-config.json"
    )

    # ---------------- create db ----------------
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE regions (id INTEGER PRIMARY KEY, name TEXT UNIQUE, slug TEXT, count INTEGER, added_2026 INTEGER, tracked INTEGER DEFAULT 0, sort_order INTEGER DEFAULT 0);
    CREATE TABLE hosts (id INTEGER PRIMARY KEY, name TEXT, gender TEXT, verified INTEGER, member_since TEXT, description TEXT, accept_rate REAL, response_time_min INTEGER, communication_rate REAL, active_rooms_count INTEGER, rooms_count INTEGER, total_success_books INTEGER, host_level TEXT, price_range TEXT, avg_price REAL, last_updated TEXT, raw TEXT);
    CREATE TABLE rooms (id INTEGER PRIMARY KEY, title TEXT, village TEXT, host_id INTEGER, host_name TEXT, status TEXT, member_since TEXT, est_date TEXT, j_est TEXT, price INTEGER, success_books INTEGER, rating REAL, reviews INTEGER, tracked INTEGER DEFAULT 0, sources TEXT, raw TEXT, updated_at TEXT);
    CREATE TABLE nights (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER, date TEXT, price INTEGER, discount INTEGER, is_unavailable INTEGER, is_instant INTEGER, is_peak INTEGER, is_holiday INTEGER, is_weekend INTEGER, is_manual_block INTEGER DEFAULT 0, source TEXT, fetched_at TEXT, UNIQUE(room_id, date, source));
    CREATE TABLE snapshots (kind TEXT, date TEXT, fetched_at TEXT, data TEXT, UNIQUE(kind, date));
    CREATE TABLE revenue (id INTEGER PRIMARY KEY AUTOINCREMENT, room_id INTEGER, host_id INTEGER, title TEXT, month TEXT, booked INTEGER, free INTEGER, gross INTEGER, gross_discounted INTEGER, discount_total INTEGER, commission INTEGER, net INTEGER, raw TEXT);
    CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT);
    CREATE INDEX idx_rooms_village ON rooms(village);
    CREATE INDEX idx_rooms_host ON rooms(host_id);
    CREATE INDEX idx_nights_room_date ON nights(room_id, date);
    """)

    # ---------------- regions ----------------
    region_order = supply.get("meta", {}).get("tracked_villages", [])
    for i, name in enumerate(region_order):
        cur.execute("INSERT OR REPLACE INTO regions (name, tracked, sort_order) VALUES (?,1,?)", (name, i))
    for vs in supply.get("village_stats", []):
        cur.execute(
            "INSERT OR REPLACE INTO regions (name, count, added_2026, tracked) VALUES (?,?,?,COALESCE((SELECT tracked FROM regions WHERE name=?),0))",
            (vs["name"], vs.get("count"), vs.get("added_2026"), vs["name"]),
        )

    # ---------------- hosts ----------------
    host_map = {}  # id -> merged dict
    for h in hosts_db.get("hosts", []):
        hid = int(h["id"])
        host_map[hid] = dict(h)
    for h in supply.get("hosts", []):
        hid = int(h["id"])
        if hid not in host_map:
            host_map[hid] = dict(h)
        else:  # supply host may have fresh price_range/avg_price — merge missing fields only
            for k, v in h.items():
                if k not in host_map[hid] or host_map[hid][k] is None:
                    host_map[hid][k] = v
    for hid, h in sorted(host_map.items()):
        def s(v):
            return v if v is None or isinstance(v, (int, float, str)) else json.dumps(v, ensure_ascii=False)
        cur.execute(
            """INSERT OR REPLACE INTO hosts
            (id,name,gender,verified,member_since,description,accept_rate,response_time_min,communication_rate,
             active_rooms_count,rooms_count,total_success_books,host_level,price_range,avg_price,last_updated,raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                hid, s(h.get("name")), s(h.get("gender")),
                1 if h.get("verified") else 0 if "verified" in h else None,
                s(h.get("member_since")), s(h.get("description")),
                s(h.get("accept_rate")), s(h.get("response_time_min")), s(h.get("communication_rate")),
                s(h.get("active_rooms_count")), s(h.get("rooms_count")), s(h.get("total_success_books")),
                s(h.get("host_level")), s(h.get("price_range")), s(h.get("avg_price")),
                s(h.get("last_updated")), json.dumps(h, ensure_ascii=False),
            ),
        )

    # ---------------- rooms (merged) ----------------
    def _hid(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    rooms = {}
    for r in supply.get("rooms", []):
        rid = int(r["id"])
        rooms[rid] = dict(r)
        rooms[rid]["sources"] = ["supply"]
    for vname, vlist in all_cabins.get("villages", {}).items():
        for r in vlist:
            rid = int(r["id"])
            if rid in rooms:
                rooms[rid].update({k: r[k] for k in ("price", "rating", "reviews", "success_books", "active") if k in r})
                rooms[rid]["village"] = vname  # tracked-village attribution wins
                rooms[rid]["sources"].append("cabin")
            else:
                rooms[rid] = dict(r)
                rooms[rid]["village"] = vname
                rooms[rid]["sources"] = ["cabin"]
                rooms[rid].setdefault("title", r.get("title"))
    for r in pricing:
        rid = int(r["id"])
        if rid in rooms:
            rooms[rid].update({k: r[k] for k in ("price", "rating", "reviews", "success_books", "status", "village") if k in r})
            rooms[rid]["sources"].append("pricing")
        else:
            rooms[rid] = dict(r)
            rooms[rid]["sources"] = ["pricing"]
        rooms[rid].setdefault("host_id", _hid(r.get("host_id")))
        rooms[rid].setdefault("host_name", r.get("host_name"))

    for rid, r in sorted(rooms.items()):
        cur.execute(
            """INSERT OR REPLACE INTO rooms
            (id,title,village,host_id,host_name,status,member_since,est_date,j_est,price,success_books,rating,reviews,tracked,sources,raw,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid, r.get("title"), r.get("village"), _hid(r.get("host_id")), r.get("host_name"),
                r.get("status"), r.get("member_since"), r.get("est_date"), r.get("j_est"),
                r.get("price") or r.get("min_price"), r.get("success_books"), r.get("rating"), r.get("reviews"),
                1 if r.get("tracked") else 0,
                ",".join(sorted(set(r["sources"]))),
                json.dumps(r, ensure_ascii=False), now,
            ),
        )

    # ---------------- nights (radar + revenue) ----------------
    manual_blocks = load_manual_blocks()
    for path in radar_room_paths:
        f = load_opt(os.path.relpath(path, ROOT))
        rid = int(f["room_id"])
        blocked_dates = manual_blocks.get(str(rid), set())
        for n in f.get("nights", []):
            cur.execute(
                """INSERT OR IGNORE INTO nights
                (room_id,date,price,discount,is_unavailable,is_instant,is_peak,is_holiday,is_weekend,is_manual_block,source,fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, n.get("date"), n.get("price"), n.get("discount"),
                 1 if n.get("is_unavailable") else 0, 1 if n.get("is_instant") else 0,
                 1 if n.get("is_peak") else 0, 1 if n.get("is_holiday") else 0, 1 if n.get("is_weekend") else 0,
                 1 if (n.get("date") in blocked_dates or n.get("is_manual_block")) else 0,
                 "radar", f.get("fetched_at")),
            )
    for rec in revenue:
        rid = int(rec["id"])
        blocked_dates = manual_blocks.get(str(rid), set())
        for n in rec.get("nights", []):
            cur.execute(
                """INSERT OR IGNORE INTO nights
                (room_id,date,price,discount,is_unavailable,is_instant,is_peak,is_holiday,is_weekend,is_manual_block,source,fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (rid, n.get("date"), n.get("price"), n.get("discount"),
                 1 if n.get("is_unavailable") else 0, 1 if n.get("is_instant") else 0,
                 1 if n.get("is_peak") else 0, 1 if n.get("is_holiday") else 0, 1 if n.get("is_weekend") else 0,
                 1 if (n.get("date") in blocked_dates or n.get("is_manual_block")) else 0,
                 "revenue", None),
            )

    # ---------------- snapshots ----------------
    for path in supply_snap_paths:
        name = os.path.basename(path)
        date = name.replace("supply-", "").replace(".json", "")
        d = json.load(open(path, encoding="utf-8"))
        cur.execute("INSERT OR REPLACE INTO snapshots (kind,date,fetched_at,data) VALUES ('supply',?,?,?)",
                    (date, d.get("date") or date, json.dumps(d, ensure_ascii=False)))
    for path in radar_snap_paths:
        name = os.path.basename(path)
        date = name.replace(".json", "")
        d = json.load(open(path, encoding="utf-8"))
        cur.execute("INSERT OR REPLACE INTO snapshots (kind,date,fetched_at,data) VALUES ('radar',?,?,?)",
                    (date, d.get("fetched_at"), json.dumps(d, ensure_ascii=False)))

    # ---------------- revenue ----------------
    for rec in revenue:
        cur.execute(
            """INSERT INTO revenue (room_id,host_id,title,month,booked,free,gross,gross_discounted,discount_total,commission,net,raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (int(rec["id"]), _hid(rec.get("host_id")), rec.get("title"), "mordad-1405",
             rec.get("booked"), rec.get("free"), rec.get("gross"), rec.get("gross_discounted"),
             rec.get("discount_total"), rec.get("commission"), rec.get("net"),
             json.dumps(rec, ensure_ascii=False)),
        )

    # ---------------- state ----------------
    state_blobs = {
        "supply_meta": supply.get("meta", {}),
        "supply_months": supply.get("months", []),
        "village_stats": supply.get("village_stats", []),
        "radar_config": radar_config,
        "pricing_meta": {"count": len(pricing), "file": "data/pricing/pricing-dataset.json"},
        "hosts_db_meta": hosts_db.get("meta", {}),
        "all_cabins_meta": all_cabins.get("meta", {}),
    }
    for k, v in state_blobs.items():
        cur.execute("INSERT OR REPLACE INTO state (key,value) VALUES (?,?)", (k, json.dumps(v, ensure_ascii=False)))

    # ---------------- meta ----------------
    cur.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (VERSION,))
    cur.execute("INSERT OR REPLACE INTO meta VALUES ('built_at', ?)", (now,))
    cur.execute("INSERT OR REPLACE INTO meta VALUES ('project', 'jajiga-tracker')")
    cur.execute("INSERT OR REPLACE INTO meta VALUES ('region', ?)", (supply.get("meta", {}).get("region", "بابلکنار (مازندران)"),))

    con.commit()

    # ---------------- verify ----------------
    counts = {}
    for t in ("regions", "hosts", "rooms", "nights", "snapshots", "revenue", "state"):
        counts[t] = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    con.close()

    expected = {
        "hosts": len(host_map),
        "rooms": len(rooms),
        "revenue": len(revenue),
        "snapshots": len(supply_snap_paths) + len(radar_snap_paths),
        "state": len(state_blobs),
    }
    ok = True
    for k, exp in expected.items():
        if counts[k] != exp:
            ok = False
            print(f"  !! MISMATCH {k}: db={counts[k]} source={exp}")
    print(f"jajiga.db built at {DB_PATH}")
    for k in ("regions", "hosts", "rooms", "nights", "snapshots", "revenue", "state"):
        print(f"  {k:10s} {counts[k]:>6}")
    print("VERIFY:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
