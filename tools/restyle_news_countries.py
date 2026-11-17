import hashlib
import json
import math
from pathlib import Path
from urllib.parse import quote

root = Path(__file__).resolve().parent.parent
hp = root / 'index.html'
cp = root / 'data/categories.json'
hb, cb = hp.read_bytes(), cp.read_bytes()
h = hb.decode('utf-8')
cfg = json.loads(cb)
marker = 'id="news-country-layout-v2"'
if marker in h:
    print('Layout patch already applied.')
    raise SystemExit(0)

def sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

assert sha(hb) == '19bb715fe270bbd749a14598fae57c35b9bee4a6', 'HTML changed; review required'
assert sha(cb) == '9ab8d7fdc393ec13b4833c0e884e7fc72ee4fe19', 'Categories changed; review required'
assert h.count('</head>') == 1
original_categories = json.loads(cb)['categories']
country_cats = {c['id'] for c in cfg['categories'] if c['subs'] == 'countries'}
assert country_cats == {'politics', 'macro', 'retail', 'oralcare'}
eu_countries = ['de', 'at', 'cz', 'sk', 'hu', 'pl', 'baltics', 'it', 'fr', 'es', 'pt', 'nl', 'be', 'lu', 'bg', 'ro', 'hr', 'si']
order = ['ru', 'us', 'cn', 'eu'] + eu_countries + ['ch', 'rs', 'nordics', 'tr', 'cis', 'my', 'sg']
by_id = {c['id']: c for c in cfg['countries']}
assert len(order) == len(set(order)) == len(cfg['countries']) == 29
assert set(order) == set(by_id), 'No country may be lost or invented'
original_by_id = json.loads(json.dumps(by_id))
by_id['ru']['name'] = 'РФ'
cfg['countries'] = [by_id[k] for k in order]
for item in cfg['countries']:
    if item['id'] != 'ru':
        assert item == original_by_id[item['id']]
assert cfg['categories'] == original_categories
old_grid = 'class="grid" id="browse">${subsOf(cat).map(s => {'
new_grid = 'class="grid${cat.subs === \'countries\' ? \' news-country-grid\' : \'\'}" id="browse">${subsOf(cat).map(s => {'
assert h.count(old_grid) == 1, 'Unexpected subcategory template'

def star(cx, cy, r):
    points = []
    for i in range(10):
        a = math.radians(-90 + 36 * i)
        radius = r if i % 2 == 0 else r * 0.381966
        points.append(f'{cx + radius * math.cos(a):.3f},{cy + radius * math.sin(a):.3f}')
    return '<polygon fill="#ffcc00" points="' + ' '.join(points) + '"/>'

svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 150 100" preserveAspectRatio="xMidYMid meet"><rect width="150" height="100" fill="#003399"/>'
for i in range(12):
    a = math.radians(-90 + i * 30)
    svg += star(75 + 29 * math.cos(a), 50 + 29 * math.sin(a), 5.5)
svg += '</svg>'
assert svg.count('<polygon') == 12
bg = 'url("data:image/svg+xml,' + quote(svg, safe='') + '")'
scope = 'a.tile[href^="#/news/p/"]:is([href*="/politics/"],[href*="/macro/"],[href*="/retail/"],[href*="/oralcare/"])'
def selectors(suffix=''):
    return ',\n'.join(scope + '[href$="/' + k + '"]' + suffix for k in ['eu'] + eu_countries)

css = '<style id="news-country-layout-v2">\n'
css += selectors() + '{background-color:#003399;background-image:' + bg + ';background-repeat:no-repeat;background-size:100% 100%;background-position:center;border-color:#002776;color:#fff;opacity:1}\n'
css += selectors(' b') + '{align-self:flex-start;background:rgba(255,255,255,.95);color:#132335;padding:4px 10px;border-radius:8px;box-shadow:0 1px 4px #0003}\n'
css += selectors(' small') + '{color:#fff}\n'
css += selectors(' .n') + '{background:#fff;color:#12314b;border:1px solid #aac0d0}\n'
css += '#browse.news-country-grid{grid-template-columns:repeat(3,minmax(0,1fr));align-items:stretch}\n'
css += '#browse.news-country-grid>.tile{min-width:0}\n'
css += '#browse.news-country-grid>.tile b{max-width:100%;box-sizing:border-box;overflow-wrap:anywhere}\n'
css += '@media(max-width:600px){#browse.news-country-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}#browse.news-country-grid>.tile{padding:10px 6px;min-height:108px}#browse.news-country-grid>.tile b{font-size:13px;line-height:1.3;padding:3px 5px}#browse.news-country-grid>.tile small{font-size:12px}}\n'
css += '</style>\n'
updated = h.replace(old_grid, new_grid, 1).replace('</head>', css + '</head>', 1)
assert updated.replace(css, '', 1).replace(new_grid, old_grid, 1) == h
assert updated.count(marker) == 1
new_cfg = json.dumps(cfg, ensure_ascii=False, indent=2) + '\n'
assert [c['id'] for c in json.loads(new_cfg)['countries']] == order
hp.write_bytes(updated.encode('utf-8'))
cp.write_bytes(new_cfg.encode('utf-8'))
print('Applied EU flags, three columns and requested order. Switzerland and Serbia precede Nordics. News untouched.')
