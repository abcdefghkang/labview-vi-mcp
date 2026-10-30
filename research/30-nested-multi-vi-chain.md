# Round 21 — 三层嵌套多 VI 链：Call 进结构、深度二，外加 batch 直驱定型

> 承接 Round 20。R20 关闭了 P6（顶层 Call ×2 编排两个子 VI），留下的问题是：Call 能不能
> **出现在结构内部**、能不能**嵌套多层**——即"子 VI 自己也是调用方"的三层链。本轮目标就是
> 这条纵深：孙 VI（`Double It.vi`，纯乘法）→ 子 VI（`Sum Of Doubles.vi`，While Loop 内
> Call 孙 VI 累加）→ 顶层（`Nested Chain Demo.vi`，Call 子 VI）。全程无 IDE、未开 Nigel，
> 整轮 8 次工具调用全部经 `mcp_call.py` 的新 **batch 模式**直驱完成。

---

## 1. 一句话结论

**嵌套 Call 链全通**：三层链（顶层 → 子 → 孙，深度 2）在 pylabview-only 路线上**一轮通过**——
三个 convert 全部 `executable:true`，两点实跑与手算逐位吻合（N=3 → Sum 12 / Count 3；
N=4 → Sum 20 / Count 4）。**Call 可以出现在 While Loop 内部**，被调方自己也可以含 Call；
配方与 R20 完全一致（被调 .vi 在同目录、先孙后子后顶、输出网号独立于 uid），**没有新方言**。

副产品：`mcp_call.py` 落地 **batch 模式**，"一轮 = 一份 JSON 计划 + 一次运行"成型；G0 的
`net-unconsumed` 检查第一次在实战中提前抓住悬空输出。

---

## 2. 程序与验证

| VI | 层 | 面板 | 内部 |
|---|---|---|---|
| `Double It.vi` | 孙（深度 2） | x 入(0) / Doubled 出(1) | 一个 `Multiply`（`x`,`y`→`x*y`） |
| `Sum Of Doubles.vi` | 子（深度 1） | N 入(0) / Sum 出(1) / Count 出(2) | While Loop + 双 SR（LV020 方言）+ **循环内 Call** `Double It.vi` |
| `Nested Chain Demo.vi` | 顶层 | N 入(0) / Sum 出(1) / Count 出(2) | 一个 `Call` → `Sum Of Doubles.vi` |

G0 全绿（3 份 0E/0W，见 §4.3 的一段插曲）。实跑（`backend:"pylabview"`，经 ActiveX）：

| N | Sum | Count | 手算 | 判定 |
|---|-----|-------|------|------|
| 3 | 12 | 3 | 2+4+6=12；3 次 | **PASS**（逐位） |
| 4 | 20 | 4 | 2+4+6+8=20；4 次 | **PASS**（逐位） |

**为什么这能证明嵌套 Call 真的接上了**：Sum 值在被读到之前穿越**四道**窗格边界
（孙 VI 出、N 次；子 VI 出；顶层出）。若循环内 Call 静默空接（LV014 陷阱），每次迭代加 0，
两个输入点 Sum 都会读 0 而 Count 照常是 N——Sum=12/20 且 Count=3/4 把**两跳 Call**都
耦合进了活数据路径。两个不同输入给出两个不同手算值，常量或默认值都过不了这两点。

---

## 3. 本轮四条新事实（全部实测）

### 3.1 Call 在结构内部照常 compose，嵌套深度无额外方言

子 VI 的 composer 报告（`artifacts/round21/convert-reports.json`）：

```
Structure 'While Loop' <- buip.xml
...
Call 'Double It.vi' <- <Element 'TypeDesc' at 0x...> (pane 4833, 16 slots)
...
wires routed: 13, left generic: 0
```

Call 与普通节点同列，从被调 .vi **文件**的 TypeDesc（pane 4833、16 槽）解析——与 R20
顶层 Call 的报告形态逐字相同。`wires routed: 13`（比 R20 同形 Accumulate N 的 12 多 1：
多了 Call 的 Doubled 网）。R6 配方的三要素（同目录、先子后主、输出网号独立于 Call uid）
**原样适用**，不因 Call 在结构内而变。

### 3.2 batch 直驱定型：一轮 = 一份 JSON 计划 + 一次运行

`scripts/mcp_call.py` 新增 `batch` 模式：`--plan plan.json` 读 JSON（数组或
`{"label","steps"}`），**一次握手顺序执行 N 个工具调用**，逐条把 verbatim 结果 + 耗时记进
合并 transcript；失败步骤不中断（后续步骤的真实失败形态也是证据）。本轮实际使用：

```
plan.json（6 步：ensure → convert×3 → run×2）  → transcript.json（10.2 KB，allOk:true）
plan-extract.json（2 步：pylv_extract×2）       → transcript-extract.json（4.2 KB，allOk:true）
```

两个 plan、两次握手、8 次调用。**同一计划当天复跑一遍**：6+2 步全部再次 ok、数值与
Call 解析逐项一致（viExisted:true 覆盖写正常）——batch 计划是**幂等可重放**的，首轮总墙钟
约 20 s、复跑约 5 s。**复现一轮不再需要 IDE、不需要人记步骤**——计划文件进版本库，
transcript 就是运行证据。

### 3.3 `ensure_labview` 的"已在跑"形态：幂等，探测成本可变

R20 冷机形态是 `startedByThisCall:true`、45 s 烧满。本轮 LabVIEW.exe 已在跑，返回的是
另一种形态（transcript 步骤 1）：

```
"state": "ready", "startedByThisCall": false, "discoveredVia": "LabVIEW.exe listener",
"port": 11557, "applicationLanguage": "Chinese", "waitedMs": 14199
```

幂等返回 `ready`，但**探测成本不恒定**：首轮 `waitedMs` 14199（14.2 s），同日复跑同一计划
只花 207 ms——首轮的 14 s 更像首次枚举 listener 的冷探测，不是固定开销。对 batch 计划的
含义：ensure 放第一步、`waitSeconds:45`、客户端超时 ≥120 s，冷/热两种形态都装得下。
run 照走 ActiveX（`runMs` 3/2 ms），与 gRPC 端口死活无关。

### 3.4 G4 铁证：Call 链接写进了磁盘文件

`pylv_extract` 把两个写入的 .vi 抽回 XML bundle（`plan-extract.json`），两份 BDHb/CONP
描述符里都有被调方全名（已存档 `artifacts/round21/`）：

```
extract-top/NestedChainDemo.xml   →  <LinkSaveQualName><String>Sum Of Doubles.vi</String>
extract-child/SumOfDoubles.xml    →  <LinkSaveQualName><String>Double It.vi</String>
```

结合实跑出值，"链接在文件里"（G4）与"链接活着"（G5）两个层面都被独立证明——
不是依赖 run 通过反推链接存在。

---

## 4. 度量数字（可直接引用）

| 指标 | 值 |
|---|---|
| batch 总览 | 2 个计划 / 8 次调用；首轮与复跑均全绿；首轮墙钟约 20 s、复跑约 5 s（幂等可重放） |
| ensure（已在跑形态） | 首轮 waitedMs 14199；复跑 207 ms——幂等 ready，探测成本不恒定 |
| convert 单 VI（内部耗时，复跑） | 599 / 982 / 950 ms（首轮 630/981/948，两轮一致） |
| run（ActiveX，复跑） | runMs 3 与 2 ms（首轮 5/4 ms）；batch 步耗时约 0.5 s |
| G0 体检 | 3/3 份 0E/0W（首轮 0E/1W，见 §4.3） |
| 数据穿越窗格次数 | Sum 值共 4 道（孙出 + N 次子出 + 顶层出） |
| 子 VI 程序框图规模 | While Loop + 2 SR + 2 Add + 1 Call + Greater Or Equal?，13 条线 |
| 描述符证据 | 两份 BDHb（38.5 KB / 10.7 KB）`LinkSaveQualName` 各写明被调方 |

### 4.3 一段插曲：G0 抓住悬空输出

子 VI 首稿没有 Count 指示器，迭代 SR 的读回输出（`4291.final_iter`）悬空——
`audit_aixml.py` 报 `WARN net-unconsumed uid=4291 Right`。按 R20 的 Accumulate N 形态
补上 Count 输出后 0E/0W。这条自研规则（此前从未在实战中命中）恰好把两点验证变得更强：
没有它，悬空不报错，但验证少一个维度。

---

## 5. 对看板的修正

- **不关闭任何看板 P 项**——看板 P7 是"测试层判据脚本"（Caraya JUnit 判据），本轮没动它；
  本轮是 R20 多 VI 编排的**纵深推进**（嵌套 Call 链），能力地图 A 档新增
  **三层嵌套多 VI 链（Call in loop，深度 2，四道窗格）**（本档 + `examples/nested-multi-vi-demo/`）。
- 多 VI 配方（R6/R20 版）补一句：Call 出现在结构内部不改变三要素；被调方自身含 Call
  无额外要求。
- 新工具形态：`scripts/mcp_call.py batch`（`--plan` / `--out`，失败不中断）。

## 6. 下一步

1. **P2/P7**（测试层）仍是最大空白：装 Caraya → `generate_test(pylabview)` →
   `lvai_run_caraya_tests` 首测；无框架自包含测试可先挂进 batch 计划当 G5 固定步骤。
2. **P3** 升级上游 v2.3.1：`dump_schema` diff 114/23 → 重打 resolve.py 补丁 →
   首测 `lvai_layout_diagram`（R19 前的产物都没有布局信息）。
3. **P1**（父类型窗格调用方）维持原判：等上游类端子语法，或 IDE 手搭样本。
4. 工具化收尾：batch 计划可以把 **G0 体检 + convert + run + 断言** 串成单计划——
   断言目前靠人读 transcript；下一步给 `mcp_call.py` 加 `expect` 字段，让 batch
   自己判 PASS/FAIL。
