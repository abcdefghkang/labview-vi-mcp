# -*- coding: utf-8 -*-
import sys, glob, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image, ImageChops, ImageDraw, ImageFont

BASE = r"C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\work\mcp_render\ats_hmi_v1"
newest = None
for d in sorted(glob.glob(os.path.join(BASE, 'export_*')), key=os.path.getmtime):
    c = glob.glob(os.path.join(d, '*p.png'))
    if c:
        m = max(c, key=os.path.getmtime)
        if newest is None or os.path.getmtime(m) > os.path.getmtime(newest):
            newest = m
print("newest render:", newest)

new = Image.open(newest).convert('RGB')
old = Image.open(r"C:\Users\<you>\AppData\Local\Temp\opencode\prev_before.png").convert('RGB')
H = min(old.height, new.height, 1010)
oldc = old.crop((0, 0, 1520, H))
newc = new.crop((0, 0, 1520, H))

diff = ImageChops.difference(oldc, newc).convert('L')
thr = diff.point(lambda p: 255 if p > 24 else 0)
bw, bh = 16, 16
blocks = []
total = 0
for by in range(0, H, bh):
    for bx in range(0, 1520, bw):
        box = thr.crop((bx, by, min(bx+bw, 1520), min(by+bh, H)))
        n = 0
        for p in box.getdata():
            if p:
                n += 1
        if n:
            total += n
            if n > bw*bh*0.06:
                blocks.append((bx, by))
pct = 100.0 * total / (1520 * H)
print(f"changed pixels: {total}  ({pct:.2f}%)")
print("flagged blocks:", len(blocks))

ov = newc.copy()
dr = ImageDraw.Draw(ov, 'RGBA')
for (bx, by) in blocks:
    dr.rectangle([bx, by, bx+bw-1, by+bh-1], fill=(255, 0, 0, 80))

try:
    f1 = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 26)
    f2 = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 22)
except Exception:
    f1 = f2 = ImageFont.load_default()

S = 0.8
w2, h2 = int(1520*S), int(H*S)
old_s = oldc.resize((w2, h2), Image.LANCZOS)
new_s = ov.resize((w2, h2), Image.LANCZOS)

lab1 = "上一版（你上次看到的预览）"
lab2 = f"新版（本次大改）: 变化像素 {total} 个 = {pct:.1f}%  红色标记 = 变化区域"

canvas = Image.new('RGB', (w2, 40 + h2 + 12 + 40 + h2 + 8), (255, 255, 255))
d = ImageDraw.Draw(canvas)
d.text((10, 6), lab1, fill=(0, 0, 0), font=f1)
canvas.paste(old_s, (0, 40))
y = 40 + h2 + 12
d.text((10, y + 6), lab2, fill=(200, 0, 0), font=f2)
canvas.paste(new_s, (0, y + 40))
out = r"C:\Users\<you>\Documents\默认项目\对比_上一版_vs_新版.png"
canvas.save(out)
print("saved", out, canvas.size)

for p in [r"C:\Users\<you>\Documents\默认项目\试验设备运转测控面板.vi",
          r"C:\Users\<you>\Documents\默认项目\面板预览.png"]:
    if os.path.isfile(p):
        print(os.path.basename(p), "mtime", __import__('datetime').datetime.fromtimestamp(os.path.getmtime(p)).strftime('%m-%d %H:%M:%S'), "size", os.path.getsize(p))
