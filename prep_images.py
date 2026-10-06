#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
스크린샷 준비 — 이 폴더의 이미지(webp/png/jpg)에서 크기가 맞는 두 장을 찾아
진짜 PNG로 변환해 real_A.png / real_B.png 로 저장한다. 파일마다 무슨 일이 있었는지 출력한다.
  real_A.png : programmers 화면  2992 x 1326
  real_B.png : Roboflow 화면     3439 x 1439
사용: python prep_images.py
"""
import glob, sys
from PIL import Image

TARGET = {(2992, 1326): 'real_A.png', (3439, 1439): 'real_B.png'}
NAMES = set(TARGET.values())

def webp_kind(path):
    head = open(path, 'rb').read(8192)
    if b'VP8L' in head: return '무손실'
    if b'VP8 ' in head: return '손실'
    return '확인 불가'

files = []
for pat in ('*.webp', '*.png', '*.jpg', '*.jpeg', '*.bmp'):
    files += glob.glob(pat)
files = sorted(set(files))
print(f"이 폴더의 이미지 {len(files)}개를 확인합니다.\n")

done = {}
for f in files:
    if f in NAMES: continue
    try:
        im = Image.open(f); size = im.size; fmt = im.format
    except Exception as e:
        print(f"  {f}: 열 수 없음 -> {type(e).__name__}: {e}")
        if f.lower().endswith('.webp'):
            print("     (이 컴퓨터의 Pillow가 WebP를 못 읽는 것일 수 있습니다. 위 메시지를 그대로 알려주세요.)")
        continue
    kind = f" [{webp_kind(f)}]" if fmt == 'WEBP' else ""
    tag = TARGET.get(size)
    print(f"  {f}  | {fmt}{kind} | {size[0]}x{size[1]}  ->  " + (tag if tag else "크기가 달라 건너뜀"))
    if tag:
        try:
            im.convert('RGB').save(tag, format='PNG'); done[tag] = f
        except Exception as e:
            print(f"     저장 실패 -> {type(e).__name__}: {e}")

print()
ok = True
for size, tag in TARGET.items():
    try:
        s = Image.open(tag).size
        print(f"  {tag}: {s[0]}x{s[1]}  {'OK' if s == size else '크기 불일치!'}" + (f"  (원본: {done[tag]})" if tag in done else "  (이전에 만든 파일)"))
        ok &= (s == size)
    except Exception:
        print(f"  {tag}: 없음 ({size[0]}x{size[1]} 크기의 스크린샷을 못 찾았습니다)")
        ok = False
if ok:
    print("\n준비 완료. 이제 python real_probe.py 를 실행하세요.")
else:
    print("\n준비가 덜 됐습니다. 위의 '크기가 달라 건너뜀'/'없음' 줄을 그대로 알려주세요.")
    print("(박스는 위 크기 기준으로 쟀기 때문에, 크기가 다른 스크린샷은 박스를 다시 재야 합니다.)")
