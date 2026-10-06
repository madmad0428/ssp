import json, itertools
from math import comb

recs = {}
for l in open("ssp_results.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if r["split"] == "eval":
        recs[(r["id"], r["res"])] = r

items = {}
import glob
for f in glob.glob("ScreenSpot-Pro/annotations/*.json"):
    for i in json.load(open(f, encoding="utf-8")):
        items[i["id"]] = i

def hit(r, it):
    if r["x"] is None: return False
    W, H = it["img_size"]
    px, py = r["x"] / 1000 * W, r["y"] / 1000 * H
    x1, y1, x2, y2 = it["bbox"]
    return x1 <= px <= x2 and y1 <= py <= y2

def mcnemar_exact(b, c):
    n = b + c
    if n == 0: return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)

levels = [l for l in ("high", "medium", "low") if any(k[1] == l for k in recs)]
ids = sorted({k[0] for k in recs if all((k[0], l) in recs for l in levels)})
H = {l: {i: hit(recs[(i, l)], items[i]) for i in ids} for l in levels}
for l in levels:
    print(l, sum(H[l].values()), "/", len(ids))
for a, b_ in itertools.combinations(levels, 2):
    b = sum(H[a][i] and not H[b_][i] for i in ids)
    c = sum(H[b_][i] and not H[a][i] for i in ids)
    print(f"{a} vs {b_}: {a}만 맞음 {b}, {b_}만 맞음 {c}, 정확 McNemar p={mcnemar_exact(b, c):.3f}")