import csv
import datetime as dt
import importlib.util
import io
import json
import math
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data/prices/notino'
DAY = '2026-11-17'
spec = importlib.util.spec_from_file_location('notino_fetch', ROOT / 'tools/notino_fetch.py')
fetcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetcher)
sites = {cc: (domain, name) for cc, domain, name in fetcher.SITES}
brands = [brand for brand, _ in fetcher.BRANDS]
paths = [OUT / (DAY + suffix) for suffix in ['.json', '.csv', '.quality.json']]
assert not any(p.exists() for p in paths), 'Snapshot already exists; refusing to overwrite'
manifest_path = OUT / 'manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
assert not any(x['date'] == DAY for x in manifest['dates']), 'Date already listed'
archive = {p: p.read_bytes() for p in OUT.glob('20*.json')}
archive.update({p: p.read_bytes() for p in OUT.glob('20*.csv')})
items, status, reports, logs, rates = [], {}, {}, [], []
for file in sorted((ROOT / 'notino-snapshots').glob('**/' + DAY + '.json')):
    data = json.loads(file.read_text(encoding='utf-8'))
    assert data['date'] == DAY
    captured = dt.datetime.fromisoformat(data['fetched_at'].replace('Z', '+00:00'))
    assert captured.astimezone(dt.timezone(dt.timedelta(hours=3))).date().isoformat() == DAY, 'Wrong observation date'
    assert len(data['status']) == 1, 'Expected one country per job'
    cc = next(iter(data['status']))
    assert cc in sites and cc not in status, 'Unexpected or duplicate country'
    assert data['fx']['EUR'] == 1 and data['fx']['date'] <= DAY
    domain, name = sites[cc]
    for item in data['items']:
        assert item['country'] == cc and item['brand'] in brands
        assert urlparse(item['url']).hostname in {domain, 'www.' + domain}
        assert isinstance(item['price'], (int, float)) and math.isfinite(item['price']) and item['price'] > 0
        assert item.get('key')
        for field in ['price_eur', 'promo_price', 'promo_price_eur']:
            value = item.get(field)
            assert value is None or (isinstance(value, (int, float)) and math.isfinite(value) and value >= 0)
    got = data['items']
    items.extend(got)
    status[cc] = dict(data['status'][cc], count=len(got), status='ok' if got else data['status'][cc].get('status', 'empty'))
    reports[cc] = {'fetched_at': data['fetched_at'], 'items': len(got), 'brands': status[cc].get('brands', {}), 'missing_brands': [b for b in brands if not any(x['brand'] == b for x in got)], 'limited': status[cc].get('limited', [])}
    logs.extend(data.get('log', []))
    rates.append(data['fx'])
assert items and rates, 'No fresh observations collected; no date will be published'
assert all(r == rates[0] for r in rates), 'Inconsistent exchange-rate snapshots'
for cc, (domain, name) in sites.items():
    if cc not in status:
        status[cc] = {'status': 'error', 'domain': domain, 'name': name, 'count': 0, 'note': 'No completed collection for this country; previous prices not substituted'}
        reports[cc] = {'items': 0, 'missing_brands': brands, 'note': status[cc]['note']}
status = {cc: status[cc] for cc in sites}
now = dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')
positive = sum(bool(s['count']) for s in status.values())
quality = {'date': DAY, 'assembled_at': now, 'items': len(items), 'countries_with_data': positive, 'countries_attempted': len(sites), 'partial': any(not s['count'] for s in status.values()) or any(r.get('missing_brands') or r.get('limited') for r in reports.values()), 'fx_date': rates[0]['date'], 'countries': reports, 'note': 'Only fresh observations; unavailable data are not copied from 16 November. Existing collector matching and variant-price rules retained.'}
data = {'date': DAY, 'fetched_at': now, 'fx': rates[0], 'brands': brands, 'countries': [{'id': cc, 'domain': domain, 'name': name} for cc, (domain, name) in sites.items()], 'status': status, 'items': items, 'log': logs[-300:], 'quality': quality}
buf = io.StringIO(newline='')
writer = csv.writer(buf, delimiter=';')
writer.writerow(['Дата', 'Страна', 'Сайт', 'Бренд', 'Линейка', 'Описание', 'Упаковка', 'Тип', 'Код товара Notino', 'Цена', 'Старая цена', 'Цена с промокодом', 'Промо', 'Валюта', 'Цена, €', 'Цена с промокодом, €', 'Ссылка'])
for x in items:
    writer.writerow([DAY, x['country'], sites[x['country']][0], x['brand'], x['line'], x.get('annotation', ''), x.get('size', ''), x.get('subcategory', ''), x['master'], x['price'], x.get('old_price') or '', x.get('promo_price') or '', x.get('promo_desc', ''), x.get('currency'), x.get('price_eur'), x.get('promo_price_eur') or '', x['url']])
manifest['dates'].append({'date': DAY, 'items': len(items), 'countries': positive, 'attempted_countries': len(sites), 'partial': quality['partial']})
manifest['dates'].sort(key=lambda x: x['date'])
manifest['updated'] = max(x['date'] for x in manifest['dates'])
for p, original in archive.items():
    assert p.read_bytes() == original, 'Archive changed'
paths[0].write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
paths[1].write_bytes(buf.getvalue().encode('utf-8-sig'))
paths[2].write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding='utf-8')
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
for p, original in archive.items():
    assert p.read_bytes() == original, 'Archive changed'
print(json.dumps({'date': DAY, 'items': len(items), 'countries_with_data': positive, 'partial': quality['partial']}, ensure_ascii=False))
