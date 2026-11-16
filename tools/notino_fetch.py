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
KIDS_TYPES = {'Kids’ Toothpastes': 'paste', 'Kids’ Toothbrushes': 'brush'}
S = http.Session()
LOG = []
LIMITED = {}


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    LOG.append(s)


def get(url, imps=('safari', 'chrome', 'firefox', 'safari', 'chrome')):
    last = None
    for imp in imps:
        try:
            r = S.get(url, impersonate=imp, timeout=60)
        except Exception as e:
            last = e; time.sleep(3); continue
        if r.status_code == 404:
            return r
        if r.status_code == 200 and 'Just a moment' not in r.text[:3000]:
            return r
        last = r
        time.sleep(4 if len(imps) == 1 else 12)
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


def pack_key(label):
    """Упаковка без языка: '2x75 ml' -> '2x75ml', '1 St.'/'1 ks' -> '1pc'."""
    t = (label or '').lower().replace(',', '.')
    m = re.search(r'(?:(\d+) ?x ?)?(\d+(?:\.\d+)?) ?(ml|g)\b', t)
    if m:
        return f"{m.group(1) or 1}x{float(m.group(2)):g}{m.group(3)}"
    m = re.search(r'(\d+) ?[^\d\s]{1,5}\.?$', t.strip())
    return f'{m.group(1)}pc' if m else ''


def variant_qty(label, unit):
    """'2x75 ml' -> 0.15 (л); '3 St.' -> 3 (шт.)"""
    t = (label or '').lower().replace(',', '.')
    if unit.lower() in ('l', 'л'):
        m = re.search(r'(?:(\d+) ?x ?)?(\d+(?:\.\d+)?) ?ml', t)
        return (int(m.group(1) or 1) * float(m.group(2)) / 1000) if m else None
    if unit.lower() in ('kg',):
        m = re.search(r'(?:(\d+) ?x ?)?(\d+(?:\.\d+)?) ?g\b', t)
        return (int(m.group(1) or 1) * float(m.group(2)) / 1000) if m else None
    m = re.search(r'(\d+) ?(st|ks|pcs|db|szt|buc|бр|τεμ|kpl|kom|pz|ud|un|stk)', t)
    return int(m.group(1)) if m else (1 if not t.strip() else None)


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
                u2 = f'https://www.{dom}' + page_url.replace('{pageNumber}', str(n)).replace('{sortOption}', '1')
                r2 = get(u2, ('safari',))
                h2 = r2.text if (r2 is not None and not isinstance(r2, Exception) and r2.status_code == 200) else ''
                l2, _ = listing(h2) if h2 else (None, None)
                if not l2:  # Cloudflare закрывает адреса с параметрами (?f=...) — остаются первые 24 товара бренда
                    LIMITED.setdefault(cc, []).append(brand); break
                prods += (l2 or {}).get('products') or []
            n_ok = 0
            for p in prods:
                if (p.get('brandName') or '').lower().replace(' ', '') not in (brand.lower(), slug.replace('-', ''), 'odolmed3', 'splatbiomed', 'biomed'):
                    if brand.lower() not in (p.get('brandName') or '').lower():
                        continue
                if p.get('primaryCategory') not in ('Teeth', None) and p.get('primarySubcategory') != 'Kids’ Teeth':
                    continue
                pi = p.get('priceInformation') or {}
                pd = p.get('promotionData') or {}
                variants = [v.get('additionalInfo') or '' for v in p.get('variants') or []]
                var = next((v.get('additionalInfo') for v in p.get('variants') or [] if v.get('id') == p.get('id')), '') or ''
                base = {'country': cc, 'brand': brand, 'brand_site': p.get('brandName'),
                        'line': ' '.join(x for x in [p.get('name'), p.get('subName')] if x).strip(),
                        'annotation': p.get('annotation') or '', 'master': p.get('masterProductCode') or p.get('productCode') or '',
                        'type': TYPES.get(p.get('primarySubcategory')) or KIDS_TYPES.get(p.get('primaryType'), 'other'), 'subcategory': p.get('primarySubcategory') or '',
                        'currency': cur, 'url': f'https://www.{dom}' + (p.get('url') or ''), 'available': p.get('stockAvailability')}
                pct = pd.get('discountValue') if pd.get('isDiscount') and pd.get('discountType') == 'Relative' else None
                code_desc = (f"−{pd.get('discountValue')}{' %' if pd.get('discountType') == 'Relative' else ''} с кодом {pd.get('voucherCode')}"
                             if pd.get('isDiscount') and pd.get('voucherCode') else '')
                price, up = pi.get('price'), (pi.get('unitPrice') or {})
                qty = variant_qty(var, (up.get('unit') or {}).get('unitName', ''))
                vprice = round(up['pricePerUnit'] * qty, 2) if (len(variants) > 1 and up.get('pricePerUnit') and qty) else price
                rows = [(var, vprice, pi.get('originalPrice') if vprice == price else None)]
                # в списке Notino цена = минимальная по вариантам; при двух вариантах она относится ко второму
                if len(variants) == 2 and vprice and price and vprice > price + 0.01:
                    other = next(v for v in variants if v != var) if var in variants else ''
                    rows.append((other, price, pi.get('originalPrice')))
                for size, pr, old in rows:
                    if pr is None:
                        continue
                    promo = (round(pr * (1 - pct / 100), 2) if pct else (pd.get('discountedPrice') if pr == price and pd.get('isDiscount') else None))
                    items.append({**base, 'size': size, 'key': base['master'] + '|' + pack_key(size),
                                  'code': p.get('productCode') or '', 'variants': len(variants), 'price': pr, 'old_price': old,
                                  'promo_price': promo, 'promo_desc': code_desc if promo else '',
                                  'unit_price': up.get('pricePerUnit') if pr == vprice else None,
                                  'unit': (up.get('unit') or {}).get('unitName', '')})
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
        status[cc] = {'status': 'ok' if got else 'empty', 'domain': dom, 'name': name, 'currency': cur, 'count': len(got), 'brands': used,
                      'limited': LIMITED.get(cc, [])}
        log(cc, dom, len(got), used)
    prev_path = os.path.join(OUT, f'{day}.json')
    if only and os.path.exists(prev_path):  # дописать к уже собранным странам этого дня
        prev = json.load(open(prev_path, encoding='utf-8'))
        # по каждой паре страна+бренд оставить вариант, где товаров больше
        for cc in list(status):
            pv = prev['status'].get(cc)
            if not pv:
                continue
            for b in set(pv.get('brands', {})) | set(status[cc].get('brands', {})):
                if pv['brands'].get(b, 0) > status[cc]['brands'].get(b, 0):
                    items = [x for x in items if not (x['country'] == cc and x['brand'] == b)] + \
                            [x for x in prev['items'] if x['country'] == cc and x['brand'] == b]
                    status[cc]['brands'][b] = pv['brands'][b]
            status[cc]['count'] = sum(1 for x in items if x['country'] == cc)
            status[cc]['status'] = 'ok' if status[cc]['count'] else 'empty'
        for k, v in prev['status'].items():
            if k not in status:
                status[k] = v
        items = [x for x in prev['items'] if x['country'] not in only] + items
    order = [c for c, _, _ in SITES]
    status = dict(sorted(status.items(), key=lambda kv: order.index(kv[0])))
    out = {'date': day, 'fetched_at': dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'), 'fx': fx,
           'brands': [b for b, _ in BRANDS], 'countries': [{'id': c, 'domain': d, 'name': n} for c, d, n in SITES if c in status],
           'status': status, 'items': items, 'log': LOG[-300:]}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f'{day}.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(OUT, f'{day}.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Дата', 'Страна', 'Сайт', 'Бренд', 'Линейка', 'Описание', 'Упаковка', 'Тип', 'Код товара Notino', 'Цена', 'Старая цена',
                    'Цена с промокодом', 'Промо', 'Валюта', 'Цена, €', 'Цена с промокодом, €', 'Ссылка'])
        for x in items:
            w.writerow([day, x['country'], status[x['country']]['domain'], x['brand'], x['line'], x['annotation'], x['size'], x['subcategory'],
                        x['master'], x['price'], x['old_price'] or '', x['promo_price'] or '', x['promo_desc'], x['currency'],
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
