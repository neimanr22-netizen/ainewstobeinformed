#!/usr/bin/env python3
"""Собирает справочник источников новостей: откуда (какой сайт и раздел) взяты ссылки.

Использование:
    python3 tools/sources.py

Читает все новости из data/days/*.json и справочник tools/sources_map.json,
пишет два файла:
    data/sources.json — для страницы «Новостные источники» на сайте
    SOURCES.md        — тот же список в виде документа для GitHub

Иерархия: группа (например, «Новостные порталы») → сайт (РБК) → раздел (Экономика).
В списке — не ссылки на сами новости, а ссылки на сайты и их разделы.

Если у новости домен, которого нет в справочнике, скрипт пишет предупреждение
и кладёт сайт в группу «Не распределено». Нужно добавить домен в
tools/sources_map.json (sites, при необходимости sections) и запустить скрипт снова.
add_news.py запускает этот скрипт сам после каждого добавления.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UNSORTED = "Не распределено"
WHOLE_SITE = "Сайт целиком"


def host_of(u):
    return urlsplit(u).netloc.lower().removeprefix("www.")


def section_of(item, host, m, netloc):
    """Возвращает (название раздела, адрес раздела) для новости."""
    site_url = "https://" + netloc + "/"
    if host == "rg.ru" and item.get("cat") == "rg" and item.get("sub") in m["rg_by_sub"]:
        return tuple(m["rg_by_sub"][item["sub"]])
    rules = m["sections"].get(host, {})
    path = urlsplit(item["url"]).path.strip("/")
    best = None
    for prefix in rules:
        if path == prefix or path.startswith(prefix + "/"):
            if best is None or len(prefix) > len(best):
                best = prefix
    if best is None:
        return WHOLE_SITE, site_url
    name, _, url = rules[best].partition("|")
    return name, url or f"https://{netloc}/{best}/"


def build():
    m = json.loads((ROOT / "tools" / "sources_map.json").read_text(encoding="utf-8"))
    groups = {g["name"]: g for g in m["groups"]}
    tree, unknown = {}, set()
    items = [it for f in sorted((DATA / "days").glob("*.json"))
             for it in json.loads(f.read_text(encoding="utf-8"))]
    # как сайт пишется в ссылках чаще всего (с www или без) — так и даём адрес раздела
    spell = {}
    for it in items:
        nl = urlsplit(it["url"]).netloc.lower()
        spell.setdefault(host_of(it["url"]), {}).setdefault(nl, 0)
        spell[host_of(it["url"])][nl] += 1
    netloc_of = {h: max(v, key=v.get) for h, v in spell.items()}
    if True:
        for it in items:
            host = host_of(it["url"])
            info = m["sites"].get(host)
            if not info:
                unknown.add(host)
                info = {"group": UNSORTED, "name": it.get("source") or host}
            site_host = info.get("site", host)
            site_key = (info["group"], info["name"], site_host)
            sec_name, sec_url = section_of(it, host, m, netloc_of[host])
            site = tree.setdefault(site_key, {})
            sec = site.setdefault(sec_url, {"name": sec_name, "url": sec_url, "count": 0,
                                            "first": it["date"], "last": it["date"]})
            sec["count"] += 1
            sec["first"] = min(sec["first"], it["date"])
            sec["last"] = max(sec["last"], it["date"])

    order = [g["name"] for g in m["groups"]] + [UNSORTED]
    out_groups = []
    for gname in order:
        sites = []
        for (g, name, shost), secs in tree.items():
            if g != gname:
                continue
            sec_list = sorted(secs.values(), key=lambda s: (s["name"] == WHOLE_SITE, -s["count"], s["name"]))
            sites.append({
                "name": name,
                "url": f"https://{netloc_of.get(shost, shost)}/",
                "count": sum(s["count"] for s in sec_list),
                "last": max(s["last"] for s in sec_list),
                "sections": sec_list,
            })
        if not sites:
            continue
        sites.sort(key=lambda s: (-s["count"], s["name"].lower()))
        out_groups.append({
            "name": gname,
            "about": groups.get(gname, {}).get("about", "Домены, которых ещё нет в tools/sources_map.json"),
            "count": sum(s["count"] for s in sites),
            "sites": sites,
        })

    result = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total_news": sum(g["count"] for g in out_groups),
        "total_sites": sum(len(g["sites"]) for g in out_groups),
        "groups": out_groups,
    }
    (DATA / "sources.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (ROOT / "SOURCES.md").write_text(to_md(result), encoding="utf-8")
    print(f"Источники: {result['total_sites']} сайтов, {sum(len(s['sections']) for g in out_groups for s in g['sites'])} разделов, "
          f"{result['total_news']} новостей → data/sources.json, SOURCES.md")
    if unknown:
        print("  ! Нет в tools/sources_map.json (попали в «Не распределено»): " + ", ".join(sorted(unknown)))
    return result


def plural(n, one, few, many):
    m10, m100 = n % 10, n % 100
    w = one if m10 == 1 and m100 != 11 else few if 2 <= m10 <= 4 and not 12 <= m100 <= 14 else many
    return f"{n} {w}"


def sites_n(n):
    return plural(n, "сайт", "сайта", "сайтов")


def news_n(n):
    return plural(n, "новость", "новости", "новостей")


def ru_date(s):
    y, mth, d = s.split("-")
    return f"{d}.{mth}.{y}"


def to_md(r):
    L = ["# Новостные источники", "",
         "Сайты и их разделы, из которых брались новости для ainewstobeinformed.ru.",
         "Здесь ссылки на источники (сайт или раздел сайта), а не на отдельные новости.",
         "Файл создаётся автоматически скриптом `tools/sources.py` — вручную не править.", "",
         f"Всего: {sites_n(r['total_sites'])}, {news_n(r['total_news'])}. "
         f"Обновлено: {ru_date(r['updated'][:10])}.", "",
         "## Оглавление", ""]
    for g in r["groups"]:
        anchor = g["name"].lower().replace(" ", "-").replace(",", "")
        L.append(f"- [{g['name']}](#{anchor}) — {sites_n(len(g['sites']))}, {news_n(g['count'])}")
    for g in r["groups"]:
        L += ["", f"## {g['name']}", "", f"_{g['about']}_", "",
              "| Сайт | Раздел | Новостей | Период |", "|---|---|---:|---|"]
        for s in g["sites"]:
            for k, sec in enumerate(s["sections"]):
                site = f"**[{s['name']}]({s['url']})**" if k == 0 else ""
                period = ru_date(sec["first"]) if sec["first"] == sec["last"] else f"{ru_date(sec['first'])} – {ru_date(sec['last'])}"
                L.append(f"| {site} | [{sec['name']}]({sec['url']}) | {sec['count']} | {period} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    build()
