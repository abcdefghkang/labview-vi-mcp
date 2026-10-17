# 02 · 能力矩阵：实测可用 / 无效 / 静默失效

> 本文所有结论都在本机 LabVIEW 2018 (32bit) + `labview-native-2018` 上实测过。
> **探针原则**：任何换环境的操作，先在 `C:\LV_AUTOTEST\gen\scratch_probe.vi` 上试，读回 + 渲染确认后再上主 VI。

## 1. 可创建对象样式（LabVIEW 原生共 1117 种，用 `search_styles(query)` 查）

### 1.1 装饰（Decoration）—— 界面还原主力

| 样式名 | 用途 | 备注 |
|---|---|---|
| `Flat Box` | **实心矩形**：管道、色条、曲线轨迹、状态条、胶囊底全靠它 | 最常用的万能件 |
| `Right Arrow` / `Left Arrow` / `Up Arrow` / `Down Arrow` | 箭头（实心三角） | 方向以名字为准，**用后渲染确认朝向** |
| `Line with Arrow (thin)` / `(thick)` | 带箭头细线 | 适合流程指示 |
| `Up/Down/Left/Right × Bow Valve × (flat/outline/shaded)` | 蝶阀轮廓（24 种组合） | 本例用 `Left Bow Valve (outline)`，设 FG Color 变蓝 |
| `Up/Down/Left/Right × Rect Valve × (flat/outline/shaded)` | 矩形阀轮廓 | 同上族 |
| `Horiz Line`（3821 附近） | 水平线 | |

已确认 ID 举例：`Right Arrow` 3825 · `Left Arrow` 3826 · `Up Arrow` 3823 · `Down Arrow` 3824 · `Left Bow Valve (outline)` 3801 · `Left Rect Valve (outline)` 3800。
**建议只记名字，用 `search_styles` 查**，不依赖 ID。

### 1.2 文本

| 样式名 | 结论 |
|---|---|
| `Label (modern)`（21960） | ✅ **唯一推荐**的文本载体：内容/底色/字色/字号/宽高全可写，渲染为带边框阴影的标签 |
| `Label (system)` | ✅ 可创建（系统风格） |
| `Free Label`（2321） | ❌ **创建报错 1060，不可用**——这是最大的经典坑 |

### 1.3 布尔（按钮 / 灯 / 开关）

| 样式名 | 用途 | 备注 |
|---|---|---|
| `LED Button`（3116） | 圆灯按钮 | |
| `Square LED (modern)`（21013） / `Round LED (modern)`（21012） | 现代 LED | **亮=绿（≈#64FF00），暗态也不暗（仍呈亮绿）；颜色不可自定义** |
| `Square LED (classic)` / `Round LED (classic)` | 经典 LED | **亮=红** |
| `Labeled Rectangular Button`（3124） | 带文字的矩形按钮 | 急停解除/供油/加油等运行按钮 |
| `Labeled Oblong/Round/Square Button` | 其他按钮形 | |
| `Vertical/Horizontal Toggle Switch (modern/classic)` | 拨杆开关 | 引气开关排 |
| `Slide Switch` / `Vertical Switch` / `Horizontal Switch` | 其他开关 | |

### 1.4 数值 / 图表

| 样式名 | 用途 | 备注 |
|---|---|---|
| `Numeric Indicator (modern)` | 数字显示 | 配 `FormatString` 控制小数位 |
| `Knob (modern)`（21000） | 旋钮 | |
| `Waveform Chart` | 波形图表 | 多曲线：加 Plot + 设曲线色 |

## 2. 属性可写性矩阵（按类）

| 类 | 可写属性（成员名） | 结果 |
|---|---|---|
| `Decoration` | `Size:Width` `Size:Height` `Position:Left` `Position:Top` `BG Color` `FG Color` | ✅ 全部有效；**尺寸必须用 Size:**（`Bounds:Area Width/Height` 写了无效） |
| `Text` | `Text` `BG Color` `FontColor` `FontSize` `FontUnder` `Size:Width` `Size:Height` `Position:Left` `Position:Top` `Justify` | ✅ 全部有效 |
| `Boolean` | `Button Size:Width` `Button Size:Height` `Position:Left` `Position:Top` `Value`("true"/"false") | ✅ 有效 |
| `Boolean`（题注部分） | `Position:*` `Visible` → ❌ 静默失效；`FontSize` → ⚠️ 不可靠 | 见第 3 节 #1 |
| `Digital` | `FormatString`（`"%.1f"` `"%.2f"` `"%d"`）`Text Width` `Position:*` | ✅ 有效 |
| `Digital`（显示格式） | `Display Format:Precision` → ❌ 报错 1435；`UnitLabel` 子对象 → ❌ 引用无效(0) | 用 FormatString + 独立文本标签做单位 |

通用：`set_property` 的 `value` **必须传字符串**（数字也写成 `"25"` 这样）。

## 3. 静默失效 & 报错清单（血泪坑，按危害排序）

1. **布尔题注不可控**：题注（Caption）固定渲染在按钮**上方**；对题注写 `Position:Left/Top`、`Visible` → **无报错但完全无效果**；`FontSize` 也不可靠（实测写 9/10 后仍显示大字号）。⇒ 题注不能当"可挪走的说明文字"用；它只能当"按钮的正上方的固有标签"。**控件的 `Position:Top` 指"题注+按钮"整体上沿，按钮主体实际渲染在 Top+12~15px 处** —— 摆位时必须按此估算。
2. **尺寸类属性分家**：装饰/文本的尺寸用 `Size:Width/Height`；布尔按钮的尺寸用 `Button Size:Width/Height`；`Bounds:Area` 一系对装饰无效。
3. **布尔 `Colors[4]` 不可写**：想自定义开关颜色会失败（无报错、不生效）。颜色由样式决定。
4. **`Free Label` 创建即报错 1060**：别用它。
5. **`Digital` 的单位标签**：取 `UnitLabel` 子对象得到无效引用（0）；小数位用 `FormatString` 设（`Display Format:Precision` 报错 1435）。
6. **`add_object` 的 `bounds` 参数被忽略**：只能用 `location:[x,y]`（左上角）+ 事后 `Size:*`。
7. **Z 序 = 创建顺序**：新对象永远盖在最上层；`Position` 修改**不改变** Z 序。⇒ 先背景/管道，后图形，最后文字。
8. **`set_property` 成功 ≠ 视觉生效**：第 1 条就是无报错失效的典型。批量改完必须 `save_vi` + `render_vi` 渲染核对。
9. **`render_vi` 返回 null 是正常的**：完成判据 = 出现新的 `export_*` 目录 / PNG mtime 更新。
10. **`run_vi` 真实执行**：会触发硬件/网络 IO。纯界面还原时不要调。
11. **透明色陷阱**：颜色 `16777216`（透明）文字会彻底不可见——可用于"隐去"，但别误用。
12. **重绘延迟**：个别属性写入后需要 `save_vi`/重新渲染才反映到 PNG；别以"刚写完的内存状态"当最终视觉。

## 4. 颜色体系

- 格式：`0x00RRGGBB` 的**十进制字符串**（如 `0xD8DCE4` → `"14212324"`）
- 案例工程调色板（可直接复用作风）：

| 名称 | Hex | 十进制 |
|---|---|---|
| 纯白 / 纯黑 | #FFFFFF / #000000 | 16777215 / 0 |
| 标题栏蓝 | #C3D9F0 | 12834800 |
| 横幅浅蓝 | #E2F0F5 | 14871541 |
| 深蓝文字 | #004070 | 16496 |
| 分区底色 | #E9E7D8 | 15266040 |
| 面板灰底 | #D6DCE8 | 14082280 |
| LED 亮绿 | #64FF00 | 6618880 |
| 管道灰 | #D8DCE4 | 14212324 |
| 进气管蓝 | #7BA6E8 | 8103656 |
| 阀门蓝 | #3949A8 | 3754408 |
| 箭头灰蓝 | #A5B4C4 | 10857924 |
| 曲线绿 | #2ECC2E | 3066926 |
| 曲线品红 | #CE3EC4 | 13516484 |
| 胶囊深灰 | #3C3C3C | 3947580 |
| 急停红 | #D03C28 | 13641768 |
| 白字 | #FFFFFF | 16777215 |

## 5. 坐标 / 渲染

- 面板内容区 **1520×1010**（窗口设置 `8,8,1560,1060`）；渲染 PNG 1520×1022 左右（底部多一条边），**y 比对前先裁到公共高度**。
- 渲染 PNG 像素坐标 ≈ 前面板坐标 **1:1**，可直接按坐标裁剪放大核验。
- 子对象（如数字控件的文本、题注）都会跟着控件一起渲染；**控件外框位置以渲染图实测为准**（因为题注占位，实际渲染位置可能比设定值低 12~15px）。
