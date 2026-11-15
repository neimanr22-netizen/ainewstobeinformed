#!/usr/bin/env python3
"""Загрузка дневных курсов валют с Investing.com в data/fx/<PAIR>.csv.

    python3 tools/fx_fetch.py 2025-01-01 2026-11-14 [USDRUB EURRUB EURUSD]

Новые дни ДОБАВЛЯЮТСЯ к уже сохранённым (старые строки не удаляются,
совпадающие даты перезаписываются свежими значениями).
Запускается GitHub Actions (workflow «Курсы валют: загрузка»), потому что
Investing.com отдаёт данные только «браузерным» запросам.
"""
import csv
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FX = ROOT / "data" / "fx"
# id инструментов Investing.com
PAIRS = {"USDRUB": 2186, "EURRUB": 1691, "EURUSD": 1}
NAMES = {"USDRUB": "USD/RUB", "EURRUB": "EUR/RUB", "EURUSD": "EUR/USD"}


def session():
    try:
        from curl_cffi import requests as r
        s = r.Session(impersonate="chrome")
    except ImportError:
        import requests as r
        s = r.Session()
        s.headers["User-Agent"] = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                   "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
    s.headers.update({"domain-id": "www", "Accept": "application/json",
                      "Origin": "https://www.investing.com", "Referer": "https://www.investing.com/"})
    return s


def f(x):
    if x in (None, ""):
        return None
    return float(str(x).replace(",", ""))


def fetch_api(s, pid, d1, d2):
    """Основной способ: api.investing.com, кусками по ~5 месяцев."""
    rows = {}
    a = d1
    while a <= d2:
        b = min(a + timedelta(days=150), d2)
        url = (f"https://api.investing.com/api/financialdata/historical/{pid}"
               f"?start-date={a}&end-date={b}&time-frame=Daily&add-missing-rows=false")
        r = s.get(url, timeout=40)
        if r.status_code != 200:
            raise RuntimeError(f"api {r.status_code}: {r.text[:200]}")
        for it in r.json().get("data") or []:
            d = (it.get("rowDateTimestamp") or it.get("rowDateRaw") or "")[:10]
            if not d:
                continue
            rows[d] = dict(close=f(it.get("last_closeRaw") or it.get("last_close")),
                           open=f(it.get("last_openRaw") or it.get("last_open")),
                           high=f(it.get("last_maxRaw") or it.get("last_max")),
                           low=f(it.get("last_minRaw") or it.get("last_min")))
        a = b + timedelta(days=1)
        time.sleep(1.5)
    return rows


def fetch_tvc(s, pid, d1, d2):
    """Запасной способ: графический сервис Investing.com (tvc)."""
    t1 = int(datetime(d1.year, d1.month, d1.day, tzinfo=timezone.utc).timestamp())
    t2 = int(datetime(d2.year, d2.month, d2.day, 23, 59, tzinfo=timezone.utc).timestamp())
    last = None
    for host in ("tvc4", "tvc6"):
        url = (f"https://{host}.investing.com/0/0/0/0/0/history?symbol={pid}&resolution=D&from={t1}&to={t2}")
        r = s.get(url, timeout=40, headers={"Referer": "https://tvc-invdn-com.investing.com/"})
        if r.status_code == 200 and r.text.strip().startswith("{"):
            j = r.json()
            if j.get("s") == "ok":
                return {datetime.fromtimestamp(t, timezone.utc).date().isoformat():
                        dict(close=c, open=o, high=h, low=l)
                        for t, c, o, h, l in zip(j["t"], j["c"], j["o"], j["h"], j["l"])}
        last = f"{host} {r.status_code}: {r.text[:150]}"
    raise RuntimeError(last)


def merge(pair, rows):
    path = FX / f"{pair}.csv"
    old = {}
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                old[r["date"]] = r
    for d, v in rows.items():
        if v["close"] is None:
            continue
        old[d] = {"date": d, **{k: ("" if v[k] is None else f"{v[k]:.4f}") for k in ("close", "open", "high", "low")}}
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "close", "open", "high", "low"])
        w.writeheader()
        for d in sorted(old):
            w.writerow(old[d])
    return len(old)


def manifest():
    m = {"source": "Investing.com", "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "pairs": {}}
    for pair in PAIRS:
        p = FX / f"{pair}.csv"
        if not p.exists():
            continue
        ds = [r["date"] for r in csv.DictReader(p.open(encoding="utf-8"))]
        if ds:
            m["pairs"][pair] = {"name": NAMES[pair], "first": ds[0], "last": ds[-1], "rows": len(ds)}
    (FX / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    a = sys.argv[1:]
    d1, d2 = date.fromisoformat(a[0]), date.fromisoformat(a[1])
    pairs = [p.upper() for p in a[2:]] or list(PAIRS)
    FX.mkdir(parents=True, exist_ok=True)
    s = session()
    ok = True
    for pair in pairs:
        pid = PAIRS[pair]
        rows = None
        for fn in (fetch_api, fetch_tvc):
            try:
                rows = fn(s, pid, d1, d2)
                if rows:
                    print(f"{pair}: {fn.__name__} → {len(rows)} дней")
                    break
            except Exception as e:
                print(f"{pair}: {fn.__name__} не сработал: {e}")
        if not rows:
            ok = False
            continue
        print(f"{pair}: всего в файле {merge(pair, rows)} дней")
    manifest()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
