"""Sweep the full Jajiga cottage catalog and find rooms closest to
~600 bookings / ~400 reviews / 5.0 rating."""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://api.jajiga.com/api/search"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
TOTAL = 2863
PER = 18
PAGES = (TOTAL + PER - 1) // PER


def fetch(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == retries - 1:
                return None
            time.sleep(2 * (attempt + 1))


def main():
    rooms = {}
    for page in range(1, PAGES + 1):
        # pagination lives INSIDE the url param
        target = f"https://www.jajiga.com/s/cottage?page={page}"
        q = urllib.parse.urlencode(
            {"per_page": PER, "page": 1, "url": target, "with[]": "rooms"}
        )
        d = fetch(f"{BASE}?{q}")
        if not d or not d.get("rooms") or not d["rooms"].get("items"):
            print(f"page {page}: FAIL/EMPTY", file=sys.stderr)
            continue
        items = d["rooms"]["items"]
        for it in items:
            rid = it["id"]
            rating = it.get("rating") or {}
            rooms[rid] = {
                "id": rid,
                "title": it.get("title", ""),
                "province": it.get("province_name", ""),
                "city": it.get("city_name", ""),
                "price": it.get("price"),
                "books": it.get("success_books", 0),
                "rating": rating.get("total"),
                "reviews": rating.get("count", 0),
                "url": f"https://www.jajiga.com/room/{rid}",
            }
        if page % 20 == 0 or page == PAGES:
            print(f"swept {page}/{PAGES}, collected {len(rooms)}", file=sys.stderr)

    print(f"\nTOTAL COLLECTED: {len(rooms)}", file=sys.stderr)
    with open("data/top_rooms_sweep.json", "w", encoding="utf-8") as f:
        json.dump(list(rooms.values()), f, ensure_ascii=False, indent=1)

    # ranking: distance to target (600 books, 400 reviews, 5.0)
    ranked = sorted(
        rooms.values(),
        key=lambda r: (
            abs((r["books"] or 0) - 600)
            + abs((r["reviews"] or 0) - 400)
            + abs((r["rating"] or 0) - 5.0) * 100
        ),
    )
    print("\n=== TOP 20 CLOSEST to 600/400/5.0 ===")
    for r in ranked[:20]:
        print(
            f"id={r['id']} | {r['title'][:55]} | {r['city']} | "
            f"رزرو={r['books']} | نظر={r['reviews']} | امتیاز={r['rating']} | قیمت={r['price']}"
        )

    print("\n=== BEST: books>=500 AND reviews>=250 sorted by score ===")
    for r in ranked:
        if (r["books"] or 0) >= 500 and (r["reviews"] or 0) >= 250:
            print(
                f"id={r['id']} | {r['title'][:55]} | {r['city']} | "
                f"رزرو={r['books']} | نظر={r['reviews']} | امتیاز={r['rating']}"
            )


if __name__ == "__main__":
    main()
