#!/usr/bin/env python3
"""Сбор цен на зубные пасты и щётки в магазинах (dm, Rossmann, Teta, Kaufland, Lidl).

Запускается в GitHub Actions (из среды Claude сайты магазинов закрыты):
    python tools/prices_fetch.py            # дата = сегодня (UTC)
Пишет сырые данные в data/prices/raw/ГГГГ-ММ-ДД.json; затем tools/prices_build.py
превращает их в data/prices/ГГГГ-ММ-ДД.json (+ .csv) и обновляет manifest.json.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import time
import traceback
import urllib.parse

try:
    from curl_cffi import requests as http
    KW = {'impersonate': 'chrome'}
except ImportError:  # локальная отладка
    import requests as http
    KW = {}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANDS = ['splat', 'biomed', 'elmex', 'sensodyne', 'biorepair', 'colgate', 'parodontax',
          'lacalut', 'odol', 'marvis', 'curaprox']
BRAND_RE = re.compile(r'(?i)\b(splat|biomed|elmex|sensodyne|biorepair|colgate|parodontax|paradontax|lacalut|odol|marvis|curaprox)')
S = http.Session()
UA = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'}
LOG = []


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def get(url, tries=6, **kw):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, headers={**UA, **kw.pop('headers', {})}, timeout=60, **KW, **kw)
            if r.status_code == 429:
                time.sleep(20 * (i + 1)); last = r; continue
            return r
        except Exception as e:  # сеть
            last = e
            time.sleep(4 * (i + 1))
    if isinstance(last, Exception):
        raise last
    return last


def num(s):
    """'1 299 Ft' / '3,45 €' / '98.90 Kč' -> float"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = html.unescape(str(s)).replace('\xa0', ' ').replace(' ', ' ')
    m = re.search(r'\d[\d .,]*', s)
    if not m:
        return None
    t = m.group(0).strip().replace(' ', '')
    if ',' in t and '.' in t:
        t = t.replace('.', '').replace(',', '.')
    elif ',' in t:
        t = t.replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
        t = t.replace('.', '')
    try:
        return float(t)
    except ValueError:
        return None


def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


ITEMS, STATUS, MISSED = [], {}, []


def add(country, store, **kw):
    kw.update(country=country, store=store)
    ITEMS.append(kw)


def status(country, store, st, url, note=''):
    STATUS[f'{country}/{store}'] = {'status': st, 'url': url, 'note': note,
                                   'count': sum(1 for x in ITEMS if x['country'] == country and x['store'] == store)}
    log(f'[{country}/{store}] {st} {STATUS[country + "/" + store]["count"]} {note}')


# ---------------- dm ----------------
DM = {'de': ('de', 'EUR'), 'at': ('at', 'EUR'), 'cz': ('cz', 'CZK'), 'sk': ('sk', 'EUR'), 'hu': ('hu', 'HUF')}


def fetch_dm(c):
    tld, cur = DM[c]
    seen = set()
    for b in BRANDS:
        page = 0
        while True:
            u = f'https://product-search.services.dmtech.com/{tld}/search?query={b}&searchType=product&pageSize=60&currentPage={page}'
            r = get(u)
            if r.status_code != 200:
                log('dm', c, b, r.status_code); MISSED.append(f'{c}/dm/{b}'); break
            d = r.json()
            for p in d.get('products', []):
                t = p['tileData']
                if p['dan'] in seen:
                    continue
                seen.add(p['dan'])
                pr = t.get('price', {}).get('price', {})
                add(c, 'dm', brand_raw=p.get('brandName') or t.get('brand', {}).get('name'),
                    title=t.get('title', {}).get('tileHeadline') or p.get('title'),
                    price=num(pr.get('current', {}).get('value')),
                    old_price=num((pr.get('previous') or pr.get('strikethrough') or {}).get('value')) if isinstance(pr.get('previous') or pr.get('strikethrough'), dict) else None,
                    promo_text='; '.join(e.get('alt', '') for e in t.get('eyecatchers', []) if e.get('alt')),
                    unit=' '.join(t.get('price', {}).get('tileInfos', [])),
                    category=', '.join(t.get('trackingData', {}).get('categories', [])),
                    currency=cur, url=f'https://www.dm.{tld}' + t.get('self', ''), gtin=str(p.get('gtin', '')))
            page += 1
            if page >= d.get('totalPages', 0) or page > 6:
                break
            time.sleep(3)
        time.sleep(3)
    miss = [m.split('/')[-1] for m in MISSED if m.startswith(c + '/dm/')]
    status(c, 'dm', 'ok', f'https://www.dm.{tld}/', ('не загрузились бренды: ' + ', '.join(miss)) if miss else '')


# ---------------- Rossmann CZ ----------------
def fetch_rossmann_cz():
    for b in BRANDS:
        u = f'https://www.rossmann.cz/vyhledavani$d4063-search.xml?query={b}&async=true&limit=200&offset=0'
        r = get(u)
        if r.status_code != 200:
            log('rossmann cz', b, r.status_code); continue
        s = r.text
        for tile in s.split('<div class="product-tile"')[1:]:
            href = re.search(r'href="(/[^"]+)" class="product-tile__image"', tile)
            title = re.search(r'product-tile__title">\s*<a[^>]*>(.*?)</a>', tile, re.S)
            brand = re.search(r'product-tile__sub--title">(.*?)</span>', tile, re.S)
            amount = re.search(r'product-tile__sub--amount">(.*?)</span>', tile, re.S)
            fin = re.search(r'product-tile__price--final">(.*?)</span>\s*</div>', tile, re.S)
            club = re.search(r'product-tile__price--club">(.*?)</span>', tile, re.S)
            if not (title and fin):
                continue
            ft = fin.group(1)
            orig = re.search(r'<s>(.*?)</s>', ft)
            cur_p = re.findall(r'<div>(.*?)</div>', ft)
            stick = [clean(x) for x in re.findall(r'class="sticker[^"]*" title="([^"]*)"', tile)]
            pct = re.findall(r'data-val="([^"]+)"', tile)
            promo = [x for x in stick if x not in ('VEGAN', 'NEJ!', 'NOVINKA', 'NOVÉ')] + pct
            clubt = clean(club.group(1)) if club else ''
            if clubt:
                promo.append('Rossmann Club: ' + clubt)
            add('cz', 'rossmann', brand_raw=clean(brand.group(1)) if brand else '', title=clean(title.group(1)),
                price=num(cur_p[-1]) if cur_p else None, old_price=num(orig.group(1)) if orig else None,
                promo_text='; '.join(dict.fromkeys(promo)), unit=clean(amount.group(1)) if amount else '',
                currency='CZK', url='https://www.rossmann.cz' + href.group(1) if href else '')
        time.sleep(1)
    status('cz', 'rossmann', 'ok', 'https://www.rossmann.cz/')


# ---------------- Rossmann HU ----------------
def fetch_rossmann_hu():
    seen = set()
    for cat in ['szajapolas/fogkremek', 'szajapolas/fogkremek/fogkrem', 'szajapolas/fogkefek', 'szajapolas/fogkefek/hagyomanyos-fogkefek',
                'szajapolas/gyermek-szajapolas', 'szajapolas/gyermek-szajapolas/gyerek-fogkremek-es-szajvizek',
                'szajapolas/gyermek-szajapolas/hagyomanyos-gyerek-fogkefe', 'szajapolas/fogfeheritok']:
        page, last, first_ids = 1, 1, None
        while page <= last and page <= 20:
            u = f'https://shop.rossmann.hu/kategoria/{cat}' + (f'?page={page}' if page > 1 else '')
            r = get(u)
            if r.status_code != 200:
                log('rossmann hu', u, r.status_code); break
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
            pp = json.loads(m.group(1))['props']['pageProps']
            last = pp.get('initialPaginatorInfo', {}).get('lastPage', 1)
            ids = [p['id'] for p in pp.get('initialProducts', [])]
            if page > 1 and ids == first_ids:
                break
            first_ids = first_ids or ids
            for p in pp.get('initialProducts', []):
                if p['id'] in seen:
                    continue
                seen.add(p['id'])
                promo = [b.get('info') for b in p.get('badges_featured', []) if b.get('info')]
                add('hu', 'rossmann', brand_raw=(p.get('brand') or {}).get('name', ''), title=p.get('name'),
                    price=num(p.get('price')), old_price=num(p.get('price_original')),
                    card_price=num(p.get('price_rplus')), promo_text='; '.join(promo),
                    category=' / '.join(x['name'] for x in p.get('category_path_main', [])),
                    currency='HUF', url='https://shop.rossmann.hu/termek/' + p.get('slug', ''))
            page += 1
            time.sleep(1)
    status('hu', 'rossmann', 'ok', 'https://shop.rossmann.hu/kategoria/szajapolas',
           'сайт без браузера отдаёт только первые 24 товара каждой категории, поэтому список неполный')


# ---------------- Teta CZ ----------------
def fetch_teta_cz():
    for n in range(1, 30):
        u = 'https://www.tetadrogerie.cz/eshop/produkty/pece-o-zuby' + (f'?strana={n}' if n > 1 else '')
        r = get(u)
        if r.status_code != 200:
            break
        s = re.sub(r'<style.*?</style>|<svg.*?</svg>', '', r.text, flags=re.S)
        s = re.sub(r'<!--.*?-->| data-v-[0-9a-f]+', '', s)
        cards = s.split('<div class="c-product-card c-product-card--list">')[1:]
        if not cards:
            break
        for c in cards:
            href = re.search(r'href="(/eshop/katalog/[^"]+)"', c)
            t = re.search(r'c-product-card__title[^>]*>(.*?)<', c)
            former = re.search(r'c-product-price__former-price[^"]*">(.*?)</div>', c)
            val = re.search(r'c-product-price__value[^"]*"><strong>(.*?)</strong>', c)
            note = re.search(r'c-product-price__note[^"]*">(.*?)</div>', c)
            flags = re.search(r'c-product__flags">(.*?)</div></div>', c)
            if not t:
                continue
            fp, vp = num(former.group(1)) if former else None, num(val.group(1)) if val else None
            promo = [clean(flags.group(1)) if flags else '', clean(note.group(1)) if note else '']
            add('cz', 'teta', brand_raw='', title=clean(t.group(1)),
                price=vp if vp is not None else fp, old_price=fp if (fp and vp and vp < fp) else None,
                promo_text='; '.join(x for x in promo if x), currency='CZK',
                url='https://www.tetadrogerie.cz' + href.group(1) if href else u)
        time.sleep(1)
    status('cz', 'teta', 'ok', 'https://www.tetadrogerie.cz/eshop/produkty/pece-o-zuby')


# ---------------- Teta SK ----------------
def fetch_teta_sk():
    for cat in ['T166-Zubne-pasty', 'T167-Zubne-kefky']:
        prev = None
        for n in range(0, 30):
            u = f'https://www.tetadrogerie.sk/produkty/{cat}/' + (f'?nparams=page;{n}' if n else '')
            r = get(u)
            if r.status_code != 200:
                break
            tiles = r.text.split('<div class="dlazdice ')[1:]
            ids = re.findall(r'<div class="dlazdice [^"]*" data-kod_id="(\d+)"', r.text)
            if not tiles or ids == prev:
                break
            prev = ids
            for c in tiles:
                href = re.search(r'href="(/produkty/[^"]+)"', c)
                t = re.search(r'class="nazov"[^>]*>(.*?)</a>', c, re.S)
                old = re.search(r'class="old_price">(.*?)</div>', c, re.S)
                cena = re.search(r'class="cena(?: [^"]*)?">(.*?)</div>', c, re.S)
                bub = re.search(r'class="bublinka">(.*?)</div>', c, re.S)
                low = re.search(r'class="min_cena_30">(.*?)</div>', c, re.S)
                if not (t and cena):
                    continue
                promo = [clean(bub.group(1)) if bub else '']
                add('sk', 'teta', brand_raw='', title=clean(t.group(1)), price=num(clean(cena.group(1))),
                    old_price=num(clean(old.group(1))) if old else None,
                    promo_text='; '.join(x for x in promo if x), note=clean(low.group(1)) if low else '',
                    currency='EUR', url='https://www.tetadrogerie.sk' + href.group(1) if href else u)
            time.sleep(1)
    status('sk', 'teta', 'ok', 'https://www.tetadrogerie.sk/produkty/T166-Zubne-pasty/')


# ---------------- Lidl ----------------
LIDL = {'de': ('de', 'DE', 'de_DE', 'EUR'), 'at': ('at', 'AT', 'de_AT', 'EUR'), 'ch': ('ch', 'CH', 'de_CH', 'CHF'),
        'cz': ('cz', 'CZ', 'cs_CZ', 'CZK'), 'sk': ('sk', 'SK', 'sk_SK', 'EUR'), 'hu': ('hu', 'HU', 'hu_HU', 'HUF')}


def fetch_lidl(c):
    tld, asg, loc, cur = LIDL[c]
    seen = set()
    for b in BRANDS:
        u = f'https://www.lidl.{tld}/q/api/search?assortment={asg}&locale={loc}&version=v2.0.0&q={b}&fetchsize=100'
        r = get(u)
        if r.status_code != 200:
            log('lidl', c, b, r.status_code); continue
        for it in r.json().get('items', []):
            g = it.get('gridbox', {}).get('data', {})
            br = g.get('brand', {}).get('name') if isinstance(g.get('brand'), dict) else (g.get('brand') or '')
            title = g.get('fullTitle') or g.get('title') or ''
            if not BRAND_RE.search(f'{br} {title}'):
                continue
            key = g.get('productId') or g.get('erpNumber') or title
            if key in seen:
                continue
            seen.add(key)
            pr = g.get('price') or {}
            disc = pr.get('discount') or {}
            lp = g.get('lidlPlus') or []
            promo = [disc.get('discountText') or (f"-{disc['percentageDiscount']} %" if disc.get('percentageDiscount') else '')]
            for rb in g.get('ribbons') or []:
                promo.append(rb.get('text', ''))
            if pr.get('packaging', {}).get('text'):
                unit = pr['packaging']['text']
            else:
                unit = ''
            st = g.get('stockAvailability', {}).get('badgeInfo', {}).get('badges', [])
            dates = ' '.join(x.get('text', '') for x in st if isinstance(x, dict))
            add(c, 'lidl', brand_raw=br, title=title, price=num(pr.get('price')),
                old_price=num(disc.get('deletedPrice') or pr.get('oldPrice')) or None,
                promo_text='; '.join(x for x in promo if x), unit=unit, note=dates, category=g.get('category', ''),
                currency=cur, url=f'https://www.lidl.{tld}' + (g.get('canonicalPath') or g.get('canonicalUrl') or ''))
        time.sleep(1)
    status(c, 'lidl', 'ok', f'https://www.lidl.{tld}/')


# ---------------- Kaufland (только акции недели) ----------------
KAUF = {'de': ('https://filiale.kaufland.de/angebote/uebersicht.html', 'EUR'),
        'cz': ('https://prodejny.kaufland.cz/nabidka/prehled.html', 'CZK'),
        'sk': ('https://predajne.kaufland.sk/aktualna-ponuka/prehlad.html', 'EUR')}


def fetch_kaufland(c):
    u, cur = KAUF[c]
    seen = set()
    for week in ['', '?kloffer-week=next']:
        r = get(u + week)
        if r.status_code != 200:
            log('kaufland', c, week, r.status_code)
            if not week:
                status(c, 'kaufland', 'blocked', u, f'HTTP {r.status_code}')
                return
            continue
        for o in re.findall(r'\{"offerId":.*?"formattedPrice":"[^"]*"\}', r.text):
            try:
                o = json.loads(o)
            except ValueError:
                continue
            text = f"{o.get('title', '')} {o.get('subtitle', '')} {o.get('detailTitle', '')}"
            if not BRAND_RE.search(text) or o['offerId'] in seen:
                continue
            seen.add(o['offerId'])
            promo = []
            if o.get('discount'):
                promo.append(f"-{o['discount']} %")
            if o.get('loyaltyFormattedPrice'):
                promo.append('с Kaufland Card: ' + o['loyaltyFormattedPrice'].replace('*', ''))
            if o.get('bbyMessage'):
                promo.append(', '.join(o['bbyMessage']))
            promo.append(f"акция {o.get('salesFrom') or o.get('dateFrom')} – {o.get('salesTo') or o.get('dateTo')}")
            add(c, 'kaufland', brand_raw=o.get('title', ''),
                title=clean(f"{o.get('title', '')} {o.get('subtitle', '')}".replace('\n', ' ')),
                description=clean(o.get('detailDescription', '')), unit=o.get('unit', ''),
                price=num(o.get('price')), old_price=num(o.get('formattedOldPrice')),
                card_price=num(o.get('loyaltyFormattedPrice')), promo_text='; '.join(promo),
                date_from=o.get('salesFrom') or o.get('dateFrom'), date_to=o.get('salesTo') or o.get('dateTo'),
                currency=cur, url=u)
    status(c, 'kaufland', 'ok', u, 'только товары из еженедельной акционной листовки')


# ---------------- Rossmann DE ----------------
def fetch_rossmann_de():
    u = 'https://www.rossmann.de/de/search/?text=elmex'
    r = get(u)
    if 'Client Challenge' in r.text or r.status_code != 200:
        status('de', 'rossmann', 'blocked', 'https://www.rossmann.de/', 'сайт закрыт защитой от ботов (Client Challenge)')
        return
    status('de', 'rossmann', 'blocked', 'https://www.rossmann.de/', 'страница открылась, но разбор не настроен')


def fx_rates():
    try:
        r = get('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml')
        rates = dict(re.findall(r"currency='([A-Z]{3})' rate='([\d.]+)'", r.text))
        day = re.search(r"time='([\d-]+)'", r.text).group(1)
        return {'date': day, 'source': 'ЕЦБ', 'EUR': 1.0, **{k: float(v) for k, v in rates.items() if k in ('CZK', 'HUF', 'CHF', 'USD')}}
    except Exception as e:
        log('fx error', e)
        return None


JOBS = [('de', 'dm', lambda: fetch_dm('de')), ('cz', 'rossmann', fetch_rossmann_cz), ('at', 'dm', lambda: fetch_dm('at')),
        ('hu', 'rossmann', fetch_rossmann_hu), ('cz', 'dm', lambda: fetch_dm('cz')), ('cz', 'teta', fetch_teta_cz),
        ('sk', 'dm', lambda: fetch_dm('sk')), ('sk', 'teta', fetch_teta_sk), ('hu', 'dm', lambda: fetch_dm('hu')),
        ('de', 'rossmann', fetch_rossmann_de),
        *[(c, 'lidl', (lambda c=c: fetch_lidl(c))) for c in LIDL],
        *[(c, 'kaufland', (lambda c=c: fetch_kaufland(c))) for c in KAUF]]


def main():
    day = sys.argv[1] if len(sys.argv) > 1 else dt.datetime.utcnow().strftime('%Y-%m-%d')
    only = set(sys.argv[2:])
    for c, st, fn in JOBS:
        if only and f'{c}/{st}' not in only:
            continue
        try:
            fn()
        except Exception as e:
            traceback.print_exc()
            STATUS[f'{c}/{st}'] = {'status': 'error', 'url': '', 'note': f'{type(e).__name__}: {e}'[:300], 'count': 0}
    out = {'date': day, 'fetched_at': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
           'fx': fx_rates(), 'status': STATUS, 'missed': MISSED, 'items': ITEMS, 'log': LOG[-200:]}
    os.makedirs(os.path.join(ROOT, 'data/prices/raw'), exist_ok=True)
    with open(os.path.join(ROOT, f'data/prices/raw/{day}.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    log('items', len(ITEMS))


if __name__ == '__main__':
    main()
