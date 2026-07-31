#!/usr/bin/env python3
"""Build hosts-babolkenar.json from collected room + host profile data."""
import json
import os
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
TMP = '/tmp/jajiga'


def host_level(total_books):
    if total_books >= 200:
        return 'حرفه‌ای'
    if total_books >= 50:
        return 'فعال'
    if total_books >= 10:
        return 'تازه‌کار'
    return 'مبتدی'


def room_class(price):
    if price is None:
        return 'نامشخص'
    if price >= 4000000:
        return 'لوکس'
    if price >= 2500000:
        return 'ممتاز'
    if price >= 1500000:
        return 'استاندارد'
    return 'اقتصادی'


def main():
    rooms = json.load(open(os.path.join(TMP, 'rooms_detail.json'), encoding='utf-8'))
    profiles = json.load(open(os.path.join(TMP, 'host_profiles.json'), encoding='utf-8'))

    # 1) room-level info per host (from our direct room fetches)
    rooms_by_host = {}
    for r in rooms:
        hid = r.get('host_id')
        if not hid:
            continue
        rooms_by_host.setdefault(hid, []).append(r)

    # 2) merge with profile room lists (authoritative for all host rooms)
    hosts_out = []
    for hid, prof in profiles.items():
        if not prof.get('name'):
            continue
        profile_rooms = prof.get('rooms') or []
        # union of room ids from profile + our fetched rooms
        seen = set()
        room_list = []
        for pr in profile_rooms:
            rid = pr.get('id')
            if rid in seen:
                continue
            seen.add(rid)
            room_list.append({
                'id': rid,
                'title': pr.get('title'),
                'url': 'https://www.jajiga.com' + (pr.get('url') or f'/room/{rid}'),
                'city': pr.get('city'),
                'price': pr.get('min_price'),
                'class': room_class(pr.get('min_price')),
                'rating': (pr.get('rating') or {}).get('total'),
                'reviews': (pr.get('rating') or {}).get('count'),
                'success_books': pr.get('success_books'),
                'bedrooms': pr.get('bedrooms'),
                'floor_area': pr.get('floor_area'),
                'guests': [pr.get('guest_number'), pr.get('max_guest_number')],
                'is_plus': pr.get('is_plus'),
                'is_instant': pr.get('is_instant'),
                'is_clean': pr.get('is_clean'),
                'discount': pr.get('discount'),
            })
        # add our fetched rooms not present in profile
        for r in rooms_by_host.get(hid, []):
            rid = r['id']
            if rid in seen:
                continue
            seen.add(rid)
            room_list.append({
                'id': rid,
                'title': r.get('title'),
                'url': 'https://www.jajiga.com/room/' + str(rid),
                'city': r.get('city'),
                'price': r.get('min_price'),
                'class': room_class(r.get('min_price')),
                'rating': r.get('rating'),
                'reviews': r.get('reviews'),
                'success_books': r.get('success_books'),
                'bedrooms': r.get('bedrooms'),
                'floor_area': r.get('floor_area'),
                'guests': [r.get('guest_number'), r.get('max_guest_number')],
                'is_plus': r.get('is_plus'),
                'is_instant': r.get('is_instant'),
                'is_clean': r.get('is_clean'),
            })

        total_books = sum((x.get('success_books') or 0) for x in room_list)
        prices = [x['price'] for x in room_list if x.get('price')]
        hosts_out.append({
            'id': hid,
            'name': prof.get('name'),
            'gender': prof.get('gender'),
            'verified': prof.get('verified'),
            'member_since': prof.get('created_at'),
            'description': prof.get('description'),
            'accept_rate': prof.get('accept_rate'),
            'response_time_min': prof.get('response_time'),
            'communication_rate': prof.get('communication_rate'),
            'active_rooms_count': prof.get('active_rooms_count'),
            'rooms_count': len(room_list),
            'rooms': room_list,
            'total_success_books': total_books,
            'host_level': host_level(total_books),
            'price_range': [min(prices), max(prices)] if prices else None,
            'avg_price': sum(prices) // len(prices) if prices else None,
            'last_updated': date.today().isoformat(),
        })

    hosts_out.sort(key=lambda h: -(h['total_success_books']))
    out = {
        'meta': {
            'source': 'api.jajiga.com',
            'region': 'بابلکنار (مازندران)',
            'total_rooms_scraped': len(rooms),
            'total_hosts': len(hosts_out),
            'last_updated': date.today().isoformat(),
        },
        'hosts': hosts_out,
    }
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, 'hosts-babolkenar.json')
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved:', path)
    print('hosts:', len(hosts_out))
    # quick stats
    levels = {}
    for h in hosts_out:
        levels[h['host_level']] = levels.get(h['host_level'], 0) + 1
    print('levels:', levels)
    multi = [h for h in hosts_out if h['rooms_count'] > 1]
    print('multi-room hosts:', len(multi))


if __name__ == '__main__':
    main()
