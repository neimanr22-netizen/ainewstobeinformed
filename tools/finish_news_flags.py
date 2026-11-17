import hashlib
import io
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parent.parent
hp = root / 'index.html'
raw = hp.read_bytes()
h = raw.decode('utf-8')
marker = 'id="news-remaining-flags-v3"'
if marker in h:
    print('Remaining flags already applied.')
    raise SystemExit(0)
sha = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
assert sha == '3089eaa436b0db4f1a069501c4c2d220ef8ac6b6', 'HTML changed; review required'
assert h.count('</head>') == 1
svg_ns = 'http://www.w3.org/2000/svg'
ET.register_namespace('', svg_ns)

def load_svg(url):
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'AI-News-Website-Flag-Assets/1.0'})
            with urllib.request.urlopen(request, timeout=45) as response:
                content = response.read(2000001)
            assert len(content) <= 2000000, 'Oversized SVG'
            node = ET.fromstring(content)
            assert node.tag == '{' + svg_ns + '}svg', 'Not SVG'
            assert '@import' not in content.decode('utf-8').lower()
            for child in node.iter():
                tag = child.tag.rsplit('}', 1)[-1].lower() if isinstance(child.tag, str) else ''
                assert tag not in {'script', 'foreignobject'}, 'Active SVG content rejected'
                for key, value in child.attrib.items():
                    name = key.rsplit('}', 1)[-1].lower()
                    assert not name.startswith('on'), 'Event handler rejected'
                    if name == 'href':
                        assert value.startswith('#'), 'External SVG reference rejected'
                    assert 'javascript:' not in value.lower()
            return content, node
        except Exception as exc:
            last = exc
            time.sleep(attempt + 1)
    raise RuntimeError('Cannot verify SVG: ' + url) from last

assets = {}
sources = []
for code in ['ch', 'rs', 'tr', 'my', 'sg', 'dk', 'se', 'no', 'fi', 'is']:
    url = 'https://flagcdn.com/' + code + '.svg'
    content, _ = load_svg(url)
    assets[code] = content
    sources.append(code + ': ' + url)

cis_urls = [
    'https://commons.wikimedia.org/wiki/Special:Redirect/file/Flag_of_the_CIS.svg',
    'https://commons.wikimedia.org/wiki/Special:Redirect/file/Commonwealth_of_Independent_States.svg',
]
for url in cis_urls:
    try:
        content, _ = load_svg(url)
        assets['cis'] = content
        sources.append('cis: ' + url)
        break
    except RuntimeError:
        pass
assert 'cis' in assets, 'CIS flag could not be downloaded and verified; no changes written'

mosaic = ET.Element('{' + svg_ns + '}svg', {'viewBox': '0 0 300 100', 'preserveAspectRatio': 'none'})
for i, code in enumerate(['dk', 'se', 'no', 'fi', 'is']):
    node = ET.fromstring(assets[code])
    if 'viewBox' not in node.attrib:
        width = re.match(r'[0-9.]+', node.attrib.get('width', ''))
        height = re.match(r'[0-9.]+', node.attrib.get('height', ''))
        assert width and height, 'Missing flag dimensions'
        node.set('viewBox', '0 0 ' + width.group() + ' ' + height.group())
    ids = {e.attrib['id']: code + '-' + e.attrib['id'] for e in node.iter() if 'id' in e.attrib}
    for element in node.iter():
        for key, value in list(element.attrib.items()):
            if key == 'id':
                element.set(key, ids[value])
            else:
                for old, new in ids.items():
                    value = value.replace('url(#' + old + ')', 'url(#' + new + ')')
                    if value == '#' + old:
                        value = '#' + new
                element.set(key, value)
        if element.tag == '{' + svg_ns + '}style' and element.text:
            for old, new in ids.items():
                element.text = element.text.replace('#' + old, '#' + new)
    node.set('x', str(i * 60))
    node.set('y', '0')
    node.set('width', '60')
    node.set('height', '100')
    node.set('overflow', 'hidden')
    node.set('preserveAspectRatio', 'xMidYMid slice')
    mosaic.append(node)
assets['nordics'] = ET.tostring(mosaic, encoding='utf-8', xml_declaration=True)

scope = 'a.tile[href^="#/news/p/"]:is([href*="/politics/"],[href*="/macro/"],[href*="/retail/"],[href*="/oralcare/"])'
codes = ['ch', 'rs', 'tr', 'my', 'sg', 'nordics', 'cis']
def selectors(suffix=''):
    return ',\n'.join(scope + '[href$="/' + k + '"]' + suffix for k in codes)
css = '<style id="news-remaining-flags-v3">\n'
css += selectors() + '{background-color:#fff;background-repeat:no-repeat;background-size:100% 100%;background-position:center;opacity:1;border-color:#8191a3}\n'
for code in codes:
    css += scope + '[href$="/' + code + '"]{background-image:url("assets/news-flags/' + code + '.svg")}\n'
css += selectors(' b') + '{align-self:flex-start;background:rgba(255,255,255,.95);color:#132335;padding:4px 10px;border-radius:8px;box-shadow:0 1px 4px #0003}\n'
css += selectors(' .n') + '{background:#fff;color:#12314b;border:1px solid #aac0d0}\n'
css += '</style>\n'
updated = h.replace('</head>', css + '</head>', 1)
assert updated.replace(css, '', 1) == h, 'Unexpected HTML modification'
assert updated.count(marker) == 1
folder = root / 'assets/news-flags'
for code in assets:
    assert not (folder / (code + '.svg')).exists(), 'Existing flag asset would be overwritten'
assert not (folder / 'SOURCES.md').exists(), 'Existing source document would be overwritten'
folder.mkdir(parents=True, exist_ok=True)
for code, content in assets.items():
    (folder / (code + '.svg')).write_bytes(content)
notes = '# Flag assets\n\nCountry flag SVG files: FlagCDN / Flagpedia (https://flagcdn.com/).\nCIS flag: Wikimedia Commons.\nNordics: custom visual collage of Denmark, Sweden, Norway, Finland and Iceland; not an official regional flag.\n\n' + '\n'.join('- ' + s for s in sources) + '\n'
(folder / 'SOURCES.md').write_text(notes, encoding='utf-8')
hp.write_bytes(updated.encode('utf-8'))
print('Added five national flags, Nordic collage and CIS flag; layout, order, existing flags and news preserved.')
