#!/usr/bin/env python3
"""Сколько новостей есть по каждой (под)категории за период.

    python3 tools/stats.py 2026-11-01 2026-11-14 [цель=10]

Показывает, где не хватает новостей до цели.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main(d1, d2, goal=10):
    cfg = json.loads((DATA / "categories.json").read_text(encoding="utf-8"))
    counts = {}
    for f in sorted((DATA / "days").glob("*.json")):
        if d1 <= f.stem <= d2:
            for it in json.loads(f.read_text(encoding="utf-8")):
                k = (it["cat"], it.get("sub"))
                counts[k] = counts.get(k, 0) + 1
    total = 0
    for c in cfg["categories"]:
        subs = cfg["countries"] if c["subs"] == "countries" else c["subs"]
        if not subs:
            n = counts.get((c["id"], None), 0)
            total += n
            print(f"{c['name']:<28} {n:>4} {'' if n >= goal else '← не хватает ' + str(goal - n)}")
            continue
        print(c["name"])
        for s in subs:
            n = counts.get((c["id"], s["id"]), 0)
            total += n
            print(f"   {s['name']:<25} {n:>4} {'' if n >= goal else '← не хватает ' + str(goal - n)}")
    print(f"Итого: {total}")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], int(a[2]) if len(a) > 2 else 10)
