"""Fetch ALL reviews for a Jajiga room and produce authenticity stats."""
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def fetch(url, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == retries - 1:
                print(f"ERR {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (attempt + 1))


def main():
    room_id = sys.argv[1] if len(sys.argv) > 1 else "3151760"
    per_page = 10
    page = 1
    all_reviews = []
    total = None
    while True:
        d = fetch(
            f"https://api.jajiga.com/api/room/{room_id}/reviews"
            f"?page={page}&per_page={per_page}"
        )
        if not d:
            break
        items = d.get("items") or []
        if total is None:
            total = d.get("pagination", {}).get("total")
        if not items:
            break
        all_reviews.extend(items)
        if total and len(all_reviews) >= total:
            break
        page += 1
        time.sleep(0.7)

    print(f"collected {len(all_reviews)} reviews (api total={total})", file=sys.stderr)
    with open(f"data/reviews/{room_id}_reviews.json", "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, ensure_ascii=False, indent=1)

    # ---------- stats ----------
    ratings = Counter(round(r.get("rating", 0), 1) for r in all_reviews)
    print(f"\n=== {room_id}: {len(all_reviews)} نظر ===")
    print("توزیع امتیاز هر نظر:", dict(sorted(ratings.items(), reverse=True)))

    dates = sorted(r.get("created_at", "") for r in all_reviews)
    print(f"اولین نظر: {dates[0][:10]} | آخرین نظر: {dates[-1][:10]}" if dates else "بدون تاریخ")
    months = Counter(d[:7] for d in dates)
    months_sorted = sorted(months.items())
    print("نظر در هر ماه:")
    for m, c in months_sorted:
        print(f"  {m}: {c}")

    review_per_rating = Counter(r.get("rating", 0) for r in all_reviews)
    not5 = [r for r in all_reviews if round(r.get("rating", 5), 1) < 5]
    print(f"\nتعداد نظرات زیر 5: {len(not5)}")
    for r in sorted(not5, key=lambda x: x.get("rating", 0))[:10]:
        print(f"  {r.get('rating')} | {r.get('created_at','')[:10]} | {r.get('user',{}).get('name','?')} | {r.get('content','')[:80]}")

    users = Counter(r.get("user", {}).get("id") for r in all_reviews)
    dup_users = {u: c for u, c in users.items() if c > 1}
    print(f"\nکاربر یکتا: {len(users)} | کاربرانی که چند نظر دادن: {len(dup_users)}")
    for u, c in sorted(dup_users.items(), key=lambda x: -x[1])[:5]:
        name = next((r.get("user", {}).get("name") for r in all_reviews if r.get("user", {}).get("id") == u), "?")
        print(f"  {name} (id={u}): {c} نظر")

    replied = sum(1 for r in all_reviews if r.get("host_reply"))
    print(f"\nپاسخ میزبان به نظرات: {replied}/{len(all_reviews)} ({replied*100//max(len(all_reviews),1)}%)")

    # keyword signals
    texts = " ".join(r.get("content", "") for r in all_reviews)
    kw = ["استخر", "جکوزی", "تمیز", "آب گرم", "پول", "گرون", "ارزون", "منظره",
          "میزبان", "برخورد", "راهنمایی", "سکوت", "طبیعت", "رفته", "قیمت", "خیلی خوب", "پیشنهاد"]
    print("\nکلیدواژه‌های پرتکرار در متن نظرها:")
    for k in kw:
        print(f"  {k}: {texts.count(k)}")


if __name__ == "__main__":
    main()
