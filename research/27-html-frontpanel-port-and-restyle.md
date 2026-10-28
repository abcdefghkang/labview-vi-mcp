# Round 18 — HTML 主界面 → LabVIEW 前面板移植 + 深度换肤：bundle XML 规律、两条死路、与一个不在 XML 里的颜色

> 任务：把 4 个 HTML 主界面（登录 / 报警 / 波形图 / 产品侧）移植成 LabVIEW VI 的**前面板**，
> 不要程序逻辑，只要外观。生成阶段用 AIXML 直出（Round 1 的老路），但用户验收的判据是
> **"像不像"**——于是本轮的全部工作量都落在深度换肤上：`pylv_extract` 拆包 → 直接编辑
> 堆 XML → `pylv_rebuild` 回写 → 自制打印助手渲染成 PNG 逐版比对。一句话总结：
> **XML 能改的都改得动，但绘图区的黑底不在 XML 里**——它是图形引擎的运行时默认，
> 唯一改法是写 VI Server 属性。

---

## 1. 两条流水线（生成 vs 换肤）

| 阶段 | 链路 | 说明 |
|---|---|---|
| 移植 | HTML 视觉规格 → AIXML 手写前面板 → `lvai_generate_vi` | 4 个 VI 一次成型；几何/控件类型按 HTML 逐个对号 |
| 验证 | `helper_fp_print.vi`（自研）→ 前面板打印为 PNG → 像素采样比对 | **不看任何 `ok` 自述**，判据是渲染图 |
| 换肤 | `pylv_extract`（VI→XML bundle）→ 编辑 `*.xml` + `*_FPHb.xml` → `pylv_rebuild`（XML→VI）→ 重新渲染 | 每版一个 vN 文件，二分定位拒载原因 |

产物：`examples/hmi-html-port/`（4 个 .vi）+ `research/artifacts/round18/`（换肤脚本、
两个助手 VI 及其 AIXML、最终渲染图）。

---

## 2. 堆 XML（FPHb.xml）规律速查——本轮实测钉死

LabVIEW 把前面板外观存在 bundle 的 `*_FPHb.xml` 里，`ddoList`（引用列表）+ `zPlaneList`
（完整定义，**顺序与 ddoList 相反**）。可编辑的规律：

| 主题 | 规律 |
|---|---|
| 坐标 | `(top, left, bottom, right)`；ddo bounds 是**绝对坐标**，零件 (parts) bounds 是**相对 ddo 左上角**，且零件不随 ddo bounds 自动缩放——缩放要手写 `scale_rel` 逐零件乘系数 |
| 颜色 | `0x00RRGGBB`（红在高位）；`01000000` = 透明 |
| 文本 | 值存 `DefaultData` 的 CDATA：`"` + **4 字节大端长度** + 内容 + `"`；长度字节错了 LabVIEW 显示乱码/异常 |
| **中文编码** | pylabview 无损往返把 GBK 字节按 MacRoman 误解码保存 ⇒ 写中文必须 `moj(s) = s.encode('gbk').decode('mac_roman')`，读出来再反向 |
| 字体 | 在主 XML 的 `<FTAB>` 段（`Prop2`/`Prop6` = 字号） |
| 透明背景 | textRec `mode 1028` 透明；`mode 0` 白底生效 |
| 自由标签 | TypeID 偶数 (92/94/96)；partID=16 是名称标签，**partID≠16 的 textRec 零件**才是显示文本 |
| 陷阱 | 文件里有 **4 个 `</zPlaneList>`**——第 1 个是波形图控件**内部窗格**的闭合，不是主列表的；字符串替换按第一个匹配会插进子树把 XML 弄坏（用 `rfind`） |
| 波形图控件 | (TypeID 47) 内部 3 个嵌套窗格只是滚动条/图例条带；网格色 `gridMaxColor`/`gridMinColor`；**注意大小写**：`<BGColor>` 与 `<bgColor>` 是两个不同的标签，只替换一个会漏 |

---

## 3. 两条死路（都做了对照实验，不是猜的）

1. **窗格零件注入 cosm 装饰件（Win95 凹凸边框）**：objFlags 115/5 × ImageResID 0/-704
   等 **4 种结构风格全部不渲染**。窗格零件绘制表是写死的——XML 注入装饰件此路不通。
2. **注入克隆的 free label fPDCO 定义**（想在面板上放"面板级装饰"）：`pylv_rebuild`
   能过、文件能存，但 **LabVIEW 加载前面板时直接拒载**（"无法加载…的前面板"）。
   二分排查（v6 去克隆 → 正常；v7a 加装饰 → 拒载）钉死元凶就是克隆定义。

推论：**HTML 的 3D 凹凸边框效果，在"不改引擎"的前提下表达不出来**——要像，得在
LabVIEW 编辑器里手动加 Decorations。这是本轮诚实的技术边界。

---

## 4. 黑底之谜：一个不在 XML 里的颜色（本轮最大收获）

换肤后标题/字体/标签/数值框全部生效，但**绘图区始终纯黑**。排查过程值得记录，因为
每一步"看起来都对"：

- 替换了 FPHb 里波形图子树**全部 4 处**深蓝 `001E4B00` → 仍黑；
- `gridMaxColor`/`gridMinColor` 改浅灰 → **网格真的变浅灰了**（替换生效的证明），底还是黑；
- 提取 uid550 子树穷举所有 `*olor*` 标签：`fillColor 00000000` 是曲线填充色
  （`fillStyle=0` 不填充，无关）；3 个内部窗格只是条带；paneHierarchy 的纯色填充件透明；
- 像素级对照 v5→v7 渲染：**黑底从生成 VI 起就存在**，换肤从未影响过它。

结论：**绘图区底色是经典风格图形的引擎默认，根本不存在于 VI 文件里**。唯一改法是
运行时写 VI Server 属性。为此造了一个**通用助手**：

```
helper_graph_style.vi（自研，AIXML 生成）
  Open VI Reference → Front Panel → Controls[] → For Loop
  → 读 Class Name → 字符串 Case 分流（"WaveformGraph"/"GraphChart" 命中）
  → Property Node write Plot Area:Colors:BG Color（U32，白色=16777215）
  → Save Instrument 保存 VI
```

实测：`run_vi_as_top_level(helper_graph_style, 波形图_v7.vi, BG=16777215)` →
重新渲染 → **绘图区纯白 (255,255,255) 主导、浅灰网格 (C8C8C8) 保留**，见
`artifacts/round18/waveform-restyled-render.png`。这个助手是**可复用资产**：以后改
曲线颜色（Plot Color）、改任意图形类控件的绘图区样式，同一套模板换个属性名即可。

---

## 5. AIXML 属性节点方言——本版本工具链的坑（与解法）

给 helper 写 AIXML 时撞上的，全部实测：

| 坑 | 事实 | 解法 |
|---|---|---|
| **NI 校验器失效** | 当前版本对所有 Property Node 一律报"无效属性名"——**连官方自带脚本都过不了校验**（`lvai_run_and_read_typed.xml` 直接喂进去也报同样的错） | `lvai_generate_vi(backend:"pylabview")`，合成器认 **`vi-server-props.json` 学习表**里的名字（`Plot Area:Colors` 就在里面，类型 `{FG Color, BG Color}` U32 簇） |
| 遍历面板 | 用 **`Controls[]`**，不是词汇表里的 `All Objects[]` | 仿官方脚本 `lvai_run_and_read_typed.xml` 的接线模式 |
| net 命名 | **net 名必须等于端子名**（`value:105.error out` 这种 `端子名:uid.端子名` 格式） | 照抄官方脚本的命名纪律 |
| uid 保留区 | uid 10/11/13/14/20/40/41 是结构/隧道保留段，占用后 net 引用全部悬空 | 自定义节点 uid 一律从 100 起编 |
| 跨结构边界 | 属性输入线穿 For Loop / Case 边界必须**每层加 Tunnel**（`In3` 三层都加） | 合成器会报，按报错逐层补 |
| 类名转型 | `{LV.GraphChart}` 属性节点前先 `To More Specific Class`，用字符串 Case 直接分流 Class Name | 本机控件实际类名是 `WaveformGraph`（两个分支都写上） |
| 回传假象 | `run_vi_as_top_level` 的输出指示器常因 bool/int32 混合编组返回空（errorCode 91） | **不改代码，重新渲染看结果**——写操作实际已发生 |

---

## 6. 换肤最终清单（`restyle_final.py`，可复跑）

从原始副本一条龙应用：剥 27 个控件编号前缀；FTAB 字号 17→12；标题文本按 mojibake
管线改写（长度字节陷阱：改 `DefaultData` 必须重算 4 字节大端长度，实体转义会踩
LabVIEW 解析坑）；参数/状态栏改"行内左标签 + navy 底白字 + 白底数值框"；LED 竖排改名；
波形图缩放重定位；面板底色 `E2`→`E0`。SELFCHECK 内建，任一锚定正则失配即报——
**之前吃过静默失败的大亏（正则多个 `\)` 导致标签重定位全部无效），所以这版每处替换
都自检命中次数**。

---

## 7. 能力地图增量

| 能力 | 状态 | 证据 |
|---|---|---|
| HTML → VI 前面板移植（无逻辑） | ✅ 端到端 ×4 | `examples/hmi-html-port/` |
| bundle 深度换肤（几何/颜色/字体/文本全可改） | ✅ 有配方与陷阱清单 | `artifacts/round18/restyle_final.py` |
| 前面板渲染验证闭环（自研打印助手） | ✅ | `artifacts/round18/helper_fp_print.vi` |
| 图形控件绘图区底色/样式运行时改写 | ✅ 通用助手 | `artifacts/round18/helper_graph_style.vi`（+AIXML 源） |
| 窗格装饰件注入 / 克隆控件注入 | ❌ **钉死不可行**（引擎绘制表写死 / 拒载） | 本档 §3 |

**本轮没有新增 LV021 规则**——以上知识属于"编辑侧配方"而非 lint 可查的静态特征；
全部沉淀在本档与 `06-best-practices.md §18.2.2`。

---

## 8. 遗留

- 曲线颜色仍为白色（真连数据画线时用 `helper_graph_style` 换 `Plot Color` 即可，如红色）；
- 右下角"运行时长"数值框略截断（坐标微调项，不影响验收）；
- 登录/报警/产品侧三个 VI 是**生成版原状**（未做波形图级深度换肤），配方已就绪，按需套用。
