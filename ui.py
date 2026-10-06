@'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
실제 UI 난이도 탐침 — 원본 색 그대로의 스크린샷에서 버튼 7개를 모델에 묻는다.

준비: 같은 폴더에
  real_A.png  (programmers 화면, 2992x1326)
  real_B.png  (Roboflow 화면,   3439x1439)
  d3_run.py   (API 키와 모델 설정을 가져온다)
실행: python real_probe.py      (끊기면 다시 실행하면 이어서 진행)

질의 28번 = 7개 버튼 x 프롬프트 2종 x 2회.
채점은 두 가지 해석으로 모두 한다.
  norm : 모델의 답을 0~1000 정규화 좌표(x먼저)로 보고 픽셀로 환산 (Gemini에서 확정한 규칙)
  pix  : 모델의 답을 픽셀 좌표 그대로로 봄 (크기 문장을 뺐을 때 형식이 바뀌는지 잡기 위함)
"""
import csv, io, json, math, os, re, sys, time
from PIL import Image

try:
    import d3_run as D
except ImportError:
    sys.exit("[중단] d3_run.py 가 같은 폴더에 있어야 합니다 (API 키와 설정을 가져옵니다).")

IMAGES = {'A': ('real_A.png', (2992, 1326)), 'B': ('real_B.png', (3439, 1439))}
# (이미지, 라벨, [정답 박스 x0,y0,x1,y1], 허용 여백 px)
TARGETS = [
    ('A', '로그인', [(2006, 11, 2072, 43)], 0),
    ('A', '자세히 보기', [(944, 830, 1035, 859), (1536, 830, 1627, 859)], 2),   # 화면에 2개: 아무 쪽이나 정답
    ('B', 'GET STARTED', [(2486, 122, 2610, 157)], 0),
    ('B', 'BOOK A DEMO', [(2350, 122, 2477, 157)], 0),
    ('B', 'Login', [(2256, 132, 2333, 147)], 6),                                # 글자 링크: 글자 박스 + 여백 6px
    ('B', 'TRY ROBOFLOW AGENT', [(1637, 1320, 1825, 1363)], 0),
    ('B', 'Accept', [(3306, 1311, 3380, 1347)], 0),
    ('B', 'Reject', [(3217, 1311, 3289, 1347)], 0),
]
PROMPTS = {
    'P1_크기문장O': "이 화면에서 '{label}' 버튼의 중심 픽셀 좌표를 구하세요.\n이미지 크기는 가로 {W}, 세로 {H}입니다.\n설명 없이 JSON만 출력: {{\"x\": <정수>, \"y\": <정수>}}",
    'P2_크기문장X': "이 화면에서 '{label}' 버튼의 중심 픽셀 좌표를 구하세요.\n설명 없이 JSON만 출력: {{\"x\": <정수>, \"y\": <정수>}}",
}
REPS = 2
OUT = "real_probe_results.csv"
FIELDS = ['img', 'label', 'prompt', 'rep', 'status', 'x', 'y', 'pred_x', 'pred_y',
          'hit_norm', 'err_norm', 'hit_pix', 'echo', 'raw']

def parse_xy(text):
    m = re.search(r'\{[^{}]*\}', text, re.S)
    if m:
        try:
            o = json.loads(m.group(0)); return float(o['x']), float(o['y'])
        except Exception:
            pass
    m = re.search(r'["\']?x["\']?\s*[:=]\s*(-?\d+\.?\d*).{0,30}?["\']?y["\']?\s*[:=]\s*(-?\d+\.?\d*)', text, re.S | re.I)
    return (float(m.group(1)), float(m.group(2))) if m else None

def inside(px, py, boxes, pad):
    return any(b[0] - pad <= px <= b[2] + pad and b[1] - pad <= py <= b[3] + pad for b in boxes)

def dist_center(px, py, boxes):
    return min(math.hypot(px - (b[0] + b[2]) / 2, py - (b[1] + b[3]) / 2) for b in boxes)

def ask(client, img_bytes, prompt):
    """반환 (응답텍스트, 오류문자열 또는 None)"""
    from google.genai import types
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=D.MODEL,
                contents=[types.Part.from_bytes(data=img_bytes, mime_type="image/png"), prompt],
                config=types.GenerateContentConfig(
                    temperature=D.TEMPERATURE, max_output_tokens=D.MAX_TOKENS,
                    thinking_config=types.ThinkingConfig(thinking_level=D.THINKING)))
            return (resp.text or ""), None
        except Exception as e:
            msg = str(e)
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                wait = 25 * (attempt + 1); print(f"  (속도제한 {wait}s 대기)"); time.sleep(wait); continue
            return "", msg
    return "", "rate limit retries exhausted"

def evaluate(img, label, boxes, pad, txt):
    W, H = IMAGES[img][1]
    rec = {'img': img, 'label': label, 'raw': txt.replace('\n', ' ')[:80]}
    ab = parse_xy(txt)
    if ab is None:
        rec.update(status='no_parse', x='', y='', pred_x='', pred_y='', hit_norm=0, err_norm='', hit_pix=0, echo=0)
        return rec
    x, y = ab; px, py = x / 1000 * W, y / 1000 * H
    rec.update(status='ok', x=x, y=y, pred_x=round(px, 1), pred_y=round(py, 1),
               hit_norm=int(inside(px, py, boxes, pad)), err_norm=round(dist_center(px, py, boxes), 1),
               hit_pix=int(inside(x, y, boxes, pad)), echo=int(x == W and y == H))
    return rec

def load_images():
    out = {}
    for k, (fn, size) in IMAGES.items():
        if not os.path.exists(fn):
            sys.exit(f"[중단] {fn} 가 이 폴더에 없습니다. 스크린샷 원본을 이 이름으로 복사하세요.")
        im = Image.open(fn)
        if im.size != size:
            sys.exit(f"[중단] {fn} 크기가 {im.size}입니다. 박스는 {size} 기준으로 쟀습니다. 같은 원본인지 확인하세요.")
        buf = io.BytesIO(); im.convert('RGB').save(buf, format='PNG'); out[k] = buf.getvalue()
    return out

def summarize(rows):
    print(f"\n{'=' * 70}\n요약 (정답 = 예측점이 박스 안. norm = 0~1000 정규화 해석, pix = 픽셀 그대로 해석)\n{'=' * 70}")
    for p in PROMPTS:
        g = [r for r in rows if r['prompt'] == p]
        if not g: continue
        hn = sum(int(r['hit_norm']) for r in g); hp = sum(int(r['hit_pix']) for r in g)
        ec = sum(int(r['echo']) for r in g); npz = sum(1 for r in g if r['status'] == 'no_parse')
        surprise = sum(1 for r in g if int(r['hit_pix']) == 1 and int(r['hit_norm']) == 0)
        print(f"{p}: norm 해석 {hn}/{len(g)}  pix 해석 {hp}/{len(g)}  에코 {ec}  좌표 못 냄 {npz}  형식 의심(pix만 맞음) {surprise}")
    print("\n버튼별 (norm 해석, 프롬프트 2종 x 2회 = 4건 중)")
    for (img, label, boxes, pad) in TARGETS:
        g = [r for r in rows if r['img'] == img and r['label'] == label]
        if g: print(f"  {img} {label:<20} {sum(int(r['hit_norm']) for r in g)}/{len(g)}")
    print("\n같은 이미지·같은 프롬프트 2회 답이 같은가 (결정성)")
    same = tot = 0
    for (img, label, boxes, pad) in TARGETS:
        for p in PROMPTS:
            g = [(r['x'], r['y']) for r in rows if r['img'] == img and r['label'] == label and r['prompt'] == p]
            if len(g) == REPS: tot += 1; same += int(len(set(g)) == 1)
    print(f"  {same}/{tot} 쌍이 동일")

def main():
    for p in PROMPTS.values():
        for (img, label, boxes, pad) in TARGETS:
            D.assert_no_color_words(p.format(label=label, W=0, H=0))
    imgs = load_images(); client = D.make_client()
    done = set()
    if os.path.exists(OUT):
        done = {(r['img'], r['label'], r['prompt'], r['rep']) for r in csv.DictReader(open(OUT, encoding='utf-8-sig'))}
    jobs = [(img, label, boxes, pad, pn, rep) for (img, label, boxes, pad) in TARGETS for pn in PROMPTS for rep in range(REPS)]
    todo = [j for j in jobs if (j[0], j[1], j[4], str(j[5])) not in done]
    print(f"전체 {len(jobs)} / 완료 {len(jobs) - len(todo)} / 이번 {len(todo)}")
    consec = 0
    for i, (img, label, boxes, pad, pn, rep) in enumerate(todo):
        W, H = IMAGES[img][1]
        prompt = PROMPTS[pn].format(label=label, W=W, H=H)
        txt, err = ask(client, imgs[img], prompt)
        if err:
            consec += 1; print(f"  [API 오류 — 저장 안 함] {err[:140]}")
            if consec >= 5: print("연속 5회 오류 — 중단합니다."); break
            continue
        consec = 0
        rec = evaluate(img, label, boxes, pad, txt); rec.update(prompt=pn, rep=rep)
        new = not os.path.exists(OUT)
        with open(OUT, 'a', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new: w.writeheader()
            w.writerow(rec)
        print(f"[{i + 1}/{len(todo)}] {img} {label:<19} {pn[:2]} r{rep}  raw={rec['raw'][:42]!r:<46} norm={rec['hit_norm']} err={rec['err_norm']} pix={rec['hit_pix']} echo={rec['echo']}", flush=True)
        if i < len(todo) - 1: time.sleep(D.SLEEP)
    if os.path.exists(OUT):
        summarize(list(csv.DictReader(open(OUT, encoding='utf-8-sig'))))

if __name__ == "__main__":
    main()
'@ | Set-Content -Path real_probe.py -Encoding UTF8