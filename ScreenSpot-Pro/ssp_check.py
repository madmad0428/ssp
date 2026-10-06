import os, sys, json, glob, re, time, random, argparse, io, math
from google import genai
from google.genai import types

ROOT = "ScreenSpot-Pro"
MODEL = "gemini-3.5-flash-lite"
OUT = "ssp_results.jsonl"

PROMPT = (
    "Find the UI element described by the instruction in this screenshot and "
    "return the point at its center. Output only JSON: {\"x\": <int>, \"y\": <int>} "
    "with coordinates normalized to a 0-1000 scale "
    "(x: 0 = left edge, 1000 = right edge; y: 0 = top edge, 1000 = bottom edge)."
)

def load_items():
    items = []
    for f in sorted(glob.glob(f"{ROOT}/annotations/*.json")):
        items += json.load(open(f, encoding="utf-8"))
    return items

def split(items):
    rng = random.Random(0)
    icons = [i for i in items if i["ui_type"] == "icon"]
    texts = [i for i in items if i["ui_type"] == "text"]
    rng.shuffle(icons); rng.shuffle(texts)
    calib = icons[:6] + texts[:6]
    ev = icons[6:31] + texts[6:31]
    return calib, ev

def read_image(path):
    data = open(path, "rb").read()
    if len(data) <= 6.5 * 1024 * 1024:
        return data, "image/png", False
    from PIL import Image
    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, "JPEG", quality=95)
    return buf.getvalue(), "image/jpeg", True

def ask(client, item, res):
    data, mime, converted = read_image(f"{ROOT}/images/{item['img_filename']}")
    level = getattr(types.MediaResolution, f"MEDIA_RESOLUTION_{res.upper()}")
    cfg = types.GenerateContentConfig(media_resolution=level)
    for attempt in range(5):
        try:
            r = client.models.generate_content(
                model=MODEL,
                contents=[types.Part.from_bytes(data=data, mime_type=mime),
                          PROMPT + "\nInstruction: " + item["instruction"]],
                config=cfg)
            return r.text, converted
        except Exception as e:
            print("재시도", attempt + 1, str(e)[:120])
            time.sleep(5 * (attempt + 1))
    return None, converted

def parse(text):
    try:
        m = re.search(r"\{.*?\}", text, re.S)
        d = json.loads(m.group(0))
        return float(d["x"]), float(d["y"])
    except Exception:
        return None

def interpret(x, y, W, H, mode):
    if mode == "xy_norm": return x / 1000 * W, y / 1000 * H
    if mode == "yx_norm": return y / 1000 * W, x / 1000 * H
    if mode == "xy_pix":  return x, y
    if mode == "yx_pix":  return y, x

def hit(rec, item, mode):
    if rec["x"] is None: return None
    W, H = item["img_size"]
    px, py = interpret(rec["x"], rec["y"], W, H, mode)
    x1, y1, x2, y2 = item["bbox"]
    return x1 <= px <= x2 and y1 <= py <= y2

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h

def load_results():
    recs = {}
    if os.path.exists(OUT):
        for line in open(OUT, encoding="utf-8"):
            r = json.loads(line)
            recs[(r["id"], r["res"])] = r
    return recs

def run(items, tag, res):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    done = load_results()
    with open(OUT, "a", encoding="utf-8") as f:
        for n, it in enumerate(items, 1):
            if (it["id"], res) in done: continue
            raw, conv = ask(client, it, res)
            xy = parse(raw) if raw else None
            rec = {"id": it["id"], "split": tag, "res": res, "raw": raw,
                   "x": xy[0] if xy else None, "y": xy[1] if xy else None,
                   "jpeg_converted": conv}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            print(n, len(items), it["id"], raw and raw.strip()[:60])
            time.sleep(4)

def report(items, res, mode):
    recs = load_results()
    rows = [(it, recs[(it["id"], res)]) for it in items if (it["id"], res) in recs]
    hs = [(it, hit(r, it, mode)) for it, r in rows]
    valid = [(it, h) for it, h in hs if h is not None]
    print(f"[{mode}/{res}] 응답 {len(rows)}개, 파싱 실패 {len(rows) - len(valid)}개")
    def line(name, sub):
        k = sum(h for _, h in sub); n = len(sub)
        lo, hi = wilson(k, n)
        print(f"  {name}: {k}/{n} = {k/n*100:.1f}%  (95% CI {lo*100:.1f}~{hi*100:.1f})" if n else f"  {name}: 없음")
    line("전체", valid)
    for t in ("icon", "text"):
        line(t, [(i, h) for i, h in valid if i["ui_type"] == t])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["calib", "eval", "report"])
    ap.add_argument("--res", default="high", choices=["low", "medium", "high"])
    ap.add_argument("--mode", default="xy_norm")
    a = ap.parse_args()
    items = load_items()
    calib, ev = split(items)
    if a.cmd == "calib":
        run(calib, "calib", a.res)
        for m in ("xy_norm", "yx_norm", "xy_pix", "yx_pix"):
            report(calib, a.res, m)
    elif a.cmd == "eval":
        run(ev, "eval", a.res)
        report(ev, a.res, a.mode)
    else:
        report(ev, a.res, a.mode)