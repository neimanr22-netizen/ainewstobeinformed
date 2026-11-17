import hashlib
import math
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parent.parent
page = root / 'index.html'
raw = page.read_bytes()
html = raw.decode('utf-8')
marker = 'news-remaining-flags-v4'
if 'id="' + marker + '"' in html:
    raise SystemExit(0)
sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
assert sha == '3089eaa436b0db4f1a069501c4c2d220ef8ac6b6', 'Page changed; review required'
assert html.count('</head>') == 1

def rect(x, y, w, h, fill):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'

def star(cx, cy, radius, color, count=5):
    points = []
    for i in range(count * 2):
        angle = -math.pi / 2 + math.pi * i / count
        r = radius if i % 2 == 0 else radius * (0.382 if count == 5 else 0.45)
        points.append(f'{cx + r * math.cos(angle):.3f},{cy + r * math.sin(angle):.3f}')
    return '<polygon fill="' + color + '" points="' + ' '.join(points) + '"/>'

def svg(body, title):
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 150" preserveAspectRatio="none"><title>' + title + '</title>' + body + '</svg>'

flags = {}
flags['ch'] = svg(rect(0, 0, 300, 150, '#da291c') + rect(135, 35, 30, 80, 'white') + rect(110, 60, 80, 30, 'white'), 'Швейцария')
flags['rs'] = svg(rect(0, 0, 300, 50, '#c6363c') + rect(0, 50, 300, 50, '#0c4076') + rect(0, 100, 300, 50, 'white'), 'Сербия — гражданский флаг без герба')
flags['tr'] = svg(rect(0, 0, 300, 150, '#e30a17') + '<circle cx="112.5" cy="75" r="37.5" fill="white"/><circle cx="121.875" cy="75" r="30" fill="#e30a17"/>' + star(165, 75, 18.75, 'white'), 'Турция')
body = ''.join(rect(0, i * 150 / 14, 300, 150 / 14 + 0.05, '#cc0001' if i % 2 == 0 else 'white') for i in range(14))
body += rect(0, 0, 150, 150 * 8 / 14, '#010066')
body += '<circle cx="57" cy="43" r="30" fill="#ffcc00"/><circle cx="66" cy="40" r="25" fill="#010066"/>' + star(109, 43, 27, '#ffcc00', 14)
flags['my'] = svg(body, 'Малайзия')
body = rect(0, 0, 300, 75, '#ef3340') + rect(0, 75, 300, 75, 'white')
body += '<circle cx="45" cy="37.5" r="25" fill="white"/><circle cx="54" cy="37.5" r="23" fill="#ef3340"/>'
for i in range(5):
    a = -math.pi / 2 + 2 * math.pi * i / 5
    body += star(87 + 18 * math.cos(a), 37.5 + 18 * math.sin(a), 7, 'white')
flags['sg'] = svg(body, 'Сингапур')
body = ''
for i, (field, outer, inner) in enumerate([('#c8102e', 'white', None), ('#006aa7', '#fecc00', None), ('#ba0c2f', 'white', '#00205b'), ('white', '#003580', None), ('#02529c', 'white', '#dc1e35')]):
    x = i * 60
    body += rect(x, 0, 60, 150, field) + rect(x + 17, 0, 12, 150, outer) + rect(x, 65, 60, 20, outer)
    if inner:
        body += rect(x + 20, 0, 6, 150, inner) + rect(x, 71, 60, 8, inner)
flags['nordics'] = svg(body, 'Условный составной флаг: Дания, Швеция, Норвегия, Финляндия и Исландия')
body = rect(0, 0, 300, 150, '#0057a8')
for x in [95, 115, 135, 155, 175, 195]:
    body += f'<path d="M150 125 Q{x} 105 {x} 52" fill="none" stroke="white" stroke-width="8"/>'
body += '<circle cx="150" cy="37" r="18" fill="#ffcc00"/>'
flags['cis'] = svg(body, 'Стилизованный общий флаг СНГ')
for value in flags.values():
    ET.fromstring(value)
scope = 'a.tile[href^="#/news/p/"]:is([href*="/politics/"],[href*="/macro/"],[href*="/retail/"],[href*="/oralcare/"])'
selectors = [scope + '[href$="/' + code + '"]' for code in flags]
css = '<style id="' + marker + '">\n'
css += ',\n'.join(selectors) + '{background-color:#fff;background-repeat:no-repeat;background-size:100% 100%;background-position:center;opacity:1;border-color:#8191a3}\n'
for code, image in flags.items():
    css += scope + '[href$="/' + code + '"]{background-image:url("data:image/svg+xml,' + quote(image, safe='') + '")}\n'
css += ',\n'.join(s + ' b' for s in selectors) + '{align-self:flex-start;background:rgba(255,255,255,.95);color:#132335;padding:4px 10px;border-radius:8px;box-shadow:0 1px 4px #0003}\n'
css += ',\n'.join(s + ' .n' for s in selectors) + '{background:#fff;color:#12314b;border:1px solid #aac0d0}\n'
css += '</style>\n'
updated = html.replace('</head>', css + '</head>', 1)
assert updated.replace(css, '', 1) == html
folder = root / 'assets/news-flags'
folder.mkdir(parents=True, exist_ok=True)
for code, image in flags.items():
    target = folder / (code + '.svg')
    assert not target.exists(), 'Existing asset requires review'
for code, image in flags.items():
    (folder / (code + '.svg')).write_text(image, encoding='utf-8')
page.write_bytes(updated.encode('utf-8'))
print('Applied seven self-contained flag backgrounds. Existing layout, order and news preserved.')
