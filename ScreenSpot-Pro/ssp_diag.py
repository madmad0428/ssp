import json, glob

items = {}
for f in glob.glob("ScreenSpot-Pro/annotations/*.json"):
    for i in json.load(open(f, encoding="utf-8")):
        items[i["id"]] = i

for line in open("ssp_results.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r["split"] != "calib" or r["x"] is None:
        continue
    it = items[r["id"]]
    W, H = it["img_size"]
    px, py = r["x"] / 1000 * W, r["y"] / 1000 * H
    x1, y1, x2, y2 = it["bbox"]
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    d = ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5
    diag = (W ** 2 + H ** 2) ** 0.5
    ok = x1 <= px <= x2 and y1 <= py <= y2
    print(f"{it['ui_type']:4} {r['id']:28} raw=({r['x']:.0f},{r['y']:.0f}) "
          f"dx={(px-cx)/W*100:+.1f}%W dy={(py-cy)/H*100:+.1f}%H "
          f"err/diag={d/diag:.3f} {'HIT' if ok else 'miss'}")