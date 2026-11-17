import hashlib
import json
import math
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
html_path = ROOT / 'index.html'
cfg_path = ROOT / 'data/categories.json'
html_bytes = html_path.read_bytes()
cfg_bytes = cfg_path.read_bytes()
html = html_bytes.decode('utf-8')
cfg = json.loads(cfg_bytes)
new = [
    ('pl', 'Польша'), ('baltics', 'Прибалтика'),
    ('nordics', 'Страны Скандинавия и Финляндия'),
    ('it', 'Италия'), ('fr', 'Франция'), ('es', 'Испания'),
    ('pt', 'Португалия'), ('nl', 'Нидерланды'), ('be', 'Бельгия'),
    ('lu', 'Люксембург'), ('bg', 'Болгария'), ('ro', 'Румыния'),
    ('hr', 'Хорватия'), ('si', 'Словения'), ('rs', 'Сербия'),
    ('tr', 'Турция'), ('cn', 'Китай'), ('cis', 'Страны СНГ'),
    ('my', 'Малайзия'), ('sg', 'Сингапур'),
]
marker = 'id="news-country-colors"'
if marker in html:
    existing = {c['id']: c['name'] for c in cfg['countries']}
    assert all(existing.get(k) == v for k, v in new), 'Incomplete existing patch'
    print('Patch already applied; nothing changed.')
    raise SystemExit(0)

def blob_sha(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

assert blob_sha(html_bytes) == 'acb4351c6b056ee2ef2fd6f4bf6a5d0bca655368', 'HTML changed; review required'
assert blob_sha(cfg_bytes) == '0ad044f7dd979f38c3406e3446ff48170228ef1f', 'Categories changed; review required'
assert html.count('</head>') == 1
assert len(new) == 20 and len({k for k, _ in new}) == 20
for category in ('politics', 'macro', 'retail', 'oralcare'):
    assert next(c for c in cfg['categories'] if c['id'] == category)['subs'] == 'countries'
old_countries = json.loads(json.dumps(cfg['countries']))
old_ids = {c['id'] for c in old_countries}
assert not old_ids.intersection(k for k, _ in new)
cfg['countries'].extend({'id': k, 'name': v} for k, v in new)
assert cfg['countries'][:len(old_countries)] == old_countries
assert len(cfg['countries']) == 29

def star(cx, cy, radius, fill, rotation=-90):
    points = []
    for i in range(10):
        angle = math.radians(rotation + i * 36)
        r = radius if i % 2 == 0 else radius * 0.381966
        points.append(f'{cx + r * math.cos(angle):.3f},{cy + r * math.sin(angle):.3f}')
    return '<polygon fill="' + fill + '" points="' + ' '.join(points) + '"/>'

def svg_bg(body, width, height):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none">{body}</svg>'
    return 'url("data:image/svg+xml,' + quote(svg, safe='') + '")'

usa = '<rect width="190" height="100" fill="white"/>'
for row in range(0, 13, 2):
    usa += f'<rect y="{row * 100 / 13:.4f}" width="190" height="{100 / 13:.4f}" fill="#b22234"/>'
usa += '<rect width="76" height="53.8462" fill="#3c3b6e"/>'
for row in range(9):
    for col in range(6 if row % 2 == 0 else 5):
        x = (col + (0.5 if row % 2 == 0 else 1)) * 76 / 6
        usa += star(x, (row + 1) * 53.8462 / 10, 2.25, 'white')
china = '<rect width="150" height="100" fill="#de2910"/>' + star(25, 25, 15, '#ffde00')
for x, y in ((50, 10), (60, 20), (60, 35), (50, 45)):
    rotation = math.degrees(math.atan2(25 - y, 25 - x))
    china += star(x, y, 5, '#ffde00', rotation)

scope = 'a.tile[href^="#/news/p/"]:is([href*="/politics/"],[href*="/macro/"],[href*="/retail/"],[href*="/oralcare/"])'
def tiles(ids):
    return ',\n'.join(scope + '[href$="/' + k + '"]' for k in ids)

eu = ['eu', 'de', 'at', 'cz', 'sk', 'hu', 'pl', 'baltics', 'it', 'fr', 'es', 'pt', 'nl', 'be', 'lu', 'bg', 'ro', 'hr', 'si']
flags = ['ru', 'us', 'cn']
css = '<style id="news-country-colors">\n'
css += tiles(eu) + '{background:#dceeff;color:#12314b;border-color:#94bfdf;opacity:1}\n'
css += ',\n'.join(scope + '[href$="/' + k + '"] small' for k in eu) + '{color:#31536c}\n'
css += tiles(flags) + '{background-size:100% 100%;background-repeat:no-repeat;border-color:#778899;opacity:1}\n'
css += tiles(['ru']) + '{background-image:linear-gradient(to bottom,#fff 0%,#fff 33.333%,#0039a6 33.333%,#0039a6 66.667%,#d52b1e 66.667%,#d52b1e 100%)}\n'
css += tiles(['us']) + '{background-image:' + svg_bg(usa, 190, 100) + '}\n'
css += tiles(['cn']) + '{background-image:' + svg_bg(china, 150, 100) + '}\n'
css += ',\n'.join(scope + '[href$="/' + k + '"] b' for k in flags) + '{align-self:flex-start;background:rgba(255,255,255,.95);color:#132335;padding:4px 10px;border-radius:8px;box-shadow:0 1px 4px #0003}\n'
css += ',\n'.join(scope + '[href$="/' + k + '"] .n' for k in eu + flags) + '{background:#fff;color:#12314b;border:1px solid #aac0d0}\n'
css += scope + '.empty{opacity:1;border-style:dashed}\n'
css += scope + ':focus-visible{outline:3px solid #1575c6;outline-offset:3px}\n'
css += '</style>\n'
updated_html = html.replace('</head>', css + '</head>', 1)
assert updated_html.replace(css, '', 1) == html, 'Unexpected HTML change'
assert updated_html.count(marker) == 1
assert usa.count('<polygon') == 50 and china.count('<polygon') == 5
new_cfg = json.dumps(cfg, ensure_ascii=False, indent=2) + '\n'
assert json.loads(new_cfg)['categories'] == json.loads(cfg_bytes)['categories']
html_path.write_bytes(updated_html.encode('utf-8'))
cfg_path.write_bytes(new_cfg.encode('utf-8'))
print('Added 20 country/group subcategories to all four news categories; styles inserted without changing existing HTML or news.')
