#!/usr/bin/env python3
"""Цены Notino по странам Европы (раздел «Цены → Пан-Европа → Notino»).

Запуск в GitHub Actions (Notino закрыт Cloudflare; проходит curl_cffi с отпечатком браузера):
    python tools/notino_fetch.py [ДАТА] [de cz ...]
Пишет data/prices/notino/ДАТА.json и ДАТА.csv, обновляет data/prices/notino/manifest.json.
Один и тот же товар в разных странах сопоставляется по коду Notino (productCode).
"""
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
import time

from curl_cffi import requests as http

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data/prices/notino')
# код страны -> (домен, название)
SITES = [
    ('de', 'notino.de', 'Германия'), ('at', 'notino.at', 'Австрия'), ('ch', 'notino.ch', 'Швейцария'),
    ('cz', 'notino.cz', 'Чехия'), ('sk', 'notino.sk', 'Словакия'), ('hu', 'notino.hu', 'Венгрия'),
    ('pl', 'notino.pl', 'Польша'), ('si', 'notino.si', 'Словения'), ('hr', 'notino.hr', 'Хорватия'),
    ('ro', 'notino.ro', 'Румыния'), ('bg', 'notino.bg', 'Болгария'), ('it', 'notino.it', 'Италия'),
    ('es', 'notino.es', 'Испания'), ('pt', 'notino.pt', 'Португалия'), ('fr', 'notino.fr', 'Франция'),
    ('be', 'notino.be', 'Бельгия'), ('nl', 'notino.nl', 'Нидерланды'), ('gr', 'notino.gr', 'Греция'),
    ('ie', 'notino.ie', 'Ирландия'), ('uk', 'notino.co.uk', 'Великобритания'), ('dk', 'notino.dk', 'Дания'),
    ('se', 'notino.se', 'Швеция'), ('fi', 'notino.fi', 'Финляндия'),
    ('lt', 'notino.lt', 'Литва'), ('lv', 'notino.lv', 'Латвия'), ('ee', 'notino.ee', 'Эстония')]
BRANDS = [('SPLAT', ['splat']), ('Biomed', ['biomed', 'splat-biomed']), ('Elmex', ['elmex']),
          ('Sensodyne', ['sensodyne']), ('Biorepair', ['biorepair']), ('Colgate', ['colgate']),
          ('Parodontax', ['parodontax']), ('Lacalut', ['lacalut']), ('Odol', ['odol', 'odol-med3']),
          ('Marvis', ['marvis']), ('Curaprox', ['curaprox'])]
TYPES = {'Toothpastes': 'paste', 'Toothbrushes': 'brush'}
S = http.Session()
LOG = []


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def get(url):
    last = None
    for imp in ['safari', 'chrome', 'firefox', 'safari', 'chrome']:
        try:
            r = S.get(url, impersonate=imp, timeout=60)
        except Exception as e:
            last = e; time.sleep(3); continue
        if r.status_code == 404:
            return r
        if r.status_code == 200 and 'Just a moment' not in r.text[:3000]:
            return r
        last = r
        time.sleep(4)
    return last


def listing(html):
    i = html.find('"numberOfProducts"')
    if i < 0:
        return None, None
    a = html.rfind('<script', 0, i)
    b = html.find('</script>', i)
    d = json.loads(html[html.find('>', a) + 1:b])

    def find(o):
        if isinstance(o, dict):
            if isinstance(o.get('listing'), dict) and 'products' in o['listing']:
                return o['listing']
            for v in o.values():
                r = find(v)
                if r:
                    return r
        elif isinstance(o, list):
            for v in o:
                r = find(v)
                if r:
                    return r
    lst = find(d)
    cur = re.search(r'"priceCurrency":"([A-Z]{3})"', html)
    return lst, cur.group(1) if cur else None


def fetch_site(cc, dom):
    items, used = [], {}
    for brand, slugs in BRANDS:
        for slug in slugs:
            u = f'https://www.{dom}/{slug}/'
            r = get(u)
            if r is None or isinstance(r, Exception) or r.status_code != 200:
                continue
            lst, cur = listing(r.text)
            if not lst:
                continue
            pages, page_url = lst.get('numberOfPages') or 1, lst.get('pageUrl') or ''
            prods = list(lst.get('products') or [])
            for n in range(2, min(pages, 25) + 1):
                time.sleep(1.2)
                r2 = get(f'https://www.{dom}' + page_url.replace('{pageNumber}', str(n)).replace('{sortOption}', '1'))
                if r2 is None or isinstance(r2, Exception) or r2.status_code != 200:
                    log(cc, slug, 'страница', n, getattr(r2, 'status_code', r2)); break
                l2, _ = listing(r2.text)
                prods += (l2 or {}).get('products') or []
            n_ok = 0
            for p in prods:
                if (p.get('brandName') or '').lower().replace(' ', '') not in (brand.lower(), slug.replace('-', ''), 'odolmed3', 'splatbiomed', 'biomed'):
                    if brand.lower() not in (p.get('brandName') or '').lower():
                        continue
                if p.get('primaryCategory') not in ('Teeth', None):
                    continue
                pi = p.get('priceInformation') or {}
                pd = p.get('promotionData') or {}
                var = next((v.get('additionalInfo') for v in p.get('variants') or [] if v.get('id') == p.get('id')), '')
                items.append({
                    'country': cc, 'brand': brand, 'brand_site': p.get('brandName'), 'line': ' '.join(x for x in [p.get('name'), p.get('subName')] if x).strip(),
                    'annotation': p.get('annotation') or '', 'size': var or '', 'code': p.get('productCode') or '',
                    'master': p.get('masterProductCode') or '', 'type': TYPES.get(p.get('primarySubcategory'), 'other'),
                    'subcategory': p.get('primarySubcategory') or '', 'price': pi.get('price'), 'old_price': pi.get('originalPrice'),
                    'promo_price': pd.get('discountedPrice') if pd.get('isDiscount') else None,
                    'promo_desc': (f"−{pd.get('discountValue')}{' %' if pd.get('discountType') == 'Relative' else ''} с кодом {pd.get('voucherCode')}"
                                   if pd.get('isDiscount') and pd.get('voucherCode') else ''),
                    'currency': cur, 'url': f'https://www.{dom}' + (p.get('url') or ''), 'available': p.get('stockAvailability')})
                n_ok += 1
            used[brand] = used.get(brand, 0) + n_ok
            time.sleep(1.2)
    return items, used


def fx_rates():
    r = get('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml')
    rates = dict(re.findall(r"currency='([A-Z]{3})' rate='([\d.]+)'", r.text))
    return {'date': re.search(r"time='([\d-]+)'", r.text).group(1), 'source': 'ЕЦБ', 'EUR': 1.0,
            **{k: float(v) for k, v in rates.items()}}


def main():
    args = sys.argv[1:]
    day = args.pop(0) if args and re.fullmatch(r'\d{4}-\d{2}-\d{2}', args[0]) else dt.datetime.utcnow().strftime('%Y-%m-%d')
    only = set(args)
    fx = fx_rates()
    items, status = [], {}
    for cc, dom, name in SITES:
        if only and cc not in only:
            continue
        try:
            got, used = fetch_site(cc, dom)
        except Exception as e:
            status[cc] = {'status': 'error', 'domain': dom, 'name': name, 'note': f'{type(e).__name__}: {e}'[:200], 'count': 0}
            log(cc, 'ошибка', e); continue
        curs = {x['currency'] for x in got if x['currency']}
        cur = curs.pop() if len(curs) == 1 else None
        for x in got:
            r = fx.get(x['currency']) if x['currency'] else None
            for k in ('price', 'old_price', 'promo_price'):
                x[k + '_eur'] = round(x[k] / r, 2) if (x.get(k) is not None and r) else None
        items += got
        status[cc] = {'status': 'ok' if got else 'empty', 'domain': dom, 'name': name, 'currency': cur, 'count': len(got), 'brands': used}
        log(cc, dom, len(got), used)
    out = {'date': day, 'fetched_at': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), 'fx': fx,
           'brands': [b for b, _ in BRANDS], 'countries': [{'id': c, 'domain': d, 'name': n} for c, d, n in SITES if c in status],
           'status': status, 'items': items, 'log': LOG[-300:]}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f'{day}.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT, f'{day}.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Дата', 'Страна', 'Сайт', 'Бренд', 'Линейка', 'Описание', 'Упаковка', 'Тип', 'Код Notino', 'Цена', 'Старая цена',
                    'Цена с промокодом', 'Промо', 'Валюта', 'Цена, €', 'Цена с промокодом, €', 'Ссылка'])
        for x in items:
            w.writerow([day, x['country'], status[x['country']]['domain'], x['brand'], x['line'], x['annotation'], x['size'], x['subcategory'],
                        x['code'], x['price'], x['old_price'] or '', x['promo_price'] or '', x['promo_desc'], x['currency'],
                        x['price_eur'], x['promo_price_eur'] or '', x['url']])
    dates = []
    for p in sorted(glob.glob(os.path.join(OUT, '20*.json'))):
        d = json.load(open(p, encoding='utf-8'))
        dates.append({'date': d['date'], 'items': len(d['items']), 'countries': len(d['status'])})
    with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'updated': day, 'dates': dates}, f, ensure_ascii=False, indent=1)
    log('итого', len(items))


if __name__ == '__main__':
    main()
