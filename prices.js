/* Раздел «Статистика → Цены» (#/stats/prices).
   Данные: data/prices/manifest.json и data/prices/<ГГГГ-ММ-ДД>.json — собираются
   tools/prices_fetch.py + tools/prices_build.py через GitHub Actions (.github/workflows/prices.yml). */
(() => {
const COUNTRIES = [
  {id: 'de', name: 'Германия'}, {id: 'at', name: 'Австрия'}, {id: 'ch', name: 'Швейцария'},
  {id: 'cz', name: 'Чехия'}, {id: 'hu', name: 'Венгрия'}, {id: 'sk', name: 'Словакия'}];
const STORES = [
  {id: 'dm', name: 'dm'}, {id: 'rossmann', name: 'Rossmann'}, {id: 'teta', name: 'Teta'},
  {id: 'kaufland', name: 'Kaufland'}, {id: 'lidl', name: 'Lidl'}];
/* в каких странах есть магазины сети */
const PRESENT = {
  de: ['dm', 'rossmann', 'kaufland', 'lidl'], at: ['dm', 'lidl'], ch: ['lidl'],
  cz: ['dm', 'rossmann', 'teta', 'kaufland', 'lidl'], hu: ['dm', 'rossmann', 'lidl'], sk: ['dm', 'teta', 'kaufland', 'lidl']};
const TYPES = [{id: 'paste', name: 'Зубные пасты'}, {id: 'brush', name: 'Зубные щётки'}];
const CUR = {EUR: '€', CZK: 'Kč', HUF: 'Ft', CHF: 'CHF'};
const PAL = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#6250d6', '#008300', '#e34948', '#0aa5b8', '#8a6d3b'];
const P = {manifest: null, days: {}};
const cname = id => (COUNTRIES.find(c => c.id === id) || {}).name || id;
const sname = id => (STORES.find(s => s.id === id) || {}).name || id;
const dfmt = d => d.split('-').reverse().join('.');
const money = (v, cur) => {
  if (v == null) return '—';
  const d = cur === 'HUF' ? 0 : 2;
  return v.toLocaleString('ru-RU', {minimumFractionDigits: d, maximumFractionDigits: d}) + ' ' + (CUR[cur] || cur);
};
const crumbs = (...xs) => `<div class="crumbs"><a href="#/">Главная</a> / <a href="#/stats">Статистика</a>${xs.map(x => ' / ' + x).join('')}</div>`;

async function loadManifest(){
  if (!P.manifest) P.manifest = await fetch('data/prices/manifest.json?v=' + Date.now()).then(r => { if (!r.ok) throw new Error('нет данных'); return r.json(); });
  return P.manifest;
}
async function loadDay(d){
  if (!P.days[d]) P.days[d] = await fetch(`data/prices/${d}.json?v=${encodeURIComponent(P.manifest.updated || '')}`).then(r => r.json());
  return P.days[d];
}

/* ---------- шаг 1: страны ---------- */
function viewPrices(){
  setPeriodBox();
  app.innerHTML = `${crumbs()}
    <h1>Цены</h1>
    <p class="sub">Цены на зубные пасты и зубные щётки в сетях dm, Rossmann, Teta, Kaufland и Lidl. Выберите страну или сравните цены.</p>
    <a class="mwide" href="#/stats/prices/compare">Сравнить цены</a>
    <div class="m3">${COUNTRIES.map(c => `<a class="mbtn" href="#/stats/prices/${c.id}">${esc(c.name)}</a>`).join('')}</div>`;
}

/* ---------- шаг 2: магазины ---------- */
function viewCountry(cc){
  setPeriodBox();
  const c = COUNTRIES.find(x => x.id === cc);
  if (!c){ location.replace('#/stats/prices'); return; }
  app.innerHTML = `${crumbs('<a href="#/stats/prices">Цены</a>')}
    <h1>${esc(c.name)}</h1>
    <p class="sub">Выберите магазин.</p>
    <div class="m3">${STORES.map(s => PRESENT[cc].includes(s.id)
      ? `<a class="mbtn" href="#/stats/prices/${cc}/${s.id}">${esc(s.name)}</a>`
      : `<span class="mbtn poff" title="Сеть не работает в этой стране">${esc(s.name)}<small>нет в стране</small></span>`).join('')}</div>`;
}

/* ---------- шаг 3: дата ---------- */
async function viewDates(cc, st){
  setPeriodBox();
  app.innerHTML = '<p class="loading">Загрузка…</p>';
  let m;
  try { m = await loadManifest(); } catch (e){ app.innerHTML = `${crumbs('<a href="#/stats/prices">Цены</a>')}<div class="empty-msg">Данные пока не загружены.</div>`; return; }
  const days = (m.dates || []).filter(d => d.stores[`${cc}/${st}`]).map(d => d.date).sort().reverse();
  const cnt = d => ((m.dates.find(x => x.date === d) || {}).stores[`${cc}/${st}`] || {});
  app.innerHTML = `${crumbs('<a href="#/stats/prices">Цены</a>', `<a href="#/stats/prices/${cc}">${esc(cname(cc))}</a>`)}
    <h1>${esc(sname(st))} · ${esc(cname(cc))}</h1>
    <p class="sub">Выберите дату, на которую показать цены.</p>
    ${days.length ? `<div class="m3">${days.map(d => {
      const s = cnt(d);
      return `<a class="mbtn" href="#/stats/prices/${cc}/${st}/${d}">${dfmt(d)}<small>${s.status === 'ok' ? (s.n_paste || 0) + ' паст · ' + (s.n_brush || 0) + ' щёток' : s.status === 'blocked' ? 'сайт закрыт' : 'нет данных'}</small></a>`;
    }).join('')}</div>` : '<div class="empty-msg">Цены по этому магазину ещё не собирались.</div>'}`;
}

/* ---------- шаг 4: графики и таблицы ---------- */
async function viewStore(cc, st, day){
  setPeriodBox();
  app.innerHTML = '<p class="loading">Загрузка…</p>';
  let D;
  try { await loadManifest(); D = await loadDay(day); } catch (e){ app.innerHTML = '<div class="empty-msg">Нет данных за эту дату.</div>'; return; }
  const key = `${cc}/${st}`, S = D.status[key] || {status: 'none'};
  const items = D.items.filter(x => x.country === cc && x.store === st);
  const head = `${crumbs('<a href="#/stats/prices">Цены</a>', `<a href="#/stats/prices/${cc}">${esc(cname(cc))}</a>`, `<a href="#/stats/prices/${cc}/${st}">${esc(sname(st))}</a>`)}
    <h1>${esc(sname(st))} · ${esc(cname(cc))} · ${dfmt(day)}</h1>
    <p class="sub">Цены на ${dfmt(day)}${S.url ? `, источник: <a href="${esc(S.url)}" target="_blank" rel="noopener">${esc(S.url.replace(/^https:\/\/(www\.)?|\/.*$/g, ''))} ↗</a>` : ''}.
    ${S.note && S.status === 'ok' ? esc(S.note[0].toUpperCase() + S.note.slice(1)) + '.' : ''}</p>`;
  if (S.status !== 'ok'){
    app.innerHTML = head + `<div class="empty-msg">${S.status === 'blocked' ? 'Сайт магазина не отдаёт цены автоматически' : 'Нет данных'}${S.note ? ': ' + esc(S.note) : ''}.</div>`;
    return;
  }
  app.innerHTML = head + `<p class="note">Регулярная цена — обычная цена магазина; промо-цена — цена по акции (в том числе по карте лояльности или при покупке нескольких штук — см. описание). ${(() => { const miss = (D.brands || []).filter(b => !items.some(x => x.brand === b)); return miss.length ? ` Не найдены в этом магазине: ${esc(miss.join(', '))}.` : ''; })()}</p>` +
    TYPES.map(t => `<section class="psec"><h2 class="fxh2">${t.name}</h2><div id="pc_${t.id}"></div></section>`).join('');
  for (const t of TYPES){
    const rows = lineRows(items.filter(x => x.type === t.id));
    const box = document.getElementById('pc_' + t.id);
    if (!rows.length){ box.innerHTML = '<div class="empty-msg">Товаров этих брендов не найдено.</div>'; continue; }
    box.innerHTML = `<div class="fxchart"><div class="pleg"><span><i class="pdot"></i>Регулярная цена</span><span><i class="pdot promo"></i>Промо-цена</span></div><div class="pplot"></div></div>
      ${tableHtml(rows)}`;
    drawMatrix(box.querySelector('.pplot'), rows.map(r => ({label: r.line, brand: r.brand, pts: [{v: r.regular, promo: r.promo, cur: r.currency, tip: r}]})), rows[0].currency);
  }
}

/* одна строка на линейку: представитель — стандартная упаковка */
function lineRows(items){
  const by = {};
  items.forEach(x => (by[x.brand + '|' + x.line] ||= []).push(x));
  return Object.values(by).map(g => {
    g.sort((a, b) => (a.rank ?? 9) - (b.rank ?? 9) || (a.regular ?? 1e9) - (b.regular ?? 1e9));
    const r = g[0];
    return {...r, n: g.length, all: g};
  }).sort((a, b) => a.brand.localeCompare(b.brand) || a.line.localeCompare(b.line));
}

function tableHtml(rows){
  return `<div class="tbl ptbl"><table class="src"><thead><tr><th>Бренд</th><th>Линейка</th><th class="num">Регулярная цена</th><th class="num">Промо цена</th></tr></thead><tbody>${
    rows.map(r => `<tr><td>${esc(r.brand)}</td>
      <td><b>${esc(r.line)}</b><div class="pprod"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>${r.size ? ' · ' + esc(r.size) : ''}</div>${r.n > 1 ? `<details class="pmore"><summary>ещё ${r.n - 1} в линейке</summary>${r.all.slice(1).map(x =>
        `<div><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.name)}</a>${x.size ? ' · ' + esc(x.size) : ''} — ${x.regular != null ? money(x.regular, x.currency) : '—'}${x.promo != null ? ' / промо ' + money(x.promo, x.currency) : ''}</div>`).join('')}</details>` : ''}</td>
      <td class="num">${money(r.regular, r.currency)}</td>
      <td class="num">${r.promo != null ? `<b class="ppromo">${money(r.promo, r.currency)}</b>` : '—'}${r.promo_desc ? `<div class="pdesc">${esc(r.promo_desc)}</div>` : ''}</td></tr>`).join('')
  }</tbody></table></div>`;
}

/* ---------- матрица: по горизонтали цена, по вертикали линейки ---------- */
function niceStep(v, n){
  const raw = v / n, p = Math.pow(10, Math.floor(Math.log10(raw)));
  return [1, 2, 2.5, 5, 10].map(k => k * p).find(k => k >= raw);
}
function drawMatrix(box, rows, cur, series){
  /* rows: [{label, brand, pts:[{v, promo, color, name, cur, tip}]}] */
  const W = Math.max(320, box.clientWidth), narrow = W < 560;
  const lw = narrow ? 128 : 230, rh = 26, top = 8, bottom = 30, r = 5;
  const groups = []; rows.forEach(x => { const g = groups[groups.length - 1]; if (!g || g.brand !== x.brand) groups.push({brand: x.brand, rows: [x]}); else g.rows.push(x); });
  const nRows = rows.length + groups.length;
  const H = top + nRows * rh + bottom, iw = W - lw - 24;
  const top0 = Math.max(...rows.flatMap(x => x.pts.flatMap(p => [p.v || 0, p.promo || 0]))) || 1;
  const step = niceStep(top0, narrow ? 4 : 6), vmax = Math.ceil(top0 * 1.02 / step) * step;
  const X = v => lw + v / vmax * iw;
  const ticks = []; for (let t = 0; t <= vmax + step / 1000; t += step) ticks.push(+t.toFixed(6));
  let s = `<svg class="fxsvg psvg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`;
  ticks.forEach(t => s += `<line class="grid" x1="${X(t)}" x2="${X(t)}" y1="${top}" y2="${H - bottom}"/><text x="${X(t)}" y="${H - 10}" text-anchor="middle">${t.toLocaleString('ru-RU', {maximumFractionDigits: 2})}</text>`);
  s += `<text x="${lw - 8}" y="${H - 10}" text-anchor="end" class="punit">цена, ${esc(CUR[cur] || cur || '')}</text>`;
  let y = top, k = 0;
  const hits = [];
  groups.forEach(g => {
    s += `<text x="4" y="${y + rh * 0.68}" class="pbrand">${esc(g.brand)}</text><line class="axis" x1="${lw}" x2="${W - 16}" y1="${y + rh - 1}" y2="${y + rh - 1}" opacity=".35"/>`;
    y += rh;
    g.rows.forEach(row => {
      const cy = y + rh / 2;
      const lab = row.label.length > (narrow ? 18 : 32) ? row.label.slice(0, narrow ? 17 : 31) + '…' : row.label;
      s += `<text x="12" y="${cy + 4}" class="plabel"><title>${esc(row.brand + ' ' + row.label)}</title>${esc(lab)}</text>`;
      s += `<line x1="${lw}" x2="${W - 16}" y1="${cy}" y2="${cy}" class="grid" stroke-dasharray="2 4"/>`;
      row.pts.forEach((p, j) => {
        const col = p.color || 'var(--ink)';
        const dy = row.pts.length > 1 ? (j - (row.pts.length - 1) / 2) * Math.min(6, 16 / row.pts.length) : 0;
        if (p.v != null && p.promo != null) s += `<line x1="${X(p.v)}" x2="${X(p.promo)}" y1="${cy + dy}" y2="${cy + dy}" stroke="${p.color || 'var(--accent)'}" stroke-width="2" opacity=".55"/>`;
        if (p.v != null) s += `<circle cx="${X(p.v)}" cy="${cy + dy}" r="${r}" fill="${col}" class="pdotc"/>`;
        if (p.promo != null) s += `<circle cx="${X(p.promo)}" cy="${cy + dy}" r="${r}" fill="var(--card)" stroke="${p.color || 'var(--accent)'}" stroke-width="2.5"/>`;
      });
      hits.push({y0: y, y1: y + rh, row});
      s += `<rect class="hit" x="0" y="${y}" width="${W}" height="${rh}" fill="transparent" data-i="${k++}"/>`;
      y += rh;
    });
  });
  s += '</svg>';
  box.innerHTML = s + '<div class="fxtip" hidden></div>';
  const tip = box.querySelector('.fxtip');
  box.querySelectorAll('.hit').forEach(el => {
    const show = ev => {
      const h = hits[+el.dataset.i], row = h.row;
      tip.innerHTML = `<div class="tt">${esc(row.brand)} ${esc(row.label)}</div>` + row.pts.map(p =>
        `<div class="tv">${p.name ? `<span class="msw" style="background:${p.color}"></span>${esc(p.name)}: ` : ''}<b>${money(p.v, p.cur || cur)}</b>${p.promo != null ? ` → промо <b>${money(p.promo, p.cur || cur)}</b>` : ''}${p.local ? ` <span class="muted">(${esc(p.local)})</span>` : ''}</div>`).join('') +
        (row.pts[0].tip && row.pts[0].tip.name ? `<div class="muted">${esc(row.pts[0].tip.name)}</div>` : '') +
        (row.pts[0].tip && row.pts[0].tip.promo_desc ? `<div class="muted">${esc(row.pts[0].tip.promo_desc)}</div>` : '');
      tip.hidden = false;
      const bx = box.getBoundingClientRect(), tx = Math.min((ev.clientX || bx.left + 40) - bx.left + 12, bx.width - tip.offsetWidth - 4);
      tip.style.left = Math.max(4, tx) + 'px'; tip.style.top = (h.y1 * (bx.width / W) + 4) + 'px';
    };
    el.addEventListener('mousemove', show); el.addEventListener('click', show);
    el.addEventListener('mouseleave', () => tip.hidden = true);
  });
}

/* ---------- сравнение цен ---------- */
async function viewCompare(q){
  setPeriodBox();
  app.innerHTML = '<p class="loading">Загрузка…</p>';
  let m;
  try { m = await loadManifest(); } catch (e){ app.innerHTML = `${crumbs('<a href="#/stats/prices">Цены</a>')}<div class="empty-msg">Данные пока не загружены.</div>`; return; }
  const days = m.dates.map(d => d.date).sort().reverse();
  const day = days.includes(q.get('d')) ? q.get('d') : days[0];
  const D = await loadDay(day);
  const avail = Object.entries(D.status).filter(([, s]) => s.status === 'ok' && (s.n_paste || s.n_brush)).map(([k]) => k)
    .sort((a, b) => COUNTRIES.findIndex(c => c.id === a.split('/')[0]) - COUNTRIES.findIndex(c => c.id === b.split('/')[0]) || STORES.findIndex(s => s.id === a.split('/')[1]) - STORES.findIndex(s => s.id === b.split('/')[1]));
  let sel = (q.get('s') || '').split(',').filter(x => avail.includes(x));
  if (!sel.length) sel = avail.filter(k => k.endsWith('/dm'));
  if (!sel.length) sel = avail.slice(0, 4);
  const type = TYPES.some(t => t.id === q.get('t')) ? q.get('t') : 'paste';
  const brands = (D.brands || []);
  let bsel = (q.get('b') || '').split(',').filter(b => brands.includes(b));
  const lab = k => `${cname(k.split('/')[0])} · ${sname(k.split('/')[1])}`;
  app.innerHTML = `${crumbs('<a href="#/stats/prices">Цены</a>')}
    <h1>Сравнить цены</h1>
    <p class="sub">Цены пересчитаны в евро по курсу ЕЦБ${D.fx && D.fx.date ? ' на ' + dfmt(D.fx.date) : ''}${D.fx ? ` (1 € = ${D.fx.CZK} Kč, ${D.fx.HUF} Ft, ${D.fx.CHF} CHF)` : ''}. Для каждой линейки взята стандартная упаковка.</p>
    <div class="picker fxctl">
      <div class="row">
        <label>Дата<select id="pDay">${days.map(d => `<option value="${d}"${d === day ? ' selected' : ''}>${dfmt(d)}</option>`).join('')}</select></label>
        <label>Товары<select id="pType">${TYPES.map(t => `<option value="${t.id}"${t.id === type ? ' selected' : ''}>${t.name}</option>`).join('')}</select></label>
      </div>
      <div class="hint">Магазины (до ${PAL.length}):</div>
      <div class="presets" id="pSt">${avail.map(k => `<button class="chip mcc${sel.includes(k) ? ' on' : ''}" data-k="${k}">${esc(lab(k))}</button>`).join('')}</div>
      <div class="hint">Бренды (пусто — все):</div>
      <div class="presets" id="pBr">${brands.map(b => `<button class="chip mcc${bsel.includes(b) ? ' on' : ''}" data-b="${esc(b)}">${esc(b)}</button>`).join('')}</div>
    </div>
    <div id="pCmp"></div>`;
  const go = () => {
    const qs = new URLSearchParams({d: $('#pDay').value, t: $('#pType').value, s: sel.join(',')});
    if (bsel.length) qs.set('b', bsel.join(','));
    location.hash = '#/stats/prices/compare?' + qs;
  };
  $('#pDay').onchange = go; $('#pType').onchange = go;
  app.querySelectorAll('#pSt .chip').forEach(b => b.onclick = () => {
    const k = b.dataset.k; sel = sel.includes(k) ? sel.filter(x => x !== k) : [...sel, k].slice(-PAL.length); go(); });
  app.querySelectorAll('#pBr .chip').forEach(b => b.onclick = () => {
    const k = b.dataset.b; bsel = bsel.includes(k) ? bsel.filter(x => x !== k) : [...bsel, k]; go(); });

  const out = $('#pCmp');
  if (!sel.length){ out.innerHTML = '<div class="empty-msg">Выберите хотя бы один магазин.</div>'; return; }
  const rate = cur => cur === 'EUR' ? 1 : (D.fx && D.fx[cur]) || null;
  const per = {};   /* линейка -> магазин -> строка */
  sel.forEach(k => {
    const [cc, st] = k.split('/');
    lineRows(D.items.filter(x => x.country === cc && x.store === st && x.type === type && (!bsel.length || bsel.includes(x.brand))))
      .forEach(r => ((per[r.brand + '|' + r.line] ||= {})[k] = r));
  });
  const lines = Object.keys(per).sort((a, b) => a.localeCompare(b));
  if (!lines.length){ out.innerHTML = '<div class="empty-msg">Нет товаров для выбранных магазинов и брендов.</div>'; return; }
  const eur = (v, cur) => v == null || !rate(cur) ? null : v / rate(cur);
  const rows = lines.map(l => {
    const [brand, line] = l.split('|');
    return {label: line, brand, pts: sel.map((k, i) => {
      const r = per[l][k]; if (!r) return null;
      return {v: eur(r.regular, r.currency), promo: eur(r.promo, r.currency), color: PAL[i], name: lab(k), cur: 'EUR',
        local: r.currency !== 'EUR' ? money(r.regular, r.currency) + (r.promo != null ? ' / ' + money(r.promo, r.currency) : '') : ''};
    }).filter(Boolean)};
  });
  out.innerHTML = `<div class="fxchart"><div class="pleg">${sel.map((k, i) => `<span><i class="msw" style="background:${PAL[i]}"></i>${esc(lab(k))}</span>`).join('')}
      <span><i class="pdot"></i>регулярная</span><span><i class="pdot promo"></i>промо</span></div><div class="pplot"></div></div>
    <div class="tbl ptbl"><table class="src"><thead><tr><th>Бренд</th><th>Линейка</th>${sel.map((k, i) => `<th class="num"><span class="msw" style="background:${PAL[i]}"></span>${esc(lab(k))}<br><small>рег. / промо, €</small></th>`).join('')}</tr></thead><tbody>${
      lines.map(l => { const [b, ln] = l.split('|'); return `<tr><td>${esc(b)}</td><td><b>${esc(ln)}</b></td>${sel.map(k => {
        const r = per[l][k]; if (!r) return '<td class="num muted">—</td>';
        return `<td class="num"><a href="${esc(r.url)}" target="_blank" rel="noopener" title="${esc(r.name)}">${money(eur(r.regular, r.currency), 'EUR')}</a>${r.promo != null ? `<br><b class="ppromo">${money(eur(r.promo, r.currency), 'EUR')}</b>` : ''}</td>`; }).join('')}</tr>`; }).join('')
    }</tbody></table></div>`;
  drawMatrix(out.querySelector('.pplot'), rows.map(r => ({...r, pts: r.pts.map(p => ({...p, color: p.color}))})), 'EUR');
}

window.viewPrices = viewPrices;
window.routePrices = (p, q) => {
  if (p[0] === 'compare') return viewCompare(q);
  if (!p[0]) return viewPrices();
  if (!PRESENT[p[0]]) return viewPrices();
  if (!p[1]) return viewCountry(p[0]);
  if (!PRESENT[p[0]].includes(p[1])){ location.replace('#/stats/prices/' + p[0]); return; }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(p[2] || '')) return viewDates(p[0], p[1]);
  return viewStore(p[0], p[1], p[2]);
};
})();
