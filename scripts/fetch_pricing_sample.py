"""Fetch a small stratified sample of full room JSONs for pricing-factor research.

Usage: python scripts/fetch_pricing_sample.py [--n 10] [--out data/pricing/sample_raw]
Picks rooms across price classes (اقتصادی/استاندارد/ممتاز/لوکس) prioritizing feature
diversity (pool, jacuzzi, instant, plus). Saves FULL API JSON per room.
"""
import json, os, sys, time, random, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTS_DB = os.path.join(ROOT, "data", "hosts-babolkenar.json")
API = "https://api.jajiga.com/api/room/{}"

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

def main():
    n = 10
    out_dir = os.path.join(ROOT, "data", "pricing", "sample_raw")
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    if "--out" in sys.argv:
        out_dir = sys.argv[sys.argv.index("--out") + 1]
    os.makedirs(out_dir, exist_ok=True)

    with open(HOSTS_DB, encoding="utf-8") as f:
        hosts = json.load(f)
    rooms = []
    for h in hosts["hosts"]:
        for r in h["rooms"]:
            rooms.append({**r, "host_id": h["id"], "host_name": h["name"],
                          "host_level": h.get("host_level"), "member_since": h.get("member_since")})

    classes = ["اقتصادی", "استاندارد", "ممتاز", "لوکس"]
    per = max(1, n // len(classes))
    picked = []
    for cls in classes:
        pool = [r for r in rooms if r.get("class") == cls]
        # prefer diverse features: pool/jacuzzi first, then instant, then random
        pool.sort(key=lambda r: (-(1 if r.get("discount") else 0), r["price"]))
        picked.extend(pool[:per])
    # top-up with jacuzzi/pool rooms for feature diversity
    have = {r["id"] for r in picked}
    for r in rooms:
        if len(picked) >= n:
            break
        if r["id"] in have:
            continue
        if "استخر" in r.get("title", "") or "جکوزی" in r.get("title", ""):
            picked.append(r)
    picked = picked[:n]
    print(f"Sampling {len(picked)} rooms:")
    for r in picked:
        print(f"  {r['id']} | {r.get('class')} | {r.get('price'):,} | {r.get('title','')[:50]}")

    out = {}
    for i, r in enumerate(picked):
        rid = r["id"]
        print(f"[{i+1}/{len(picked)}] fetching {rid} ...")
        data = fetch(API.format(rid))
        if data:
            out[rid] = data
            with open(os.path.join(out_dir, f"{rid}.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        time.sleep(random.uniform(2.0, 4.0))

    print(f"\nSaved {len(out)}/{len(picked)} to {out_dir}")
    # Inventory of fields for the FIRST room
    if out:
        first = next(iter(out.values()))
        print("\n=== FULL FIELD INVENTORY (first room) ===")
        def walk(d, prefix=""):
            if isinstance(d, dict):
                for k, v in d.items():
                    walk(v, prefix + k + ".")
            elif isinstance(d, list):
                if d and isinstance(d[0], (dict, list)):
                    print(f"  {prefix.rstrip('.')}[] ({len(d)} items)")
                    walk(d[0], prefix)
                else:
                    print(f"  {prefix.rstrip('.')}[] = {d[:8]}")
            else:
                s = str(d)
                print(f"  {prefix.rstrip('.')} = {s[:70]}")
        walk(first)

if __name__ == "__main__":
    main()
