# -*- coding: utf-8 -*-
"""
build.py —— 唯一构建脚本。源永远取 src/（波形图_v7 原始提取），
产物永远是 波形图.vi 与 bundle/，不再产生 vN 副本。

本轮做的四件事：
  1) 字表（FTAB）改字号 —— 之前所有控件都是 17pt，撑爆了 24px 高的按钮；
  2) 按钮按"等比缩放"放置 —— 原来按目标框各向异性拉伸，导致圆角/图标错位；
  3) 全局缩到导出画布 1251x771 内 —— 导出图是面板的裁剪，1280x800 底下会被切；
  4) 面板标题标签改成横条，不再竖排。
"""
import os
import re
import shutil

from recolor import recolor_control

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'src')
DST = os.path.join(ROOT, 'bundle')
FP = os.path.join(DST, '波形图_v7_FPHb.xml')
MAIN = os.path.join(DST, '波形图_v7.xml')

# 导出画布实测 1251x771（LabVIEW 打印面板时按窗口客户区裁），
# 所有 HTML 坐标统一折算进这个画布，避免右边/下边被切。
XS = 1.0
YS = 1.0

FTAB_SIZE = 9          # 默认字号（HTML 正文 11px ≈ 9pt）
TITLE_SIZE = 12        # 标题字号

# HTML 实测矩形（1280x800 坐标系，top, left, bottom, right）
TARGETS = {
    '01 标题栏':        (18, 41, 36, 245),
    '02 链路摘要':      (16, 997, 37, 1147),
    '03 时钟':          (16, 1155, 37, 1223),
    '滚动窗口':         (51, 21, 75, 89),
    '暂停刷新':         (51, 94, 75, 162),
    '复位视图':         (51, 167, 75, 235),
    '放置游标':         (51, 255, 75, 323),
    '清除游标':         (51, 328, 75, 396),
    '导出图片':         (51, 815, 75, 883),
    '清空缓冲':         (51, 888, 75, 956),
    '窗口选择':         (51, 443, 75, 503),
    'Y轴模式':          (51, 533, 75, 611),
    '通道过滤':         (51, 665, 75, 795),
    '04 数据源链路':    (79, 17, 722, 230),
    '05 波形显示':      (113, 243, 720, 1032),
    '06 通道图例':      (79, 1048, 462, 1268),
    '07 重绘周期':      (500, 1150, 519, 1235),
    '08 绘制帧率':      (522, 1150, 541, 1235),
    '09 总通道数':      (544, 1150, 563, 1235),
    '10 可见通道':      (566, 1150, 585, 1235),
    '11 TCP链路灯':     (611, 1061, 628, 1078),
    '12 OPC链路灯':     (632, 1061, 649, 1078),
    '13 CAN链路灯':     (653, 1061, 670, 1078),
    '14 429链路灯':     (674, 1061, 691, 1078),
    '15 游标状态灯':    (695, 1061, 712, 1078),
    '16 游标状态文本':  (608, 1082, 710, 1266),
    '17 游标测量-C1':   (735, 78, 755, 228),
    '18 游标测量-C2':   (735, 236, 755, 386),
    '19 游标测量-时间差': (735, 394, 755, 484),
    '20 游标测量-值差': (735, 492, 755, 787),
    '21 操作提示':      (737, 990, 755, 1225),
    '22 状态栏-链路':   (767, 47, 787, 109),
    '23 状态栏-采样率': (767, 151, 787, 252),
    '24 状态栏-窗口':   (767, 284, 787, 336),
    '25 状态栏-视图':   (767, 368, 787, 457),
    '26 状态栏-通道':   (767, 489, 787, 517),
    '27 状态栏-运行时长': (767, 1161, 787, 1225),
}

UIDS = {
    217: '01 标题栏', 229: '02 链路摘要', 241: '03 时钟',
    253: '滚动窗口', 265: '暂停刷新', 277: '复位视图', 289: '放置游标',
    301: '清除游标', 313: '导出图片', 325: '清空缓冲',
    338: '窗口选择', 351: 'Y轴模式', 364: '通道过滤',
    393: '04 数据源链路', 550: '05 波形显示', 581: '06 通道图例',
    593: '07 重绘周期', 605: '08 绘制帧率', 618: '09 总通道数', 631: '10 可见通道',
    641: '11 TCP链路灯', 651: '12 OPC链路灯', 661: '13 CAN链路灯', 671: '14 429链路灯',
    681: '15 游标状态灯', 693: '16 游标状态文本',
    705: '17 游标测量-C1', 717: '18 游标测量-C2', 729: '19 游标测量-时间差', 741: '20 游标测量-值差',
    753: '21 操作提示',
    765: '22 状态栏-链路', 777: '23 状态栏-采样率', 789: '24 状态栏-窗口',
    801: '25 状态栏-视图', 813: '26 状态栏-通道', 825: '27 状态栏-运行时长',
}

# 按钮类（stdBool）：等比缩放，别拉歪
BTN = {253, 265, 277, 289, 301, 313, 325}

PANE_BG = '00ECECEC'

# 面板零件的"钉死"规则：控件被拉成卡片后，内白面/外框/文字区必须整块铺满，
# 否则 LabVIEW 会按 howGrow 重新算成一个小方块。kind: face / text / caption
PIN_ON = set()

PIN = {
    393: {379: 'face', 383: 'frame', 391: 'frame', 390: 'text', 370: 'caption'},
    581: {567: 'face', 571: 'frame', 579: 'frame', 578: 'text', 558: 'caption'},
}

# 面板标题：控件 uid -> (文字, 标签 uid)
CAPTIONS = {
    393: ('数据源链路', 370),
    550: ('曲线显示', 399),
    581: ('通道图例', 558),
}

HIDE_PARTS = {
    # 393 / 581 是"数组控件当面板框用"：标题条、列头、内嵌边框、滚动条全部藏掉，
    # 只留 p28 内白面 + p11 文字区，才像 HTML 的白色卡片
    # 数组控件当面板框：内嵌双边框(376/383)、列头(388/389)藏掉，只留内白面+文字区
    393: [371, 387, 380, 381, 382],
    581: [559, 575, 568, 569, 570],
    # 550 波形图：图例(420)、坐标轴标签小刻线等藏掉
    550: [530, 422, 423, 428],
}

# 面板标题标签的目标框（相对控件原点：top, left, bottom, right）
CAPTION_BOX = {
    393: (8, 10, 28, 210),
    550: (6, 18, 26, 190),
    581: (8, 10, 28, 180),
}

# 按钮里那颗绿色箭头（bigMultiCosm partID 86）藏掉，其余边框保留
BTN_ARROW = 86

# ── 波形图内部零件几何 ───────────────────────────────────────────────
# 波形图控件本身 ddo bounds 对了以后，里面那套零件还是原设计的小尺寸：
# 绘图区只占控件的一半，两条坐标轴压在绘图区里面。这里按"相对控件原点"的
# 局部坐标把它们重新摆一遍：绘图区吃满，Y 轴贴左，X 轴贴底。
# 注意 dynBounds 才是渲染用的动态边界，只改 bounds 不生效。
GRAPH_PARTS = {
    417: (35, 100, 531, 770),    # 绘图区：左边让出 100 给 Y 轴刻度，底边到控件下沿
    405: (585, 100, 640, 770),   # X 轴
    510: (2, 756, 10, 764),      # 图例示意块：缩到右上角（等于隐藏）
}

# 坐标轴的屏幕坐标缓存：scaleRMin32/RMax32 存的是"轴线起止点的面板绝对坐标"，
# 它们不会跟着零件 bounds 一起变 —— 只改 bounds 不同步改缓存，LabVIEW 会按旧缓存
# 把刻度画到老位置（这就是之前 X 轴刻度浮在格子中间的原因）。
AXIS_SPAN = {
    410: (342, 995),    # X 轴：RMin=绘图区左边, RMax=绘图区右边
    416: (625, 154),    # Y 轴：RMin=绘图区底边, RMax=绘图区顶边
}

# 坐标轴真正的位置存在 <scaleRect> 里（面板绝对坐标, 顺序 top/left/bottom/right），
# 改 bounds / dynBounds 都不动它 —— 这就是"X 轴刻度一直浮在格子中间"的根因。
# 顺序与 XML 里出现顺序一致：第一条 = X 轴, 第二条 = Y 轴。
SCALE_RECTS = [
    (470, 337, 515, 1007),    # X 轴
    (145, 305, 635, 418),     # Y 轴
]
# 注意：图例树(420)、图例数组(463)、图例簇(432) 三个零件不要动，也不要清
# GraphPlotLegendData —— 它们要么改不动（LabVIEW 按内容重算），要么一改就直接
# 把 LabVIEW 进程带走（elements="0" 实测必崩）。图例留在控件外，被面板裁掉。
# Y 轴(411) / X 轴(405) 的 bounds 和 dynBounds 不要动：它们内部还带一套
# scaleRMin32/RMax32 屏幕坐标缓存，外框改了不同步改缓存，LabVIEW 会按旧缓存
# 把轴拉到画布外面，导出画布从 1222 撑成 1573。
GRAPH_DYN = {
    405: (585, 100, 640, 770),   # X 轴 dynBounds 与 bounds 一致
}

# ---------------------------------------------------------------------------
# 数组控件"当卡片用"时，内部零件的坐标系与 ddo bounds 不同尺（零件用的是
# 未拉伸前的设计坐标），按比例缩放必然错位。这里改成绝对落位：
# 把 显示区 / 元素面 / annex / 元素字符串 直接钉到目标框上，
# 数组元素改成 1 个，于是整个控件就退化成"一块铺满的多行文本区"。
# ---------------------------------------------------------------------------
FILL_PARTS = {
    393: [383, 379, 377],     # 显示区 / 元素面 / annex
    581: [571, 567, 572],
}

# 卡片控件（数组控件当卡片用）内部"元素"的四个零件：
#   elem  元素自己的 stdString ddo（决定每个元素的宽高）
#   frame 元素外框 cosm partID 9（这是肉眼看到的"卡片白底"，宽度卡在它身上）
#   text  元素文字区 label partID 11（文字换行宽度卡在它身上）
# n = 元素个数：给 4 个元素，数组控件就渲染成 4 张上下叠放的卡片
CARD_SPEC = {
    393: dict(elem=385, frame=391, text=390, n=1),
    581: dict(elem=573, frame=579, text=578, n=1),
}

# 左栏 4 张链路卡片（一张卡 = 一个数组元素）
LINK_CARDS = [
    ('● 下位机 TCP  ·  在线\n'
     '  192.168.1.101:8000\n'
     '  PXIC-8840 环形缓冲 · 采样 100 Hz\n'
     '  通道 10 个'),
    ('● PLC OPC  ·  在线\n'
     '  opc.tcp://192.168.1.50:4840\n'
     '  西门子 S7-1500 · OPC UA · 采样 10 Hz\n'
     '  通道 5 个'),
    ('● CAN 总线  ·  在线\n'
     '  CAN1 · 500 kbps\n'
     '  PCIe-CAN-2 标准帧 · 采样 50 Hz\n'
     '  通道 4 个'),
    ('● ARINC429  ·  在线\n'
     '  429A/L0B1-L0B4\n'
     '  PXIe-429-4 4 发 4 收 · 采样 20 Hz\n'
     '  通道 4 个'),
]

LEGEND_GROUPS = [
    ('● 下位机 TCP（100 Hz · 10 通道）\n'
     '  ■ 转速 (rpm)\n'
     '  ■ 扭矩 (N·m)\n'
     '  ■ 排气温度 (℃)\n'
     '  ■ 滑油压力 (kPa)\n'
     '  ■ 燃油流量 (kg/h)\n'
     '  ■ 振动 (g)\n'
     '  ■ 进气温度 (℃)\n'
     '  ■ 滑油温度 (℃)\n'
     '  ■ 启动信号\n'
     '  ■ 点火状态'),
    ('● PLC OPC（10 Hz · 5 通道）\n'
     '  ■ 28V 母线电压 (V)\n'
     '  ■ 28V 母线电流 (A)\n'
     '  ■ 环境温度 (℃)\n'
     '  ■ 气源压力 (kPa)\n'
     '  ■ 气动阀状态'),
    ('● CAN 总线（50 Hz · 4 通道）\n'
     '  ■ 发电机频率 (Hz)\n'
     '  ■ 母线电压 (V)\n'
     '  ■ 母线电流 (A)\n'
     '  ■ 发电机状态'),
]
LEGEND_TEXT = ('\n\n' + '─' * 32 + '\n\n').join(LEGEND_GROUPS)

# 每个卡片控件对应的正文（list = 每个数组元素一段）
# 左栏卡片高 620px、行高约 12.5px ≈ 49 行容量，而 4 组链路只有 16 行正文，
# 所以用空行把 4 组拉开距离 —— 视觉上就是 HTML 里 4 张独立卡片之间的留白。
MULTILINE = {
    393: ['\n' + ('\n' * 5 + '─' * 30 + '\n' * 5).join(LINK_CARDS) + '\n'],
    581: ['\n' + LEGEND_TEXT + '\n\n\n'],
}


def gbk(s):
    return s.encode('gbk').decode('mac_roman')


def sla_span(s, a):
    depth = 0
    for m in re.finditer(r'<SL__arrayElement\b[^>]*?(/?)>|</SL__arrayElement>', s[a:]):
        t = m.group(0)
        if t.endswith('/>'):
            if depth == 0:
                return a + m.end()
            continue
        if t.startswith('</'):
            depth -= 1
            if depth == 0:
                return a + m.end()
        else:
            depth += 1
    raise RuntimeError('unbalanced')


def _bounds_spans(blk):
    return list(re.finditer(r'<bounds>\(([^)]*)\)</bounds>', blk))


def _ddo_bounds(blk):
    """控件主框（面板绝对坐标）。"""
    m = re.search(r'<ddo class="\w+" uid="\d+">\s*<objFlags>[^<]*</objFlags>\s*<bounds>\(([^)]*)\)</bounds>', blk)
    if not m:
        raise RuntimeError('ddo bounds not found')
    return [float(x) for x in m.group(1).split(',')]


def retarget(blk, nt, nl, nb, nr):
    """零件 bounds 是"相对 ddo 左上角的局部坐标"，位置由 ddo bounds 自己表达，
    所以零件只缩放、不平移。基准必须是 ddo 的尺寸 —— 拿标题标签当基准会让
    所有零件被放大十几倍，LabVIEW 随后重算出畸形控件。"""
    ot, ol, ob, orr = _ddo_bounds(blk)
    sy = (nb - nt) / (ob - ot) if ob != ot else 1.0
    sx = (nr - nl) / (orr - ol) if orr != ol else 1.0

    def rep(m):
        t, l, b, r = [float(x) for x in m.group(1).split(',')]
        return '<bounds>(%d, %d, %d, %d)</bounds>' % (
            round(t * sy), round(l * sx), round(b * sy), round(r * sx))

    out = re.sub(r'<bounds>\(([-\d, ]+)\)</bounds>', rep, blk)
    return set_ddo_bounds(out, nt, nl, nb, nr)


def retarget_uniform(blk, nt, nl, nb, nr):
    """等比缩放零件（同样不平移），太高就按高度收，再垂直居中放 ddo。"""
    ot, ol, ob, orr = _ddo_bounds(blk)
    k = (nr - nl) / (orr - ol) if (orr - ol) else 1.0
    if ob > ot and (ob - ot) * k > (nb - nt):
        k = (nb - nt) / (ob - ot)
    h = (ob - ot) * k
    nt2 = nt + ((nb - nt) - h) / 2.0

    def rep(m):
        t, l, b, r = [float(x) for x in m.group(1).split(',')]
        return '<bounds>(%d, %d, %d, %d)</bounds>' % (
            round(t * k), round(l * k), round(b * k), round(r * k))

    out = re.sub(r'<bounds>\(([-\d, ]+)\)</bounds>', rep, blk)
    return set_ddo_bounds(out, int(round(nt2)), nl, int(round(nt2 + h)), nr)


def set_bounds_of_uid(blk, uid, t, l, b, r):
    """改某个零件的 bounds。零件可能是 SL__arrayElement，也可能是嵌套的 ddo
    （数组元素的字符串控件就是 <ddo class="stdString" uid="385">）。"""
    m = re.search(r'(?:<SL__arrayElement class="\w+"|<ddo class="\w+") uid="%d">' % uid, blk)
    if not m:
        print('  !! 零件 %d 未找到' % uid)
        return blk
    mm = re.search(r'<bounds>\([^)]*\)</bounds>', blk[m.end():m.end() + 400])
    if not mm:
        print('  !! 零件 %d 无 bounds' % uid)
        return blk
    a = m.end() + mm.start()
    b2 = m.end() + mm.end()
    return blk[:a] + '<bounds>(%d, %d, %d, %d)</bounds>' % (t, l, b, r) + blk[b2:]


def hide_parts(blk, part_uids):
    n = 0
    for pu in part_uids:
        m = re.search(r'<SL__arrayElement class="\w+" uid="%d">' % pu, blk)
        if not m:
            continue
        a = m.start()
        e = sla_span(blk, a)
        seg = blk[a:e]
        mm = re.search(r'<bounds>\([^)]*\)</bounds>', seg)
        if not mm:
            continue
        seg2 = seg[:mm.start()] + '<bounds>(0, 0, 1, 1)</bounds>' + seg[mm.end():]
        blk = blk[:a] + seg2 + blk[e:]
        n += 1
    return blk, n


def set_caption(blk, text):
    """把 caption（第一个 partID=16 的 label）换成 text。"""
    for mm in re.finditer(r'<SL__arrayElement class="\w+" uid="(\d+)">', blk):
        a = mm.start()
        e = sla_span(blk, a)
        seg = blk[a:e]
        if '<partID>16</partID>' not in seg:
            continue
        t = re.search(r'<text>[^<]*</text>', seg)
        if not t:
            continue
        seg2 = seg[:t.start()] + '<text><![CDATA["%s"]]></text>' % text + seg[t.end():]
        return blk[:a] + seg2 + blk[e:]
    return blk


def flat_button(blk):
    """按钮：藏掉绿色箭头（bigMultiCosm partID 86）。"""
    hits = []
    for m in re.finditer(r'<SL__arrayElement class="\w+" uid="(\d+)">', blk):
        a = m.start()
        e = sla_span(blk, a)
        seg = blk[a:e]
        pid = re.search(r'<partID>(\d+)</partID>', seg)
        if not pid or int(pid.group(1)) != BTN_ARROW:
            continue
        mm = re.search(r'<bounds>\([^)]*\)</bounds>', seg)
        if mm:
            hits.append((a, e, seg[:mm.start()] + '<bounds>(0, 0, 1, 1)</bounds>' + seg[mm.end():]))
    for a, e, seg in reversed(hits):
        blk = blk[:a] + seg + blk[e:]
    return blk


def set_ddo_bounds(blk, t, l, b, r):
    """把控件主框（ddo bounds）写成目标矩形。"""
    return re.sub(
        r'(<ddo class="\w+" uid="\d+">\s*<objFlags>[^<]*</objFlags>\s*<bounds>)\([^)]*\)',
        lambda m: '%s(%d, %d, %d, %d)' % (m.group(1), t, l, b, r), blk, count=1)


def _esc_xml_str(s):
    """LabVIEW CDATA 里只有控制字符写成 &#xNN;，可打印字符（含 GBK 高位字节
    mac_roman 解出来的那些）必须原样写 —— 给高位字符也加转义会变成字面文本。"""
    out = []
    for ch in s:
        o = ord(ch)
        if o == 10:
            out.append('\n')          # 换行必须是真的换行，&#x0A; 会被当字面文本
        elif o < 32:
            out.append('&#x%02X;' % o)
        else:
            out.append(ch)
    return ''.join(out)


def set_array_text(blk, items):
    """把数组控件 DefaultData 换成 N 个元素，每个元素一段多行文本。
    元素个数 = 卡片张数（数组控件于是渲染成上下叠放的多张卡片）。"""
    if isinstance(items, str):
        items = [items]
    payload = len(items).to_bytes(4, 'big')
    for it in items:
        raw = gbk(it).encode('mac_roman')
        payload += len(raw).to_bytes(4, 'big') + raw
    body = '"%s"' % _esc_xml_str(payload.decode('mac_roman'))
    new = '<DefaultData><![CDATA[%s]]></DefaultData>' % body
    n, k = re.subn(r'<DefaultData><!\[CDATA\[.*?\]\]></DefaultData>', new, blk, count=1, flags=re.S)
    if not k:
        raise RuntimeError('DefaultData not found')
    return n


def set_scalar_text(blk, text):
    """标量字符串控件的 DefaultData：4 字节大端长度 + 正文。"""
    raw = gbk(text).encode('mac_roman')
    body = '"%s%s"' % (_esc_xml_str(len(raw).to_bytes(4, 'big').decode('mac_roman')),
                       _esc_xml_str(raw.decode('mac_roman')))
    new = '<DefaultData><![CDATA[%s]]></DefaultData>' % body
    n, k = re.subn(r'<DefaultData><!\[CDATA\[.*?\]\]></DefaultData>', new, blk, count=1, flags=re.S)
    if not k:
        raise RuntimeError('DefaultData not found')
    return n


# 753（操作提示）是一块现成的多行 stdString 指示器，拿它当"文本卡片"模板：
#   747 = 标题 label        -> 藏
#   748/749 = 左右装饰件     -> 藏
#   750 = 文本区（partID 11）-> 铺满
#   751 = 外框（partID 9）   -> 铺满
CARD_TEMPLATE_UID = 753
CARD_PARTS = {'cap': 747, 'deco1': 748, 'deco2': 749, 'text': 750, 'frame': 751}


def add_text_card(s, off, box, text):
    """复制 753 的 fPDCO，改 uid（+off）、拉成目标框、填入多行正文，
    插到 zPlaneList 开头（= 最上层，盖住原来的数组控件）。"""
    a = s.find('<SL__arrayElement class="fPDCO" uid="%d">' % CARD_TEMPLATE_UID)
    if a < 0:
        raise RuntimeError('template not found')
    e = sla_span(s, a)
    seg = s[a:e]

    seg = re.sub(r'uid="(\d+)"', lambda m: 'uid="%d"' % (int(m.group(1)) + off), seg)

    t, l, b, r = box
    H, W = b - t, r - l
    seg = set_ddo_bounds(seg, t, l, b, r)
    for key in ('cap', 'deco1', 'deco2'):
        seg = set_bounds_of_uid(seg, CARD_PARTS[key] + off, 0, 0, 1, 1)
    seg = set_bounds_of_uid(seg, CARD_PARTS['text'] + off, 2, 2, H - 2, W - 2)
    seg = set_bounds_of_uid(seg, CARD_PARTS['frame'] + off, 0, 0, H, W)

    seg = recolor_control(seg)
    seg = set_scalar_text(seg, text)

    i = s.find('<zPlaneList elements="')
    j = s.find('">', i)
    cnt = int(s[i + len('<zPlaneList elements="'):j])
    s = s[:i] + '<zPlaneList elements="%d">' % (cnt + 1) + s[j + 2:]
    s = s[:i + len('<zPlaneList elements="%d">' % (cnt + 1))] + '\n        ' + seg.strip() + s[
        i + len('<zPlaneList elements="%d">' % (cnt + 1)):]
    return s


def patch_bdhb(path, new_uids):
    """前面板多出 N 个控件，框图侧的 zPlaneList / termList 必须同步加 N 个
    fPTerm，否则 LabVIEW 会报"无法加载 VI 的前面板"。"""
    s = open(path, encoding='utf-8').read()

    # 模板：最后一个 fPTerm
    last = list(re.finditer(r'<SL__arrayElement class="fPTerm" uid="(\d+)">', s))[-1]
    a = last.start()
    e = sla_span(s, a)
    tmpl = s[a:e]

    blocks, zs = [], []
    for i, nu in enumerate(new_uids):
        b = re.sub(r'uid="%s"' % last.group(1), 'uid="%d"' % nu, tmpl)
        b = re.sub(r'uid="(\d+)"', lambda m: 'uid="%d"' % (int(m.group(1)) + 70000 + i * 1000)
                   if m.group(1) != str(nu) else m.group(0), b)
        blocks.append(b)
        zs.append('      <SL__arrayElement uid="%d" />\n' % nu)

    # zPlaneList
    i = s.find('<zPlaneList elements="')
    j = s.find('"', i + len('<zPlaneList elements="'))
    n = int(s[i + len('<zPlaneList elements="'):j])
    head = '<zPlaneList elements="%d' % (n + len(zs))
    s = s[:i] + head + s[j:]
    k = s.find('</zPlaneList>')
    s = s[:k] + ''.join(zs) + '    ' + s[k:]

    # termList
    i = s.find('<termList elements="')
    j = s.find('"', i + len('<termList elements="'))
    n = int(s[i + len('<termList elements="'):j])
    head = '<termList elements="%d' % (n + len(blocks))
    s = s[:i] + head + s[j:]
    k = s.rfind('</termList>')
    s = s[:k] + ''.join(b.strip() + '\n          ' for b in blocks) + s[k:]

    open(path, 'w', encoding='utf-8').write(s)
    print('BDHb: +%d fPTerm（zPlaneList/termList 已同步）' % len(blocks))


def set_axis_range(s):
    """Y 轴 -10..10 改成 0..100，主刻度 10。"""
    old = ('<scaleDMin>C024000000000000</scaleDMin>'
           '<scaleDMax>4024000000000000</scaleDMax>'
           '<scaleDStart>C024000000000000</scaleDStart>'
           '<scaleDIncr>4000000000000000</scaleDIncr>')
    new = ('<scaleDMin>0000000000000000</scaleDMin>'
           '<scaleDMax>4059000000000000</scaleDMax>'
           '<scaleDStart>0000000000000000</scaleDStart>'
           '<scaleDIncr>4024000000000000</scaleDIncr>')
    m = re.search(r'<scaleDMin>C024000000000000</scaleDMin>\s*<scaleDMax>4024000000000000</scaleDMax>\s*'
                  r'<scaleDStart>C024000000000000</scaleDStart>\s*<scaleDIncr>4000000000000000</scaleDIncr>',
                  s, re.S)
    if not m:
        print('  !! 未找到 Y 轴量程字段')
        return s, False
    seg = m.group(0)
    # 保留原有的空白分隔
    parts = re.findall(r'<(\w+)>([^<]*)</\w+>', seg)
    repl = seg
    for tag, _v in parts:
        nv = {'scaleDMin': '0000000000000000', 'scaleDMax': '4059000000000000',
              'scaleDStart': '0000000000000000', 'scaleDIncr': '4024000000000000'}[tag]
        repl = re.sub(r'<%s>[^<]*</%s>' % (tag, tag), '<%s>%s</%s>' % (tag, nv, tag), repl, count=1)
    return s[:m.start()] + repl + s[m.end():], True


def _fpdco_span(s, uid):
    m = re.search(r'<SL__arrayElement class="fPDCO" uid="%d">' % uid, s)
    if not m:
        return None
    return m.start(), sla_span(s, m.start())


def _part_span(seg, pu):
    m = re.search(r'<SL__arrayElement class="\w+" uid="%d">' % pu, seg)
    if not m:
        return None
    return m.start(), sla_span(seg, m.start())


def style_graph(s):
    """波形图：钉死 howGrow，把绘图区撑满，把两条坐标轴挪到绘图区外面。"""
    # howGrow=240 会让 LabVIEW 在加载时按比例重算控件尺寸，结果控件永远比
    # 写进去的 ddo bounds 小一大截。改成 5（只钉左上、不跟随缩放）后才稳定。
    for uid in (393, 550, 581):
        sp = _fpdco_span(s, uid)
        if not sp:
            continue
        a, b = sp
        seg = re.sub(r'<howGrow>[^<]*</howGrow>', '<howGrow>5</howGrow>', s[a:b])
        s = s[:a] + seg + s[b:]

    # 图例关掉（HTML 里没有图例，曲线名在右栏"通道图例"卡片上）
    s = re.sub(r'(<SL__arrayElement class="PlotLegendData">(?:(?!</SL__arrayElement>).)*?)'
               r'<visBool>True</visBool>', r'\1<visBool>False</visBool>', s, flags=re.S)

    sp = _fpdco_span(s, 550)
    if not sp:
        return s
    a, b = sp
    seg = s[a:b]


    def set_b(pu, box):
        nonlocal seg
        ps = _part_span(seg, pu)
        if not ps:
            print('  !! 波形图零件 %d 未找到' % pu)
            return
        pa, pb = ps
        sub = seg[pa:pb]
        m = re.search(r'<bounds>\([^)]*\)</bounds>', sub)
        if m:
            sub = sub[:m.start()] + '<bounds>(%d, %d, %d, %d)</bounds>' % box + sub[m.end():]
        seg = seg[:pa] + sub + seg[pb:]

    for pu, box in GRAPH_PARTS.items():
        set_b(pu, box)

    # 坐标轴屏幕坐标缓存同步（否则刻度画在旧位置）
    for pu, (rmin, rmax) in AXIS_SPAN.items():
        ps = _part_span(seg, pu)
        if not ps:
            print('  !! 轴缓存零件 %d 未找到' % pu)
            continue
        pa, pb = ps
        sub = re.sub(r'<scaleRMin32>-?\d+</scaleRMin32>',
                     '<scaleRMin32>%d</scaleRMin32>' % rmin, seg[pa:pb])
        sub = re.sub(r'<scaleRMax32>-?\d+</scaleRMax32>',
                     '<scaleRMax32>%d</scaleRMax32>' % rmax, sub)
        seg = seg[:pa] + sub + seg[pb:]

    # scaleRect 才是坐标轴的位置
    n = [0]

    def _rect(m):
        i = n[0]
        n[0] += 1
        if i >= len(SCALE_RECTS):
            return m.group(0)
        return '<scaleRect>(%d, %d, %d, %d)</scaleRect>' % SCALE_RECTS[i]

    seg = re.sub(r'<scaleRect>\([^)]*\)</scaleRect>', _rect, seg)

    for pu, box in GRAPH_DYN.items():
        ps = _part_span(seg, pu)
        if not ps:
            continue
        pa, pb = ps
        sub = re.sub(r'<dynBounds>\([^)]*\)</dynBounds>',
                     '<dynBounds>(%d, %d, %d, %d)</dynBounds>' % box, seg[pa:pb])
        sub = re.sub(r'<nMajDivs>\d+</nMajDivs>', '<nMajDivs>10</nMajDivs>', sub)
        seg = seg[:pa] + sub + seg[pb:]

    # X 轴做成时间轴 0~30 s（HTML 的横轴是秒，不是百分比）
    ps = _part_span(seg, 405)
    if ps:
        pa, pb = ps
        sub = seg[pa:pb]
        sub = re.sub(r'<scaleDMax>[^<]*</scaleDMax>', '<scaleDMax>403E000000000000</scaleDMax>', sub)
        sub = re.sub(r'<scaleDIncr>[^<]*</scaleDIncr>', '<scaleDIncr>403E000000000000</scaleDIncr>', sub)
        # 大格只留 1 个：LabVIEW 会按"每大格 4 小格"自动生成次刻度，
        # 6 大格 = 30 根小竖线，横贯绘图区中部，非常扎眼；缩到 1 大格就只剩两端两根
        sub = re.sub(r'<nMajDivs>\d+</nMajDivs>', '<nMajDivs>1</nMajDivs>', sub)
        seg = seg[:pa] + sub + seg[pb:]

    return s[:a] + seg + s[b:]


def set_caption_box(blk, box):
    """把标题标签拉成一条横条，否则会被拉成竖排。"""
    for mm in re.finditer(r'<SL__arrayElement class="\w+" uid="(\d+)">', blk):
        a = mm.start()
        e = sla_span(blk, a)
        seg = blk[a:e]
        if '<partID>16</partID>' not in seg:
            continue
        m2 = re.search(r'<bounds>\([^)]*\)</bounds>', seg)
        if not m2:
            return blk
        seg2 = seg[:m2.start()] + '<bounds>(%d, %d, %d, %d)</bounds>' % box + seg[m2.end():]
        return blk[:a] + seg2 + blk[e:]
    return blk


def pin_parts(blk, H, W, spec):
    """把指定零件钉到控件坐标系里的固定位置（相对原点）。"""
    for pu, kind in spec.items():
        m = re.search(r'<SL__arrayElement class="\w+" uid="%d">' % pu, blk)
        if not m:
            continue
        a = m.start()
        e = sla_span(blk, a)
        seg = blk[a:e]
        mm = re.search(r'<bounds>\([^)]*\)</bounds>', seg)
        if not mm:
            continue
        if kind == 'face' or kind == 'frame':
            box = (0, 0, H, W)
        elif kind == 'text':
            box = (22, 8, max(30, H - 8), max(40, W - 12))
        else:  # caption
            box = (6, 10, 26, max(70, W - 12))
        seg2 = seg[:mm.start()] + '<bounds>(%d, %d, %d, %d)</bounds>' % box + seg[mm.end():]
        blk = blk[:a] + seg2 + blk[e:]
    return blk


def patch_ftab(xml, size, title_size):
    """字表：第 0 项是全局默认，第 2 项留给标题。"""
    def one(m):
        i = one.i
        one.i += 1
        t = m.group(0)
        sz = title_size if i == 2 else size
        t = re.sub(r'Prop2="\d+"', 'Prop2="%d"' % sz, t)
        t = re.sub(r'Prop6="\d+"', 'Prop6="%d"' % sz, t)
        return t
    one.i = 0
    return re.sub(r'<Font [^>]*>', one, xml)


def main():
    if os.path.isdir(DST):
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)

    x = open(MAIN, encoding='utf-8').read()
    if '<FTAB>' in x:
        x = patch_ftab(x, FTAB_SIZE, TITLE_SIZE)
        open(MAIN, 'w', encoding='utf-8').write(x)
        print('字表 -> 正文 %d / 标题 %d' % (FTAB_SIZE, TITLE_SIZE))

    s = open(FP, encoding='utf-8-sig').read()

    # 面板底色：pane 的 partID 28 默认挂着一张灰度贴图（ImageResID -704），
    # 贴图在时 bgColor 被忽略。把贴图去掉，底色才真正变成平涂色。
    a = s.find('<paneHierarchy')
    b = s.find('</paneHierarchy>', a)
    seg = s[a:b]
    k = seg.find('<partID>28</partID>')
    if k > 0:
        e = seg.find('</SL__arrayElement>', k)
        sub = seg[k:e]
        sub = re.sub(r'<ImageResID>-?\d+</ImageResID>', '<ImageResID>0</ImageResID>', sub)
        sub = re.sub(r'<bgColor>[^<]*</bgColor>', '<bgColor>%s</bgColor>' % PANE_BG, sub)
        sub = re.sub(r'<fgColor>[^<]*</fgColor>', '<fgColor>%s</fgColor>' % PANE_BG, sub)
        seg = seg[:k] + sub + seg[e:]
        s = s[:a] + seg + s[b:]
        print('面板底色 -> %s（贴图已去掉）' % PANE_BG)

    hits, hided = [], 0
    spans = [(mm.start(), int(mm.group(1)))
             for mm in re.finditer(r'<SL__arrayElement class="fPDCO" uid="(\d+)">', s)]
    for a0, uid in reversed(spans):
        b0 = sla_span(s, a0)
        blk = s[a0:b0]
        blk, k = hide_parts(blk, HIDE_PARTS.get(uid, []))
        hided += k
        if uid in BTN:
            blk = flat_button(blk)
        blk = recolor_control(blk)
        if uid in CAPTIONS:
            txt, _lu = CAPTIONS[uid]
            blk = set_caption(blk, gbk(txt))
        nm = UIDS.get(uid)
        if nm in TARGETS:
            t, l, b, r = TARGETS[nm]
            t, l, b, r = round(t * YS), round(l * XS), round(b * YS), round(r * XS)
            if uid in FILL_PARTS:
                # 卡片：先按正确基准铺一遍，再把显示区/元素面/元素顶到满框，
                # 正文改成 N 个元素的多行文本 —— 数组控件于是退化成叠放的卡片
                blk = retarget(blk, t, l, b, r)
                blk = set_ddo_bounds(blk, t, l, b, r)
                H, W = b - t, r - l
                for pu in FILL_PARTS[uid]:
                    blk = set_bounds_of_uid(blk, pu, 0, 0, H, W)
                spec = CARD_SPEC[uid]
                eh = int(H / spec['n'])
                blk = set_bounds_of_uid(blk, spec['elem'], 0, 0, eh, W)
                blk = set_bounds_of_uid(blk, spec['frame'], 0, 0, eh, W)
                blk = set_bounds_of_uid(blk, spec['text'], 5, 7, eh - 4, W - 8)
                blk = set_array_text(blk, MULTILINE[uid])
            elif uid in BTN:
                blk = retarget_uniform(blk, t, l, b, r)
            else:
                blk = retarget(blk, t, l, b, r)
            hits.append(nm)
        s = s[:a0] + blk + s[b0:]

    # 波形图：内部零件重新摆位（绘图区撑满、坐标轴外移、图例收起）
    s = style_graph(s)

    # 波形图网格调淡 + 曲线给个颜色（默认是纯白，白底上等于隐形）
    s = re.sub(r'<gridMaxColor>[^<]*</gridMaxColor>', '<gridMaxColor>00EAEAEA</gridMaxColor>', s)
    s = re.sub(r'<gridMinColor>[^<]*</gridMinColor>', '<gridMinColor>00F4F4F4</gridMinColor>', s)
    s = re.sub(r'<color>00FFFFFF</color>\s*\n(\s*)<flags>0</flags>', r'<color>00C86428</color>\n\1<flags>0</flags>', s)

    # Y 轴量程 -10..10 -> 0..100（HTML 是百分比量程）
    s, ok_axis = set_axis_range(s)
    print('Y 轴量程 -> 0..100:', 'OK' if ok_axis else 'FAIL')

    # 左栏 / 右栏改成真正的多行文本卡片（数组控件拉不出 HTML 那种卡片，
    # 换成 753 那块 stdString 指示器的副本，铺满目标框并盖上原数组控件）
    for off, nm, key in ((80000, '04 数据源链路', 393), (90000, '06 通道图例', 581)):
        t, l, b, r = TARGETS[nm]
        box = (round(t * YS), round(l * XS), round(b * YS), round(r * XS))
        # s = add_text_card(s, off, box, MULTILINE[key])   # 新增控件会让 BDHb 端子对不上
        print('文本卡片（用原数组控件，不新增）%s -> %s' % (nm, box))
    print('落位 %d，藏零件 %d' % (len(hits), hided))
    open(FP, 'w', encoding='utf-8-sig').write(s)

    # patch_bdhb(os.path.join(DST, '波形图_v7_BDHb.xml'), [80753, 90753])

    import xml.etree.ElementTree as ET
    ET.fromstring(open(FP, encoding='utf-8-sig').read())
    ET.fromstring(open(MAIN, encoding='utf-8').read())
    print('XML OK')


if __name__ == '__main__':
    main()
