#!/usr/bin/env python3
"""Сырые цены (data/prices/raw/ДАТА.json) -> data/prices/ДАТА.json + .csv + manifest.json.

Определяет бренд, тип товара (паста / щётка), линейку (единое название на всех языках),
размер упаковки, регулярную и промо-цену с описанием акции.
    python tools/prices_build.py [ДАТА ...]   # без аргументов — все сырые файлы
"""
import csv
import glob
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, 'data/prices')
BRANDS = ['SPLAT', 'Biomed', 'Elmex', 'Sensodyne', 'Biorepair', 'Colgate', 'Parodontax',
          'Lacalut', 'Odol', 'Marvis', 'Curaprox']
BRAND_RE = re.compile(r'\b(splat|biomed|elmex|sensodyne|biorepair|colgate|parodontax|paradontax|lacalut|odol|marvis|curaprox)')
STORES_IN = {'de': ['dm', 'rossmann', 'kaufland', 'lidl'], 'at': ['dm', 'lidl'], 'ch': ['lidl'],
             'cz': ['dm', 'rossmann', 'teta', 'kaufland', 'lidl'], 'hu': ['dm', 'rossmann', 'lidl'],
             'sk': ['dm', 'teta', 'kaufland', 'lidl']}


def asc(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(ch for ch in s if not unicodedata.combining(ch)).lower().replace('®', '').replace('™', '')


# ---------- тип товара ----------
PASTE = re.compile(r'zahnpast|zahncreme|zahngel|zubn\w* past|fogkrem|toothpaste|\bpasta\b|zubne pasty|zubni pasty|zahnpasta')
BRUSH = re.compile(r'zahnburst|zubn\w* kart|zubn\w* kef|fogkef|toothbrush|\bcs ?\d{3,5}\b|kartac|kefk|zahnbursten|zubne kefky|zubni kartac')
NOT = re.compile(r'mundsp|mundwasser|mundschaum|mundspray|ustni vod|ustna vod|ustne vod|szajviz|szajspray|oblit|zahnseide|nit\b|'
                 r'fogselyem|mezizub|medzizub|fogkozt|interdentalburst|interdental fogkefe$|\bvelikost\b|\bc\. ?\d|velkost|iso ?\d|0[,.]\d+ ?mm|'
                 r'aufsteck|burstenkop|hlavic|potfej|nahradn|refill|elektri|elektro|electric|akku|sonic|zungen|jazyk|nyelv|'
                 r'protez|prothes|haftcreme|serum|bleaching|strips|pen\b|tablet|anfarbe|plaque|aligner|pena\b|aronal|krem\b.*\b(arnika|vadgeszt|ordogcs)|whitening kit|gel protector')
SET = re.compile(r'\bset\b|suprava|sada\b|szett|geschenk|darcek|darek|ajandek|\+ ?zubn\w* kart|\+ ?pouzdro|\+ ?fogkef|\+ ?zubn\w* kef|kefka \+|kartacek \+|fogkefe \+|mundhygiene-set|zahnpflege set')
CAT_PASTE = re.compile(r'zahnpasta|zubni past|zubne past|fogkrem|starostlivost o detske zuby|bielenie zubov|prve zubky')
CAT_BRUSH = re.compile(r'zahnburst|zubni kartac|zubne kef|fogkef')


def kind(x):
    t = asc(f"{x.get('title', '')} {x.get('description', '')}")
    cat = asc(x.get('category', ''))
    if NOT.search(t) or re.search(r'mundsp|ustne vod|szajviz|interdental|elektromos|potfej|bleaching|ustni vod', cat):
        return None
    p, b = bool(PASTE.search(t)) or bool(CAT_PASTE.search(cat)), bool(BRUSH.search(t)) or bool(CAT_BRUSH.search(cat))
    if SET.search(t) or (p and b and not CAT_PASTE.search(cat) and not CAT_BRUSH.search(cat)):
        return None
    if p and b:
        return 'paste' if CAT_PASTE.search(cat) else 'brush'
    return 'paste' if p else 'brush' if b else None


# ---------- линейки ----------
KIDS = r'kids|kinder|kid\'s|baby|\bdet(sk|i\b)|gyerek|gyermek|prvniho zoubku|milchzahn|perlick|0 ?- ?[236]\b|[023] ?- ?6\b|0 bis 6|2 bis 6|0-2|0 ?- ?3|3 ?- ?6|smiles'
JUN = r'junior|juniorzahn|6 ?- ?1[23]|6\+|teens'
L = {
 'elmex': {'paste': [
    (JUN, 'Junior'), (KIDS, 'Kids'),
    (r'sensitiv\w* prof|repair ?& ?prevent|repair&prevent', 'Sensitive Professional'),
    (r'sensitiv\w* plus|sensitivity ?\+|gum care|gum streng|zahnfleischpflege|instant care', 'Sensitive Plus'),
    (r'gentle white|sensitiv\w* whitening|sensitiv\w*.*duopack|sensitiv|citliv', 'Sensitive'),
    (r'enamel|opti-?namel|opti-?schmelz|zahnschmelz|erozi|weiss-schmelz', 'Enamel Professional'),
    (r'intensiv|caries plus|kariesschutz plus', 'Caries Plus Intensive Cleaning'),
    (r'(anti.?caries|kariesschutz|caries protection) prof|professional', 'Caries Protection Professional'),
    (r'kariesschutz|caries|kaz|fogszuvas|mentholfrei|complete care|whitening', 'Caries Protection')],
  'brush': [(JUN, 'Junior'), (KIDS, 'Kids'), (r'interx', 'InterX'), (r'expert pr[ae]z?c?i|interdental', 'Sensitive Expert Precision'), (r'kariesschutz|caries', 'Caries Protection'),
    (r'ultra ?soft|ultra mak|super soft|extra (weich|soft)', 'Ultra Soft'), (r'sensitiv', 'Sensitive'), (r'intensiv', 'Intensive Cleaning')]},
 'sensodyne': {'paste': [
    (JUN, 'Pronamel Junior'), (KIDS, 'Pronamel Kids'),
    (r'clinical repair', 'Clinical Repair'), (r'clinical white', 'Clinical White'),
    (r'(pro ?schmelz|pronamel) clinical|clinical zahnschmelz', 'Pronamel Clinical'),
    (r'pronamel|pro ?schmelz', 'Pronamel'), (r'repair ?& ?protect|repair&protect|repair & protect', 'Repair & Protect'),
    (r'rapid', 'Rapid Relief'), (r'advanced white|true white', 'Advanced White'),
    (r'co?mp?l\w*te protection|kompletn\w* ochran|complete whitening|komplett', 'Complete Protection'),
    (r'multi ?care', 'MultiCare'), (r'extra whitening', 'Extra Whitening'), (r'deep clean', 'Deep Clean'),
    (r'gum|zahnfleisch|dasn|dasien', 'Sensitivity & Gum'), (r'anti.?caries|fogszuvas', 'Anti Caries'),
    (r'fluor|flouride|original', 'Fluoride')],
  'brush': [(KIDS, 'Pronamel Kids'), (r'co?mp?l\w*te protection', 'Complete Protection'), (r'repair', 'Repair & Protect'),
    (r'deep clean', 'Deep Clean'), (r'multi ?care', 'MultiCare'), (r'advanced clean', 'Advanced Clean'),
    (r'true white', 'True White'), (r'precision', 'Precision'), (r'weich|soft|mekk|makk|puha', 'Soft')]},
 'parodontax': {'paste': [
    (r'intensive gum repair|advanced\+', 'Intensive Gum Repair'),
    (r'active (gum )?repair|aktivn\w* obnov|aktivna obnov|aktivna ochrana|zahnfleisch active|advanced whitening|active gum', 'Active Gum Repair'),
    (r'gum ?& ?breath|gum\+breath|zapach|zapach', 'Gum + Breath & Sensitivity'),
    (r'strength|starkung|starkt|posilen|posilnen|\bgum\b', 'Gum Strengthen & Protect'),
    (r'complete protection|kompletn|komplett', 'Complete Protection'), (r'ultra clean', 'Ultra Clean'),
    (r'herbal', 'Herbal'), (r'classic|original|fluoridfrei|bez fluoridu', 'Classic'),
    (r'whitening|naturlich wei', 'Whitening'), (r'extra fr', 'Extra Fresh'), (r'fluorid', 'Fluoride')],
  'brush': [(r'interdental', 'Interdental'), (r'expert clean', 'Expert Clean'), (r'gentle clean', 'Gentle Clean'),
    (r'complete protection', 'Complete Protection'), (r'gums? & teeth|extra soft', 'Gums & Teeth Extra Soft')]},
 'lacalut': {'paste': [
    (r'kids', 'Kids'), (JUN, 'Junior'), (r'white ?&? ?repair', 'White & Repair'), (r'aktiv plus', 'Aktiv Plus'),
    (r'aktiv.*(citliv|sensitiv|erzekeny)', 'Aktiv Gum & Sensitive'),
    (r'aktiv.*(bel|biel|white|weiss|feher)', 'Aktiv Gum & Gentle White'),
    (r'aktiv.*(sklovin|zahnschmelz|zdrav|gesunder|fogzomanc)|fogin\w* ?& ?fogzomanc', 'Aktiv Gum & Enamel'),
    (r'aktiv.*(hlbkov|deep)', 'Aktiv Deep Clean'), (r'aktiv', 'Aktiv'),
    (r'sensitiv\w* plus', 'Sensitive Plus'), (r'sensitiv|senstive|remineral', 'Sensitive'),
    (r'flora', 'Flora'), (r'white|feherito', 'White')],
  'brush': []},
 'odol': {'paste': [
    (r'milchzahn', 'med3 Milchzahn'), (r'juniorzahn', 'med3 Juniorzahn'), (KIDS, 'Perlička (Kids)'), (JUN, 'Junior'),
    (r'stoma|paradentol', 'Stoma Paradentol'), (r'velvet white', 'Velvet White'), (r'velvet fresh', 'Velvet Fresh'),
    (r'visible white|white renew', 'White Renew'), (r'whitening plus', 'med3 Whitening Plus'),
    (r'extra white', 'med3 Extra White'), (r'white ?& ?shine', 'med3 White & Shine'), (r'white\+', 'med3 White+'),
    (r'extreme clean', 'med3 Extreme Clean'), (r'extre\w* fresh', 'med3 Extreme Fresh'), (r'all in one|rundumschutz', 'med3 All in One'),
    (r'fresh plus', 'med3 Fresh Plus'), (r'minzfrisch', 'med3 Minzfrisch'), (r'original', 'med3 Original'),
    (r'whitening', 'Whitening'), (r'classic', 'Classic'), (r'herbal', 'Herbal'), (r'fluorid', 'Fluorid')],
  'brush': [(KIDS, 'Perlička (Kids)'), (r'flex', 'Flex-Zone'), (r'klasick|classic', 'Classic')]},
 'colgate': {'paste': [
    (JUN, 'Junior'), (KIDS, 'Kids'), (r'max white.*expert|expert white', 'Max White Expert'), (r'max white.*purple|purple', 'Max White Purple Reveal'),
    (r'max white.*(ultra|luminous)', 'Max White Ultra'), (r'max white.*charcoal', 'Max White Charcoal'),
    (r'max white.*(sparkle|diamond)', 'Max White Sparkle Diamonds'), (r'max white.*crystal', 'Max White White Crystals'),
    (r'max white.*one', 'Max White One'), (r'max white', 'Max White'), (r'max fresh', 'Max Fresh'),
    (r'total', 'Total'), (r'triple action', 'Triple Action'), (r'sensitive|sensitiv|pro.?relief|citliv|erzekeny', 'Sensitive Pro-Relief'),
    (r'advanced white.*charcoal', 'Advanced White Charcoal'), (r'advanced white', 'Advanced White'), (r'optic white', 'Optic White'), (r'sensation white', 'Sensation White'),
    (r'komplett|complete', 'Komplett'), (r'cavity|kariesschutz|caries', 'Cavity Protection'),
    (r'herbal|krauter', 'Herbal'), (r'natural|naturals', 'Naturals'), (r'elixir', 'Elixir'), (r'periogard|gum', 'Gum'),
    (r'duraphat', 'Duraphat'), (r'charcoal|aktivkohle|uhli|uhlie', 'Charcoal'), (r'whit|bel|biel|feher', 'Whitening'), (r'fresh', 'Fresh')],
  'brush': [
    (JUN, 'Junior'), (KIDS, 'Kids'), (r'360', '360°'), (r'extra clean', 'Extra Clean'), (r'slim ?soft', 'Slim Soft'),
    (r'zig.?zag', 'ZigZag'), (r'premier', 'Premier Clean'), (r'twister', 'Twister'), (r'gum', 'Gum Care'),
    (r'max white', 'Max White'), (r'recycl|bamboo|bambus', 'Recyclable / Bamboo'), (r'cushion', 'Cushion Clean'),
    (r'sensitiv|citliv', 'Sensitive'), (r'high density', 'High Density'), (r'ultra soft|extra soft', 'Ultra Soft'),
    (r'medium|stredn|mittel|kozepes', 'Medium'), (r'soft|mekk|makk|weich|puha', 'Soft')]},
 'curaprox': {'paste': [(r'enzycal', 'Enzycal'), (r'be you', 'Be You'), (r'black is white', 'Black is White'),
    (r'white is black', 'White is Black'), (KIDS, 'Kids')],
  'brush': [(r'kids|baby|child|dets|gyerek', 'Kids'), (r'5460|ultra ?soft', 'CS 5460 Ultra Soft'), (r'3960|super ?soft', 'CS 3960 Super Soft'),
    (r'12460|velvet', 'CS 12460 Velvet'), (r'1560|\bsoft\b', 'CS 1560 Soft'), (r'7600|smart', 'CS 7600 Smart'),
    (r'100[69]|single', 'CS 1006 Single'), (r'708|implant', 'CS 708 Implant'), (r'ortho', 'Ortho'), (r'surgical', 'CS Surgical')]},
 'biorepair': {'paste': [
    (r'peribioma pro', 'Peribioma Pro'), (r'peribioma|gum', 'Peribioma Gum Protection'), (r'total prot', 'Total Protective Repair'),
    (r'night', 'Advanced Intensive Night'), (r'50\+', 'Advanced Complete Protection 50+'), (r'fast sensitive', 'Fast Sensitive Repair'),
    (r'sensitivity', 'Advanced Sensitivity'), (r'active shield', 'Advanced Active Shield'), (r'pro white', 'Pro White'),
    (KIDS, 'Kids'), (JUN, 'Junior'), (r'advanced|sklovin|zahnschmelz|karies', 'Advanced Enamel')],
  'brush': []},
 'biomed': {'paste': [(r'charcoal', 'Charcoal'), (r'super ?white', 'Superwhite'), (r'sensitive', 'Sensitive'), (r'calcimax', 'Calcimax'),
    (r'gum ?health', 'Gum Health'), (r'vita ?fresh', 'Vitafresh'), (r'citrus', 'Citrus Fresh'), (r'white complex', 'White Complex'),
    (r'biocomplex', 'Biocomplex'), (KIDS, 'Kids')], 'brush': []},
 'marvis': {'paste': [(r'classic', 'Classic Strong Mint'), (r'whitening', 'Whitening Mint'), (r'sensitive|gums', 'Sensitive Gums'),
    (r'aquatic', 'Aquatic Mint'), (r'cinnamon', 'Cinnamon Mint'), (r'ginger', 'Ginger Mint'), (r'jasmin', 'Jasmin Mint'),
    (r'licorice', 'Amarelli Licorice'), (r'anise', 'Anise Mint')], 'brush': []},
 'splat': {'paste': [], 'brush': []},
}
NOISE = re.compile(r'\b(zahnpasta|zahncreme|zahnburste|zubn[ia]|pasta|kartacek|kartacky|kefka|kefky|fogkrem|fogkefe|s fluoridem|s fluoridom|'
                   r'fluoridos|pro citliv\w* zuby|pre citliv\w* zuby|na citliv\w* zuby|duopack|duo pack|doppelpack|reisegro\w*|ruzne druhy|'
                   r'tobbfele|sortiert|bel[ie]ci|bieliaca|specialni|\d+ ?x ?\d+ ?ml|\d+ ?(ml|st|ks|db|g)\b|1 anzahl)\b')


def line_of(brand, typ, x):
    t = asc(f"{x.get('brand_raw', '')} {x.get('title', '')}")
    for pat, name in L.get(brand.lower(), {}).get(typ, []):
        if re.search(pat, t):
            return name
    # запасной вариант: очищенное название
    s = BRAND_RE.sub(' ', asc(x.get('title', '')))
    s = re.sub(r'med ?3', ' ', s)
    s = NOISE.sub(' ', s)
    s = re.sub(r'[,;()\-–]+|\.\.\.|…', ' ', s)
    w = [w for w in s.split() if len(w) > 1][:3]
    if not w:
        return 'Разные виды' if 'druh' in asc(x.get('description', '')) or 'sort' in asc(x.get('description', '')) else 'Classic'
    return ' '.join(v.capitalize() for v in w)


# ---------- упаковка ----------
def pack(x, typ):
    t = asc(f"{x.get('title', '')} {x.get('unit', '')}")
    m = re.search(r'(\d+) ?x ?(\d+(?:[.,]\d+)?) ?ml', t)
    if m:
        n, ml = int(m.group(1)), float(m.group(2).replace(',', '.'))
        return n, ml, f'{n}×{m.group(2)} мл'
    n = 2 if re.search(r'duo ?pack|doppelpack|duopack|duo\b', t) else 1
    m = re.search(r'(\d+(?:[.,]\d+)?) ?ml', t)
    if typ == 'paste' and m:
        ml = float(m.group(1).replace(',', '.'))
        if n == 2 and ml >= 100:
            ml /= 2
        return n, ml, (f'2×{ml:g} мл' if n == 2 else f'{ml:g} мл')
    m = re.search(r'(\d+) ?(st|ks|db|pcs|kusy?)\b', t)
    if typ == 'brush':
        k = int(m.group(1)) if m else 3 if re.search(r'trio|tripack|3-pack|3 pack', t) else 2 if re.search(r'duo', t) else 1
        return k, None, f'{k} шт.'
    return 1, None, ''


def rank(typ, n, ml):
    if typ == 'brush':
        return 0 if n == 1 else 1 if n == 2 else 2
    if ml is None:
        return 5 if n == 1 else 6
    if n == 1:
        return 0 if 70 <= ml <= 100 else 1 if 45 <= ml < 70 else 2 if ml > 100 else 4
    return 3


# ---------- промо ----------
TR = [(r'R\+ kártyával (\d+)% kedvezmény', r'с картой Rossmann+ скидка \1%'),
      (r'\*?za 1 ks při koupi (\d+) ks', r'цена за 1 шт. при покупке \1 шт.'),
      (r'produktů značek? ', 'товаров брендов '), (r'produktů značky ', 'товаров бренда '), (r' v libovolné kombinaci', ' в любой комбинации'),
      (r'\ba\b', 'и'), (r'Naše značka', 'собственная марка'), (r'AKCE', 'акция'), (r'% sleva', 'скидка'),
      (r'Rossmann Club', 'по карте Rossmann Club'), (r'Mega Schnäppchen|Megaúlovek|Megaúlovok', 'суперцена'),
      (r'Ajánlat érvényes:', 'акция действует'), (r'Pouze v prodejnách', 'только в магазинах'), (r'Nur in der Filiale', 'только в магазинах'),
      (r'Nur Online', 'только онлайн'), (r'Výprodeje?|Dopredaj logo|Výpredaj', 'распродажа'), (r'Klub Rossmann; ', ''),
      (r' Kč CLUB cena', ' Kč'), (r'Rossmann Club: ', 'Rossmann Club '), (r'Neu\b', 'новинка'), (r'Najnižšia cena za 30 dní', 'мин. цена за 30 дней')]


def tr(s):
    for a, b in TR:
        s = re.sub(a, b, s)
    s = re.sub(r'(?:акция; )?(?:скидка; )?-(\d+) ?%', r'скидка \1 %', s)
    parts = list(dict.fromkeys(x.strip() for x in s.split(';') if x.strip()))
    return '; '.join(parts)


def prices(x):
    p, old, card = x.get('price'), x.get('old_price'), x.get('card_price')
    m = re.search(r'Rossmann Club: ([\d.,]+)', x.get('promo_text') or '')
    if m and not card:
        card = float(m.group(1).replace(',', '.'))
    desc = tr(x.get('promo_text') or '')
    note = x.get('note') or ''
    if x['store'] == 'lidl' and re.search(r'\d\d\.\d\d\.', note):
        desc = '; '.join(v for v in [desc, tr(note)] if v)
    if old and p and p < old - 0.001:
        return old, p, desc or f'скидка {round((1 - p / old) * 100)} %'
    if card and p and card < p - 0.001:
        return p, card, desc
    if x['store'] == 'kaufland' or (x['store'] == 'lidl' and re.search(r'\d\d\.\d\d\.', note)):
        return None, p, (desc + '; обычная цена в листовке не указана').strip('; ')
    if desc and re.search(r'скидк|%|акци', desc) and not re.search(r'только онлайн|новинка', desc):
        return p, None, desc
    return p, None, desc if re.search(r'по карте|при покупке', desc) else ''


def brand_of(x):
    src = x.get('brand_raw') if x['store'] in ('dm', 'rossmann', 'lidl', 'kaufland') and x.get('brand_raw') else x.get('title', '')
    m = BRAND_RE.search(asc(src))
    if not m and x['store'] in ('lidl', 'kaufland'):
        m = BRAND_RE.search(asc(x.get('title', '')))
    if not m:
        return None
    b = m.group(1).replace('paradontax', 'parodontax')
    return next(B for B in BRANDS if B.lower() == b)


def build(day):
    raw = json.load(open(os.path.join(DIR, 'raw', f'{day}.json'), encoding='utf-8'))
    items, skipped = [], 0
    for x in raw['items']:
        b = brand_of(x)
        if not b or x.get('price') is None:
            skipped += 1; continue
        typ = kind(x)
        if not typ:
            skipped += 1; continue
        n, ml, size = pack(x, typ)
        reg, promo, desc = prices(x)
        name = re.sub(r'\s+', ' ', x.get('title', '')).strip()
        if x['store'] == 'dm' and x.get('brand_raw') and not asc(name).startswith(asc(x['brand_raw'])[:4]):
            name = f"{x['brand_raw']} {name}"
        items.append({'country': x['country'], 'store': x['store'], 'brand': b, 'type': typ, 'line': line_of(b, typ, x),
                      'name': name, 'size': size, 'rank': rank(typ, n, ml), 'regular': reg, 'promo': promo,
                      'promo_desc': desc, 'currency': x['currency'], 'url': x.get('url', '')})
    seen, uniq = set(), []
    for it in items:
        k = (it['country'], it['store'], it['name'], it['regular'], it['promo'])
        if k not in seen:
            seen.add(k); uniq.append(it)
    items = sorted(uniq, key=lambda i: (i['country'], i['store'], i['type'], BRANDS.index(i['brand']), i['line'], i['rank']))
    status = {}
    for c, sts in STORES_IN.items():
        for s in sts:
            k = f'{c}/{s}'
            st = dict(raw['status'].get(k, {'status': 'none', 'url': '', 'note': 'не собиралось'}))
            st.pop('count', None)
            st['n_paste'] = sum(1 for i in items if i['country'] == c and i['store'] == s and i['type'] == 'paste')
            st['n_brush'] = sum(1 for i in items if i['country'] == c and i['store'] == s and i['type'] == 'brush')
            status[k] = st
    out = {'date': day, 'fetched_at': raw.get('fetched_at'), 'fx': raw.get('fx'), 'brands': BRANDS,
           'status': status, 'items': items}
    with open(os.path.join(DIR, f'{day}.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(DIR, f'{day}.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Дата', 'Страна', 'Магазин', 'Тип', 'Бренд', 'Линейка', 'Товар', 'Упаковка',
                    'Регулярная цена', 'Промо цена', 'Описание промо', 'Валюта', 'Ссылка'])
        for i in items:
            w.writerow([day, i['country'], i['store'], 'паста' if i['type'] == 'paste' else 'щётка', i['brand'], i['line'], i['name'],
                        i['size'], i['regular'] if i['regular'] is not None else '', i['promo'] if i['promo'] is not None else '',
                        i['promo_desc'], i['currency'], i['url']])
    print(day, 'товаров:', len(items), 'отброшено:', skipped)
    return out


def manifest():
    dates = []
    for p in sorted(glob.glob(os.path.join(DIR, '20*.json'))):
        d = json.load(open(p, encoding='utf-8'))
        dates.append({'date': d['date'], 'stores': d['status'], 'items': len(d['items'])})
    with open(os.path.join(DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump({'updated': max(x['date'] for x in dates) if dates else '', 'dates': dates}, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    days = sys.argv[1:] or [os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(DIR, 'raw', '*.json')))]
    for d in days:
        build(d)
    manifest()
