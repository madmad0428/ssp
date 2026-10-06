import json, glob, os
from collections import Counter

root = "ScreenSpot-Pro"
items = []
for f in sorted(glob.glob(f"{root}/annotations/*.json")):
    items += json.load(open(f, encoding="utf-8"))

print("총", len(items))
print(Counter(i["ui_type"] for i in items))
print(Counter(i["group"] for i in items))

missing = [i["id"] for i in items if not os.path.exists(f"{root}/images/{i['img_filename']}")]
print("이미지 없는 항목:", len(missing), missing[:5])

ratios = sorted(
    (i["bbox"][2]-i["bbox"][0]) * (i["bbox"][3]-i["bbox"][1]) / (i["img_size"][0]*i["img_size"][1])
    for i in items
)
n = len(ratios)
print("타깃 면적비(%%) 10%%: %.4f / 중앙값: %.4f / 90%%: %.4f"
      % (ratios[n//10]*100, ratios[n//2]*100, ratios[9*n//10]*100))