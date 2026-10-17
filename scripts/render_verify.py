# -*- coding: utf-8 -*-
"""渲染核验三件套：找最新渲染 / 裁剪放大 / 像素取色

用法（先设 PYTHONIOENCODING=utf-8）:
  python render_verify.py                              # 列出最新渲染路径与尺寸
  python render_verify.py crop x0 y0 x1 y1 [放大倍数]   # 裁剪保存（默认 3 倍）
  python render_verify.py pixel x y                    # 取色（输出 hex 与 0x00RRGGBB 十进制）

把 BASE 改成自己的渲染目录。
"""
import sys, os, glob
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image

BASE = r"C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\work\mcp_render\ats_hmi_v1"
OUT = r"C:\Users\<you>\AppData\Local\Temp\opencode"


def newest_render():
    best = None
    for d in sorted(glob.glob(os.path.join(BASE, 'export_*')), key=os.path.getmtime):
        for f in glob.glob(os.path.join(d, '*p.png')):
            if best is None or os.path.getmtime(f) > os.path.getmtime(best):
                best = f
    return best


def main():
    args = sys.argv[1:]
    path = newest_render()
    if not path:
        print('没找到渲染 PNG，请检查 BASE:', BASE)
        return
    im = Image.open(path).convert('RGB')
    if not args:
        print('最新渲染:', path, im.size)
        return
    cmd = args[0]
    if cmd == 'crop' and len(args) >= 5:
        x0, y0, x1, y1 = map(int, args[1:5])
        s = float(args[5]) if len(args) > 5 else 3.0
        c = im.crop((x0, y0, x1, y1))
        c = c.resize((int(c.width * s), int(c.height * s)), Image.LANCZOS)
        out = os.path.join(OUT, f'crop_{x0}_{y0}_{x1}_{y1}.png')
        c.save(out)
        print('保存:', out, c.size)
    elif cmd == 'pixel' and len(args) >= 3:
        x, y = int(args[1]), int(args[2])
        r, g, b = im.getpixel((x, y))
        print(f'({x},{y}) = #{r:02X}{g:02X}{b:02X} -> 0x00RRGGBB 十进制 = {r * 65536 + g * 256 + b}')
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
