#!/usr/bin/env python3
"""Добавляет новости из batch-файлов в хранилище сайта.

Использование:
    python3 tools/add_news.py batch1.json [batch2.json ...]

Batch-файл — JSON-массив объектов:
    {
      "date": "2026-11-14",          # дата публикации новости в источнике (НЕ дата сбора)
      "cat": "rbc",                  # id категории из data/categories.json
      "sub": "politics",             # id подкатегории или null, если подкатегорий нет
      "title": "Заголовок",
      "summary": "2–4 предложения пересказа",
      "url": "https://...",
      "source": "РБК"                # необязательно; по умолчанию — домен ссылки
    }

Хранилище:
    data/days/YYYY-MM-DD.json  — новости за день (по дате новости)
    data/manifest.json         — список дней и число новостей в каждом

Повторы отбрасываются: одинаковая ссылка (без utm/якорей) или одинаковый
заголовок в той же подкатегории.
"""
import hashlib
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DAYS = DATA / "days"


def load_tree():
    cfg = json.loads((DATA / "categories.json").read_text(encoding="utf-8"))
    countries = [c["id"] for c in cfg["countries"]]
    tree = {}
    for c in cfg["categories"]:
        subs = c["subs"]
        if subs == "countries":
            tree[c["id"]] = set(countries)
        else:
            tree[c["id"]] = {s["id"] for s in subs}
    return tree


def norm_url(u):
    p = urlsplit(u.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "from", "ref"))]
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/")
    return urlunsplit(("https", host, path, urlencode(q), ""))


def norm_title(t):
    return re.sub(r"[^\w]+", " ", t.lower()).strip()


def host_of(u):
    return urlsplit(u).netloc.lower().removeprefix("www.")


def main(paths):
    tree = load_tree()
    DAYS.mkdir(parents=True, exist_ok=True)

    # загрузить существующее
    by_day = {}
    seen_url, seen_title = set(), set()
    for f in DAYS.glob("*.json"):
        items = json.loads(f.read_text(encoding="utf-8"))
        by_day[f.stem] = items
        for it in items:
            seen_url.add(norm_url(it["url"]))
            seen_title.add((it["cat"], it.get("sub"), norm_title(it["title"])))

    today = date.today().isoformat()
    added, dup, bad = 0, 0, []
    for p in paths:
        batch = json.loads(Path(p).read_text(encoding="utf-8"))
        for it in batch:
            err = None
            d = it.get("date", "")
            try:
                datetime.strptime(d, "%Y-%m-%d")
            except ValueError:
                err = f"неверная дата {d!r}"
            cat, sub = it.get("cat"), it.get("sub")
            if not err and cat not in tree:
                err = f"нет категории {cat!r}"
            if not err:
                if tree[cat] and sub not in tree[cat]:
                    err = f"нет подкатегории {sub!r} в {cat}"
                if not tree[cat]:
                    sub = None
            for k in ("title", "summary", "url"):
                if not err and not str(it.get(k, "")).strip():
                    err = f"пустое поле {k}"
            if not err and not it["url"].startswith(("http://", "https://")):
                err = "ссылка должна начинаться с http"
            if err:
                bad.append((it.get("title", "?"), err))
                continue
            nu = norm_url(it["url"])
            nt = (cat, sub, norm_title(it["title"]))
            if nu in seen_url or nt in seen_title:
                dup += 1
                continue
            seen_url.add(nu)
            seen_title.add(nt)
            rec = {
                "id": hashlib.sha1(nu.encode()).hexdigest()[:10],
                "date": d,
                "cat": cat,
                "sub": sub,
                "title": it["title"].strip(),
                "summary": it["summary"].strip(),
                "url": it["url"].strip(),
                "source": (it.get("source") or host_of(it["url"])).strip(),
                "added": it.get("added", today),
            }
            by_day.setdefault(d, []).append(rec)
            added += 1

    for d, items in by_day.items():
        items.sort(key=lambda x: (x["cat"], x["sub"] or "", x["title"]))
        (DAYS / f"{d}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    manifest = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "days": {d: len(by_day[d]) for d in sorted(by_day)},
    }
    (DATA / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"Добавлено: {added}, повторов отброшено: {dup}, с ошибками: {len(bad)}")
    for t, e in bad:
        print(f"  ! {t[:70]} — {e}")
    total = sum(manifest["days"].values())
    print(f"Всего в хранилище: {total} новостей за {len(manifest['days'])} дн.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
