import json, glob
items = {}
for f in glob.glob("ScreenSpot-Pro/annotations/*.json"):
    for i in json.load(open(f, encoding="utf-8")):
        items[i["id"]] = i
def load(fn):
    return {r["id"]: r for r in (json.loads(l) for l in open(fn, encoding="utf-8"))
            if r["split"] == "eval" and r["res"] == "high"}
def hit(r):
    it = items[r["id"]]; W, H = it["img_size"]
    if r["x"] is None: return False
    px, py = r["x"]/1000*W, r["y"]/1000*H
    x1, y1, x2, y2 = it["bbox"]
    return x1 <= px <= x2 and y1 <= py <= y2
a, b = load("ssp_results.jsonl"), load("ssp_results_rep.jsonl")
ids = sorted(set(a) & set(b))
flips = sum(hit(a[i]) != hit(b[i]) for i in ids)
print(f"1회차 {sum(hit(a[i]) for i in ids)}/{len(ids)}, 2회차 {sum(hit(b[i]) for i in ids)}/{len(ids)}, 뒤집힘 {flips}")