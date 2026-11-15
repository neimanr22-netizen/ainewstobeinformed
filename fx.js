/* Раздел «Статистика → Курсы валют» (#/stats/fx).
   Данные: data/fx/<PAIR>.csv (Investing.com, дневные закрытия), data/fx/manifest.json,
   data/fx/forecasts.json (прогнозы аналитиков). При открытии страницы автоматически подгружаются
   свежие курсы из открытых источников в интернете (рынок + ЦБ РФ). */
(() => {
const PAIRS = ['USDRUB', 'EURRUB', 'EURUSD'];
const CUR = {USD: 'Доллар США (USD)', EUR: 'Евро (EUR)', RUB: 'Рубль (RUB)'};
const STEP = {day: 'День', month: 'Месяц', quarter: 'Квартал', year: 'Год'};
const FX = {series: {}, manifest: null, forecasts: null, live: null, cbr: null};

const num = (v, d = 4) => v == null || isNaN(v) ? '—' : v.toLocaleString('ru-RU', {minimumFractionDigits: d, maximumFractionDigits: d});
const dmy = s => s ? `${s.slice(8, 10)}.${s.slice(5, 7)}.${s.slice(0, 4)}` : '';
const pct = (a, b) => (b / a - 1) * 100;
const sign = x => (x > 0 ? '+' : x < 0 ? '−' : '') + Math.abs(x).toLocaleString('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '%';

async function getJSON(url, ms = 8000){
  const c = new AbortController(), t = setTimeout(() => c.abort(), ms);
  try { const r = await fetch(url, {signal: c.signal, cache: 'no-store'}); if (!r.ok) throw new Error(r.status); return await r.json(); }
  finally { clearTimeout(t); }
}

/* ---------- данные из репозитория ---------- */
async function loadFiles(force){
  const v = force ? Date.now() : (FX.manifest?.updated || Date.now());
  FX.manifest = await getJSON('data/fx/manifest.json?v=' + Date.now());
  const ver = encodeURIComponent(force ? v : FX.manifest.updated);
  await Promise.all(PAIRS.map(async p => {
    const t = await fetch(`data/fx/${p}.csv?v=${ver}`).then(r => r.text());
    const rows = t.trim().split(/\r?\n/).slice(1).map(l => l.split(',')).filter(x => x[1]);
    FX.series[p] = rows.map(x => ({d: x[0], c: +x[1]}));
  }));
  FX.forecasts = await getJSON('data/fx/forecasts.json?v=' + Date.now()).catch(() => null);
}

/* ---------- курсы из интернета ---------- */
async function loadLive(){
  const tries = [
    async () => {   // fawazahmed0 currency-api (jsDelivr / Cloudflare)
      for (const base of ['https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/',
                          'https://latest.currency-api.pages.dev/v1/currencies/']){
        try {
          const [u, e] = await Promise.all([getJSON(base + 'usd.json'), getJSON(base + 'eur.json')]);
          return {USDRUB: u.usd.rub, EURRUB: e.eur.rub, EURUSD: e.eur.usd, when: dmy(u.date), src: 'Currency API (рыночный курс)'};
        } catch (e) {}
      }
      throw new Error('currency-api');
    },
    async () => {   // ExchangeRate-API (open access)
      const j = await getJSON('https://open.er-api.com/v6/latest/USD');
      const d = new Date(j.time_last_update_utc);
      return {USDRUB: j.rates.RUB, EURRUB: j.rates.RUB / j.rates.EUR, EURUSD: 1 / j.rates.EUR,
              when: d.toLocaleDateString('ru-RU'), src: 'ExchangeRate-API (рыночный курс)'};
    }
  ];
  for (const t of tries){ try { const r = await t(); if (r.USDRUB > 0) return r; } catch (e) {} }
  return null;
}
async function loadCbr(){
  try {
    const j = await getJSON('https://www.cbr-xml-daily.ru/daily_json.js');
    return {USDRUB: j.Valute.USD.Value / j.Valute.USD.Nominal, EURRUB: j.Valute.EUR.Value / j.Valute.EUR.Nominal,
            USDprev: j.Valute.USD.Previous, EURprev: j.Valute.EUR.Previous, when: dmy(j.Date.slice(0, 10))};
  } catch (e) { return null; }
}

/* ---------- верхний блок: текущие курсы и прогнозы ---------- */
function cardsHtml(){
  return PAIRS.map(p => {
    const s = FX.series[p] || [], last = s[s.length - 1], prev = s[s.length - 2];
    const d = p === 'EURUSD' ? 4 : 2;
    const live = FX.live && FX.live[p], cbr = FX.cbr && FX.cbr[p];
    const big = live ?? last?.c;
    const ch = last && prev ? pct(prev.c, last.c) : null;
    return `<div class="fxcard">
      <div class="fxname">${p.slice(0, 3)}/${p.slice(3)}</div>
      <div class="fxbig">${num(big, d)}</div>
      ${live != null ? `<div class="fxline">Онлайн, ${esc(FX.live.when)} · ${esc(FX.live.src)}</div>` : ''}
      ${last ? `<div class="fxline">Investing.com, закрытие ${dmy(last.d)}: <b>${num(last.c, d)}</b> ${ch != null ? `<span class="${ch >= 0 ? 'up' : 'down'}">${sign(ch)}</span>` : ''}</div>` : ''}
      ${cbr != null ? `<div class="fxline">ЦБ РФ на ${esc(FX.cbr.when)}: <b>${num(cbr, d)}</b></div>` : ''}
    </div>`;
  }).join('');
}
function forecastsHtml(){
  const F = FX.forecasts;
  if (!F || !F.items?.length) return '<div class="empty-msg">Прогнозы пока не загружены.</div>';
  const items = [...F.items].sort((a, b) => b.date.localeCompare(a.date));
  return `<div class="tbl"><table class="src fxf"><thead><tr><th>Кто прогнозирует</th><th>Горизонт</th><th class="num">USD/RUB, ₽</th><th>Дата</th></tr></thead><tbody>${
    items.map(i => `<tr class="first"><td><b>${esc(i.org)}</b><small>${esc(i.comment || '')} <a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.source)} ↗</a></small></td>
      <td class="hz">${esc(i.horizon)}</td><td class="num"><b>${esc(i.value)}</b></td><td class="per">${dmy(i.date)}</td></tr>`).join('')
  }</tbody></table></div><p class="hint">Список прогнозов обновлён ${dmy(F.updated)}. ${esc(F.note || '')}</p>`;
}

/* ---------- ряд для выбранной пары ---------- */
function seriesFor(a, b){
  const key = a + b, inv = b + a;
  if (FX.series[key]) return FX.series[key];
  if (FX.series[inv]) return FX.series[inv].map(x => ({d: x.d, c: 1 / x.c}));
  return [];
}
function groupKey(d, step){
  if (step === 'day') return d;
  if (step === 'month') return d.slice(0, 7);
  if (step === 'quarter') return d.slice(0, 4) + '-Q' + (Math.floor((+d.slice(5, 7) - 1) / 3) + 1);
  return d.slice(0, 4);
}
const MN = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
function keyLabel(k, step, long){
  if (step === 'day') return long ? dmy(k) : `${k.slice(8, 10)}.${k.slice(5, 7)}${long ? '' : '.' + k.slice(2, 4)}`;
  if (step === 'month') return `${MN[+k.slice(5, 7) - 1]} ${long ? k.slice(0, 4) : k.slice(2, 4)}`;
  if (step === 'quarter') return `${k.slice(6)} кв. ${long ? k.slice(0, 4) : k.slice(2, 4)}`;
  return k;
}
function aggregate(rows, step){
  const out = [];
  rows.forEach(r => {
    const k = groupKey(r.d, step), g = out[out.length - 1];
    if (g && g.k === k){ g.c = r.c; g.to = r.d; g.min = Math.min(g.min, r.c); g.max = Math.max(g.max, r.c); g.sum += r.c; g.n++; }
    else out.push({k, c: r.c, from: r.d, to: r.d, min: r.c, max: r.c, sum: r.c, n: 1});
  });
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

/* ---------- график ---------- */
function drawChart(box, pts, opts){
  const W = Math.max(300, box.clientWidth), H = W < 520 ? 280 : 360;
  const m = {l: 56, r: 16, t: 14, b: 34}, iw = W - m.l - m.r, ih = H - m.t - m.b;
  const vals = pts.map(p => p.c), lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || hi * 0.01, ticks = niceTicks(lo - pad, hi + pad);
  const y0 = ticks[0], y1 = ticks[ticks.length - 1];
  const X = i => m.l + (pts.length === 1 ? iw / 2 : i * iw / (pts.length - 1));
  const Y = v => m.t + ih - (v - y0) / (y1 - y0) * ih;
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)},${Y(p.c).toFixed(1)}`).join('');
  const nLab = Math.max(2, Math.floor(iw / 90)), every = Math.max(1, Math.ceil(pts.length / nLab));
  let xl = '';
  for (let i = 0; i < pts.length; i += every)
    xl += `<text x="${X(i)}" y="${H - 10}" text-anchor="middle">${esc(keyLabel(pts[i].k, opts.step))}</text>`;
  box.innerHTML = `<svg class="fxsvg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${esc(opts.title)}">
    ${ticks.map(t => `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(t)}" y2="${Y(t)}"/><text class="yl" x="${m.l - 8}" y="${Y(t) + 4}" text-anchor="end">${num(t, opts.dig)}</text>`).join('')}
    <line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${m.t + ih}" y2="${m.t + ih}"/>
    <g class="xl">${xl}</g>
    <path class="ln" d="${d}"/>
    ${pts.length <= 40 ? pts.map((p, i) => `<circle class="pt" cx="${X(i)}" cy="${Y(p.c)}" r="2.5"/>`).join('') : ''}
    <g class="hov" visibility="hidden"><line class="cross" y1="${m.t}" y2="${m.t + ih}"/><circle class="dot" r="5"/></g>
    <rect class="hit" x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>
  </svg><div class="fxtip" hidden></div>`;
  const svg = box.querySelector('svg'), hov = svg.querySelector('.hov'), cross = hov.querySelector('.cross'),
        dot = hov.querySelector('.dot'), tip = box.querySelector('.fxtip');
  const show = ev => {
    const r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * W / r.width;
    const i = Math.max(0, Math.min(pts.length - 1, Math.round((x - m.l) / (iw / Math.max(1, pts.length - 1)))));
    const p = pts[i], px = X(i), py = Y(p.c);
    hov.setAttribute('visibility', 'visible');
    cross.setAttribute('x1', px); cross.setAttribute('x2', px);
    dot.setAttribute('cx', px); dot.setAttribute('cy', py);
    const prev = pts[i - 1];
    tip.innerHTML = `<div class="tt">${esc(keyLabel(p.k, opts.step, true))}${opts.step !== 'day' ? ` <span class="muted">(${dmy(p.from)} – ${dmy(p.to)})</span>` : ''}</div>
      <div class="tv">${esc(opts.title)}: <b>${num(p.c, opts.dig)}</b>${prev ? ` <span class="${p.c >= prev.c ? 'up' : 'down'}">${sign(pct(prev.c, p.c))}</span>` : ''}</div>
      ${opts.step !== 'day' ? `<div class="muted">Закрытие периода · мин ${num(p.min, opts.dig)} · макс ${num(p.max, opts.dig)} · средн. ${num(p.sum / p.n, opts.dig)}</div>` : ''}`;
    tip.hidden = false;
    const sx = px * r.width / W, sy = py * r.height / H, tw = tip.offsetWidth;
    tip.style.left = Math.max(0, Math.min(r.width - tw, sx - tw / 2)) + 'px';
    tip.style.top = Math.max(0, sy - tip.offsetHeight - 14) + 'px';
  };
  const hide = () => { hov.setAttribute('visibility', 'hidden'); tip.hidden = true; };
  svg.addEventListener('pointermove', show);
  svg.addEventListener('pointerdown', show);
  svg.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') hide(); });
}

/* ---------- страница ---------- */
async function viewFx(q){
  setPeriodBox();
  app.innerHTML = '<p class="loading">Загрузка…</p>';
  try { await loadFiles(); }
  catch (e){ app.innerHTML = `<div class="empty-msg">Не удалось загрузить курсы: ${esc(e.message)}</div>`; return; }
  const M = FX.manifest.pairs, first = Object.values(M).map(x => x.first).sort()[0], last = Object.values(M).map(x => x.last).sort().pop();
  const st = {from: q.get('from') || first, to: q.get('to') || last, step: q.get('step') || 'day', a: q.get('a') || 'USD', b: q.get('b') || 'RUB'};
  app.innerHTML = `
    <div class="crumbs"><a href="#/">Главная</a> / <a href="#/stats">Статистика</a></div>
    <h1>Курсы валют</h1>
    <div class="fxhead"><p class="sub" id="fxStatus">Последние закрытия по данным Investing.com.</p></div>
    <div class="fxcards" id="fxCards">${cardsHtml()}</div>
    <h2 class="fxh2">Прогнозы аналитиков: USD/RUB</h2>
    <div id="fxFc">${forecastsHtml()}</div>
    <h2 class="fxh2">Динамика курса</h2>
    <div class="picker fxctl">
      <div class="row">
        <label>С даты<input type="date" id="fxFrom" value="${st.from}" min="${first}" max="${last}"></label>
        <label>По дату<input type="date" id="fxTo" value="${st.to}" min="${first}" max="${last}"></label>
      </div>
      <div class="presets" id="fxPre">
        <button class="chip" data-m="1">1 месяц</button><button class="chip" data-m="3">3 месяца</button>
        <button class="chip" data-m="6">6 месяцев</button><button class="chip" data-m="12">1 год</button>
        <button class="chip" data-ytd="1">С начала года</button><button class="chip" data-all="1">Весь архив</button>
      </div>
      <div class="row">
        <label>Деление<select id="fxStep">${Object.entries(STEP).map(([k, v]) => `<option value="${k}" ${k === st.step ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
        <label>Валюта 1 (что покупаем)<select id="fxA">${Object.entries(CUR).map(([k, v]) => `<option value="${k}" ${k === st.a ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
        <label>Валюта 2 (чем платим)<select id="fxB">${Object.entries(CUR).map(([k, v]) => `<option value="${k}" ${k === st.b ? 'selected' : ''}>${v}</option>`).join('')}</select></label>
      </div>
    </div>
    <div class="fxchart"><div class="fxtitle" id="fxTitle"></div><div id="fxPlot"></div><div class="fxsum" id="fxSum"></div></div>
    <p class="hint">Источник: Investing.com, дневные цены закрытия. В архиве — с ${dmy(first)} по ${dmy(last)}. Для месяца, квартала и года показано закрытие периода; при наведении — также минимум, максимум и среднее.</p>`;

  const sync = () => {
    const qs = new URLSearchParams({from: st.from, to: st.to, step: st.step, a: st.a, b: st.b});
    history.replaceState(null, '', '#/stats/fx?' + qs);
  };
  const render = () => {
    sync();
    const plot = $('#fxPlot'), title = `${st.a}/${st.b}`;
    $('#fxTitle').innerHTML = `<b>${title}</b> <span class="muted">— сколько ${st.b} стоит 1 ${st.a} · ${STEP[st.step].toLowerCase()} · ${dmy(st.from)} – ${dmy(st.to)}</span>`;
    if (st.a === st.b){ plot.innerHTML = '<div class="empty-msg">Выберите две разные валюты.</div>'; $('#fxSum').innerHTML = ''; return; }
    const rows = seriesFor(st.a, st.b).filter(r => r.d >= st.from && r.d <= st.to);
    const pts = aggregate(rows, st.step);
    if (!pts.length){ plot.innerHTML = '<div class="empty-msg">За этот период данных нет.</div>'; $('#fxSum').innerHTML = ''; return; }
    const dig = st.b === 'RUB' ? 2 : 4;
    drawChart(plot, pts, {step: st.step, dig, title});
    const c = rows.map(r => r.c), mn = Math.min(...c), mx = Math.max(...c), ch = pct(rows[0].c, rows[rows.length - 1].c);
    $('#fxSum').innerHTML = `<span>Начало: <b>${num(rows[0].c, dig)}</b></span><span>Конец: <b>${num(rows[rows.length - 1].c, dig)}</b></span>
      <span>Изменение: <b class="${ch >= 0 ? 'up' : 'down'}">${sign(ch)}</b></span><span>Мин: <b>${num(mn, dig)}</b> (${dmy(rows[c.indexOf(mn)].d)})</span>
      <span>Макс: <b>${num(mx, dig)}</b> (${dmy(rows[c.indexOf(mx)].d)})</span><span>Дней: <b>${rows.length}</b></span>`;
  };
  const setRange = () => {
    let a = $('#fxFrom').value, z = $('#fxTo').value;
    if (!a || !z) return;
    if (a > z) [a, z] = [z, a];
    st.from = a; st.to = z; render();
  };
  $('#fxFrom').onchange = setRange; $('#fxTo').onchange = setRange;
  $('#fxStep').onchange = e => { st.step = e.target.value; render(); };
  $('#fxA').onchange = e => { st.a = e.target.value; render(); };
  $('#fxB').onchange = e => { st.b = e.target.value; render(); };
  app.querySelectorAll('#fxPre .chip').forEach(btn => btn.onclick = () => {
    const z = parse(last); let a;
    if (btn.dataset.all) a = first;
    else if (btn.dataset.ytd) a = last.slice(0, 4) + '-01-01';
    else { z.setUTCMonth(z.getUTCMonth() - +btn.dataset.m); a = iso(z); }
    if (a < first) a = first;
    $('#fxFrom').value = a; $('#fxTo').value = last; setRange();
  });
  let rt; window.onresize = () => { clearTimeout(rt); rt = setTimeout(() => { if ($('#fxPlot')) render(); }, 150); };
  render();

  const update = async () => {
    if (!$('#fxCards')) return;
    const [live, cbr] = await Promise.all([loadLive(), loadCbr()]);
    if (!$('#fxCards')) return;
    FX.live = live; FX.cbr = cbr;
    $('#fxCards').innerHTML = cardsHtml();
    $('#fxFc').innerHTML = forecastsHtml();
    const t = new Date().toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit'});
    $('#fxStatus').textContent = live || cbr
      ? `Обновлено в ${t}: онлайн-курсы${live ? '' : ' (рыночные недоступны)'}${cbr ? ' и официальные курсы ЦБ РФ' : ''}.`
      : `Обновлено в ${t}: онлайн-источники не ответили, показаны последние закрытия Investing.com.`;
  };
  update();
}
window.viewFx = viewFx;
})();
