# round5 产物清单（研究第五轮：pylabview 编辑链）

对应文档：`../../11-pylabview-edit-chain.md`（结论与方法论）。

环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1。
生成走 grpc AIXML 通道（validate → convert），编辑走 pylabview（pylv_extract /
pylv_apply / pylv_rebuild / pylv_route），运行走 pylabview（ActiveX），读侧导出走 grpc。

## E1 — AIXML 补丁编辑环（新增 Scale 功能）

| 文件 | 字节 | 说明 |
|---|---|---|
| `batch-averager-scaled.aixml.xml` | 12628 | 补丁源：round4 `batch-averager.aixml.xml` + Scale 控件（uid 105）+ Accumulate 帧 Multiply 节点（uid 610） |
| `Batch Averager Scaled.vi` | 13457 | convert 产物。运行：Scale=1 → Average=3.0；Scale=2 → Sum=24 / Average=6.0 |
| `scaled-export.aixml.xml` | 22028 | grpc 回导（fromCache=false）：Scale=105、Multiply=610（uid_parent=350）、Add 改读 `610.x*y` 全部保留 |

## E2 — pylabview bundle 深编编辑环（常量字符串值）

| 文件 | 字节 | 说明 |
|---|---|---|
| `extract-batch-main.xml` | 30918 | pylv_extract 主清单（BD 4900 行 / FP 1317 行的索引），uid 坐标系证据 |
| `deep-edit-BDHb.xml` | 261638 | 深编后的 BD 堆：`<ConstValue>00000006496E69743B20</ConstValue>`（"Init; "）→ `00000006494E49543B20`（"INIT; "），sed 原位唯一匹配 |
| `batch-averager-deep.vi` | 13758 | pylv_rebuild 产物。运行：Average=3.0、Log="INIT; Load; …" |
| `deep-export.aixml.xml` | 21849 | grpc 回导：uid 1000/100/101/230-248/500-504、内联枚举全部保留 |

> 复现深编需完整 11 文件 bundle（extract 全量产物），此处仅保留主清单与被编辑的
> BDHb 两件关证；完整 bundle 可用 `pylv_extract` 对本 VI 重新生成。

## E3 — 多 VI 运行配方（round3 重放 + 首次取到数值）

| 文件 | 字节 | 说明 |
|---|---|---|
| `clamp-value.aixml.xml` | 2265 | round3 子 VI 源（重放用） |
| `clamp-demo.aixml.xml` | 5013 | round3 主 VI 源（重放用，Call target="Clamp Value.vi"） |
| `Clamp Value.vi` | 5619 | 子 VI，convert（openVI:true），持开于 addon 实例 |
| `Clamp Value Alt.vi` | 5623 | 备选目标，同样 openVI:true 生成 |
| `Clamp Demo Regen.vi` | 8468 | 主 VI 重放产物。运行：Final Value=10、Iterations=8、Saturated=true、History=[1.5,3,4.5,6,7.5,9,10,10] |

## E4 — retarget 写侧改写（运行侧未过，边界记录）

| 文件 | 字节 | 说明 |
|---|---|---|
| `Clamp Demo.vi` | 8482 | retarget 产物：引用改指 `Clamp Value Alt.vi`（link records 2 name + 2 path、caption 全改写；LabVIEW 自带导出 callTargets=["Clamp Value Alt.vi"]）。**运行 execState 0 未过**，见文档 §5.2 |
| `Clamp Demo.aliases` | 41 | 运行环境 IP 别名文件（GBK，"我的电脑 = 192.168.10.105"） |

## E5 — placeLabels 注释归位

| 文件 | 字节 | 说明 |
|---|---|---|
| `batch-averager-placelabels.vi` | 13754 | placeLabels 产物：FreeLabel uid 1000 bounds `(142,-22,161,155)` → `(586,566,605,743)`，clearance 68px，复跑 Average=3.0 正常 |

## E6 — conpane 边界对照证据

| 文件 | 字节 | 说明 |
|---|---|---|
| `ni-ref-FPHb.xml` | 48140 | NI 官方 `State Machine Fundamentals.vi` 的前面板堆：与本机生成 VI 同样 `<cons elements="12" />` 空数组 + conNum=-1，证明 conpane 失败是 LV2026 格式实情而非生成缺陷 |

## 复现要点

1. 补丁优先走 AIXML（validate 守门）；深编走 bundle（二进制载荷改编码值须保持
   长度前缀一致）；布局/引用走 pylv_apply（placeLabels 可靠、retarget 慎用、
   conpane 本机不可用）；
2. uid 坐标系跨 AIXML/RSRC 共享：读侧拿到的 uid 直接去写侧定位，新增元素 uid
   在回导中保真；
3. 多 VI 配方：子 VI convert（openVI:true）→ 主 VI convert → 运行，改引用也走它；
4. 切勿对已被 LabVIEW 加载的路径 rebuild（pylv_apply 的 closeActiveProject 步骤
   在本机 helperAixmlInvalid）。
