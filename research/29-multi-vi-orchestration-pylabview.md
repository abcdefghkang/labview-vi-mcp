# Round 20 — 多 VI 编排在 pylabview-only 闭环上跑通（P6 关闭），外加一个被改写的前提

> 承接 Round 17/19。本轮从一台**冷机**开始：`LabVIEW.exe` 没在跑、gRPC/Nigel 未启动
> （`lvai_status` 十一个候选端口全不可用，与 R17/R19 相同）。目标钉在看板优先级 **P6：
> 多 VI 版复杂程序**——顶层 VI 调用一个迭代子 VI + 一个汇总子 VI。全程未开 IDE、未开 Nigel，
> 整条 `author → convert(pylabview) → run(pylabview)` 闭环在冷机上无人值守跑通，两点验证
> 与手算值逐位吻合。另有一个副产品：无 IDE 挂载时用 60 行 stdio JSON-RPC 直驱服务器。

---

## 1. 一句话结论

**P6 关闭**：顶层 VI 经两个 `Call` 编排两个子 VI（一个 While Loop + 双 shift register 的
迭代器、一个纯除法的汇总器），`Sum/Count/Mean` 三个输出在 N=5 与 N=3 两个输入点上
与手算值逐位吻合（15/5/3.0 与 6/3/2.0）。多 VI 协作——数据两次穿越连接器窗格——
在 pylabview-only 路线上是**已验证可交付**能力。

**但 R6 配方的一条前提被改写**：pylabview composer 对 `Call` 的解析读的是**被调 .vi 文件
本身**，不要求子 VI 在编（round 6 的 `openVI:true` 是 gRPC/NI 路线的要求）。真正的硬
约束只剩**顺序**：先子 VI、后调用方。

---

## 2. 程序与验证

| VI | 角色 | 面板 | 内部 |
|---|---|---|---|
| `Accumulate N.vi` | 迭代子 VI | N 入(conIdx0) / Sum 出(1) / Count 出(2) | While Loop + 2 SR（LV020 方言，同 Accumulator） |
| `Mean Of Pair.vi` | 汇总子 VI | x 入(0) / y 入(1) / Mean 出(2) | 一个 `Divide`（`x`,`y`→`x/y`，round4 语料已验拼写） |
| `Multi VI Demo.vi` | 顶层编排 | N 入(0) / Sum(1) / Count(2) / Mean(3) 出 | 两个 `Call`，输出网号独立于 Call 的 uid（round6 已验形态） |

G0 全绿（三份 AIXML，0E/0W）。实跑（`backend:"pylabview"`，经 ActiveX，`runMs=3`）：

| N | Sum | Count | Mean | 判定 |
|---|-----|-------|------|------|
| 5 | 15 | 5 | 3.00000000000000 | **PASS**（逐位） |
| 3 | 6 | 3 | 2.00000000000000 | **PASS**（逐位） |

**为什么这能证明 Call 真的接上了**：若 Call 静默空接（LV014 陷阱），两个输入点下
Sum/Count 都只会是指示器默认 0、Mean 是 0/0。两个**不同**输入给出两个**不同**的
手算值，把"N 进"与"三值出"两个方向都钉死了。

---

## 3. 本轮四条新事实（全部实测）

### 3.1 `Call` 的解析在 pylabview 后端是**查磁盘**，不是查 IDE 内存

三个 convert 的 `composerReport` 直接写明（见 `artifacts/round20/convert-reports.json`）：

```
Call 'Accumulate N.vi'  <- <Element 'TypeDesc'> (pane 4833, 16 slots)
Call 'Mean Of Pair.vi'  <- <Element 'TypeDesc'> (pane 4833, 16 slots)
```

composer 是**从被调 .vi 文件里读出连接器窗格**（pane 4833、16 槽）来对上 Call 端子的；
同一响应里的 `openVINote` 明说 "Not opened: the pylabview backend writes the file and has
no road into the IDE"。两个子 VI 全程没进过 IDE 内存。

**修正后的配方**（比 round 6 更简单）：

| 路线 | 子 VI 前置条件 | 顺序 |
|---|---|---|
| gRPC/NI（validate/generate） | `openVI:true` 保持在编（R6/R16 上游一致） | 先子后主 |
| **pylabview** | **被调 .vi 文件存在于同目录即可，`openVI:true` 被接受且被忽略** | **先子后主（硬约束）** |

### 3.2 `lvai_ensure_labview` 能无人值守冷启动整条闭环

本轮起点 `LabVIEW.exe` 不存在。`lvai_ensure_labview(waitSeconds:45)` 自己把
**LabVIEW 2026 (64-bit)** 拉起（`startedByThisCall:true`、`launchMethod:"explorer"`、
自动清 LVAutoSave 防恢复对话框）。gRPC 服务没起来（要 Nigel，45 s 预算烧满返回
"starting"）——**这不影响任何一步**：run 走 ActiveX。冷机 → 出值的完整链：

```
lvai_ensure_labview → convert ×3 (pylabview, 0.7/0.7/1.6 s) → run ×2 (pylabview, 3 ms each)
```

R17 的"pylabview-only 闭环"前提是 "`LabVIEW.exe` 在跑"；本轮把它前推到
**"`LabVIEW.exe` 不在跑也行"**——闭环对环境的要求进一步降为一台装了 LabVIEW 的机器。

### 3.3 int→DBL 类型提升**穿越子 VI 边界**且 composer 接受

`Mean Of Pair.vi` 里 int32/int32 过 `Divide` 出 DBL（LabVIEW 除法语义），顶层 VI 把这个
DBL 网穿过自己的连接器窗格接到 `double` 指示器——composer 接受、run 返回
`3.00000000000000`。**跨窗格的类型提升是可用能力**（此前语料全是同型网）。

### 3.4 无 IDE 挂载时可用 stdio JSON-RPC 直驱服务器（新工具 `scripts/mcp_call.py`）

R19 会话遭遇 COM 整场不可用；本轮更进一步——**agent 的工具列表里根本没有 lvai_*/**
（MCP 服务器没挂载）。解法是 60 行纯标准库 Python：spawn `LabVIEWMCP.exe`、initialize
握手、`tools/list`、`tools/call`，逐行收发 newline-delimited JSON-RPC。整轮 9 次调用
全部经它完成。**服务器本身就是可执行文件**——"能不能调到工具"从此不再依赖 IDE。

---

## 4. 度量数字（可直接引用）

| 指标 | 值 |
|---|---|
| 冷启动到首个 run 出值 | ensure 45 s（烧满预算）+ convert 3.1 s + run 3 ms |
| convert 单 VI | 698–1588 ms（与 R15 的 0.5–1.5 s 吻合） |
| run（ActiveX，`runMs`） | 3 ms |
| 实测工具面 | **99**（94 `lvai_*` + 5 `pylv_*`），与 R11 一致（本机 v2.0.1） |
| G0 体检 | 3/3 份 0E/0W |
| 连接器穿越次数 | 每个值 2 次（出子 VI 窗格 → 进顶层窗格） |

---

## 5. 上游生态增量（同日网络调研，供 P3/P4/P5/P10 决策）

| 项 | 状态 | 对本研究的含义 |
|---|---|---|
| 上游版本 | **v2.3.1（2026-10-28）**，v2.2.0 后隔天连发 8 版 | 本机 v2.0.1 落后两代；P3 升级窗口成熟，但**升级会覆盖 resolve.py 补丁，必须重打** |
| 工具面 | 上游 114 工具/23 RPC（本机 99） | 新增 `lvai_layout_diagram`（自研布局引擎，2026-10-16 起内置于所有写入流程）与 `lvai_error_list`（Broken VI List 读"为什么坏"）——**P4/P5 上游已交付** |
| 类说明符常量 / 运行时动态派发 | **上游 AIXML 仍无类端子语法**（`ref{UDClassInst}`，类身份不编码进类型串；动态端子仅 `connection:"dynamic"` 标注靠 `add_class_method` 布线） | **P10 维持"表达不出来"判定**；P1 的 IDE 手搭调用方仍是唯一路径 |
| `lvai_apply_aixml_to_vi` | 上游已封死（改走重新生成） | 与 R5/R11 的编辑侧结论一致：改引用走 AIXML 重放，不做原地 patch |
| 其他桥接方案 | NI Nigel（官方、IDE 内嵌、不可外接）；JanGoebel Toolkit（VIPM+HTTP，早期）；lvkit（pylabview 净室衍生，**只读**）；LabVIEW CSM MCP（未验证） | **能从零生成复杂 VI 的仍只有 Zuehlke 方案**——本研究的对象选对了 |
| 方法论文献 | SimuGen（Simulink 多智能体）、ComfySearch（RL 探索节点图）、Simulink Agentic Toolkit（2026-04 官方） | 共性 = 文本→中间图→类型/语义校验→回读渲染验证，与本研究 G0–G5 闸门同构，可互引 |

---

## 6. 对看板的修正

- **P6 关闭**（本档 + `examples/multi-vi-demo/`）。
- 能力地图 A 档新增：**多 VI 编排（顶层 Call ×2，两值穿越窗格，类型提升跨界）**；
  **冷机无人值守闭环**（ensure_labview 起 LabVIEW）。
- R6 多 VI 配方按 §3.1 细化为双路线版本。
- 新工具：`scripts/mcp_call.py`（无 IDE 复现入口）；`tools/lvrule_check.py` 无新增规则
  （本轮没有新的静默失败形状——所有写法一次过）。

## 7. 下一步

1. **P2/P7**（测试层）仍是最大空白；上游 `lvai_run_caraya_tests` 已上线，装 Caraya 后
   先跑 `generate_test(pylabview)`，再看 `lvai_typedef_tree` 崩溃是否复现。
2. **P3** 升级上游 v2.3.1 → `lvai_dump_schema` diff 114/23 → 重打 resolve.py → 首测
   `lvai_layout_diagram`（R19 之前的 AIXML 全部没有布局信息，这个工具补的是 AI 产物
   最后一块"人看不懂"的短板）。
3. **P1**（父类型窗格调用方）维持：上游没补类端子语法之前，只能 IDE 手搭样本。
4. `mcp_call.py` 补批量/回放模式，把"一轮 = 一份 JSON 计划 + 一次运行"变成可归档形态。
