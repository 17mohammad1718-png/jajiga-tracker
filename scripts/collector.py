"""
Jajiga Collector — جمع‌آوری قیمت کلبه‌های بابلکنار
====================================================
Upgraded to Playwright for client-side rendered data extraction.

Usage:
    pip install playwright && playwright install chromium
    python collector.py                  # scrape all known listings
    python collector.py --discover       # also discover new listings from search pages

Extracts: title, price, rating, reviews, guests, bedrooms, area_sqm, base_price
"""

import json
import os
import re
import sys
import time
import random
import logging
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths (resolved relative to THIS file, not cwd)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(PROJECT_ROOT, "data", "all-cabins.json")
BASE_URL = "https://www.jajiga.com"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}
DELAY_MIN = 2.0   # seconds between requests
DELAY_MAX = 4.0   # seconds between requests
MAX_RETRIES = 2
PAGE_TIMEOUT_MS = 30_000  # 30s to load

# Villages and their category URLs on jajiga.com
VILLAGES = {
    "سیدکلا":    "/s/seyyedkolababolkenar/cottage",
    "قرآن تالار": "/s?text=%D9%82%D8%B1%D8%A2%D9%86+%D8%AA%D8%A7%D9%84%D8%A7%D8%B1+%D8%A8%D8%A7%D8%A8%D9%84%DA%A9%D9%86%D8%A7%D8%B1",
    "گونه کلا":  "/s?text=%DA%AF%D9%88%D9%86%D9%87+%DA%A9%D9%84%D8%A7+%DA%A9%D9%84%D8%A8%D9%87",
    "شیردارکلا": "/s?text=%D8%B4%DB%8C%D8%B1%D8%AF%D8%A7%D8%B1%DA%A9%D9%84%D8%A7+%DA%A9%D9%84%D8%A8%D9%87",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("collector")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def parse_number(text):
    """Parse a Persian/English number string to int or None."""
    if not text:
        return None
    # Remove Persian/Arabic commas and thousand separators
    cleaned = text.replace("٬", "").replace(",", "").replace("\u200c", "").strip()
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    if not cleaned:
        return None
    try:
        val = float(cleaned) if "." in cleaned else int(cleaned)
        return val
    except ValueError:
        return None


def random_delay():
    """Sleep a random time between DELAY_MIN and DELAY_MAX."""
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


# ---------------------------------------------------------------------------
# Data extraction from a single room page
# ---------------------------------------------------------------------------
EXTRACT_JS = """
() => {
    const text = document.body.innerText || '';
    const result = {};

    // Title
    const h1 = document.querySelector('h1');
    result.title = h1 ? h1.textContent.trim() : null;

    // Code (room ID)
    const codeMatch = text.match(/کد:\\s*(\\d+)/);
    result.code = codeMatch ? parseInt(codeMatch[1]) : null;

    // Rating and review count
    // Pattern: "4.7\\n(54 نظر)"
    const ratingMatch = text.match(/(\\d+\\.\\d+)\\s*\\n\\s*\\((\\d+)\\s*نظر\\)/);
    if (ratingMatch) {
        result.rating = parseFloat(ratingMatch[1]);
        result.reviews = parseInt(ratingMatch[2]);
    } else {
        result.rating = null;
        result.reviews = null;
    }

    // Guests: "تا X مهمان"
    const guestsMatch = text.match(/تا\\s*(\\d+)\\s*مهمان/);
    result.guests = guestsMatch ? parseInt(guestsMatch[1]) : null;

    // Bedrooms: "X اتاق‌خواب" or "X اتاق خواب"
    const bedMatch = text.match(/(\\d+)\\s*اتاق\\s*خواب/);
    result.bedrooms = bedMatch ? parseInt(bedMatch[1]) : null;

    // Area: after bedrooms, look for "X متر\\n" then "زیربنا X متر"
    const areaMatch = text.match(/(\\d+)\\s*متر\\s*\\n\\s*زیربنا/);
    if (areaMatch) {
        result.area_sqm = parseInt(areaMatch[1]);
    } else {
        // Fallback: "X متر\\n" pattern
        const areaMatch2 = text.match(/(\\d+)\\s*متر\\s*\\n/);
        result.area_sqm = areaMatch2 ? parseInt(areaMatch2[1]) : null;
    }

    // Base price from calendar: prices are large numbers (>= 1,000,000)
    // Calendar shows "day price" pairs like "17 8٬100٬000"
    // Threshold of 1M filters out similar-listing sidebar prices (typically 200k)
    // and extra-guest surcharge text (100k-800k).
    const priceMatches = [...text.matchAll(/\\b(\\d+)\\s+([\\d۰-۹][٬\\d]*)\\b/g)];
    let basePrice = null;
    for (const m of priceMatches) {
        const day = parseInt(m[1]);
        const priceStr = m[2].replace(/[٬]/g, '');
        const price = parseInt(priceStr);
        if (day >= 1 && day <= 31 && price >= 1000000) {
            basePrice = price;
            break;  // take the first available day's price
        }
    }
    result.base_price = basePrice;

    // Standard + extra capacity: "6 نفر استاندارد + 4 نفر اضافه"
    const stdCapMatch = text.match(/(\\d+)\\s*نفر\\s*استاندارد\\s*\\+\\s*(\\d+)\\s*نفر\\s*اضافه/);
    if (stdCapMatch) {
        result.standard_capacity = parseInt(stdCapMatch[1]);
        result.extra_capacity = parseInt(stdCapMatch[2]);
    }

    return result;
}
"""


def scrape_room(page, room_id, retries=MAX_RETRIES):
    """Navigate to a room page and extract data. Returns dict or None on failure."""
    url = f"{BASE_URL}/room/{room_id}"

    for attempt in range(retries + 1):
        try:
            log.info(f"  Fetching room {room_id} (attempt {attempt + 1})")
            page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            # Wait for h1 to appear (indicates content loaded)
            page.wait_for_selector("h1", timeout=PAGE_TIMEOUT_MS)
            # Extra wait for JS-rendered content (calendar data is CSR)
            page.wait_for_timeout(4000)

            data = page.evaluate(EXTRACT_JS)

            # Validate we got something meaningful
            if not data.get("title"):
                raise ValueError("No title found — page may not have loaded correctly")

            data["id"] = room_id
            data["url"] = url
            return data

        except Exception as e:
            log.warning(f"  Attempt {attempt + 1} failed for room {room_id}: {e}")
            if attempt < retries:
                wait = (attempt + 1) * 5
                log.info(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                log.error(f"  All {retries + 1} attempts failed for room {room_id}")
                return None

    return None


# ---------------------------------------------------------------------------
# Discovery: find room IDs from listing pages
# ---------------------------------------------------------------------------
DISCOVER_JS = """
() => {
    const links = document.querySelectorAll('a[href*="/room/"]');
    const ids = new Set();
    links.forEach(a => {
        const match = a.href.match(/\\/room\\/(\\d+)/);
        if (match) ids.add(parseInt(match[1]));
    });
    return Array.from(ids);
}
"""


def discover_room_ids(page, max_pages=5):
    """Scrape listing pages to discover new room IDs."""
    all_ids = set()

    for village, url_path in VILLAGES.items():
        log.info(f"Discovering rooms in {village}...")
        for pg in range(1, max_pages + 1):
            url = f"{BASE_URL}{url_path}"
            if pg > 1:
                separator = "&" if "?" in url_path else "?"
                url = f"{BASE_URL}{url_path}{separator}page={pg}"

            try:
                page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
                page.wait_for_selector("a[href*='/room/']", timeout=PAGE_TIMEOUT_MS)
                page.wait_for_timeout(1500)

                ids = page.evaluate(DISCOVER_JS)
                new_ids = [i for i in ids if i not in all_ids]
                all_ids.update(ids)
                log.info(f"  Page {pg}: {len(ids)} rooms, {len(new_ids)} new")

                if not new_ids:
                    break  # no new rooms, stop paginating

                random_delay()

            except Exception as e:
                log.warning(f"  Page {pg} failed for {village}: {e}")
                break

    return all_ids


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------
def load_existing_data():
    """Load existing JSON data. Returns (meta_dict, villages_dict)."""
    if not os.path.exists(DATA_FILE):
        return {
            "last_updated": "",
            "source": "jajiga.com",
            "region": "بابلکنار",
            "type": "cottage (کلبه چوبی + کلبه سوئیسی)",
        }, {}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("meta", {})
    villages = data.get("villages", {})
    return meta, villages


# Fields the scraper is responsible for updating.
# Everything else in the existing record is preserved as-is.
SCRAPER_FIELDS = {
    "title", "url", "price", "price_source", "rating", "reviews",
    "guests", "rooms", "floor", "standard_capacity", "extra_capacity",
    "last_scrape_status", "last_scrape_attempt",
}

def merge_scraped_data(villages, scraped, room_id):
    """Merge scraped data into villages dict. Preserves ALL existing
    fields that the scraper doesn't explicitly manage — this means
    flags like is_own_listing, id_unverified, _note, or any custom
    metadata survive across scrape runs.
    Returns True if data was updated, False if listing not found."""
    for vname, cabins in villages.items():
        for cabin in cabins:
            if cabin["id"] == room_id:
                # Preserve everything the scraper doesn't own
                preserved = {k: v for k, v in cabin.items() if k not in SCRAPER_FIELDS}

                now_iso = datetime.now(timezone.utc).isoformat()
                cabin["title"] = scraped.get("title") or cabin.get("title")
                cabin["url"] = scraped.get("url") or cabin.get("url")

                if scraped.get("base_price") is not None:
                    cabin["price"] = scraped["base_price"]
                    cabin["price_source"] = "calendar_base"
                elif scraped.get("price") is not None:
                    cabin["price"] = scraped["price"]

                if scraped.get("rating") is not None:
                    cabin["rating"] = scraped["rating"]
                if scraped.get("reviews") is not None:
                    cabin["reviews"] = scraped["reviews"]

                if scraped.get("guests") is not None:
                    cabin["guests"] = scraped["guests"]
                if scraped.get("bedrooms") is not None:
                    cabin["rooms"] = scraped["bedrooms"]
                if scraped.get("area_sqm") is not None:
                    cabin["floor"] = scraped["area_sqm"]
                if scraped.get("standard_capacity") is not None:
                    cabin["standard_capacity"] = scraped["standard_capacity"]
                if scraped.get("extra_capacity") is not None:
                    cabin["extra_capacity"] = scraped["extra_capacity"]

                cabin["last_scrape_status"] = "ok"
                cabin["last_scrape_attempt"] = now_iso

                # Restore all non-scraper fields (handles is_own_listing etc.)
                cabin.update(preserved)
                return True

    return False  # room_id not found in any village


def mark_failed(villages, room_id):
    """Mark a failed scrape on an existing listing."""
    for vname, cabins in villages.items():
        for cabin in cabins:
            if cabin["id"] == room_id:
                now_iso = datetime.now(timezone.utc).isoformat()
                cabin["last_scrape_status"] = "failed"
                cabin["last_scrape_attempt"] = now_iso
                return True
    return False


def add_new_listing(villages, scraped, village_name="نامشخص"):
    """Add a newly discovered listing to the data."""
    if village_name not in villages:
        villages[village_name] = []

    now_iso = datetime.now(timezone.utc).isoformat()
    cabin = {
        "id": scraped.get("id"),
        "title": scraped.get("title", "نامشخص"),
        "price": scraped.get("base_price") or scraped.get("price") or 0,
        "rooms": scraped.get("bedrooms") or 0,
        "floor": scraped.get("area_sqm") or 0,
        "guests": scraped.get("guests") or 0,
        "rating": scraped.get("rating") or 0,
        "reviews": scraped.get("reviews") or 0,
        "url": scraped.get("url", f"{BASE_URL}/room/{scraped.get('id')}"),
        "last_scrape_status": "ok",
        "last_scrape_attempt": now_iso,
    }
    if scraped.get("base_price"):
        cabin["price_source"] = "calendar_base"
    if scraped.get("standard_capacity"):
        cabin["standard_capacity"] = scraped["standard_capacity"]
    if scraped.get("extra_capacity"):
        cabin["extra_capacity"] = scraped["extra_capacity"]

    villages[village_name].append(cabin)
    log.info(f"  Added new listing {cabin['id']} to {village_name}")


def save_data(meta, villages):
    """Write data to JSON file."""
    meta["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = {
        "meta": meta,
        "villages": villages,
    }
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info(f"Saved {sum(len(v) for v in villages.values())} listings to {DATA_FILE}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def collect_all_room_ids(villages):
    """Get all room IDs from existing data."""
    ids = set()
    for cabins in villages.values():
        for cabin in cabins:
            ids.add(cabin["id"])
    return ids


def main():
    discover_mode = "--discover" in sys.argv

    log.info("=" * 50)
    log.info("Jajiga Collector — Starting scrape run")
    log.info(f"Mode: {'discover + update' if discover_mode else 'update only'}")
    log.info("=" * 50)

    # Load existing data
    meta, villages = load_existing_data()
    existing_ids = collect_all_room_ids(villages)
    log.info(f"Loaded {len(existing_ids)} existing listings")

    # Discover new IDs if requested
    all_ids = set(existing_ids)
    if discover_mode:
        log.info("\n--- Discovery phase ---")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            new_ids = discover_room_ids(page)
            browser.close()

        discovered = new_ids - existing_ids
        all_ids = new_ids
        log.info(f"Discovery found {len(new_ids)} total IDs ({len(discovered)} new)")

    # Scrape each room
    log.info(f"\n--- Scraping {len(all_ids)} rooms ---")
    success = 0
    failed = 0

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])

        for i, room_id in enumerate(sorted(all_ids), 1):
            log.info(f"[{i}/{len(all_ids)}] Room {room_id}")

            scraped = scrape_room(page, room_id)

            if scraped and scraped.get("title"):
                # Check if this is a new listing
                if room_id not in existing_ids:
                    add_new_listing(villages, scraped)
                else:
                    merged = merge_scraped_data(villages, scraped, room_id)
                    if not merged:
                        log.warning(f"  Could not merge {room_id} — not found in villages")
                        # Still record as discovered
                        add_new_listing(villages, scraped)

                success += 1
                log.info(
                    f"  ✅ {scraped.get('title', '?')[:50]} | "
                    f"price={scraped.get('base_price')} | "
                    f"★{scraped.get('rating')} ({scraped.get('reviews')}) | "
                    f"{scraped.get('guests')} guests"
                )
            else:
                mark_failed(villages, room_id)
                failed += 1
                log.error(f"  ❌ Failed to scrape room {room_id}")

            # Rate limiting
            if i < len(all_ids):
                random_delay()

        browser.close()

    # Save
    save_data(meta, villages)

    log.info("\n" + "=" * 50)
    log.info(f"Run complete: {success} succeeded, {failed} failed")
    log.info("=" * 50)


if __name__ == "__main__":
    main()
