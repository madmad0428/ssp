import json, glob, statistics as st
from collections import Counter

items = {}
for f in glob.glob("ScreenSpot-Pro/annotations/*.json"):
    for i in json.load(open(f, encoding="utf-8")):
        items[i["id"]] = i

rows = []
for line in open("ssp_results.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r["split"] != "eval" or r["x"] is None:
        continue
    it = items[r["id"]]
    W, H = it["img_size"]
    px, py = r["x"] / 1000 * W, r["y"] / 1000 * H
    x1, y1, x2, y2 = it["bbox"]
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    diag = (W ** 2 + H ** 2) ** 0.5
    e = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5 / diag
    hit = x1 <= px <= x2 and y1 <= py <= y2
    tier = "HIT" if hit else ("근처" if e < 0.03 else ("중간" if e < 0.10 else "엉뚱"))
    rows.append((it["ui_type"], tier, e, (px - cx) / W, (py - cy) / H))

for t in ("icon", "text"):
    sub = [r for r in rows if r[0] == t]
    print(t, len(sub), dict(Counter(r[1] for r in sub)))
miss = [r for r in rows if r[1] != "HIT"]
if miss:
    print("miss 오차 중앙값(err/diag):", round(st.median(r[2] for r in miss), 3))
    print("miss dx 평균(%W):", round(st.mean(r[3] for r in miss) * 100, 2),
          " dy 평균(%H):", round(st.mean(r[4] for r in miss) * 100, 2))