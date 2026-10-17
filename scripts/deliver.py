# -*- coding: utf-8 -*-
"""把主 VI 和最新渲染复制到用户工作目录"""
import glob, os, shutil, time

MASTER = r'C:\LV_AUTOTEST\gen\ats_hmi_v1.vi'
OUT_VI = r'C:\Users\<you>\Documents\默认项目\试验设备运转测控面板.vi'
OUT_PNG = r'C:\Users\<you>\Documents\默认项目\面板预览.png'
BASE = r'C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\work\mcp_render\ats_hmi_v1'

# 最新渲染
dirs = sorted(glob.glob(os.path.join(BASE, 'export_*')), key=os.path.getmtime, reverse=True)
png = None
for d in dirs:
    c = glob.glob(os.path.join(d, '*p.png'))
    if c:
        png = max(c, key=os.path.getmtime)
        break
print('master:', MASTER, os.path.getsize(MASTER), 'bytes')
print('render:', png)

os.makedirs(os.path.dirname(OUT_VI), exist_ok=True)
shutil.copy2(MASTER, OUT_VI)
shutil.copy2(png, OUT_PNG)
print('copied ->', OUT_VI, os.path.getsize(OUT_VI), 'bytes')
print('copied ->', OUT_PNG, os.path.getsize(OUT_PNG), 'bytes')

from PIL import Image
im = Image.open(OUT_PNG)
print('preview size:', im.size)
