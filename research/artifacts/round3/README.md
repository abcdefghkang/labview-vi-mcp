# round3 产物清单（研究第三轮：复杂程序）

对应文档：`../../08-complex-programs.md`（结论）与 `../../09-measured-session-2.md`（实测原始记录）。

## AIXML 源码

| 文件 | 说明 | validate |
|---|---|---|
| `saturating-accumulator.aixml.xml` | 饱和累加器基线（SR 种子在循环内） | errorCode 1（成环误报） |
| `variant-a-nocase.aixml.xml` | 对分变体 A：去掉 Case | errorCode 1 |
| `variant-b-noindex.aixml.xml` | 对分变体 B：去掉索引输出隧道 | errorCode 1 |
| `variant-c-panelstop.aixml.xml` | 对分变体 C：Condition 改读面板 Stop | errorCode 1 |
| `variant-d-rootseds.aixml.xml` | 对分变体 D：种子全部移根级 | **errorCode 0** ✓ |
| `variant-e-mixedseeds.aixml.xml` | 对分变体 E：仅一个种子移根级 | errorCode 1（确认任一即触发） |
| `saturating-accumulator-v2.aixml.xml` | 最终设计：Case+索引隧道+内部停止+根级种子 | errorCode 0 |
| `clamp-value.aixml.xml` | 子 VI：两个嵌套 Case 的区间钳位 (x,lo,hi)→clamped | errorCode 0 |
| `clamp-demo.aixml.xml` | 主 VI：While+3SR 循环内 Call 子 VI | validate 拒 SubVI（预期）；loadedSubVIs 路线生成成功 |

## 生成的 VI（LabVIEW 2026 26.3.1f1 中文版实测可运行）

| 文件 | 字节 | 说明 |
|---|---|---|
| `Saturating Accumulator.vi` | 8354 | 复杂单 VI，4/4 功能测试通过 |
| `Clamp Value.vi` | 5623 | 子 VI（嵌套 Case） |
| `Clamp Demo.vi` | 8462 | 主 VI（循环内 Call），2/2 测试通过 |

## 项目容器

| 文件 | 说明 |
|---|---|
| `Clamp Demo.lvproj` | 手写项目，describe_project / open_file 均 errorCode 0 |
| `Clamp Demo.aliases` | LabVIEW 随项目生成的别名文件 |

**注意**：`Clamp Demo.lvproj` 内的 Item URL 是生成机器上的绝对路径
（`/C/Users/heiyashi/WorkBuddy/automation-2026-10-18-03-19-34/labview-mcp-research/round3/...`）。
克隆到其他机器后需先把 VI 放到本目录、再把 URL 改成实际绝对路径（格式：盘符变一级目录、
正斜杠），并保持 UTF-8 BOM 与条目顺序（VI 在 Dependencies/Build Specifications 之前）。

## 复现要点

1. uid 全部 ≥100（低 uid 会触发保留区修复，源文件与生成物对不上）；
2. ShiftReg `Left inputs` 种子必须来自根级元素；
3. 主子 VI 同目录，先生成子 VI（openVI:true 保持在编）再生成主 VI；
4. 含 Call 时 validate 报 `Unsupported SubVI` 属预期，看 convert 结果。
