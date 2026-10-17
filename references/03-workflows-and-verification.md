# 03 · 工作流与校验脚本

## 0. 能力探针（一切未知先测）

对没把握的属性/样式，**永远先在草稿 VI `C:\LV_AUTOTEST\gen\scratch_probe.vi` 上验证**：

```
open_vi(scratch) → add_object 试验对象 → set_property 写目标属性
→ get_property 读回 → save_vi → render_vi → 裁剪看图 → 得出结论再上主 VI
```

本经验库所有"静默失效"结论都来自这个流程。别在主 VI 上赌。

## 1. 新建 VI 工作流

1. `new_vi(path)` —— 路径已存在会被拒绝（不会覆盖）。
2. `search_styles(query)` 查样式实名（如 `"Valve"`、`"LED"`）。
3. `add_object` 建对象，**创建顺序 = Z 序**：背景 → 管道/图形 → 文字。
4. `set_property` 配置（value 一律字符串）。多个对象用 Code Mode `execute` 循环批量配置。
5. `inspect_vi` 取最新引用。
6. （需要逻辑时）`inspect_node` → `wire` → `clean_up_diagram`。
7. `save_vi` → `render_vi({path, surface:"panel"})` → 像素核验。

## 2. 存量 VI 批量修改工作流（实战主力）

```
open_vi(path)
→ inspect_vi(path) 全量清单（reference/class/label/position）→ 落 TSV 备查
→ 制定按区域编辑计划（删什么/改什么/加什么）
→ execute 跑批量脚本（每步 try/catch，收失败清单）
→ save_vi → render_vi → 逐区域裁剪核验 → 修正 → 再渲染
```

### 2.1 Code Mode 批量编辑模板（JavaScript）

```js
const lv = tools["labview-native-2018"];
const ok = [], fail = [];

async function sp(cls, member, ref, val) {
  // 改属性：cls 如 'Decoration'/'Text'/'Boolean'；val 强制字符串
  try {
    await lv.set_property({ object_class: cls, member, reference: ref, value: String(val) });
    ok.push(`${cls}.${member}@${ref}`);
  } catch (e) {
    fail.push(`${cls}.${member}@${ref}: ${String(e).slice(0, 140)}`);
  }
}

async function mk(style, x, y, w, h, cls /*'Decoration'|'Text'|...*/) {
  // 建对象 + 定尺寸 + 定位，返回引用
  const r = await lv.add_object({ owner: PANEL_REF, style, location: [x, y] });
  const ref = r.result;
  await sp(cls, 'Size:Width', ref, w);
  await sp(cls, 'Size:Height', ref, h);
  await sp(cls, 'Position:Left', ref, x);
  await sp(cls, 'Position:Top', ref, y);
  return ref;
}

async function del_(refs) {
  try { await lv.delete_objects({ references: refs }); ok.push(`del:${refs.length}`); }
  catch (e) { fail.push(`del ${refs}: ${String(e).slice(0, 140)}`); }
}

// —— 你的编辑步骤（顺序：先删、后加背景、再文字）——
// await del_([...]);
// const p = await mk('Flat Box', 30, 540, 1110, 12, 'Decoration');
// await sp('Decoration', 'BG Color', p, 14212324);

return { okCount: ok.length, failCount: fail.length, fail: fail.slice(0, 40) };
```

要点：
- **每步独立 try/catch**（`edit_batch` 是遇错即停、不回滚，只适合小批次高把握操作）。
- 返回先给 `okCount/failCount` 摘要，失败清单截断显示，避免输出过载。
- 顺序：先删除（按引用）→ 再建背景 → 再建图形 → 最后文字（Z 序）。改位置可随时补。

### 2.2 编辑后核对模板（Python）

1) 找最新渲染 → 2) 逐区域裁剪放大 3) 用 read 工具看图 4) 修正。

```python
# -*- coding: utf-8 -*-
import glob, os
from PIL import Image
BASE = r"C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\work\mcp_render\ats_hmi_v1"
newest = None
for d in sorted(glob.glob(os.path.join(BASE, 'export_*')), key=os.path.getmtime):
    c = glob.glob(os.path.join(d, '*p.png'))
    if c:
        m = max(c, key=os.path.getmtime)
        if newest is None or os.path.getmtime(m) > os.path.getmtime(newest):
            newest = m
im = Image.open(newest).convert('RGB')
regions = {
    'A_左侧区':   (20, 58, 510, 380),
    'B_中部区':   (510, 58, 930, 380),
    'C_右侧区':   (930, 58, 1500, 380),
}
out = r"C:\Users\<you>\AppData\Local\Temp\opencode"
for name, (x0, y0, x1, y1) in regions.items():
    c = im.crop((x0, y0, x1, y1))
    s = min(3.0, 1400 / max(c.width, 1))
    c = c.resize((int(c.width*s), int(c.height*s)), Image.LANCZOS)
    p = os.path.join(out, f"crop_{name}.png")
    c.save(p)
    print(name, '->', p, c.size)
```

运行方式（Git Bash 会乱码中文，**用 write 工具写脚本再跑**）：

```
PYTHONIOENCODING=utf-8 "C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\runtime\python.exe" 脚本路径.py
```

## 3. 照片/截图还原方法论（image-driven）

1. **比例校准**：目标渲染宽 1520；照片宽 W → 比例 s = 1520/W。**x、y 比例可能不同**（手机照片有畸变），必须用已知地标（大的分区框、管道线）在照片/渲染中的坐标反推，再定标定公式。
2. **分区战术**：照片与渲染各裁同一矩形区域、2~4× 放大、并排对比，**一次只核对一个区域**，看完再下一个。
3. **取色**：`im.getpixel((x, y))` 直接采样（照片/渲染都可以），得到 RGB → 转 `0x00RRGGBB` → 十进制字符串。
4. **语义不明查照片**：文字读不清时放大原图再认（本例"回油"曾被误做成"燃油"、KA 编号、单位都是在照片里放大定案的）。照片是唯一事实来源。
5. **小步迭代**：每轮 3~5 个区域，渲染核验后再下一批；每轮留档旧预览便于差分。
6. **取舍**：空间不足时不硬塞（本例"单向阀"用了缩写、"最大流量阀"整条撤掉），保持视觉密度接近照片。

## 4. 交付工作流（对用户）

1. **主副本与交付件分离**：
   - master：`C:\LV_AUTOTEST\gen\ats_hmi_v1.vi`（所有编辑都作用在这里）
   - 交付 VI：`C:\Users\<you>\Documents\默认项目\试验设备运转测控面板.vi`
   - 预览 PNG：`C:\Users\<you>\Documents\默认项目\面板预览.png`
2. 交付脚本：`scripts/deliver.py`（master + 最新渲染 → 复制到上面两个路径）。
3. **每个交付都量化差异**：`scripts/compare_deliver.py` 输出
   - `changed pixels: N (P%)`（阈值 >24 / 16×16 块 / 块内 >6% 标红）
   - 上下叠放对比图：上=旧版，下=新版+红色变化块 → `对比_上一版_vs_新版.png`
4. 汇报格式（中文）：**改动像素数 + 占比 + 分区域变更清单 + 交付路径**。
   - 经验值：~200 px = 肉眼不可见（会被抱怨"和上一版没区别"）；~9 万 px = 5~6%，明显变化。
5. 给用户看：用 browser.preview 打开 `面板预览.png` 与 `对比_上一版_vs_新版.png`。

## 5. 常见故障处理

| 症状 | 处理 |
|---|---|
| MCP 调用 45s 超时 | 改走 CLI：`C:\LV_MCP\bin\LabVIEWMCP.exe --pylv-extract <vi> --out <dir>`；或拆小批次 |
| `edit_batch` 中途失败 | 拆成更小批次；失败步骤单独重试（无回滚，注意重复执行副作用） |
| 渲染没更新 | 先确认 `save_vi` 已保存；找新的 `export_*` 目录；PNG 取 mtime 最新 |
| 属性写了没反应 | 大概率是静默失效（见 02 第 3 节）→ 换方案（如用独立文本代替题注） |
| 端子/引用对不上 | 重新 `inspect_vi` / `inspect_node` —— 重配置后引用会变 |
| 中文路径/输出乱码 | 别在 shell 里拼中文命令；写 .py 脚本 + `PYTHONIOENCODING=utf-8` |
