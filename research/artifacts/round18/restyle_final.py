# -*- coding: utf-8 -*-
# 波形图.vi 前面板换肤 最终版 (v7)
import re

BASE = r'C:\Users\heiyashi\WorkBuddy\2026-10-27-16-11-47\hmi_vi\bundle_waveform'
FPHB = BASE + r'\波形图_FPHb.xml'
MAIN = BASE + r'\波形图.xml'

def moj(s):
    return s.encode('gbk').decode('mac_roman')

data = open(FPHB, encoding='utf-8-sig').read()
main = open(MAIN, encoding='utf-8-sig').read()

def find_sub(s, uid, cls='fPDCO'):
    start = s.find('<SL__arrayElement class="%s" uid="%d">' % (cls, uid))
    if start < 0: raise RuntimeError('uid %d not found' % uid)
    depth = 0
    for m in re.finditer(r'<SL__arrayElement\b[^>]*?(/?)>|</SL__arrayElement>', s[start:]):
        tok = m.group(0)
        if tok.endswith('/>'):
            if depth == 0: return start, start + m.end()
            continue
        if tok.startswith('</'):
            depth -= 1
            if depth == 0: return start, start + m.end()
        else:
            depth += 1
    raise RuntimeError('unbalanced uid %d' % uid)

def replace_sub(s, uid, new):
    a, b = find_sub(s, uid)
    return s[:a] + new + s[b:]

BRE = re.compile(r'<bounds>\((-?\d+), (-?\d+), (-?\d+), (-?\d+)\)</bounds>')

def scale_rel(sub, fx, fy):
    cnt = [0]
    def f(m):
        cnt[0] += 1
        if cnt[0] == 1: return m.group(0)
        t, l, b, r = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        return '<bounds>(%d, %d, %d, %d)</bounds>' % (
            round(t * fy), round(l * fx), round(b * fy), round(r * fx))
    return BRE.sub(f, sub)

def set_ddo_bounds(sub, t, l, b, r):
    return BRE.sub('<bounds>(%d, %d, %d, %d)</bounds>' % (t, l, b, r), sub, count=1)

def edit_label_text(sub, txt_moj, which=1):
    cnt = [0]
    def f(m):
        cnt[0] += 1
        if cnt[0] == which: return '<text>"%s"</text>' % txt_moj
        return m.group(0)
    return re.sub(r'<text>"[^"]*"</text>', f, sub)

def set_label_rel(sub, t, l, b, r):
    pat = re.compile(r'(<SL__arrayElement class="label"[^>]*>\s*<objFlags>[^<]*</objFlags>\s*<partID>16</partID>.*?<bounds>)\([^)]*\)(</bounds>)', re.S)
    new, n = pat.subn(lambda m: m.group(1) + '(%d, %d, %d, %d)' % (t, l, b, r) + m.group(2), sub, count=1)
    if not n: print('  WARN label rel miss uid?')
    return new

def repl_bounds(sub, old, new):
    if old in sub: return sub.replace(old, new, 1)
    print('  WARN bounds missing:', old)
    return sub

def recolor_value_parts(sub, fg, bg, opaque=True):
    out = []
    for m in re.finditer(r'<SL__arrayElement class="label"[^>]*>.*?</SL__arrayElement>', sub, re.S):
        seg = m.group(0)
        if '<textRec' in seg and '<partID>16<' not in seg:
            seg = re.sub(r'<fgColor>[0-9A-Fa-f]+</fgColor>', '<fgColor>%s</fgColor>' % fg, seg)
            seg = re.sub(r'<bgColor>[0-9A-Fa-f]+</bgColor>', '<bgColor>%s</bgColor>' % bg, seg)
            if opaque:
                seg = re.sub(r'(<textRec[^>]*>\s*<mode>)\d+(</mode>)', r'\g<1>0\g<2>', seg)
        out.append((m.start(), m.end(), seg))
    for a, b, seg in reversed(out):
        sub = sub[:a] + seg + sub[b:]
    return sub

NAVY = '00003C8C'; DIM = '005A7A9A'; WHITE = '00FFFFFF'
RED = '00C82828'; BLUE = '001858C8'; DARK = '001A1A1A'

# ---------- 1. 剥编号 ----------
data, n = re.subn(r'<text>"\d\d ', '<text>"', data)
print('stripped:', n)

# ---------- 2. 字体 ----------
ftab = main[main.find('<FTAB>'):main.find('</FTAB>')]
main = main.replace(ftab, ftab.replace('Prop2="17"', 'Prop2="12"').replace('Prop6="17"', 'Prop6="12"'))

# ---------- 3. 顶部自由标签 ----------
a, b = find_sub(data, 217)          # 标题: 只清 label, 保留原值文本
seg = data[a:b]
seg = edit_label_text(seg, '')
seg = set_ddo_bounds(seg, 12, 14, 34, 470)
data = replace_sub(data, 217, seg)

for uid, t, l, b2, r in ((229, 16, 548, 38, 720), (241, 12, 1160, 34, 1272)):
    a, b = find_sub(data, uid)
    seg = data[a:b]
    seg = edit_label_text(seg, '')
    seg = recolor_value_parts(seg, NAVY, '01000000', opaque=False)
    seg = set_ddo_bounds(seg, t, l, b2, r)
    data = replace_sub(data, uid, seg)
# (按钮/下拉 253-364 保持原始几何不动)

# ---------- 4. 数据源链路数组 ----------
a, b = find_sub(data, 393)
seg = data[a:b]
seg = edit_label_text(seg, '')
seg = repl_bounds(seg, '<bounds>(19, 41, 76, 255)</bounds>', '<bounds>(19, 41, 80, 203)</bounds>')
seg = repl_bounds(seg, '<bounds>(23, 45, 72, 251)</bounds>', '<bounds>(23, 45, 76, 199)</bounds>')
seg = set_ddo_bounds(seg, 118, 12, 204, 220)
data = replace_sub(data, 393, seg)

# ---------- 5. 波形图: 缩放 + 白底浅网格 ----------
a, b = find_sub(data, 550)
seg = data[a:b]
seg = edit_label_text(seg, '')
seg = seg.replace('<bgColor>001E4B00</bgColor>', '<bgColor>00FFFFFF</bgColor>')
seg = seg.replace('<fgColor>001E4B00</fgColor>', '<fgColor>00B8B8B8</fgColor>')
seg = seg.replace('<BGColor>001E4B00</BGColor>', '<BGColor>00FFFFFF</BGColor>')
seg = seg.replace('<FGColor>001E4B00</FGColor>', '<FGColor>00B8B8B8</FGColor>')
seg = seg.replace('<gridMaxColor>00006600</gridMaxColor>', '<gridMaxColor>00C8C8C8</gridMaxColor>')
seg = seg.replace('<gridMinColor>00003300</gridMinColor>', '<gridMinColor>00E8E8E8</gridMinColor>')
seg = scale_rel(seg, 790/724.0, 564/590.0)
seg = set_ddo_bounds(seg, 114, 244, 678, 1034)
data = replace_sub(data, 550, seg)

# ---------- 6. 通道图例数组 ----------
a, b = find_sub(data, 581)
seg = data[a:b]
seg = edit_label_text(seg, '')
seg = repl_bounds(seg, '<bounds>(19, 41, 76, 255)</bounds>', '<bounds>(19, 41, 290, 205)</bounds>')
seg = repl_bounds(seg, '<bounds>(23, 45, 72, 251)</bounds>', '<bounds>(23, 45, 286, 201)</bounds>')
seg = repl_bounds(seg, '<bounds>(56, 45, 72, 239)</bounds>', '<bounds>(280, 45, 296, 205)</bounds>')
seg = repl_bounds(seg, '<bounds>(23, 239, 72, 255)</bounds>', '<bounds>(23, 189, 290, 205)</bounds>')
seg = repl_bounds(seg, '<bounds>(56, 239, 72, 255)</bounds>', '<bounds>(280, 189, 296, 205)</bounds>')
seg = set_ddo_bounds(seg, 116, 1058, 414, 1268)
data = replace_sub(data, 581, seg)

# ---------- 7. 采集状态数值 ----------
for uid, y in ((593, 460), (605, 482), (618, 504), (631, 526)):
    a, b = find_sub(data, uid)
    seg = data[a:b]
    seg = scale_rel(seg, 116/132.0, 20/36.0)
    seg = set_label_rel(seg, 3, -68, 19, -4)
    seg = recolor_value_parts(seg, NAVY, WHITE, opaque=True)
    seg = set_ddo_bounds(seg, y, 1152, y + 20, 1268)
    data = replace_sub(data, uid, seg)

# ---------- 8. LED ----------
for uid, y, txt, lr in ((641, 566, 'TCP 链路', 110), (651, 590, 'OPC 链路', 110),
                        (661, 614, 'CAN 链路', 110), (671, 638, 'ARINC429 链路', 130),
                        (681, 662, None, 110)):
    a, b = find_sub(data, uid)
    seg = data[a:b]
    seg = edit_label_text(seg, '' if txt is None else moj(txt))
    seg = set_label_rel(seg, 2, 24, 18, lr)
    seg = set_ddo_bounds(seg, y, 1058, y + 20, 1078)
    data = replace_sub(data, uid, seg)

# ---------- 9. 游标状态文本 ----------
a, b = find_sub(data, 693)
seg = data[a:b]
seg = edit_label_text(seg, '')
seg = recolor_value_parts(seg, DARK, '01000000', opaque=False)
seg = scale_rel(seg, 188/264.0, 24/40.0)
seg = set_ddo_bounds(seg, 662, 1084, 686, 1272)
data = replace_sub(data, 693, seg)

# ---------- 10. 游标测量行 ----------
for uid, l, r, fx, fg in ((705, 14, 170, 156/192.0, RED), (717, 178, 368, 190/192.0, BLUE),
                          (729, 376, 500, 124/116.0, RED), (741, 508, 880, 372/374.0, BLUE),
                          (753, 940, 1272, 332/364.0, DIM)):
    a, b = find_sub(data, uid)
    seg = data[a:b]
    seg = edit_label_text(seg, '')
    bg = '01000000' if uid == 753 else WHITE
    seg = recolor_value_parts(seg, fg, bg, opaque=(uid != 753))
    seg = scale_rel(seg, fx, 24/40.0)
    seg = set_ddo_bounds(seg, 700, l, 724, r)
    data = replace_sub(data, uid, seg)

# ---------- 11. 状态栏 (加宽值框) ----------
for uid, l, r, fx, txt, ll in ((765, 48, 206, 158/162.0, '链路', -34),
                               (777, 260, 380, 120/172.0, '采样率', -50),
                               (789, 418, 508, 90/122.0, '窗口', -34),
                               (801, 546, 696, 150/162.0, '视图', -34),
                               (813, 734, 794, 60/82.0, '通道', -34),
                               (825, 1150, 1272, 122/132.0, '运行时长', -58)):
    a, b = find_sub(data, uid)
    seg = data[a:b]
    seg = edit_label_text(seg, moj(txt))
    seg = set_label_rel(seg, 4, ll, 22, -4)
    seg = recolor_value_parts(seg, NAVY, WHITE, opaque=True)
    seg = scale_rel(seg, fx, 26/40.0)
    seg = set_ddo_bounds(seg, 738, l, 764, r)
    data = replace_sub(data, uid, seg)

# ---------- 12. 面板底色 ----------
data = data.replace('<fgColor>00E2E2E2</fgColor>\n          <bgColor>00E2E2E2</bgColor>',
                    '<fgColor>00E0E0E0</fgColor>\n          <bgColor>00E0E0E0</bgColor>', 1)

open(FPHB, 'w', encoding='utf-8-sig').write(data)
open(MAIN, 'w', encoding='utf-8-sig').write(main)

# 自检
parts = re.split(r'(<!\[CDATA\[.*?\]\]>)', data, flags=re.S)
stack = []; ok = True
tok = re.compile(r'<(/?)([\w:]+)[^>]*?(/?)>')
for p in parts:
    if p.startswith('<![CDATA['): continue
    for mm in tok.finditer(p):
        cl, nm, sc = mm.groups()
        if sc: continue
        if cl:
            if stack and stack[-1] == nm: stack.pop()
            else: print('SELFCHECK MISMATCH:', nm, stack[-3:]); ok = False; break
        else: stack.append(nm)
    if not ok: break
print('SELFCHECK:', 'OK' if ok and not stack else 'FAIL')
print('SAVED')
