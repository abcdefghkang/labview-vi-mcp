# 11 — Round5：pylabview 编辑链与"读侧坐标 + 写侧补丁"闭环

> 标注惯例：【实测】= 本机一手测量数据；【源码】= 参考代码库/官方示例结论；【经验】= 通用工程结论。
> 环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1；生成走 grpc AIXML 通道
> （validate → convert），编辑与运行走 pylabview（ActiveX，pylv_extract/apply/rebuild/route），
> 读侧导出走 grpc（convert_vi_to_aixml）。
> 产物：`research/artifacts/round5/`（清单见该目录 README）。

Round4 解决了"从零生成复杂 VI"（状态机 + .ctl + 读侧回导）。Round5 回答下一个问题：
**生成之后怎么改？** AI 不可能每次都从零重写——真实工作流是"在已有 VI 上做增量修改"。
本轮把 pylabview 编辑链（pylv_extract → 编辑 bundle → pylv_rebuild，以及 pylv_apply 的
外科手术操作）完整跑通，建立了**"读侧坐标（uid）+ 写侧补丁"**的编辑循环方法论。

---

## 1. 路线决策矩阵：什么时候用哪套表示

Round3-4 已经确立双服务器格局（grpc 管生成、pylabview 管运行），Round5 补上**编辑**维度。
三条编辑路线的实测分工【实测】：

| 场景 | 路线 | 依据 |
|---|---|---|
| 自包含生成 VI（无本地 subVI 调用） | **AIXML 补丁**：改 `.aixml.xml` → validate → convert | E1 实验：validate 0 → convert 13457 B → 运行语义正确（见 §3） |
| AIXML 表达不了的构造 / 深编细节（常量值、注释位置、连接器） | **pylabview bundle 编辑**：pylv_extract → 改 XML/bundle → pylv_rebuild | E2 实验：BDHb 内常量值 sed 替换 → rebuild 13758 B → 运行语义正确（见 §4） |
| 引用本地 subVI 的 caller（name-only 链接） | **AIXML 重放配方**：先生成子 VI（openVI:true）再生成 caller；retarget 仅改链接记录 | E3/E4 实验：重放配方运行成功取到全值；retarget 写侧成功但运行侧未过（见 §5-6） |

**决策规则（写进方法论）**：
1. 先问"这个改动 AIXML 能不能表达"。能表达→走 AIXML 补丁环（有 validate 守门，最安全）；
2. 不能表达（或要知道 AIXML 里不存在的坐标，如注释像素位置）→ 走 pylabview bundle 环；
3. 带 subVI 引用的程序→绝不手抠 bundle 里的链接记录，用 AIXML 重放配方或 pylv_route retarget。

## 2. 关键基础设施：两套表示共享同一套 uid 坐标系【实测】

编辑循环成立的前提是"读侧定位"和"写侧补丁"说的是同一个坐标。本轮用逐一对照证实：

| AIXML 元素 | RSRC 堆（BDHb/FPHb）对应 |
|---|---|
| `Structure uid=200`（While Loop） | `whileLoop` 结构体，uid 200 |
| `Structure uid=300`（Case） | `select` 结构体，uid 300 |
| `CaseFrame uid=310/350` | 帧对象（diag 310/350） |
| `ShiftReg uid=230/231` | rSR/lSR 对，uid 230/231 |
| `FreeLabel uid=1000` | `SL__arrayElement class="label" uid="1000"` |
| `Node uid=610`（补丁新增 Multiply） | 回导后仍在 `uid_parent="350"`（Accumulate 帧）内 |

**结论**：AIXML 的 uid 就是 RSRC 堆的 uid。读侧（pylv_extract / convert_vi_to_aixml）
拿到的 uid 可以直接去写侧（AIXML 补丁或 bundle 编辑）定位——**这就是"读侧坐标 +
写侧补丁"闭环的地基**。round4 已证回导 uid 100% 保真；round5 进一步证明该保真度
对**编辑后**的 VI 同样成立（E1/E2 的回导文件中，新增的 Scale=105、Multiply=610、
移动后的 label=1000 全部按原 uid 出现）。

## 3. 编辑环 E1：AIXML 补丁（新增 Scale 功能）【实测】

对 round4 的 Batch Averager 状态机做功能增量：每个样本累加前先乘一个 Scale 系数。
补丁只改两处（`batch-averager-scaled.aixml.xml`，round4 源文件的差量）：

```xml
<!-- 新增控件（根级） -->
<Control _name="Scale" ... outputs="value:105.value" type="double" uid="105" value="1"/>
<!-- Accumulate 帧（uid 350）内：新增 Multiply，Add 的 y 输入改读它 -->
<Node _name="Multiply" inputs="x:243.item,y:105.value" outputs="x*y:610.scaled" uid="610" uid_parent="350"/>
```

全链路结果：

| 步骤 | 结果 |
|---|---|
| `lvai_validate_aixml` | **errorCode 0** |
| `lvai_convert_aixml_to_vi` | 成功，`Batch Averager Scaled.vi` 13457 B |
| pylabview 运行 | Scale=1 → Average=3.0（与原语义一致）；Scale=2 → Sum=24 / Average=6.0（= 2×均值，补丁语义正确） |
| grpc 回导 | `scaled-export.aixml.xml`（22028 B，fromCache=false）：Scale=105、Multiply=610（uid_parent=350）、Add 改读 `610.x*y` 全部保留 |

**结论**：AIXML 补丁是功能增量的首选路线——补丁即差量 diff，validate 守门，
回导验证闭环。uid 手工选取避开了 round3 发现的 10-35 保留区（新 uid 一律 ≥100）。

## 4. 编辑环 E2：pylabview bundle 深编（改常量字符串值）【实测】

有些改动 AIXML 表达不了，或需要动 AIXML 抽象掉的细节。选最小深编目标：
日志字符串常量 `"Init; "` → `"INIT; "`（ round4 状态机 Init 帧写入的日志前缀）。

流程：`pylv_extract`（batch-averager-copy.vi → 11 文件 bundle）→ 定位 → `pylv_rebuild`。

**定位方法**（可复用的读数知识）：RSRC 堆里字符串常量值编码为
**4 字节小端长度前缀 + ASCII hex**：

```xml
<!-- BDHb.xml，唯一匹配 -->
<ConstValue>00000006496E69743B20</ConstValue>   <!-- "Init; "：6 字符 + 3B 20 = '; ' -->
<!-- sed 原位替换为 -->
<ConstValue>00000006494E49543B20</ConstValue>   <!-- "INIT; " -->
```

全链路结果：

| 步骤 | 结果 |
|---|---|
| pylv_extract | 11 文件 bundle（main xml 551 行、BDHb 4900 行、FPHb 1317 行 + bin/png），annotate 注释标出终端名 |
| sed 替换 ConstValue | 唯一匹配，长度前缀不变（6 字符 → 6 字符） |
| `pylv_rebuild` | `batch-averager-deep.vi` 13758 B |
| pylabview 运行 | Average=3.0（功能未坏），Log="INIT; Load; …"（深编生效） |
| grpc 回导 | `deep-export.aixml.xml`（21849 B）：uid=1000 标签、控件、SR、枚举类型全部保留 |

**结论**：bundle 深编成立且验证闭环完整。**要点**：改二进制载荷里的编码值时
保持长度前缀一致（或同步改前缀），优先 sed 原位替换保证唯一匹配；rebuild 不要求
LabVIEW 运行（纯文件操作），但运行验证必须走 pylabview/grpc 让真 LabVIEW 加载。

## 5. pylv_apply 三类外科手术操作【实测】

`pylv_apply` 不需要写 XML，直接对 VI 做结构化操作；无操作时退化为只读 inspect
（保留 bundle 供检视）。本轮实测两类成功、一类受环境限制：

### 5.1 placeLabels：注释归位【成功】

把 FreeLabel（uid 1000，"Batch averager state machine"）从 (142,-22) 移到
While Loop 旁 (586,566)。前后 extract 对照，bounds 从
`(142, -22, 161, 155)` 变为 `(586, 566, 605, 743)`（uid 1000 不变），
clearance 68 px。**改后 VI 复跑正常**（Average=3.0）。
这是"读侧坐标（extract 读出 bounds）→ 写侧补丁（placeLabels 给新坐标）"的最小实例。

### 5.2 retarget：改写 subVI 引用【写侧成功，运行侧未过】

`Clamp Demo.vi`（round3 产物，调用 `Clamp Value.vi`）的引用改指
`Clamp Value Alt.vi`。pylv_route/apply 的 retarget 实测改写：

- link records：2 条 name + 2 条 path 记录全部改写；
- caption 替换；
- LabVIEW 自带导出佐证：`callTargets=["Clamp Value Alt.vi"]`；
- 文件 8462 → 8482 B。

**但运行验证未过**：retarget 后的 caller 走 pylabview 运行仍报
`viNotExecutable`（execState 0，linker error）。排查已排除：副本/aliases/IP
均非因（本机确有 192.168.10.105）。关键对照实验：把新目标
`Clamp Value Alt.vi` 用 round3 重放配方（convert openVI:true）生成到
addon 实例持开后，retarget 版 caller **仍 execState 0**；而同路线重生成的
`Clamp Demo Regen.vi` 运行成功并取到全值（Final Value=10、Iterations=8、
Saturated=true、History=[1.5,3,4.5,6,7.5,9,10,10]）。

**结论（边界记录）**：name-only 链接的 caller，经 pylv-rebuild 写侧改写引用后，
在本机无法通过运行级验证；convert 路线再生的 caller 可以。推测 rebuild 产物与
convert 产物在 subVI 链接的解析结构上存在差异（如链接记录的路径形态或
loadedSubVIs 登记方式），列入下次方向。**工程建议：改引用的需求优先用
AIXML 重放配方（§6），retarget 作为写侧备查手段。**

### 5.3 conpane：连接器面板编辑【本机不可用】

`pylv_apply` 的 conpane 操作报 `no <cons> array in the front-panel heap`。
根因不是生成缺陷——对照实验【实测】：

| 文件 | FPHb 连接器表示 |
|---|---|
| 本机生成的 `Batch Averager.vi` | `<cons elements="12" />`（空数组）+ 7 处 `<conNum>-1</conNum>` |
| NI 官方 `State Machine Fundamentals.vi` | 同样 `<cons elements="12" />` + 8 处 conNum=-1 |

即 **LV2026 的 FPHb 就是这么表示连接器的**（pylabview 提取器对空 cons 数组
无法 materialize），官方示例一模一样。叠加已知环境问题（grpc
`lvai_connector_pane` 助手 helperAixmlInvalid），结论：
**本机不要依赖 conpane/连接器面板测量；连接关系在生成时用 AIXML 的
`connection="recommended"` 属性一次到位**（round4 实测该属性正常生效）。

## 6. 多 VI 运行配方复现与扩展【实测】

把 round3 的多 VI 配方（先生成子 VI openVI:true 保持子在编，再生成主 VI）
原样重放并首次取到具体数值：

| 文件 | 字节 | 说明 |
|---|---|---|
| `Clamp Value.vi` | 5619 | 子 VI，convert（openVI:true），持开于 addon 实例 |
| `Clamp Value Alt.vi` | 5623 | 备选目标，同样 openVI:true 生成 |
| `Clamp Demo Regen.vi` | 8468 | 主 VI 重放产物，pylabview 运行成功 |

运行读数：Final Value=10、Iterations=8、Saturated=true、
History=[1.5,3,4.5,6,7.5,9,10,10]（与手推一致：Start 1.5，每轮 +1.5，
第 7 轮起饱和在 10）。

**这补齐了 round3 遗留的缺口**：当时多 VI 只能验证"能跑"，本轮验证"跑对"。

## 7. 环境边界清单（Round5 新增）

1. **conpane / grpc 连接器面板探针双坏**（§5.3）：LV2026 空 cons 表示 +
   helperAixmlInvalid。规避：生成时写 `connection=` 属性。
2. **pylv_apply 的 closeActiveProject 步骤 helperAixmlInvalid**：工具会自动继续
   （VI 未加载时安全）。**教训：切勿对已被 LabVIEW 加载的路径做 rebuild**，
   先 close 再操作。
3. **retarget 后 caller 运行不过**（§5.2）：name-only 链接 + rebuild 文件的
   组合在本机不可运行验证；用 AIXML 重放配方替代。
4. GBK 中文报错经 gRPC 崩 .NET 客户端（round3 已知，本轮复现在 pylv_apply
   的项目关闭步骤）。

## 8. Round5 结论汇总（可复用经验）

1. **编辑循环方法论**：读侧（extract/回导，拿 uid 坐标）→ 写侧（AIXML 补丁 或
   bundle 深编 或 pylv_apply 操作）→ 运行验证 → 回导核对。四步闭环全通路实测。
2. **uid 坐标系跨表示共享**是这一切的地基：AIXML uid = RSRC uid，补丁新增元素
   的 uid 在回导中保真（105/610/1000 三例）。
3. **改动分级选路线**：能 AIXML 表达→补丁（有 validate 守门）；不能→bundle 深编
   （二进制载荷改编码值，保持长度前缀）；纯布局/引用→pylv_apply 操作
   （placeLabels 可靠，retarget 慎用，conpane 本机不可用）。
4. **多 VI 配方**：子 VI convert（openVI:true）→ 主 VI convert → 运行，
   是引用本地 subVI 的程序唯一稳定路线；改引用也走它（重放），不手抠链接。
5. 字符串常量深编的编码格式：4 字节长度前缀 + ASCII hex，可 sed 级替换。

## 9. 下次方向

1. **retarget 运行不过的根因**：对照 pylv-rebuild 与 convert 两种 caller 的
   subVI 链接记录结构差异（link records 的 path 形态、loadedSubVIs 登记），
   或为 retarget 增加"path 承载链接"的写法，让改写后的 caller 可运行。
2. **状态机模板参数化**：状态表（状态/转移条件/寄存器动作）→ AIXML 生成器，
   让 AI 从表格直接产状态机（round4 遗留）。
3. `lvai_bind_pane_typedef` 类成员上下文扩测，打通 .ctl 绑定（round4 遗留）。
4. 数组/字符串/簇操作节点、事件结构（DQMH 前置）覆盖面试探。
5. 未解决边界：引用**未打开**的既有 subVI（生产主流形态，validate/convert
   均拒绝）——可能需要 pylv_extract 读侧 + AIXML 重生成的混合路线。
