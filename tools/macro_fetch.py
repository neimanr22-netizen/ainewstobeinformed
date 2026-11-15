#!/usr/bin/env python3
"""Сбор макроэкономических данных для раздела «Статистика → Макроэкономика».

Запускается в GitHub Actions (.github/workflows/macro.yml): из среды Claude статистические
API недоступны. Результат — data/macro/<страна>.json и data/macro/meta.json.

Источники (только официальные):
  МВФ (World Economic Outlook, DataMapper API) — ВВП, ВВП на душу, инфляция, безработица, в т.ч. оценки текущего года
  Всемирный банк (WDI API) — чистый экспорт, ВНД на душу, площадь, население, урбанизация; запасной источник
  Евростат (API) — ВВП, ВВП на душу, чистый экспорт, HICP, безработица для стран ЕС/ЕАСТ; регионы NUTS
  ЕЦБ (Data Portal) — курс EUR/USD для пересчёта долларовых рядов в евро
  BIS (Банк международных расчётов) — ключевые ставки центробанков и помесячная инфляция
  Бюро переписи США и BEA — штаты США
Ручные данные по регионам (страны вне Евростата) — data/macro/regions_manual/<страна>.json
"""
import csv, io, json, os, re, sys, time, zipfile, datetime as dt
import requests

OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'macro')
Y0 = 2000
TODAY = dt.date.today()
Y1 = TODAY.year
YEARS = list(range(Y0, Y1 + 1))
S = requests.Session()
S.headers['User-Agent'] = 'Mozilla/5.0 (ainewstobeinformed.ru macro data bot; +https://github.com/neimanr22-netizen/ainewstobeinformed)'
LOG = []

def log(*a):
    msg = ' '.join(str(x) for x in a)
    print(msg, flush=True); LOG.append(msg)

def get(url, params=None, tries=3, timeout=90, **kw):
    for k in range(tries):
        try:
            r = S.get(url, params=params, timeout=timeout, **kw)
            if r.status_code == 200:
                return r
            log(f'  HTTP {r.status_code} {r.url[:160]}')
            if r.status_code in (400, 404):
                return None
        except Exception as e:
            log(f'  ошибка {type(e).__name__}: {e} {url[:120]}')
        time.sleep(3 * (k + 1))
    return None

# id, название, ISO2, ISO3, код ВБ, код МВФ, код BIS, код Евростата, уровень NUTS для регионов, год перехода на евро
C = [
    ('ru', 'Россия',      'RU', 'RUS', 'RUS', 'RUS', 'RU', None,        None, None),
    ('us', 'США',         'US', 'USA', 'USA', 'USA', 'US', None,        None, None),
    ('eu', 'ЕС',          'EU', 'EUU', 'EUU', 'EU',  'XM', 'EU27_2020', 0,    1999),
    ('de', 'Германия',    'DE', 'DEU', 'DEU', 'DEU', 'DE', 'DE', 1, 1999),
    ('at', 'Австрия',     'AT', 'AUT', 'AUT', 'AUT', 'AT', 'AT', 2, 1999),
    ('ch', 'Швейцария',   'CH', 'CHE', 'CHE', 'CHE', 'CH', 'CH', 3, None),
    ('cz', 'Чехия',       'CZ', 'CZE', 'CZE', 'CZE', 'CZ', 'CZ', 3, None),
    ('sk', 'Словакия',    'SK', 'SVK', 'SVK', 'SVK', 'SK', 'SK', 3, 2009),
    ('hu', 'Венгрия',     'HU', 'HUN', 'HUN', 'HUN', 'HU', 'HU', 3, None),
    ('fr', 'Франция',     'FR', 'FRA', 'FRA', 'FRA', 'FR', 'FR', 1, 1999),
    ('it', 'Италия',      'IT', 'ITA', 'ITA', 'ITA', 'IT', 'IT', 2, 1999),
    ('es', 'Испания',     'ES', 'ESP', 'ESP', 'ESP', 'ES', 'ES', 2, 1999),
    ('pt', 'Португалия',  'PT', 'PRT', 'PRT', 'PRT', 'PT', 'PT', 2, 1999),
    ('nl', 'Нидерланды',  'NL', 'NLD', 'NLD', 'NLD', 'NL', 'NL', 2, 1999),
    ('be', 'Бельгия',     'BE', 'BEL', 'BEL', 'BEL', 'BE', 'BE', 2, 1999),
    ('lu', 'Люксембург',  'LU', 'LUX', 'LUX', 'LUX', 'LU', 'LU', 3, 1999),
    ('lv', 'Латвия',      'LV', 'LVA', 'LVA', 'LVA', 'LV', 'LV', 3, 2014),
    ('lt', 'Литва',       'LT', 'LTU', 'LTU', 'LTU', 'LT', 'LT', 3, 2015),
    ('ee', 'Эстония',     'EE', 'EST', 'EST', 'EST', 'EE', 'EE', 3, 2011),
    ('fi', 'Финляндия',   'FI', 'FIN', 'FIN', 'FIN', 'FI', 'FI', 3, 1999),
    ('se', 'Швеция',      'SE', 'SWE', 'SWE', 'SWE', 'SE', 'SE', 3, None),
    ('no', 'Норвегия',    'NO', 'NOR', 'NOR', 'NOR', 'NO', 'NO', 3, None),
    ('dk', 'Дания',       'DK', 'DNK', 'DNK', 'DNK', 'DK', 'DK', 2, None),
    ('cn', 'Китай',       'CN', 'CHN', 'CHN', 'CHN', 'CN', None, None, None),
    ('tr', 'Турция',      'TR', 'TUR', 'TUR', 'TUR', 'TR', 'TR', 2, None),
    ('my', 'Малайзия',    'MY', 'MYS', 'MYS', 'MYS', 'MY', None, None, None),
    ('sg', 'Сингапур',    'SG', 'SGP', 'SGP', 'SGP', 'SG', None, None, None),
    ('ph', 'Филиппины',   'PH', 'PHL', 'PHL', 'PHL', 'PH', None, None, None),
    ('id', 'Индонезия',   'ID', 'IDN', 'IDN', 'IDN', 'ID', None, None, None),
]
CN = {c[0]: dict(id=c[0], name=c[1], iso2=c[2], iso3=c[3], wb=c[4], imf=c[5], bis=c[6], estat=c[7], nuts=c[8], euro=c[9]) for c in C}

SRC = {
    'imf':   ('МВФ — World Economic Outlook (DataMapper)', 'https://www.imf.org/external/datamapper/'),
    'wb':    ('Всемирный банк — World Development Indicators', 'https://data.worldbank.org/'),
    'estat': ('Евростат', 'https://ec.europa.eu/eurostat/web/main/data/database'),
    'ecb':   ('ЕЦБ — курс EUR/USD', 'https://data.ecb.europa.eu/data/datasets/EXR/EXR.M.USD.EUR.SP00.A'),
    'bis':   ('BIS — ключевые ставки ЦБ и индексы потребительских цен', 'https://data.bis.org/'),
    'census':('Бюро переписи США — оценки населения штатов', 'https://www.census.gov/programs-surveys/popest.html'),
    'bea':   ('BEA — ВВП штатов США', 'https://www.bea.gov/data/gdp/gdp-state'),
}

# ---------------------------------------------------------------- ЕЦБ: курс EUR/USD
def ecb_usd():
    r = get('https://data-api.ecb.europa.eu/service/data/EXR/M.USD.EUR.SP00.A',
            {'format': 'csvdata', 'startPeriod': f'{Y0}-01'})
    if not r:
        raise SystemExit('ЕЦБ недоступен — без курса пересчёт в EUR невозможен')
    by = {}
    for row in csv.DictReader(io.StringIO(r.text)):
        y = int(row['TIME_PERIOD'][:4]); by.setdefault(y, []).append(float(row['OBS_VALUE']))
    rate = {y: sum(v) / len(v) for y, v in by.items()}
    log('ЕЦБ EUR/USD:', {y: round(v, 4) for y, v in rate.items() if y >= Y1 - 2}, f'месяцев в {Y1}: {len(by.get(Y1, []))}')
    return rate, {y: len(v) for y, v in by.items()}

# ---------------------------------------------------------------- МВФ DataMapper
def imf(ind, codes):
    out = {}
    for k in range(0, len(codes), 12):
        part = codes[k:k + 12]
        r = get(f'https://www.imf.org/external/datamapper/api/v1/{ind}/' + '/'.join(part),
                {'periods': ','.join(map(str, YEARS))})
        if not r:
            continue
        try:
            vals = r.json().get('values', {}).get(ind, {})
        except Exception as e:
            log('  МВФ: не JSON', ind, e); continue
        for c, ser in vals.items():
            out[c] = {int(y): float(v) for y, v in ser.items() if v is not None and Y0 <= int(y) <= Y1}
    log(f'МВФ {ind}: {len(out)} стран')
    return out

# ---------------------------------------------------------------- Всемирный банк
def wb(ind, codes):
    out = {}
    r = get(f'https://api.worldbank.org/v2/country/{";".join(codes)}/indicator/{ind}',
            {'format': 'json', 'per_page': 20000, 'date': f'{Y0}:{Y1}'})
    if not r:
        return out
    try:
        js = r.json()
        rows = js[1] or []
    except Exception as e:
        log('  ВБ: не JSON', ind, e); return out
    for x in rows:
        if x['value'] is None:
            continue
        out.setdefault(x['countryiso3code'] or x['country']['id'], {})[int(x['date'])] = float(x['value'])
    log(f'ВБ {ind}: {len(out)} стран')
    return out

def wb_latest(ind, codes):
    """Последнее доступное значение и год."""
    d = wb(ind, codes)
    return {c: (max(s), s[max(s)]) for c, s in d.items() if s}

# ---------------------------------------------------------------- Евростат (JSON-stat)
def jsonstat_rows(js):
    ids, sizes = js['id'], js['size']
    cats = []
    for d in ids:
        idx = js['dimension'][d]['category']['index']
        inv = {v: k for k, v in idx.items()} if isinstance(idx, dict) else dict(enumerate(idx))
        cats.append(inv)
    strides = [1] * len(ids)
    for i in range(len(ids) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    vals = js.get('value', {})
    items = vals.items() if isinstance(vals, dict) else enumerate(vals)
    for flat, v in items:
        if v is None:
            continue
        flat = int(flat); rec = {}
        for i, d in enumerate(ids):
            rec[d] = cats[i][(flat // strides[i]) % sizes[i]]
        rec['value'] = v
        yield rec

def estat(ds, params, label=False):
    p = {'format': 'JSON', 'lang': 'EN'}; p.update(params)
    r = get(f'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{ds}', p, timeout=180)
    if not r:
        return None, None
    js = r.json()
    if 'error' in js:
        log('  Евростат:', ds, js['error']); return None, None
    labels = js['dimension']['geo']['category'].get('label', {}) if label else None
    return list(jsonstat_rows(js)), labels

def estat_series(ds, params, geos, timefmt='A'):
    """{geo: {период: значение}}; для годовых — ключи int."""
    out = {}
    pp = dict(params); pp['geo'] = geos
    rows, _ = estat(ds, pp)
    if rows is None:
        return None
    for x in rows:
        t = x['time']
        key = int(t) if timefmt == 'A' else t.replace('M', '-')
        if timefmt == 'A' and not (Y0 <= key <= Y1):
            continue
        out.setdefault(x['geo'], {})[key] = float(x['value'])
    log(f'Евростат {ds}: {len(out)} стран')
    return out

def estat_try(variants, geos, timefmt='A'):
    for ds, params in variants:
        d = estat_series(ds, params, geos, timefmt)
        if d:
            return d, ds
    return {}, None

def ecb_hicp(area):
    r = get(f'https://data-api.ecb.europa.eu/service/data/ICP/M.{area}.N.000000.4.ANR',
            {'format': 'csvdata', 'startPeriod': f'{Y0}-01'}, tries=2)
    if not r:
        return {}
    out = {}
    for row in csv.DictReader(io.StringIO(r.text)):
        if row.get('OBS_VALUE'):
            out[row['TIME_PERIOD'][:7]] = float(row['OBS_VALUE'])
    return out

# ---------------------------------------------------------------- BIS
def bis(flow, key):
    for url in (f'https://stats.bis.org/api/v1/data/{flow}/{key}/all',
                f'https://stats.bis.org/api/v2/data/dataflow/BIS/{flow}/1.0/{key}'):
        r = get(url, {'format': 'csv', 'startPeriod': f'{Y0 - 1}-01'}, tries=2)
        if not r or not r.text.strip():
            continue
        out = {}
        for row in csv.DictReader(io.StringIO(r.text)):
            t, v = row.get('TIME_PERIOD'), row.get('OBS_VALUE')
            if t and v not in (None, '', 'NaN'):
                out[t[:7]] = float(v)
        if out:
            return out
    return {}

# ---------------------------------------------------------------- регионы
def nuts_level(code):
    return len(code) - 2

def estat_regions():
    """Население, плотность и ВВП на душу (EUR) по регионам NUTS для всех стран Евростата."""
    res = {}
    pop, lab = estat('demo_r_pjanaggr3', {'sex': 'T', 'age': 'TOTAL', 'unit': 'NR', 'lastTimePeriod': 3}, label=True)
    dens, lab2 = estat('demo_r_d3dens', {'unit': 'PER_KM2', 'lastTimePeriod': 3}, label=True)
    gdp, lab3 = estat('nama_10r_3gdp', {'unit': 'EUR_HAB', 'lastTimePeriod': 3}, label=True)
    labels = {}
    for L in (lab3, lab2, lab):
        if L: labels.update(L)
    def latest(rows):
        d = {}
        for x in rows or []:
            g, t = x['geo'], int(x['time'])
            if g not in d or t > d[g][0]:
                d[g] = (t, float(x['value']))
        return d
    P, D, G = latest(pop), latest(dens), latest(gdp)
    log(f'Регионы Евростата: население {len(P)}, плотность {len(D)}, ВВП {len(G)}')
    return P, D, G, labels

def regions_for(c, P, D, G, labels):
    if c['nuts'] is None:
        return None
    def build(codes):
        rows = []
        for g in codes:
            p, d, x = P.get(g), D.get(g), G.get(g)
            if not (p or d or x):
                continue
            rows.append({'code': g, 'name': labels.get(g, g),
                         'pop': p[1] if p else None, 'pop_y': p[0] if p else None,
                         'dens': d[1] if d else None, 'dens_y': d[0] if d else None,
                         'gdp_pc': x[1] if x else None, 'gdp_y': x[0] if x else None})
        # только действующее деление: регионы с населением за последний год
        ly = max((r['pop_y'] for r in rows if r['pop_y']), default=None)
        if ly:
            rows = [r for r in rows if r['pop_y'] == ly]
        return rows
    if c['id'] == 'eu':
        rows = build(['BE','BG','CZ','DK','DE','EE','IE','EL','ES','FR','HR','IT','CY','LV','LT','LU','HU','MT','NL','AT','PL','PT','RO','SI','SK','FI','SE'])
        title = 'Страны — члены ЕС'
    else:
        cc = c['estat']
        def codes(lv):
            return sorted(g for g in set(P) | set(D) | set(G)
                          if g.startswith(cc) and nuts_level(g) == lv and not g[len(cc):].startswith('Z'))
        lv = c['nuts']; rows = build(codes(lv))
        if rows and not any(r['gdp_pc'] for r in rows):
            # на этом уровне нет ВВП — пробуем более крупные регионы
            for l2 in range(lv - 1, 0, -1):
                r2 = build(codes(l2))
                if len(r2) > 1 and any(r['gdp_pc'] for r in r2):
                    log(f'  регионы {cc}: на уровне NUTS {lv} нет ВВП, берём NUTS {l2}'); rows, lv = r2, l2; break
        title = {1: 'Регионы NUTS 1', 2: 'Регионы NUTS 2', 3: 'Регионы NUTS 3'}[lv]
    if not rows:
        return None
    rows.sort(key=lambda r: -(r['pop'] or 0))
    years = lambda k: sorted({r[k] for r in rows if r[k]})
    note = None
    if c['id'] == 'no':
        note = 'Норвегия изменила деление на губернии (фюльке) с 1 января 2024 г.; плотность и ВРП по новым регионам Евростат пока не публикует.'
    return {'level': title, 'currency': 'EUR', 'rows': rows, **({'note': note} if note else {}),
            'years': {'pop': years('pop_y'), 'dens': years('dens_y'), 'gdp': years('gdp_y')},
            'sources': [
                ['Евростат: население регионов на 1 января (demo_r_pjanaggr3)', 'https://ec.europa.eu/eurostat/databrowser/view/demo_r_pjanaggr3/default/table'],
                ['Евростат: плотность населения по регионам (demo_r_d3dens)', 'https://ec.europa.eu/eurostat/databrowser/view/demo_r_d3dens/default/table'],
                ['Евростат: ВВП регионов на душу населения, EUR (nama_10r_3gdp)', 'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3gdp/default/table'],
            ]}

US_STATES = {'01':'Alabama','02':'Alaska','04':'Arizona','05':'Arkansas','06':'California','08':'Colorado','09':'Connecticut','10':'Delaware','11':'District of Columbia','12':'Florida','13':'Georgia','15':'Hawaii','16':'Idaho','17':'Illinois','18':'Indiana','19':'Iowa','20':'Kansas','21':'Kentucky','22':'Louisiana','23':'Maine','24':'Maryland','25':'Massachusetts','26':'Michigan','27':'Minnesota','28':'Mississippi','29':'Missouri','30':'Montana','31':'Nebraska','32':'Nevada','33':'New Hampshire','34':'New Jersey','35':'New Mexico','36':'New York','37':'North Carolina','38':'North Dakota','39':'Ohio','40':'Oklahoma','41':'Oregon','42':'Pennsylvania','44':'Rhode Island','45':'South Carolina','46':'South Dakota','47':'Tennessee','48':'Texas','49':'Utah','50':'Vermont','51':'Virginia','53':'Washington','54':'West Virginia','55':'Wisconsin','56':'Wyoming'}
US_RU = {'Alabama':'Алабама','Alaska':'Аляска','Arizona':'Аризона','Arkansas':'Арканзас','California':'Калифорния','Colorado':'Колорадо','Connecticut':'Коннектикут','Delaware':'Делавэр','District of Columbia':'Округ Колумбия','Florida':'Флорида','Georgia':'Джорджия','Hawaii':'Гавайи','Idaho':'Айдахо','Illinois':'Иллинойс','Indiana':'Индиана','Iowa':'Айова','Kansas':'Канзас','Kentucky':'Кентукки','Louisiana':'Луизиана','Maine':'Мэн','Maryland':'Мэриленд','Massachusetts':'Массачусетс','Michigan':'Мичиган','Minnesota':'Миннесота','Mississippi':'Миссисипи','Missouri':'Миссури','Montana':'Монтана','Nebraska':'Небраска','Nevada':'Невада','New Hampshire':'Нью-Гэмпшир','New Jersey':'Нью-Джерси','New Mexico':'Нью-Мексико','New York':'Нью-Йорк','North Carolina':'Северная Каролина','North Dakota':'Северная Дакота','Ohio':'Огайо','Oklahoma':'Оклахома','Oregon':'Орегон','Pennsylvania':'Пенсильвания','Rhode Island':'Род-Айленд','South Carolina':'Южная Каролина','South Dakota':'Южная Дакота','Tennessee':'Теннесси','Texas':'Техас','Utah':'Юта','Vermont':'Вермонт','Virginia':'Виргиния','Washington':'Вашингтон','West Virginia':'Западная Виргиния','Wisconsin':'Висконсин','Wyoming':'Вайоминг'}

def us_regions(usd):
    # население: Census Vintage (последний доступный)
    pop, pop_y, pop_url = {}, None, None
    for v in range(Y1, Y1 - 4, -1):
        url = f'https://www2.census.gov/programs-surveys/popest/datasets/2020-{v}/state/totals/NST-EST{v}-ALLDATA.csv'
        r = get(url, tries=1)
        if not r:
            continue
        rd = csv.DictReader(io.StringIO(r.content.decode('latin-1')))
        for row in rd:
            if row.get('SUMLEV') == '040' and row.get('STATE') in US_STATES:
                pop[US_STATES[row['STATE']]] = float(row[f'POPESTIMATE{v}'])
        if pop:
            pop_y, pop_url = v, url; break
    log(f'Census: население {len(pop)} штатов, {pop_y}')
    # площадь суши: Census Gazetteer
    land, land_url = {}, None
    for v in range(Y1, Y1 - 6, -1):
        url = f'https://www2.census.gov/geo/docs/maps-data/data/gazetteer/{v}_Gazetteer/{v}_Gaz_state_national.zip'
        r = get(url, tries=1)
        if not r:
            continue
        try:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            txt = z.read(z.namelist()[0]).decode('latin-1')
            rows = list(csv.DictReader(io.StringIO(txt), delimiter='\t'))
            for row in rows:
                row = {k.strip(): (v or '').strip() for k, v in row.items() if k}
                if row.get('NAME') in US_RU:
                    land[row['NAME']] = float(row['ALAND_SQMI']) * 2.589988
            if land:
                land_url = url; break
        except Exception as e:
            log('  Gazetteer:', e)
    log(f'Census Gazetteer: площадь {len(land)} штатов')
    # ВВП штатов: BEA, SAGDP2 (текущие доллары, млн)
    gdp, gdp_y = {}, None
    r = get('https://apps.bea.gov/regional/zip/SAGDP.zip', timeout=300)
    if r:
        try:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            name = next(n for n in z.namelist() if re.match(r'SAGDP2(N|__)?_?ALL_AREAS.*\.csv', n, re.I) or re.match(r'SAGDP2.*ALL_AREAS.*\.csv', n, re.I))
            txt = z.read(name).decode('latin-1')
            rows = list(csv.DictReader(io.StringIO(txt)))
            ycols = [k for k in rows[0] if k and k.strip().isdigit()]
            for row in rows:
                if (row.get('LineCode') or '').strip() == '1' and (row.get('GeoName') or '').strip().rstrip(' *') in US_RU:
                    nm = row['GeoName'].strip().rstrip(' *')
                    for yc in sorted(ycols, reverse=True):
                        try:
                            gdp[nm] = (int(yc), float(row[yc]) * 1e6); break
                        except Exception:
                            continue
            gdp_y = max((v[0] for v in gdp.values()), default=None)
            log(f'BEA: ВВП {len(gdp)} штатов ({name}), {gdp_y}')
        except Exception as e:
            log('  BEA:', e)
    if not pop:
        return None
    rows = []
    for nm, p in pop.items():
        g = gdp.get(nm)
        gpc = None
        if g and g[0] in usd:
            # ВВП на душу считаем по населению того же года, если есть, иначе по последнему
            gpc = g[1] / p / usd[g[0]]
        rows.append({'code': nm, 'name': US_RU[nm], 'pop': p, 'pop_y': pop_y,
                     'dens': p / land[nm] if nm in land else None, 'dens_y': pop_y if nm in land else None,
                     'gdp_pc': gpc, 'gdp_y': g[0] if g else None})
    rows.sort(key=lambda r: -r['pop'])
    years = lambda k: sorted({r[k] for r in rows if r[k]})
    return {'level': 'Штаты и округ Колумбия', 'currency': 'EUR', 'rows': rows,
            'years': {'pop': years('pop_y'), 'dens': years('dens_y'), 'gdp': years('gdp_y')},
            'note': 'Плотность — население / площадь суши (Gazetteer). ВВП штата на душу — ВВП штата в текущих долларах (BEA) / население, пересчитано в EUR по среднегодовому курсу ЕЦБ.',
            'sources': [['Бюро переписи США: оценки населения штатов', pop_url],
                        ['Бюро переписи США: Gazetteer (площадь суши)', land_url or 'https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html'],
                        ['BEA: ВВП штатов (SAGDP2)', 'https://apps.bea.gov/regional/downloadzip.htm']]}

_FX = {}
def ecb_annual(cur):
    """Среднегодовой курс ЕЦБ: единиц валюты за 1 EUR."""
    if cur not in _FX:
        r = get(f'https://data-api.ecb.europa.eu/service/data/EXR/A.{cur}.EUR.SP00.A', {'format': 'csvdata', 'startPeriod': '2015'})
        _FX[cur] = {int(x['TIME_PERIOD']): float(x['OBS_VALUE']) for x in csv.DictReader(io.StringIO(r.text))} if r else {}
        log(f'ЕЦБ курс {cur}/EUR:', {y: round(v, 4) for y, v in _FX[cur].items() if y >= Y1 - 3})
    return _FX[cur]

def finish_regions(d):
    """Пересчёт ВРП на душу из национальной валюты в EUR и сводка лет."""
    cur = d.get('currency_nat')
    if cur:
        fx = ecb_annual(cur)
        for r in d['rows']:
            v, y = r.get('gdp_pc_nat'), r.get('gdp_y')
            r['gdp_pc'] = v / fx[y] if v is not None and y in fx else None
        d['sources'] = d['sources'] + [[f'ЕЦБ: среднегодовой курс {cur}/EUR (для пересчёта в евро)', f'https://data.ecb.europa.eu/data/datasets/EXR/EXR.A.{cur}.EUR.SP00.A']]
    d['currency'] = 'EUR'
    years = lambda k: sorted({r[k] for r in d['rows'] if r.get(k)})
    d['years'] = {'pop': years('pop_y'), 'dens': years('dens_y'), 'gdp': years('gdp_y')}
    return d

PH_RU = {'National Capital Region': 'Столичный регион (Манила)', 'Cordillera Administrative Region': 'Кордильерский административный регион',
         'Ilocos Region': 'Илокос', 'Cagayan Valley': 'Долина Кагаян', 'Central Luzon': 'Центральный Лусон', 'CALABARZON': 'Калабарсон',
         'MIMAROPA': 'Мимаропа', 'Bicol Region': 'Бикол', 'Western Visayas': 'Западные Висайи', 'Central Visayas': 'Центральные Висайи',
         'Eastern Visayas': 'Восточные Висайи', 'Zamboanga Peninsula': 'Полуостров Замбоанга', 'Northern Mindanao': 'Северный Минданао',
         'Davao Region': 'Давао', 'SOCCSKSARGEN': 'Сокскарген', 'Caraga': 'Карага', 'Bangsamoro': 'Бангсаморо (BARMM)',
         'Negros Island Region': 'Регион острова Негрос'}
def ph_key(label):
    t = label.replace(' ', ' ')
    for k in PH_RU:
        if k.lower() in t.lower():
            return k
    m = re.search(r'Region\s+([IVX]+[AB]?)\b', t)
    roman = {'I': 'Ilocos Region', 'II': 'Cagayan Valley', 'III': 'Central Luzon', 'IVA': 'CALABARZON', 'IV-A': 'CALABARZON', 'IVB': 'MIMAROPA',
             'V': 'Bicol Region', 'VI': 'Western Visayas', 'VII': 'Central Visayas', 'VIII': 'Eastern Visayas', 'IX': 'Zamboanga Peninsula',
             'X': 'Northern Mindanao', 'XI': 'Davao Region', 'XII': 'SOCCSKSARGEN', 'XIII': 'Caraga'}
    return roman.get(m.group(1)) if m else None

def pxweb(url, pick):
    """Запрос к PXWeb (PSA OpenSTAT). pick(code, values, texts) -> список кодов или None (= все).
    Возвращает список записей {код_переменной: (код, текст), ..., 'value': число}."""
    r = get(url)
    if not r:
        return None
    meta = r.json(); q = []; lab = {}
    for v in meta['variables']:
        vals = v.get('values'); txts = v.get('valueTexts', vals)
        if vals: lab[v['code']] = dict(zip(vals, txts))
        sel = pick(v['code'], vals, txts)
        q.append({'code': v['code'], 'selection': {'filter': 'all', 'values': ['*']} if sel is None else {'filter': 'item', 'values': sel}})
    rr = S.post(url, json={'query': q, 'response': {'format': 'json'}}, timeout=180)
    if rr.status_code != 200:
        log('  PXWeb', rr.status_code, rr.text[:200]); return None
    js = json.loads(rr.content.decode('utf-8-sig'))
    cols = [c['code'] for c in js['columns'] if c.get('type') != 'c']
    out = []
    for row in js['data']:
        v = row['values'][0]
        try: v = float(str(v).replace(',', ''))
        except Exception: continue
        rec = {c: (k, lab.get(c, {}).get(k, k)) for c, k in zip(cols, row['key'])}
        rec['value'] = v; out.append(rec)
    log(f'  PXWeb {url.rsplit("/", 1)[-1]}: {len(out)} значений; пример: {out[:2]}')
    return out

def ph_regions():
    base = 'https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB/'
    # ВРП на душу, текущие цены (последний год)
    gdp, gy, names = {}, None, {}
    def pick_gdp(code, vals, txts):
        if vals is None: return None
        if 'year' in code.lower() or 'period' in code.lower(): return [vals[-1]]
        cur = [v for v, t in zip(vals, txts) if 'current' in t.lower()]
        return cur[:1] if cur else None
    js = pxweb(base + '2B/GP/RG/PCI/0772B5BPCP1.px', pick_gdp) or []
    for x in js:
        code, label = x['Region']; k = ph_key(label)
        if k:
            gdp[code] = x['value']; names[code] = k; gy = int(x['Year'][1])
    # население и площадь — перепись 2024 (коды PSGC; регионы — XX00000000)
    pop = {}
    def pick_pop(code, vals, txts):
        if vals is None: return None
        if code == 'Parameter':
            return [v for v, t in zip(vals, txts) if t.startswith('2024 Population') or 'Land Area' in t]
        return None
    for x in pxweb(base + '1A/PO_2024/0221A6DLPD0.px', pick_pop) or []:
        code = x['Geographic Location'][0]
        if not re.match(r'^\d{2}0{8}$', code) or code == '0000000000':
            continue
        par = x['Parameter'][1]
        pop.setdefault(code, {}).setdefault('pop' if 'Population' in par else 'area', x['value'])
    log('PSA: регионов с населением', len(pop), '; с ВРП', len(gdp), gy, '; без названия:', [c for c in pop if c not in names])
    if not gdp:
        return None
    rows = []
    for code, k in names.items():
        d = pop.get(code, {}); p = d.get('pop'); a = d.get('area')
        rows.append({'code': code, 'name': PH_RU[k], 'pop': p, 'pop_y': 2024 if p else None,
                     'dens': p / a if p and a else None, 'dens_y': 2024 if p and a else None,
                     'gdp_pc_nat': gdp[code], 'gdp_y': gy})
    rows.sort(key=lambda r: -(r['pop'] or 0))
    return finish_regions({'level': 'Регионы (18)', 'currency_nat': 'PHP', 'rows': rows,
        'note': 'Население и площадь — перепись населения на 1 июля 2024 г.; ВРП на душу населения — в текущих ценах, пересчитан из песо в евро по среднегодовому курсу ЕЦБ.',
        'sources': [['Статистическое управление Филиппин (PSA): население, площадь и плотность по регионам, перепись 2024', 'https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/DB__1A__PO_2024/0221A6DLPD0.px/'],
                    ['Статистическое управление Филиппин (PSA): ВРП на душу населения по регионам', 'https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/DB__2B__GP__RG__PCI/0772B5BPCP1.px/']]})

CH_NUTS = {'Vaud': 'CH011', 'Valais': 'CH012', 'Geneva': 'CH013', 'Berne': 'CH021', 'Fribourg': 'CH022', 'Solothurn': 'CH023',
           'Neuchâtel': 'CH024', 'Jura': 'CH025', 'Basel-Stadt': 'CH031', 'Basel-Landschaft': 'CH032', 'Aargau': 'CH033', 'Zurich': 'CH040',
           'Glarus': 'CH051', 'Schaffhausen': 'CH052', 'Appenzell A. Rh.': 'CH053', 'Appenzell I. Rh.': 'CH054', 'St. Gallen': 'CH055',
           'Graubünden': 'CH056', 'Thurgau': 'CH057', 'Lucerne': 'CH061', 'Uri': 'CH062', 'Schwyz': 'CH063', 'Obwalden': 'CH064',
           'Nidwalden': 'CH065', 'Zug': 'CH066', 'Ticino': 'CH070'}
def ch_patch(reg):
    """ВВП кантонов на душу (BFS, CHF) — в Евростате его нет."""
    page = 'https://www.bfs.admin.ch/asset/en/je-e-04.02.06.03'
    r = get(page)
    m = r and re.search(r'https://dam-api\.bfs\.admin\.ch/hub/api/dam/assets/\d+/master', r.text)
    if not m:
        log('BFS: ссылка на таблицу не найдена'); return
    x = get(m.group(0))
    from python_calamine import CalamineWorkbook
    wb_ = CalamineWorkbook.from_filelike(io.BytesIO(x.content))
    rows = [tuple(r) for r in wb_.get_sheet_by_index(0).to_python()]
    hdr = next(r for r in rows if r and r[0] == 'Canton')
    rows = [tuple(None if v == '' else v for v in r) for r in rows]; hdr = tuple(None if v == '' else v for v in hdr)
    years = [(i, int(str(v).rstrip('p').split('.')[0])) for i, v in enumerate(hdr) if v and str(v).rstrip('p').split('.')[0].isdigit()]
    i, y = years[-1]
    vals = {}
    for r in rows[rows.index(hdr) + 1:]:
        if not r or r[0] is None: break
        if r[0] in CH_NUTS and isinstance(r[i], (int, float)):
            vals[CH_NUTS[r[0]]] = r[i]
    fx = ecb_annual('CHF')
    n = 0
    for row in reg['rows']:
        if row['code'] in vals and y in fx:
            row['gdp_pc'] = vals[row['code']] / fx[y]; row['gdp_y'] = y; n += 1
    reg['years']['gdp'] = [y]
    reg['sources'] += [['Федеральное статистическое управление Швейцарии (BFS): ВВП кантонов на душу населения, CHF', page],
                       ['ЕЦБ: среднегодовой курс CHF/EUR (для пересчёта в евро)', 'https://data.ecb.europa.eu/data/datasets/EXR/EXR.A.CHF.EUR.SP00.A']]
    reg['note'] = f'ВВП кантонов на душу — данные BFS за {y} г. (предварительные), пересчитаны из франков в евро по среднегодовому курсу ЕЦБ.'
    log(f'BFS: ВВП на душу для {n} кантонов, {y}')

def manual_regions(cid):
    p = os.path.join(OUT, 'regions_manual', cid + '.json')
    if os.path.exists(p):
        d = json.load(open(p, encoding='utf-8'))
        return d if d.get('patch') else finish_regions(d)
    return None

# ---------------------------------------------------------------- сборка
def pick(*sources):
    """Сливает ряды {год: значение}: первый источник главный, остальные заполняют пропуски.
    Возвращает (ряд, {год: ключ_источника})."""
    ser, src = {}, {}
    for key, s in sources:
        for y, v in (s or {}).items():
            if y not in ser and v is not None:
                ser[y] = v; src[y] = key
    return dict(sorted(ser.items())), src

def to_eur(s, usd, scale=1.0):
    return {y: v * scale / usd[y] for y, v in (s or {}).items() if y in usd}

def main():
    os.makedirs(OUT, exist_ok=True)
    usd, usd_n = ecb_usd()
    ids = list(CN)
    wbc = [CN[i]['wb'] for i in ids]
    imfc = [CN[i]['imf'] for i in ids]
    estc = [CN[i]['estat'] for i in ids if CN[i]['estat']]

    # --- годовые ряды
    I = {k: imf(k, imfc) for k in ('NGDPD', 'NGDPDPC', 'PCPIPCH', 'LUR')}
    W = {k: wb(k, wbc) for k in ('NY.GDP.MKTP.CD', 'NY.GDP.PCAP.CD', 'NE.RSB.GNFS.CD', 'NY.GNP.PCAP.CD',
                                  'FP.CPI.TOTL.ZG', 'SL.UEM.TOTL.ZS')}
    E = {}
    E['gdp'], _ = estat_try([('nama_10_gdp', {'na_item': 'B1GQ', 'unit': 'CP_MEUR'})], estc)
    E['gdp_pc'], _ = estat_try([('nama_10_pc', {'na_item': 'B1GQ', 'unit': 'CP_EUR_HAB'})], estc)
    ex, _ = estat_try([('nama_10_gdp', {'na_item': 'P6', 'unit': 'CP_MEUR'})], estc)
    im, _ = estat_try([('nama_10_gdp', {'na_item': 'P7', 'unit': 'CP_MEUR'})], estc)
    E['net_exp'] = {g: {y: ex[g][y] - im[g][y] for y in ex[g] if y in im.get(g, {})} for g in ex}
    E['infl'], E['infl_ds'] = estat_try([('prc_hicp_ainr', {'unit': 'RCH_A_AVG', 'coicop18': 'TOTAL'}),
                                         ('prc_hicp_aind', {'unit': 'RCH_A_AVG', 'coicop': 'CP00'})], estc)
    E['unemp'], _ = estat_try([('une_rt_a', {'age': 'Y15-74', 'sex': 'T', 'unit': 'PC_ACT'})], estc)
    E['infl_m'], E['infl_m_ds'] = estat_try([('prc_hicp_minr', {'unit': 'RCH_A', 'coicop18': 'TOTAL'}),
                                             ('prc_hicp_manr', {'unit': 'RCH_A', 'coicop': 'CP00'})], estc, 'M')
    log('Евростат HICP: годовой —', E['infl_ds'], '; месячный —', E['infl_m_ds'])

    # --- общие сведения
    G = {k: wb_latest(k, wbc) for k in ('AG.SRF.TOTL.K2', 'AG.LND.TOTL.K2', 'SP.POP.TOTL', 'SP.URB.TOTL.IN.ZS', 'EN.POP.DNST')}

    # --- регионы
    try:
        RP, RD, RG, RL = estat_regions()
    except Exception as e:
        log('Регионы Евростата: ошибка', e); RP = RD = RG = {}; RL = {}

    # --- ставки и месячная инфляция
    xm_rate = bis('WS_CBPOL', 'M.XM')
    log('BIS ставка ЕЦБ:', len(xm_rate), 'мес.')
    est_years = {Y1}   # для текущего года данные МВФ — оценка/прогноз

    meta_c = []
    for cid in ids:
        c = CN[cid]; e = c['estat']; i3 = c['imf']; w = c['wb']
        A, srcs = {}, {}
        def put(key, *s):
            A[key], srcs[key] = pick(*s)
        put('gdp', ('estat', to_eur(E['gdp'].get(e), {y: 1 for y in YEARS}, 1e6) if e else None),
                   ('imf', to_eur(I['NGDPD'].get(i3), usd, 1e9)),
                   ('wb', to_eur(W['NY.GDP.MKTP.CD'].get(w), usd)))
        put('gdp_pc', ('estat', E['gdp_pc'].get(e) if e else None),
                      ('imf', to_eur(I['NGDPDPC'].get(i3), usd)),
                      ('wb', to_eur(W['NY.GDP.PCAP.CD'].get(w), usd)))
        put('net_exp', ('estat', {y: v * 1e6 for y, v in E['net_exp'].get(e, {}).items()} if e else None),
                       ('wb', to_eur(W['NE.RSB.GNFS.CD'].get(w), usd)))
        put('infl', ('estat', E['infl'].get(e) if e else None),
                    ('imf', I['PCPIPCH'].get(i3)),
                    ('wb', W['FP.CPI.TOTL.ZG'].get(w)))
        put('income', ('wb', to_eur(W['NY.GNP.PCAP.CD'].get(w), usd)))
        put('unemp', ('estat', E['unemp'].get(e) if e else None),
                     ('imf', I['LUR'].get(i3)),
                     ('wb', W['SL.UEM.TOTL.ZS'].get(w)))
        # оценки: значения МВФ за текущий год
        est = {k: sorted(y for y, s in srcs[k].items() if s == 'imf' and y in est_years) for k in srcs}

        # месячная инфляция
        M, msrc = {}, {}
        fresh = (TODAY - dt.timedelta(days=200)).strftime('%Y-%m')
        hicp = E['infl_m'].get(e) if e else None
        if hicp and max(hicp) >= fresh:
            M['infl_m'] = {k: v for k, v in sorted(hicp.items()) if k >= f'{Y0}-01'}; msrc['infl_m'] = ['estat']
        else:
            if hicp: log(f'  Евростат HICP {e} устарел (до {max(hicp)})')
            b = bis('WS_LONG_CPI', f'M.{c["bis"]}.771')
            M['infl_m'] = {k: v for k, v in sorted(b.items()) if k >= f'{Y0}-01'}; msrc['infl_m'] = ['bis'] if b else []
        # ключевая ставка (для стран еврозоны — ставка ЕЦБ с года перехода на евро)
        own = {} if c['bis'] == 'XM' or c['euro'] == 1999 else bis('WS_CBPOL', f'M.{c["bis"]}')
        rate, rsrc = {}, []
        if c['euro']:
            for k, v in xm_rate.items():
                if int(k[:4]) >= c['euro']:
                    rate[k] = v
            if rate: rsrc.append('ecb_rate')
            for k, v in own.items():
                if int(k[:4]) < c['euro'] and k not in rate:
                    rate[k] = v
            if any(int(k[:4]) < c['euro'] for k in own): rsrc.append('bis')
        else:
            rate = own
            if own: rsrc.append('bis')
        M['rate_m'] = {k: v for k, v in sorted(rate.items()) if k >= f'{Y0}-01'}; msrc['rate_m'] = rsrc
        # годовая ключевая ставка — на конец года (декабрь; для текущего года — последний месяц)
        ry = {}
        for k, v in M['rate_m'].items():
            ry[int(k[:4])] = v
        A['rate'] = ry; srcs['rate'] = {y: (rsrc[0] if rsrc else 'bis') for y in ry}
        log(f'{cid}: ' + ', '.join(f'{k}={len(v)}' for k, v in A.items()) + ', ' + ', '.join(f'{k}={len(v)}' for k, v in M.items()))

        # общие сведения
        gen = {}
        for key, ind in (('area', 'AG.SRF.TOTL.K2'), ('land', 'AG.LND.TOTL.K2'), ('pop', 'SP.POP.TOTL'), ('urban', 'SP.URB.TOTL.IN.ZS')):
            if w in G[ind]:
                gen[key] = {'year': G[ind][w][0], 'value': G[ind][w][1]}
        if 'pop' in gen and 'land' in gen:
            gen['dens'] = {'year': gen['pop']['year'], 'value': gen['pop']['value'] / gen['land']['value']}
        elif w in G['EN.POP.DNST']:
            gen['dens'] = {'year': G['EN.POP.DNST'][w][0], 'value': G['EN.POP.DNST'][w][1]}

        # регионы
        reg = None
        if cid == 'us':
            try: reg = us_regions(usd)
            except Exception as ex: log('США регионы: ошибка', ex)
        elif cid == 'ph':
            try: reg = ph_regions()
            except Exception as ex: log('Филиппины регионы: ошибка', repr(ex))
        elif c['nuts'] is not None and RP:
            reg = regions_for(c, RP, RD, RG, RL)
            if cid == 'ch' and reg:
                try: ch_patch(reg)
                except Exception as ex: log('BFS: ошибка', repr(ex))
        man = manual_regions(cid)
        if man and (not reg or man.get('override')):
            reg = man
        elif man and reg and man.get('patch'):
            pt = man['patch']
            for r in reg['rows']:
                x = pt['rows'].get(r['code'])
                if x:
                    for k, v in x.items():
                        if r.get(k) is None: r[k] = v
            reg['years'][pt['field']] = pt['years']
            reg['sources'] += pt['sources']
            if pt.get('note'): reg['note'] = (reg.get('note', '') + ' ' + pt['note']).strip()

        def used(k, d): return sorted(set(d.values()) if isinstance(d, dict) else set(d))
        data = {
            'id': cid, 'name': c['name'], 'updated': TODAY.isoformat(),
            'annual': {k: {str(y): v for y, v in s.items()} for k, s in A.items()},
            'annual_src': {k: {str(y): v for y, v in s.items()} for k, s in srcs.items()},
            'estimates': {k: v for k, v in est.items() if v},
            'monthly': M, 'monthly_src': msrc,
            'general': gen, 'regions': reg,
            'euro_from': c['euro'],
        }
        with open(os.path.join(OUT, cid + '.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        meta_c.append({'id': cid, 'name': c['name'], 'iso3': c['iso3']})

    last_m = max((max(json.load(open(os.path.join(OUT, x['id'] + '.json')))['monthly'].get(k) or {'0': 0}) for x in meta_c for k in ('infl_m', 'rate_m')))
    meta = {'updated': TODAY.isoformat(), 'last_month': last_m, 'countries': meta_c,
            'eurusd': {str(y): round(v, 6) for y, v in usd.items()},
            'eurusd_months': {str(y): n for y, n in usd_n.items()},
            'sources': SRC,
            'datasets': {'hicp_annual': E.get('infl_ds'), 'hicp_monthly': E.get('infl_m_ds')}}
    with open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, 'fetch_log.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(LOG) + '\n')

if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--debug':
        fn = {'ph': ph_regions}[sys.argv[2]]
        import pprint
        _orig = pxweb
        pprint.pprint(fn())
    else:
        main()
