# 12 — Round6（一）：retarget 运行不过的根因——闭环第五轮悬案

> 标注惯例：【实测】= 本机一手测量数据；【源码】= 参考代码库/官方示例结论；【经验】= 通用工程结论。
> 环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1；生成走 grpc AIXML 通道
> （validate → convert），运行走 pylabview（ActiveX）。
> 产物：`research/artifacts/round6/retarget-evidence/`（清单见该目录 README）。

Round5 留下一个悬案：用 `pylv_route` retarget 改写 caller 的 subVI 引用后，caller 运行
`execState 0`（损坏），而同源重放再生的 caller 运行正常。本轮把根因定位到**字节级**，
并确立了一条**不依赖 retarget、稳定可跑**的多 VI 运行配方。

---

## 1. 结论（先给答案）

**retarget 运行失败的真正根因：被指向的目标 VI 的"内部 Name"与调用方所用的"链接名"
不一致，导致 name-only 链接悬空，caller 在保存/重编译时找不到可解析的子 VI。**

具体在本例：`Clamp Value Alt.vi` 文件末尾的 VI Name 段是 `"Clamp Value.vi"`（注意**不是**
文件名 `Clamp Value Alt.vi`）。retarget 把 caller 的链接记录改成了 `Clamp Value Alt.vi`，
但 LabVIEW 按 name 解析子 VI 时，目标内部叫 `Clamp Value.vi`，两边永不匹配 → 链接悬空
→ caller 成为 source-only VI，加载需重编译却又缺可解析子 VI → 报
*「无法执行该VI。必须使用LabVIEW完整版开发系统才可以解决该错误。」*。

> 这是 Round5 记录里"推测 rebuild 与 convert 产物的 subVI 链接解析结构有差异"的**否定**——
> 差异不在链接记录结构，而在**目标 VI 自身的 Name 字段**与链接名对不上。rebuild 与
> convert 产物的链接记录结构其实一致（见 §4）。

---

## 2. 证据链（逐环实证）

### 2.1 VI 内部 Name = 文件末尾长度前缀字符串【实测】

LabVIEW 的 VI 在 RSRC 里用一段 `Name` 区记录自己的名字，形式为 `长度字节 + 名字字符串`
（如 `\x0c` + `Sub Alpha.vi`）。`convert` 按 AIXML 的 `_name` 写这一段。因此一个 VI 的
"文件名"和"内部 Name"可以不同——前者是磁盘路径，后者是 LabVIEW 内存里解析子 VI 用的键。

对 `Clamp Value Alt.vi` 做二进制抽取（`x-alt/ClampValueAlt_*.bin`），其 Name 段明确是
`Clamp Value.vi`，与文件名不符。这就是 retarget 改写后链接仍悬空的直接原因。

### 2.2 改写链接名后能跑——证明是"按名解析"【实测】

把 caller 的链接名 sed 改成与目标内部 Name 一致（即指向真正叫 `Clamp Value.vi` 的那个），
生成的 `Clamp Demo Swapped.vi` **至今仍完美运行**（Final Value=10、Iterations=8、
Saturated=true、History 全对）。这证明内存里确实是**按 name 解析**子 VI，而非按路径或磁盘回退。

### 2.3 ActiveX 与 gRPC 落在同一个 LabVIEW 进程【实测】

早年"ActiveX 只认内存解析、磁盘回退"的假设被推翻。关键实验（Test M）：

- 生成 `Sub Zeta.vi`（5616 B）+ `Caller Zeta.vi`（8451 B）并运行正常；
- **运行中途把 `Sub Zeta.vi` 文件从磁盘移走**，caller 仍然完美运行。

说明子 VI 一旦经 `convert(openVI:true)` 进入 LabVIEW 内存，调用就完全在内存内解析，
与磁盘无关。进一步：用 `pylabview` 后端运行时的 LabVIEW 进程 PID（30516）与 gRPC 宿主
（Nigel 启动的 lvai 服务）是**同一个进程**——两条路线共享一个 LabVIEW 实例。所以
"ActiveX 走磁盘回退"的假说不成立，问题纯粹在**链接名能否匹配内存里已注册的名字**。

### 2.4 rebuild 产物从不进入"可按名解析"状态【实测】

Round5 的 exp-f/exp-g 失败，真实原因在此（此前误归因到磁盘回退）：

- `pylv_rebuild` 产出的子 VI（如 `Sub Alpha.vi`）**从不向 LabVIEW 注册"可按名解析"的状态**；
- `lvai_open_file` 只把 VI **按路径**载入内存（语义等同 Error 1357 的"按路径引用"），
  **不**注册可解析名；
- 决定性一击：`caller-p2.aixml.xml`（`target="Sub Alpha.vi"`）走 `convert` 直接报
  **Error 53 不支持管理器调用**——即 Call 节点要解析的子 VI 虽在内存（按路径）却不可按名解析。

对照：`convert(openVI:true)` 生成的子 VI 会注册为"可按名解析"状态（Call 能解析），这才是
稳定配方（见 §3）。

### 2.5 caller 损坏的直观表现【实测】

回导损坏的 `Caller F.vi`（`export-callerF.xml`）：其 `<Call target="Sub Alpha.vi" .../>`
**没有任何输入/输出端子**，且 3 条连线丢失（SR 右端自环 `232.value→232.value2`）。而正常的
`export-swapped.xml` 里 Call 端子齐全（`inputs="x:250.x+y,lo:212.value,hi:213.value"`
`outputs="clamped:260.clamped"`）。差异即来自链接悬空后 composer 无法接线。

---

## 3. 实用配方（不再依赖 retarget）【实测，三例全过】

| 步骤 | 操作 | 说明 |
|---|---|---|
| 1 | `convert` 子 VI，`openVI:true`（保持在编、注册可解析名） | 关键：openVI 让子 VI 进入"可按名解析"状态 |
| 2 | `convert` 主 VI（Call 的 `target` 写子 VI 文件名，**须与子 VI 内部 Name 一致**） | 同目录，convert 走 loadedSubVIs 解析 |
| 3 | `run_vi_and_read_values`，`backend="pylabview"` | 全链路运行取值 |

已验证三例：`Clamp Demo Swapped.vi`（retarget 改写名后重跑）、`Caller N.vi`（Kappa/
Caller，Final Value=10、Iterations=8、Saturated=true、History=[1.5,3,4.5,6,7.5,9,10,10]）、
`Caller Zeta.vi`（移走子 VI 仍能跑，证同进程）。

**铁律（写进方法论）**：多 VI 程序里，**调用方用的链接名必须与被调用 VI 的内部 Name 完全一致**；
若目标 VI 的 `_name` 与文件名不同（重命名/复制遗留），要么改 AIXML `_name` 让两者统一，
要么让 `convert` 按文件名写 Name（本机 composer 即如此）。retarget 只改链接记录、不动目标
内部 Name，因此遇到"文件名≠内部 Name"的目标必然悬空。

---

## 4. 链接记录结构对照（rebuild vs convert 一致）【实测】

回导对比 `Clamp Demo Retargeted.vi` 与重放生成的 `Clamp Demo Regen.vi`：两者的 subVI 链接
记录结构完全相同——`LVIN`→`VIVI`→`LinkSaveQualName` + `LinkSavePathRef`（空首段 + 文件名段，
TpVal=1）。**结构不是差异来源**，差异只在"目标内部 Name 是否匹配链接名"以及"目标是否处于
可按名解析状态"（rebuild 产物不注册）。

---

## 5. 失败的边界与已排除项

- **副本 / aliases / IP / 目标是否持开**：均已逐一排除，不是根因。
- **Error 语义对照**：1051 / 1357 都发生在 `Save:Instrument`，表示 Call **已解析**、只是
  保存撞名/撞路径；**Error 53** = 不支持管理器调用（子 VI 未处于可解析状态）。两者是判别
  "到底解析到没有"的免费探针。
- **retarget 仍可用场景**：当目标 VI 内部 Name == 文件名时，retarget 改写链接记录即可；
  一旦不等，必须用 §3 配方或先统一 `_name`。

---

## 6. 复现与产物索引

`research/artifacts/round6/retarget-evidence/`：

| 文件 | 说明 |
|---|---|
| `Clamp Demo Swapped.vi` / `Clamp Value.vi` / `Clamp Value Alt.vi` / `Clamp Demo Regen.vi` | 运行证据：Swapped 与 Regen 全值通过；Alt 即"文件名≠内部Name"的目标 |
| `export-callerF.xml` / `export-swapped.xml` | 决定性 diff：坏者 Call 无端子、三线丢失；好者端子齐全 |
| `Kappa.vi` / `Caller N.vi` / `kappa.aixml.xml` / `caller-n.aixml.xml` | openVI 配方例一（全值通过） |
| `Sub Zeta.vi` / `Caller Zeta.vi` / `zeta.aixml.xml` / `caller-z.aixml.xml` | Test M：移走子 VI 仍能跑，证 ActiveX=gRPC 同进程 |
| `caller-p2.aixml.xml` | `target="Sub Alpha.vi"` → convert 报 Error 53，证 rebuild/open_file 子 VI 不可按名解析 |

> 完整的中间稿（含 `x-*` 二进制 bundle 转储、memprobe 备份）保留在本地
> `labview-mcp-research/round6/retarget-diag/`，未全部入库以免仓库膨胀；上面是足以
> 复现结论的最小证据集。
