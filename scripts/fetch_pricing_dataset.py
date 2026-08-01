"""Fetch FULL pricing-factor data for Jajiga villages and build a merged dataset.

Phase 1 of the pricing algorithm project (NO analysis yet — data collection only).

For each cabin in all-cabins.json for the given villages:
  - GET api.jajiga.com/api/room/{id}  -> features, properties, sub-ratings, geo,
    land_area, discounts, cancellation, pictures, vr/video, types/regions, host
  - merge existing tracker fields (occupancy_30, pool, jacuzzi, own)

Usage:
  python scripts/fetch_pricing_dataset.py                      # all villages
  python scripts/fetch_pricing_dataset.py --villages سیدکلا,گونه کلا

Outputs:
  data/pricing/{slug}_raw/{id}.json       full API JSON per room (raw)
  data/pricing/{slug}-pricing.json        per-village merged factor dataset
  data/pricing/pricing-dataset.json       ALL villages combined (with village field)
  data/pricing/pricing-dataset.csv        flat CSV (one row per room)
"""
import json, os, sys, time, random, csv, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CABINS = os.path.join(ROOT, "data", "all-cabins.json")
API = "https://api.jajiga.com/api/room/{}"
PRICING_DIR = os.path.join(ROOT, "data", "pricing")
OUT_JSON = os.path.join(PRICING_DIR, "pricing-dataset.json")
OUT_CSV = os.path.join(PRICING_DIR, "pricing-dataset.csv")

# village -> (persian name, slug)
VILLAGES = {
    "سیدکلا": "seydkola",
    "گونه کلا": "gonehkola",
    "قرآن تالار": "quran_talar",
    "شیردارکلا": "shirdarkola",
}

def fetch(url, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == retries - 1:
                print(f"  FAIL {url}: {e}")
                return None
            time.sleep(5 * (i + 1))

def feature_persian(features):
    """Map feature keys to their Persian names/descriptions."""
    names = {}
    for f in features or []:
        key = f.get("name", "")
        desc = f.get("description")
        if desc:
            names[key] = desc
        else:
            names[key] = key
    return names

def extract(room, tracker, village):
    """Extract the factor dataset from a full room API response."""
    ratings = room.get("ratings") or {}
    host = room.get("host") or {}
    pics = room.get("pictures") or []
    disc = room.get("discounts") or []
    return {
        "id": room.get("id"),
        "village": village,
        "title": room.get("title"),
        "url": f"https://www.jajiga.com/room/{room.get('id')}",
        "status": room.get("status"),
        # --- physical ---
        "bedrooms": room.get("bedrooms"),
        "floor_area": room.get("floor_area"),
        "land_area": room.get("land_area"),
        "floors_count": room.get("floors_count"),
        "guest_number": room.get("guest_number"),
        "max_guest_number": room.get("max_guest_number"),
        "sleep_arrange": room.get("sleep_arrange"),
        "types": room.get("types") or [],
        "regions": room.get("regions") or [],
        "stays_min": room.get("stays_min"),
        "stays_max": room.get("stays_max"),
        # --- price ---
        "min_price": room.get("min_price"),
        "extra_price": room.get("extra_price"),
        "cancellation_policy": room.get("cancellation_policy"),
        # --- badges ---
        "is_plus": room.get("is_plus"),
        "is_instant": room.get("is_instant"),
        "is_clean": room.get("is_clean"),
        "is_new": room.get("is_new"),
        "properties": [p.get("name") for p in (room.get("properties") or [])],
        # --- amenities ---
        "features": sorted(feature_persian(room.get("features") or []).keys()),
        "feature_desc": feature_persian(room.get("features") or []),
        "features_count": len(room.get("features") or []),
        # --- trust/demand ---
        "success_books": room.get("success_books"),
        "rating": ratings.get("total"),
        "reviews": ratings.get("count"),
        "rating_accuracy": ratings.get("accuracy"),
        "rating_communication": ratings.get("communication"),
        "rating_cleanliness": ratings.get("cleanliness"),
        "rating_location": ratings.get("location"),
        "rating_checkin": ratings.get("checkin"),
        "rating_value": ratings.get("value"),
        "is_recently": ratings.get("is_recently"),
        "is_bad_host": ratings.get("is_bad_host"),
        # --- discounts ---
        "current_discount_percent": room.get("current_discount_percent"),
        "current_discount": room.get("current_discount"),
        "discounts": disc,
        # --- media ---
        "pictures_count": len(pics),
        "vr_photo": room.get("vr_photo"),
        "video_url": room.get("video_url"),
        # --- location ---
        "geo": room.get("geo"),
        # --- host ---
        "host_id": host.get("id"),
        "host_name": host.get("name"),
        "host_gender": host.get("gender"),
        "host_created_at": host.get("created_at"),
        "host_accept_rate": host.get("accept_rate"),
        "host_response_time": host.get("response_time"),
        "host_communication_rate": host.get("host_communication_rate"),
        # --- tracker extras ---
        "occupancy_30": tracker.get("occupancy_30"),
        "occupancy_30_unavailable": tracker.get("occupancy_30_unavailable"),
        "occupancy_30_total": tracker.get("occupancy_30_total"),
        "pool": tracker.get("pool", 0),
        "jacuzzi": tracker.get("jacuzzi", 0),
        "own": tracker.get("own", False),
    }

def main():
    os.makedirs(PRICING_DIR, exist_ok=True)

    # which villages to fetch
    if "--villages" in sys.argv:
        idx = sys.argv.index("--villages")
        wanted = [v.strip() for v in sys.argv[idx + 1].split(",") if v.strip()]
    else:
        wanted = list(VILLAGES.keys())

    with open(CABINS, encoding="utf-8") as f:
        cabins = json.load(f)
    villages = cabins["villages"]

    all_data = []
    total_ok = 0
    total_all = 0
    for village in wanted:
        slug = VILLAGES.get(village, village)
        raw_dir = os.path.join(PRICING_DIR, f"{slug}_raw")
        os.makedirs(raw_dir, exist_ok=True)
        out_json = os.path.join(PRICING_DIR, f"{slug}-pricing.json")

        items = villages.get(village, [])
        print(f"\n=== {village} ({slug}): {len(items)} cabins ===")
        total_all += len(items)

        dataset = []
        ok = 0
        for i, cabin in enumerate(items):
            rid = cabin["id"]
            print(f"  [{i+1}/{len(items)}] fetching {rid} ...")
            raw = fetch(API.format(rid))
            if raw:
                with open(os.path.join(raw_dir, f"{rid}.json"), "w", encoding="utf-8") as f:
                    json.dump(raw, f, ensure_ascii=False, indent=1)
                rec = extract(raw, cabin, village)
                rec["village_slug"] = slug
                dataset.append(rec)
                ok += 1
            else:
                # keep tracker fields only (fallback record)
                rec = {
                    "id": rid, "village": village, "village_slug": slug,
                    "title": cabin.get("title"),
                    "url": f"https://www.jajiga.com/room/{rid}",
                    "status": "fetch_failed",
                    "min_price": cabin.get("price"),
                    "occupancy_30": cabin.get("occupancy_30"),
                    "occupancy_30_unavailable": cabin.get("occupancy_30_unavailable"),
                    "occupancy_30_total": cabin.get("occupancy_30_total"),
                    "pool": cabin.get("pool", 0), "jacuzzi": cabin.get("jacuzzi", 0),
                    "own": cabin.get("own", False),
                }
                dataset.append(rec)
            time.sleep(random.uniform(2.0, 4.0))

        dataset.sort(key=lambda r: (r.get("min_price") is None, r.get("min_price") or 0))
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=1)
        print(f"  Saved {ok}/{len(items)} to {out_json}")
        total_ok += ok
        all_data.extend(dataset)

    # combined dataset (sorted by village then price)
    all_data.sort(key=lambda r: (r.get("village", ""), r.get("min_price") is None, r.get("min_price") or 0))
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=1)
    print(f"\nCombined: {total_ok}/{total_all} -> {OUT_JSON}")

    # CSV (flat; amenities as | joined)
    if all_data:
        flat_keys = [k for k in all_data[0].keys() if k not in ("features", "feature_desc", "discounts", "types", "regions", "properties", "geo")]
        with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=flat_keys + ["features", "properties", "geo_lat", "geo_lng", "discounts"])
            w.writeheader()
            for r in all_data:
                row = {k: r.get(k) for k in flat_keys}
                row["features"] = "|".join(r.get("features") or [])
                row["properties"] = "|".join(r.get("properties") or [])
                geo = r.get("geo") or {}
                row["geo_lat"] = geo.get("lat")
                row["geo_lng"] = geo.get("lng")
                row["discounts"] = json.dumps(r.get("discounts") or [], ensure_ascii=False)
                w.writerow(row)
        print(f"CSV saved: {OUT_CSV}")

if __name__ == "__main__":
    main()
