# -*- coding: utf-8 -*-
"""Mechanical keyword-based theme classifier — runs on 100% of the corpus.
Baseline distribution to complement LLM sample tagging.
Output: data/reviews_mining/keyword_stats.json + per-review tags data/reviews_mining/keyword_tags.json"""
import glob
import json
import sys
import io
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "data/reviews_mining"

POS_WORDS = ["عالی", "ممنون", "تشکر", "دوست داشتیم", "بی نظیر", "بینظیر", "لذت", "پیشنهاد",
             "تمیز", "مرتب", "خوشبرخورد", "مهمان نواز", "مهمان‌نواز", "قشنگ", "خوب بود", "راحت"]
NEG_WORDS = ["بد", "کثیف", "نظافت نبود", "خراب", "شکایت", "متأسف", "متاسف", "تکرار نمیکنم",
             "تکرار نمی", "پشیمون", "پشیمان", "ضعف", "مشکل", "سرد بود", "گرم نبود", "قطع بود",
             "نبود", "کسل", "کیفی نبود"]


def sentiment_of(text):
    p = sum(1 for w in POS_WORDS if w in text)
    n = sum(1 for w in NEG_WORDS if w in text)
    if p and not n:
        return "pos"
    if n and not p:
        return "neg"
    if n and p:
        return "mixed"
    return "neutral"


def main():
    tax = json.load(open(f"{BASE}/taxonomy.json", encoding="utf-8"))
    kw_map = [(t["id"], t["fa"], t["keywords"]) for t in tax["themes"] if t["id"] != "other"]

    corpus = json.load(open(f"{BASE}/corpus.json", encoding="utf-8"))
    theme_hits = Counter()
    theme_sent = defaultdict(Counter)
    theme_prov = defaultdict(Counter)
    theme_year = defaultdict(Counter)
    sent_total = Counter()
    per_review = {}

    for r in corpus:
        text = (r.get("content") or "")
        if not text:
            continue
        sent = sentiment_of(text)
        sent_total[sent] += 1
        hits = []
        for tid, _, kws in kw_map:
            if any(k in text for k in kws):
                hits.append(tid)
        # max 2 themes: keep ones with most distinct keyword matches
        scored = [(tid, sum(1 for k in kws if k in text)) for tid, _, kws in kw_map
                  if any(k in text for k in kws)]
        scored.sort(key=lambda x: -x[1])
        for tid, _ in scored[:2]:
            theme_hits[tid] += 1
            theme_sent[tid][sent] += 1
            theme_prov[tid][r.get("province") or "?"] += 1
            theme_year[tid][(r.get("created_at") or "????")[:4]] += 1
        per_review[f"{r['room_id']}:{r['review_id']}"] = {"themes": [t for t, _ in scored[:2]],
                                                          "kw_sentiment": sent}

    json.dump(per_review, open(f"{BASE}/keyword_tags.json", "w", encoding="utf-8"),
              ensure_ascii=False)
    stats = {
        "corpus": len(corpus),
        "classified": len(per_review),
        "sentiment_total": dict(sent_total),
        "themes": [{"id": tid, "fa": fa, "count": theme_hits[tid],
                    "sent": dict(theme_sent[tid]), "by_province": dict(theme_prov[tid].most_common(5)),
                    "by_year": dict(sorted(theme_year[tid].items()))}
                   for tid, fa in [(t[0], t[1]) for t in kw_map] if theme_hits[tid]],
    }
    json.dump(stats, open(f"{BASE}/keyword_stats.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"classified {len(per_review)} / {len(corpus)} reviews")
    print("sentiment:", dict(sent_total))
    for t in stats["themes"]:
        print(f"  {t['fa']}: {t['count']}")


if __name__ == "__main__":
    main()
