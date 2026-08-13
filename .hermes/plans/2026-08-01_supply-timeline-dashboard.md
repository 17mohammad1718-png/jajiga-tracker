# Supply Timeline Dashboard (بابلکنار) — Implementation Plan

> **For Hermes:** Execute this plan task-by-task directly in this session after user approval ("go").

**Goal:** A new single-file dashboard showing how the supply of hosts and accommodations in Babolkenar has grown over time, with a timeline — built from real Jajiga data.

**Architecture:**
- Historical dates: hosts already carry `member_since` in `data/hosts-babolkenar.json` (346 hosts). Rooms have no `created_at`, so we backfill an *estimated* listing date from the earliest `pictures[].created_at` (photo upload) via `/api/room/{id}` (fallback: earliest review via `/api/room/{id}/reviews`).
- Forward accuracy: a daily snapshot script records the full Babolkenar room-id set + search-API market counts. Diffing snapshots gives *exact* added/removed dates from today onward.
- Dashboard: `supply-dashboard.html` — single-file, RTL, dark, **no external dependencies** (inline SVG charts), following all established Jajiga dashboard conventions (English digits in monospace, centered cells, 3-state sort, medals, sticky headers, Jalali dates).

**Tech Stack:** Python 3.11 (stdlib only: urllib, json, re) + single-file HTML (inline SVG/JS, zero CDN).

---

## Data facts (verified 2026-08-01)

| Signal | Source | Meaning |
|---|---|---|
| `host.member_since` | already in `data/hosts-babolkenar.json` ("2019-06-20") | host joined Jajiga — **exact** |
| `pictures[].created_at` | `/api/room/{id}` ("2026-04-09") | earliest photo upload ≈ listing creation — **estimate** |
| review `created_at` | `/api/room/{id}/reviews` | earliest review = evidence room existed — **estimate** |
| sitemap `<lastmod>` | absent | no signal, skip |
| search API `meta.rooms_count` | `/api/search?per_page=1&url=...` | market size: `/s/babolkenar` → 510, `/s/babolkenar/cottage` → 329 |
| snapshot diff | daily script | exact added/removed going forward |

Universe: 346 hosts / 459+ rooms (union of `hosts-babolkenar.json` + `all-cabins.json` room ids).

---

## Task 1: Backfill room estimated dates

**Files:**
- Create: `scripts/supply_backfill.py`
- Output: `data/supply/room-dates.json`

**Objective:** For every unique room id (union of hosts DB + all-cabins), fetch `/api/room/{id}` (2–4s delay, retry ×3, ONE stream — WinError 10061 rule), extract:
- `first_photo` = min of `pictures[].created_at`
- `first_review` = earliest review date — only if no pictures (rare): fetch last page of reviews (`pagination.total` → last page) and take min `created_at`
- `est_date` = min(first_photo, first_review) or null
- `host_id`, `status` (active/inactive)

**Verification:**
```bash
python scripts/supply_backfill.py --limit 5   # quick test on 5 rooms
python scripts/supply_backfill.py             # full run (~460 rooms, ~20-30 min)
python -c "import json;d=json.load(open('data/supply/room-dates.json',encoding='utf-8'));print(len(d), sum(1 for v in d.values() if v['est_date']))"
```
Expected: `>= 450`, `>= 440` dated. Sample: room 3297585 → `first_photo: 2026-04-09`.

## Task 2: Build the supply dataset

**Files:**
- Create: `scripts/supply_build.py`
- Output: `data/supply-data.json`, inject into `supply-dashboard.html` (replace `__DATA__` marker)

**Objective:** Merge hosts DB + room-dates.json into one payload:
- per room: `id, title, village` (existing pattern dict, longest-match first), `host_id, host_name, member_since, est_date, status, price, success_books`
- per host: `id, name, member_since, rooms_count, total_books, host_level, first_room_date` (min est_date of their rooms)
- monthly series (Gregorian → Jalali month labels via the proven `g2j` from hosts dashboard v3.1): rooms added/month, hosts joined/month, cumulative both
- village breakdown: current count + added this year

**Verification:** run `python scripts/supply_build.py` → prints summary (total hosts/rooms, date range, rooms with est_date, count of undated); check `data/supply-data.json` shape with python.

## Task 3: Build the dashboard

**Files:**
- Create: `supply-dashboard.html` (repo root, next to `dashboard.html` / `hosts-dashboard.html`)

**Sections (RTL, dark, no external deps):**
1. Hero: title + scope chips (بابلکنار · 346 میزبان · 459 اقامتگاه · تاریخ بروزرسانی)
2. KPI cards: total hosts / total rooms / added this month (rooms, hosts) / avg rooms per month
3. **Cumulative supply area chart** (inline SVG): rooms curve + hosts curve, monthly, Jalali labels
4. **New per month bar chart** (inline SVG): rooms/month + hosts/month
5. **Timeline** (vertical, per month): hosts joined + rooms added events, Jalali month/year headers
6. Village cards: count + added-this-year per village (6 tracked + بابلکنار مرکزی/سایر)
7. Sortable tables: **newest hosts** (member_since desc) + **newest rooms** (est_date desc) — full conventions: `#` rank medal top-3, `en` monospace digits, center cells (name right), 3-state sort cycle, no inner scrollbar
8. Caveat footer (Persian): dates before 2026-08-01 are estimates from photo/review evidence; from snapshot start they are exact.

**Verification:** open `supply-dashboard.html` in browser; console asserts (row counts, sort toggles, svg path length > 0); screenshot to confirm rendering. Known anchors: host فتحعلی member_since 2019-06-20 → oldest group; own listing est 2026-04-09 → recent group.

## Task 4: Daily snapshot script

**Files:**
- Create: `scripts/supply_snapshot.py`
- Output: `data/snapshots/supply-YYYY-MM-DD.json` `{date, meta_counts:{babolkenar, cottage}, room_ids[]}`
- Thin launcher: `~/AppData/Local/hermes/scripts/supply_snapshot.py` → subprocess to project script (cron path rule)

**Objective:** catalog sweep `/s/babolkenar?page=1..N` (in-url pagination, ~26 requests, ~2 min) + 2 market-stats calls; diff vs previous snapshot → prints `+N added, -M removed` with ids.

**Verification:** `python scripts/supply_snapshot.py` → new file + diff output; run twice → second run shows `+0 added`.

## Task 5: Cron automation

- `cronjob action=list` first (orphan-duplicate pitfall) — check existing `weekly_update` job.
- Create daily job: `0 9 * * *` → `scripts/supply_snapshot.py` (no_agent=True, silent when no change, alert on diff).
- Create weekly job: Sunday 10:00 → backfill new rooms (supply_backfill incremental) + `supply_build.py` + report summary (agent mode, Persian summary).

**Verification:** `cronjob action=list` → both jobs `ok`, next_run correct.

---

## Scope

**IN:** supply timeline dashboard (hosts + rooms), date backfill, daily snapshots, cron, `data/supply/`, `data/snapshots/`.
**OUT:** changes to `dashboard.html` / `hosts-dashboard.html`; Telegram reporting; price/occupancy analysis; host-DB rebuild.

## Risks / Mitigations

1. **Photo date ≠ creation date** (old listing re-photographed, or first photos deleted) → label estimates clearly; min(photo, review); snapshots give exact data forward.
2. **Backfill rate limits / network flakiness** (~460 calls, WinError 10051/10061) → 2–4s delays, retry ×3, single stream, resumable (skip ids already in output).
3. **Jalali conversion bugs** → reuse the exact verified `g2j` function from hosts-dashboard v3.1 (2019-06-20 → خرداد 1398 anchor test).
4. **Undated rooms** (no pictures/reviews, e.g. inactive) → "تاریخ نامشخص" group + not counted in monthly series.
5. **Churn** (rooms removed historically) → not recoverable; only forward diffs track removals — documented in caveats.
