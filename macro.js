/* Раздел «Статистика → Макроэкономика» (#/stats/macro).
   Данные: data/macro/meta.json и data/macro/<страна>.json — собираются tools/macro_fetch.py
   через GitHub Actions (.github/workflows/macro.yml). */
(() => {
const IND = [
  {id: 'gdp',     name: 'ВВП в EUR',                       per: 'year',  unit: 'млрд EUR', k: 1e-9, dig: 1},
  {id: 'gdp_pc',  name: 'ВВП в EUR на душу населения',     per: 'year',  unit: 'EUR',      k: 1,    dig: 0},
  {id: 'net_exp', name: 'Размер чистого экспорта',         per: 'year',  unit: 'млрд EUR', k: 1e-9, dig: 1, about: 'экспорт минус импорт товаров и услуг'},
  {id: 'infl',    name: 'Годовая инфляция',                per: 'year',  unit: '%',        k: 1,    dig: 1, about: 'рост цен в среднем за год к предыдущему году'},
  {id: 'infl_m',  name: 'Помесячная годовая инфляция',     per: 'month', unit: '%',        k: 1,    dig: 1, about: 'цены месяца к тому же месяцу прошлого года'},
  {id: 'rate',    name: 'Ключевая ставка',                 per: 'year',  unit: '%',        k: 1,    dig: 2, about: 'на конец года'},
  {id: 'rate_m',  name: 'Месячная ключевая ставка',        per: 'month', unit: '%',        k: 1,    dig: 2, about: 'на конец месяца'},
  {id: 'income',  name: 'Средний доход населения в EUR',   per: 'year',  unit: 'EUR',      k: 1,    dig: 0, about: 'валовой национальный доход на душу населения'},
  {id: 'unemp',   name: 'Безработица',                     per: 'year',  unit: '%',        k: 1,    dig: 1, about: 'доля безработных в рабочей силе, в среднем за год'},
];
const ECON_ROWS = ['gdp', 'gdp_pc', 'net_exp', 'rate', 'infl', 'unemp'];
const COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948'];
const COLORS_D = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#0ca30c', '#9085e9', '#e66767'];
const dark = () => matchMedia('(prefers-color-scheme: dark)').matches;
const MN = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const MNL = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'];
const M = {meta: null, c: {}};

/* ссылки на источники по показателям */
const ES = id => `https://ec.europa.eu/eurostat/databrowser/view/${id}/default/table`;
const ECB = ['ЕЦБ: среднегодовой курс EUR/USD (для пересчёта долларов в евро)', 'https://data.ecb.europa.eu/data/datasets/EXR/EXR.M.USD.EUR.SP00.A'];
const SRC = {
  gdp:     {estat: ['Евростат: ВВП в текущих ценах, млн EUR (nama_10_gdp)', ES('nama_10_gdp')],
            imf: ['МВФ, World Economic Outlook: ВВП в текущих ценах, млрд USD (NGDPD)', 'https://www.imf.org/external/datamapper/NGDPD@WEO/OEMDC/ADVEC/WEOWORLD'],
            wb: ['Всемирный банк: ВВП, текущие USD (NY.GDP.MKTP.CD)', 'https://data.worldbank.org/indicator/NY.GDP.MKTP.CD'], usd: 1},
  gdp_pc:  {estat: ['Евростат: ВВП на душу населения, EUR (nama_10_pc)', ES('nama_10_pc')],
            imf: ['МВФ, World Economic Outlook: ВВП на душу населения, USD (NGDPDPC)', 'https://www.imf.org/external/datamapper/NGDPDPC@WEO/OEMDC/ADVEC/WEOWORLD'],
            wb: ['Всемирный банк: ВВП на душу населения, текущие USD (NY.GDP.PCAP.CD)', 'https://data.worldbank.org/indicator/NY.GDP.PCAP.CD'], usd: 1},
  net_exp: {estat: ['Евростат: экспорт (P6) минус импорт (P7) товаров и услуг, млн EUR (nama_10_gdp)', ES('nama_10_gdp')],
            wb: ['Всемирный банк: внешнее сальдо товаров и услуг, текущие USD (NE.RSB.GNFS.CD)', 'https://data.worldbank.org/indicator/NE.RSB.GNFS.CD'], usd: 1},
  infl:    {estat: ['Евростат: гармонизированный индекс потребительских цен (HICP), среднегодовой рост (prc_hicp_ainr)', ES('prc_hicp_ainr')],
            imf: ['МВФ, World Economic Outlook: инфляция, средние цены за год (PCPIPCH)', 'https://www.imf.org/external/datamapper/PCPIPCH@WEO/OEMDC/ADVEC/WEOWORLD'],
            wb: ['Всемирный банк: инфляция, потребительские цены (FP.CPI.TOTL.ZG)', 'https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG']},
  infl_m:  {ecb: ['ЕЦБ: гармонизированный индекс потребительских цен (HICP), год к году (ICP)', 'https://data.ecb.europa.eu/data/datasets/ICP'],
            estat: ['Евростат: гармонизированный индекс потребительских цен (HICP), месяц к тому же месяцу прошлого года (prc_hicp_minr)', ES('prc_hicp_minr')],
            bis: ['Банк международных расчётов (BIS): индексы потребительских цен, год к году (по данным национальных статслужб)', 'https://data.bis.org/topics/CPI']},
  rate:    {ecb_rate: ['ЕЦБ: ключевая ставка — до сентября 2024 г. ставка основных операций рефинансирования, далее ставка по депозитам (ряд BIS для еврозоны)', 'https://data.bis.org/topics/CBPOL/BIS%2CWS_CBPOL%2C1.0/M.XM'],
            bis: ['Банк международных расчётов (BIS): ключевые ставки центральных банков', 'https://data.bis.org/topics/CBPOL']},
  income:  {wb: ['Всемирный банк: валовой национальный доход на душу населения, текущие USD (NY.GNP.PCAP.CD)', 'https://data.worldbank.org/indicator/NY.GNP.PCAP.CD'], usd: 1},
  unemp:   {estat: ['Евростат: уровень безработицы, 15–74 года (une_rt_a)', ES('une_rt_a')],
            imf: ['МВФ, World Economic Outlook: уровень безработицы (LUR)', 'https://www.imf.org/external/datamapper/LUR@WEO/OEMDC/ADVEC/WEOWORLD'],
            wb: ['Всемирный банк: безработица, оценка МОТ (SL.UEM.TOTL.ZS)', 'https://data.worldbank.org/indicator/SL.UEM.TOTL.ZS']},
};
SRC.rate_m = SRC.rate;
const GEN_SRC = [
  ['Всемирный банк: площадь территории (AG.SRF.TOTL.K2)', 'https://data.worldbank.org/indicator/AG.SRF.TOTL.K2'],
  ['Всемирный банк: площадь суши (AG.LND.TOTL.K2) — для расчёта плотности', 'https://data.worldbank.org/indicator/AG.LND.TOTL.K2'],
  ['Всемирный банк: численность населения (SP.POP.TOTL)', 'https://data.worldbank.org/indicator/SP.POP.TOTL'],
  ['Всемирный банк: городское население, % (SP.URB.TOTL.IN.ZS)', 'https://data.worldbank.org/indicator/SP.URB.TOTL.IN.ZS'],
];
const NOTES = {
  us: {rate: 'Для ФРС показана середина целевого диапазона ставки по федеральным фондам.'},
  sg: {rate: 'Денежно-кредитное управление Сингапура (MAS) не устанавливает ключевую ставку: политика проводится через курс сингапурского доллара.'},
};

const fmt = (v, d) => v == null || isNaN(v) ? '—' : v.toLocaleString('ru-RU', {minimumFractionDigits: d, maximumFractionDigits: d});
const big = v => v == null ? '—' : v >= 1e9 ? fmt(v / 1e9, 2) + ' млрд' : v >= 1e6 ? fmt(v / 1e6, 2) + ' млн' : fmt(v, 0);
const ind = id => IND.find(x => x.id === id);
const keyLabel = (k, long) => k.length === 4 ? k : `${(long ? MNL : MN)[+k.slice(5, 7) - 1]} ${long ? k.slice(0, 4) : k.slice(2, 4)}`;

async function loadMeta(){
  if (!M.meta) M.meta = await fetch('data/macro/meta.json?v=' + Date.now()).then(r => { if (!r.ok) throw new Error('нет данных'); return r.json(); });
  return M.meta;
}
async function loadC(id){
  if (!M.c[id]) M.c[id] = await fetch(`data/macro/${id}.json?v=${encodeURIComponent(M.meta.updated)}`).then(r => r.json());
  return M.c[id];
}
/* ряд показателя: {ключ: значение в единицах графика} */
function seriesOf(C, I){
  const s = I.per === 'month' ? (C.monthly[I.id] || {}) : (C.annual[I.id] || {});
  const o = {}; Object.entries(s).forEach(([k, v]) => { if (v != null) o[k] = v * I.k; });
  return o;
}
function srcKeys(C, I){
  if (I.per === 'month') return C.monthly_src?.[I.id] || [];
  return [...new Set(Object.values(C.annual_src?.[I.id] || {}))];
}
function srcHtml(list){
  const seen = new Set();
  const items = list.filter(([n, u]) => u && !seen.has(u + n) && seen.add(u + n));
  return items.length ? `<div class="msrc"><b>Источники:</b><ul>${items.map(([n, u]) => `<li><a href="${esc(u)}" target="_blank" rel="noopener">${esc(n)} ↗</a></li>`).join('')}</ul></div>` : '';
}
function indSources(C, I){
  const keys = srcKeys(C, I), out = keys.map(k => SRC[I.id][k]).filter(Boolean);
  if (SRC[I.id].usd && keys.some(k => k !== 'estat')) out.push(ECB);
  return out;
}
/* все ключи периода между a и b */
function keysBetween(a, b, per){
  const out = [];
  if (per === 'year'){ for (let y = +a; y <= +b; y++) out.push(String(y)); return out; }
  let y = +a.slice(0, 4), m = +a.slice(5, 7);
  while (`${y}-${String(m).padStart(2, '0')}` <= b){ out.push(`${y}-${String(m).padStart(2, '0')}`); if (++m > 12){ m = 1; y++; } }
  return out;
}
function niceTicks(lo, hi, n = 5){
  const span = hi - lo || Math.abs(hi) || 1, raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * p).find(s => s >= raw);
  const a = Math.floor(lo / step) * step, t = [];
  for (let v = a; v <= hi + step * 0.001; v += step) t.push(+v.toFixed(10));
  if (t[t.length - 1] < hi) t.push(+(t[t.length - 1] + step).toFixed(10));
  return t;
}

/* ---------- график: одна или несколько линий ---------- */
function drawLines(box, keys, series, I, est = {}){
  const W = Math.max(300, box.clientWidth), H = W < 520 ? 280 : 360;
  const m = {l: 62, r: 16, t: 14, b: 34}, iw = W - m.l - m.r, ih = H - m.t - m.b;
  const vals = series.flatMap(s => keys.map(k => s.v[k]).filter(v => v != null));
  if (!vals.length){ box.innerHTML = '<div class="empty-msg">За выбранный период данных нет.</div>'; return; }
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (I.unit !== '%' && lo > 0 && !I.id.startsWith('net')) lo = Math.min(lo, 0);
  const pad = (hi - lo) * 0.06 || Math.abs(hi) * 0.05 || 1, ticks = niceTicks(lo < 0 ? lo - pad : Math.max(0, lo - pad), hi + pad);
  const y0 = ticks[0], y1 = ticks[ticks.length - 1];
  const X = i => m.l + (keys.length === 1 ? iw / 2 : i * iw / (keys.length - 1));
  const Y = v => m.t + ih - (v - y0) / (y1 - y0) * ih;
  const nLab = Math.max(2, Math.floor(iw / 70)), every = Math.max(1, Math.ceil(keys.length / nLab));
  let xl = '';
  for (let i = 0; i < keys.length; i += every) xl += `<text x="${X(i)}" y="${H - 10}" text-anchor="middle">${esc(keyLabel(keys[i]))}</text>`;
  const pal = dark() ? COLORS_D : COLORS;
  const paths = series.map(s => {
    let d = '', pen = false;
    keys.forEach((k, i) => { const v = s.v[k]; if (v == null){ pen = false; return; } d += `${pen ? 'L' : 'M'}${X(i).toFixed(1)},${Y(v).toFixed(1)}`; pen = true; });
    const col = s.color != null ? pal[s.color] : 'var(--accent)';
    const dots = keys.length <= 40 ? keys.map((k, i) => s.v[k] == null ? '' :
      `<circle cx="${X(i)}" cy="${Y(s.v[k])}" r="${(est[s.id] || []).includes(k) ? 4 : 2.5}" fill="${(est[s.id] || []).includes(k) ? 'var(--card)' : col}" stroke="${col}" stroke-width="${(est[s.id] || []).includes(k) ? 2 : 0}"/>`).join('') : '';
    return `<path d="${d}" fill="none" stroke="${col}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>${dots}`;
  }).join('');
  const zero = y0 < 0 && y1 > 0 ? `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${Y(0)}" y2="${Y(0)}"/>` : '';
  box.innerHTML = `<svg class="fxsvg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(I.name)}">
    ${ticks.map(t => `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(t)}" y2="${Y(t)}"/><text x="${m.l - 8}" y="${Y(t) + 4}" text-anchor="end">${fmt(t, Math.abs(y1 - y0) < 5 ? 1 : 0)}</text>`).join('')}
    <line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"/>${zero}
    <g>${xl}</g>${paths}
    <g class="hov" visibility="hidden"><line class="cross" y1="${m.t}" y2="${m.t + ih}"/></g>
    <rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
  </svg><div class="fxtip" hidden></div>`;
  const svg = box.querySelector('svg'), hov = svg.querySelector('.hov'), cross = hov.querySelector('.cross'), tip = box.querySelector('.fxtip');
  const show = ev => {
    const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(keys.length - 1, Math.round((x - m.l) / (iw / Math.max(1, keys.length - 1))))), k = keys[i], px = X(i);
    hov.setAttribute('visibility', 'visible'); cross.setAttribute('x1', px); cross.setAttribute('x2', px);
    const rows = series.map(s => ({s, v: s.v[k]})).sort((a, b) => (b.v ?? -1e99) - (a.v ?? -1e99));
    tip.innerHTML = `<div class="tt">${esc(keyLabel(k, true))}</div>` + rows.map(({s, v}) =>
      `<div class="tv">${series.length > 1 ? `<i class="msw" style="background:${s.color != null ? pal[s.color] : 'var(--accent)'}"></i>${esc(s.name)}: ` : ''}<b>${fmt(v, I.dig)}</b> ${v == null ? '' : esc(I.unit)}${(est[s.id] || []).includes(k) ? ' <span class="muted">(оценка)</span>' : ''}</div>`).join('');
    tip.hidden = false;
    const sx = px * r.width / W, tw = tip.offsetWidth;
    tip.style.left = Math.max(0, Math.min(r.width - tw, sx + 12 + tw > r.width ? sx - tw - 12 : sx + 12)) + 'px';
    tip.style.top = '8px';
  };
  svg.addEventListener('pointermove', show); svg.addEventListener('pointerdown', show);
  svg.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse'){ hov.setAttribute('visibility', 'hidden'); tip.hidden = true; } });
}

/* ---------- блок выбора показателя и периода ---------- */
function indSelect(cur){
  return `<label>Показатель<select id="mInd"><option value="">— выберите показатель —</option>${
    IND.map(i => `<option value="${i.id}" ${i.id === cur ? 'selected' : ''}>${esc(i.name)} — ${i.per === 'year' ? 'по годам' : 'по месяцам'}</option>`).join('')}</select></label>`;
}
function periodSelects(I, keys, from, to){
  const opt = sel => keys.map(k => `<option value="${k}" ${k === sel ? 'selected' : ''}>${esc(keyLabel(k, true))}</option>`).join('');
  const w = I.per === 'year' ? 'год' : 'месяц';
  return `<div class="row"><label>С (${w})<select id="mFrom">${opt(from)}</select></label><label>По (${w})<select id="mTo">${opt(to)}</select></label></div>
    <div class="presets" id="mPre">${I.per === 'year'
      ? '<button class="chip" data-n="5">5 лет</button><button class="chip" data-n="10">10 лет</button><button class="chip" data-n="0">Весь период</button>'
      : '<button class="chip" data-n="12">12 месяцев</button><button class="chip" data-n="36">3 года</button><button class="chip" data-n="120">10 лет</button><button class="chip" data-n="0">Весь период</button>'}</div>`;
}
function bindPeriod(keys, st, render){
  const set = () => { let a = $('#mFrom').value, z = $('#mTo').value; if (a > z) [a, z] = [z, a]; st.from = a; st.to = z; render(); };
  $('#mFrom').onchange = set; $('#mTo').onchange = set;
  app.querySelectorAll('#mPre .chip').forEach(b => b.onclick = () => {
    const n = +b.dataset.n; $('#mTo').value = keys[keys.length - 1];
    $('#mFrom').value = n ? keys[Math.max(0, keys.length - n)] : keys[0]; set();
  });
}

/* ---------- список стран ---------- */
async function viewMacro(){
  setPeriodBox();
  app.innerHTML = '<p class="loading">Загрузка…</p>';
  let meta;
  try { meta = await loadMeta(); } catch (e){ app.innerHTML = '<div class="empty-msg">Данные пока не загружены.</div>'; return; }
  app.innerHTML = `
    <div class="crumbs"><a href="#/">Главная</a> / <a href="#/stats">Статистика</a></div>
    <h1>Макроэкономика</h1>
    <p class="sub">Выберите страну или сравните несколько стран. Данные с ${2000} года, обновлены ${esc(meta.updated.split('-').reverse().join('.'))}.</p>
    <a class="mwide" href="#/stats/macro/compare">Сравнить страны</a>
    <div class="m3">${meta.countries.map(c => `<a class="mbtn" href="#/stats/macro/${c.id}">${esc(c.name)}</a>`).join('')}</div>`;
}

/* ---------- страница страны ---------- */
async function viewMacroCountry(id, q){
  setPeriodBox();
  app.innerHTML = '<p class="loading">Загрузка…</p>';
  let C;
  try { await loadMeta(); C = await loadC(id); } catch (e){ app.innerHTML = '<div class="empty-msg">Нет данных по этой стране.</div>'; return; }
  const st = {ind: q.get('ind') || '', from: q.get('from') || '', to: q.get('to') || ''};
  const open = new Set((q.get('open') || '').split(',').filter(Boolean));
  app.innerHTML = `
    <div class="crumbs"><a href="#/stats">Статистика</a> / <a href="#/stats/macro">Макроэкономика</a></div>
    <h1>${esc(C.name)}</h1>
    <div class="picker fxctl"><div class="row">${indSelect(st.ind)}</div><div id="mPer"></div></div>
    <div class="fxchart" id="mChart" hidden><div class="fxtitle" id="mTitle"></div><div id="fxPlot"></div><div class="fxsum" id="mSum"></div></div>
    <div id="mSrc"></div>
    <div class="msecs">
      <details class="msec" data-s="general" ${open.has('general') ? 'open' : ''}><summary>Общее</summary><div class="mbody">${generalHtml(C)}</div></details>
      <details class="msec" data-s="econ" ${open.has('econ') ? 'open' : ''}><summary>Экономика страны</summary><div class="mbody">${econHtml(C)}</div></details>
    </div>`;
  const sync = () => {
    const qs = new URLSearchParams();
    if (st.ind) qs.set('ind', st.ind);
    if (st.ind && st.from) { qs.set('from', st.from); qs.set('to', st.to); }
    const o = [...app.querySelectorAll('.msec[open]')].map(d => d.dataset.s); if (o.length) qs.set('open', o.join(','));
    history.replaceState(null, '', `#/stats/macro/${id}` + (qs.toString() ? '?' + qs : ''));
  };
  const toEnd = () => app.querySelectorAll('.msec[open] .mwrap').forEach(w => { if (!w.dataset.s){ w.scrollLeft = w.scrollWidth; w.dataset.s = 1; } });
  app.querySelectorAll('.msec').forEach(d => d.addEventListener('toggle', () => { sync(); toEnd(); }));
  toEnd();
  const render = () => {
    sync();
    const I = ind(st.ind);
    if (!I){ $('#mChart').hidden = true; $('#mSrc').innerHTML = ''; return; }
    const s = seriesOf(C, I), keys = Object.keys(s).sort();
    $('#mChart').hidden = false;
    $('#mTitle').innerHTML = `<b>${esc(I.name)}</b>, ${esc(I.unit)} <span class="muted">${I.about ? '— ' + esc(I.about) : ''}${st.from ? ` · ${esc(keyLabel(st.from, true))} – ${esc(keyLabel(st.to, true))}` : ''}</span>`;
    if (!keys.length){
      $('#fxPlot').innerHTML = `<div class="empty-msg">${esc(NOTES[id]?.[I.id.replace('_m', '')] || 'По этому показателю данных нет.')}</div>`;
      $('#mSum').innerHTML = ''; $('#mSrc').innerHTML = ''; return;
    }
    const all = keysBetween(keys[0], keys[keys.length - 1], I.per);
    const sel = keysBetween(st.from, st.to, I.per);
    const est = {[id]: (C.estimates?.[I.id] || []).map(String)};
    drawLines($('#fxPlot'), sel, [{id, name: C.name, v: s}], I, est);
    const have = sel.filter(k => s[k] != null);
    if (have.length){
      const a = have[0], z = have[have.length - 1], vs = have.map(k => s[k]), mn = Math.min(...vs), mx = Math.max(...vs);
      $('#mSum').innerHTML = `<span>${esc(keyLabel(a, true))}: <b>${fmt(s[a], I.dig)}</b></span><span>${esc(keyLabel(z, true))}: <b>${fmt(s[z], I.dig)}</b></span>
        <span>Мин: <b>${fmt(mn, I.dig)}</b> (${esc(keyLabel(have[vs.indexOf(mn)], true))})</span><span>Макс: <b>${fmt(mx, I.dig)}</b> (${esc(keyLabel(have[vs.indexOf(mx)], true))})</span>
        ${est[id].length && est[id].some(k => sel.includes(k)) ? '<span>○ — оценка МВФ за текущий год</span>' : ''}`;
    } else $('#mSum').innerHTML = '';
    $('#mSrc').innerHTML = srcHtml(indSources(C, I)) + (NOTES[id]?.[I.id.replace('_m', '')] ? `<p class="hint">${esc(NOTES[id][I.id.replace('_m', '')])}</p>` : '') +
      (C.euro_from && I.id.startsWith('rate') && C.id !== 'eu' ? `<p class="hint">С ${C.euro_from} г. страна в еврозоне — показана ставка ЕЦБ${C.euro_from > 2000 ? '; до этого — ставка национального ЦБ, если она есть в базе BIS' : ''}.</p>` : '');
    void all;
  };
  const choose = () => {
    const I = ind(st.ind);
    if (!I){ $('#mPer').innerHTML = ''; render(); return; }
    const s = seriesOf(C, I), keys = Object.keys(s).sort();
    if (!keys.length){ $('#mPer').innerHTML = ''; st.from = st.to = ''; render(); return; }
    const all = keysBetween(keys[0], keys[keys.length - 1], I.per);
    if (!all.includes(st.from)) st.from = all[0];
    if (!all.includes(st.to)) st.to = all[all.length - 1];
    $('#mPer').innerHTML = periodSelects(I, all, st.from, st.to);
    bindPeriod(all, st, render);
    render();
  };
  $('#mInd').onchange = e => { st.ind = e.target.value; st.from = st.to = ''; choose(); };
  let rt; window.onresize = () => { clearTimeout(rt); rt = setTimeout(() => { if ($('#mChart') && st.ind) render(); }, 150); };
  choose();
}

function generalHtml(C){
  const g = C.general || {}, row = (n, x, d, u) => `<tr><td>${n}</td><td class="num"><b>${x ? fmt(x.value, d) : '—'}</b> ${x ? u : ''}</td><td class="per">${x ? x.year : ''}</td></tr>`;
  let h = `<h3 class="mh3">Основные данные</h3><div class="tbl"><table class="src mt"><thead><tr><th>Показатель</th><th class="num">Значение</th><th>Год</th></tr></thead><tbody>
    ${row('Площадь страны', g.area, 0, 'км²')}
    ${row('Население', g.pop, 0, 'чел.')}
    ${row('Плотность населения', g.dens, 1, 'чел./км²')}
    ${row('Коэффициент урбанизации (доля городского населения)', g.urban, 1, '%')}
  </tbody></table></div>${srcHtml(GEN_SRC)}<p class="hint">Плотность = население / площадь суши. Данные Всемирного банка — последний доступный год.</p>`;
  const R = C.regions;
  h += `<h3 class="mh3">Регионы${R ? ` <span class="muted">· ${esc(R.level)}</span>` : ''}</h3>`;
  if (!R || !R.rows?.length) return h + `<div class="empty-msg">${esc(C.id === 'sg' ? 'Сингапур — город-государство без регионального деления в официальной статистике.'
      : C.id === 'id' ? 'Статистическое агентство Индонезии (BPS) закрыло автоматическую загрузку своих таблиц, поэтому данные по провинциям пока не загружены.'
      : 'Данные по регионам пока не загружены.')}</div>${C.id === 'id' ? srcHtml([['BPS: численность населения по провинциям', 'https://www.bps.go.id/en/statistics-table/2/MTk3NSMy/population-by-province.html'], ['BPS: ВРП на душу населения по провинциям, текущие цены', 'https://www.bps.go.id/en/statistics-table/3/YWtoQlRVZzNiMU5qU1VOSlRFeFZiRTR4VDJOTVVUMDkjMw==/produk-domestik-regional-bruto-per-kapita-atas-dasar-harga-berlaku-menurut-provinsi--ribu-rupiah']]) : ''}`;
  const yr = a => a?.length ? (a.length > 1 ? `${a[0]}–${a[a.length - 1]}` : a[0]) : '';
  const cur = R.currency || 'EUR';
  h += `<div class="tbl"><table class="src mt"><thead><tr><th>Регион</th><th class="num">Население, чел.${R.years?.pop?.length ? ` (${yr(R.years.pop)})` : ''}</th><th class="num">Плотность, чел./км²${R.years?.dens?.length ? ` (${yr(R.years.dens)})` : ''}</th><th class="num">ВВП на душу, ${esc(cur)}${R.years?.gdp?.length ? ` (${yr(R.years.gdp)})` : ''}</th></tr></thead><tbody>${
    R.rows.map(r => `<tr><td>${esc(r.name)}${r.code && r.code !== r.name && /^[A-Z]{2}/.test(r.code) ? ` <small class="muted">${esc(r.code)}</small>` : ''}</td><td class="num">${fmt(r.pop, 0)}</td><td class="num">${fmt(r.dens, 1)}</td><td class="num">${fmt(r.gdp_pc, 0)}</td></tr>`).join('')
  }</tbody></table></div>${R.note ? `<p class="hint">${esc(R.note)}</p>` : ''}${srcHtml(R.sources || [])}`;
  return h;
}

function econHtml(C){
  const y1 = +C.updated.slice(0, 4), years = []; for (let y = 2000; y <= y1; y++) years.push(String(y));
  const rows = ECON_ROWS.map(ind);
  const label = I => ({gdp: 'ВВП, млрд EUR', gdp_pc: 'ВВП на душу населения, EUR', net_exp: 'Чистый экспорт, млрд EUR', rate: 'Ключевая ставка (на конец года), %', infl: 'Годовая инфляция, %', unemp: 'Безработица, %'})[I.id];
  const body = rows.map(I => {
    const s = seriesOf(C, I), est = (C.estimates?.[I.id] || []).map(String);
    return `<tr><th class="rh">${esc(label(I))}</th>${years.map(y => `<td class="num${est.includes(y) ? ' est' : ''}">${fmt(s[y], I.unit === '%' ? (I.id === 'rate' ? 2 : 1) : I.dig)}${est.includes(y) ? '*' : ''}</td>`).join('')}</tr>`;
  }).join('');
  const src = rows.flatMap(I => indSources(C, I));
  const anyEst = rows.some(I => (C.estimates?.[I.id] || []).length);
  return `<div class="tbl mwrap"><table class="src mt myears"><thead><tr><th class="rh">Показатель</th>${years.map(y => `<th class="num">${y}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>
    <p class="hint">${anyEst ? '* — оценка МВФ (World Economic Outlook) за текущий год. ' : ''}Значения в долларах пересчитаны в евро по среднегодовому курсу ЕЦБ. Прочерк — данных нет.${NOTES[C.id]?.rate ? ' ' + esc(NOTES[C.id].rate) : ''}</p>${srcHtml(src)}`;
}

/* ---------- сравнение стран ---------- */
async function viewMacroCompare(q){
  setPeriodBox();
  app.innerHTML = '<p class="loading">Загрузка…</p>';
  let meta;
  try { meta = await loadMeta(); } catch (e){ app.innerHTML = '<div class="empty-msg">Данные пока не загружены.</div>'; return; }
  const st = {ind: q.get('ind') || '', from: q.get('from') || '', to: q.get('to') || ''};
  /* страна → номер цвета; цвет закреплён за страной, пока она выбрана */
  const sel = new Map();
  (q.get('c') || 'ru,us,eu,cn').split(',').filter(c => meta.countries.some(x => x.id === c)).slice(0, 8).forEach(c => {
    const used = new Set(sel.values()); sel.set(c, [0, 1, 2, 3, 4, 5, 6, 7].find(k => !used.has(k)));
  });
  app.innerHTML = `
    <div class="crumbs"><a href="#/stats">Статистика</a> / <a href="#/stats/macro">Макроэкономика</a></div>
    <h1>Сравнить страны</h1>
    <div class="picker fxctl"><div class="row">${indSelect(st.ind)}</div><div id="mPer"></div>
      <div class="mpick"><div class="hint" style="margin:6px 0 8px">Страны (до 8):</div><div class="presets" id="mCs">${meta.countries.map(c => `<button class="chip mcc" data-c="${c.id}">${esc(c.name)}</button>`).join('')}</div></div></div>
    <div class="fxchart" id="mChart" hidden><div class="fxtitle" id="mTitle"></div><div class="mleg" id="mLeg"></div><div id="fxPlot"></div></div>
    <div id="mTbl"></div><div id="mSrc"></div>`;
  const pal = () => dark() ? COLORS_D : COLORS;
  const paintChips = () => app.querySelectorAll('.mcc').forEach(b => {
    const k = sel.get(b.dataset.c);
    b.classList.toggle('on', k != null);
    b.style.cssText = k != null ? `border-color:${pal()[k]};box-shadow:inset 0 0 0 1px ${pal()[k]}` : '';
    b.innerHTML = (k != null ? `<i class="msw" style="background:${pal()[k]}"></i>` : '') + esc(meta.countries.find(x => x.id === b.dataset.c).name);
  });
  const sync = () => {
    const qs = new URLSearchParams();
    if (st.ind) qs.set('ind', st.ind);
    if (st.ind && st.from){ qs.set('from', st.from); qs.set('to', st.to); }
    qs.set('c', [...sel.keys()].join(','));
    history.replaceState(null, '', '#/stats/macro/compare?' + qs);
  };
  let allKeys = [];
  const render = async () => {
    sync(); paintChips();
    const I = ind(st.ind);
    if (!I){ $('#mChart').hidden = true; $('#mTbl').innerHTML = $('#mSrc').innerHTML = ''; return; }
    const ids = [...sel.keys()];
    const Cs = await Promise.all(ids.map(loadC));
    if (ind(st.ind) !== I) return;
    const series = Cs.map((C, i) => ({id: C.id, name: C.name, color: sel.get(C.id), v: seriesOf(C, I)}));
    const est = Object.fromEntries(Cs.map(C => [C.id, (C.estimates?.[I.id] || []).map(String)]));
    const keys = keysBetween(st.from, st.to, I.per);
    $('#mChart').hidden = false;
    $('#mTitle').innerHTML = `<b>${esc(I.name)}</b>, ${esc(I.unit)} <span class="muted">${I.about ? '— ' + esc(I.about) : ''} · ${esc(keyLabel(st.from, true))} – ${esc(keyLabel(st.to, true))}</span>`;
    $('#mLeg').innerHTML = series.map(s => `<span><i class="msw" style="background:${pal()[s.color]}"></i>${esc(s.name)}</span>`).join('');
    if (!series.length){ $('#fxPlot').innerHTML = '<div class="empty-msg">Выберите хотя бы одну страну.</div>'; $('#mTbl').innerHTML = $('#mSrc').innerHTML = ''; return; }
    drawLines($('#fxPlot'), keys, series, I, est);
    /* таблица: страны по строкам, периоды по столбцам (для месяцев — не больше 24 последних) */
    const tk = I.per === 'month' && keys.length > 24 ? keys.slice(-24) : keys;
    setTimeout(() => { const w = $('#mTbl .mwrap'); if (w) w.scrollLeft = w.scrollWidth; });
    $('#mTbl').innerHTML = `<h3 class="mh3">Таблица${tk.length < keys.length ? ' <span class="muted">· последние 24 месяца периода</span>' : ''}</h3>
      <div class="tbl mwrap"><table class="src mt myears"><thead><tr><th class="rh">Страна</th>${tk.map(k => `<th class="num">${esc(keyLabel(k))}</th>`).join('')}</tr></thead><tbody>${
      series.map(s => `<tr><th class="rh"><i class="msw" style="background:${pal()[s.color]}"></i>${esc(s.name)}</th>${tk.map(k => `<td class="num">${fmt(s.v[k], I.dig)}${est[s.id].includes(k) ? '*' : ''}</td>`).join('')}</tr>`).join('')
      }</tbody></table></div><p class="hint">${Object.values(est).some(a => a.some(k => tk.includes(k))) ? '* и ○ на графике — оценка МВФ за текущий год. ' : ''}${I.unit.includes('EUR') ? 'Значения в долларах пересчитаны в евро по среднегодовому курсу ЕЦБ. ' : ''}Прочерк — данных нет.</p>`;
    $('#mSrc').innerHTML = srcHtml(Cs.flatMap(C => indSources(C, I)));
  };
  const choose = () => {
    const I = ind(st.ind);
    if (!I){ $('#mPer').innerHTML = ''; render(); return; }
    const y1 = meta.updated.slice(0, 4);
    allKeys = I.per === 'year' ? keysBetween('2000', y1, 'year') : keysBetween('2000-01', meta.last_month || meta.updated.slice(0, 7), 'month');
    if (!allKeys.includes(st.from)) st.from = allKeys[0];
    if (!allKeys.includes(st.to)) st.to = allKeys[allKeys.length - 1];
    $('#mPer').innerHTML = periodSelects(I, allKeys, st.from, st.to);
    bindPeriod(allKeys, st, render);
    render();
  };
  app.querySelectorAll('.mcc').forEach(b => b.onclick = () => {
    const c = b.dataset.c;
    if (sel.has(c)) sel.delete(c);
    else { if (sel.size >= 8) return; const used = new Set(sel.values()); sel.set(c, [0, 1, 2, 3, 4, 5, 6, 7].find(k => !used.has(k))); }
    render();
  });
  $('#mInd').onchange = e => { st.ind = e.target.value; st.from = st.to = ''; choose(); };
  let rt; window.onresize = () => { clearTimeout(rt); rt = setTimeout(() => { if ($('#mChart') && st.ind) render(); }, 150); };
  paintChips(); choose();
}

window.viewMacro = viewMacro;
window.viewMacroCountry = viewMacroCountry;
window.viewMacroCompare = viewMacroCompare;
})();
