# Round 12 — 边界、事件超时与"面板保留"移植：三条只在真机上才看得见的定律

> 环境：LabVIEW 2026 26.3.1f1 中文版（up 29 min，gRPC 44136）、LabVIEWMCP **2.0.1**（77eb0b22）、
> pylabview 3.12 x64（pinned 6976864）。仍是 v2.0.1，本轮没有升级——升级被放到了最后（见 §8）。
> 全部结论均为**本机实测**，每个数字都能用 `artifacts/round12/` 里的文件复现。

---

## 0. 一页结论

| # | 结论 | 证据 | 代价 |
|---|---|---|---|
| 1 | **跨结构边界的线必须显式打隧道**，而这条规则离线闸门里一直缺着 | 原件 0E/5W 过闸，composer 连拒两次（`net '4203.ms'` / `net '4205.one'`） | 2 个往返 |
| 2 | **两个 composer 的边界语义相反**：NI 转换器自动补隧道（43→154），pylabview 直接拒 | 同一份 `round4/batch-averager.aixml.xml`：grpc `errorCode 0` / pylabview `composerRefused` | 1 个往返 |
| 3 | **事件结构的帧和事件注册都活着**（3 个 EventSpec 逐字段正确），**只有超时端子写不进去** | 回导 BDHb：`EventNodeEvents elements="3"`；`eventTimeOut` dco 无任何 signal 引用 | 1 次回导 |
| 4 | 因此 **` Timeout ` 帧永不触发**：500 ms 超时、2.2 s 运行、`Timeouts=0`，无任何报错 | ActiveX 运行快照 | 1 次运行 |
| 5 | **`lvai_graft_diagram` 在本机只能用 pylabview**：grpc 的 helper 被拒；pylabview 全绿并跑出正确结果 | grpc `helperAixmlInvalid`；pylabview 7 个 swap 全 `errorCode 0`、`execState 1`、运行 `Sum=12/Average=4/Stop` | 6 个往返 |
| 6 | **helper 家族在本站整体失效**：4 个 helper 文档被拒（78 个里点名的 4 个），连带 4 类工具 | `lvai_run_and_read_typed.xml`、`lvai_run_for_ms.xml`、`lvpane_probe.xml`、graft 的核心 helper | — |
| 7 | **测试层卡在 `noTerminals`**：生成的 VI 读不到连接器窗格端子 | `lvai_generate_test` → `failedAtStep: placeholder` | 1 个往返 |

一句话：Round 11 弄清"工具面是什么"，Round 12 弄清**同一份文档在不同 composer 下的命运不一样**，
以及**哪些能力在中文版 LV2026 上只能走 pylabview**。

---

## 1. 起点：Round 7 那个从未跑过的探针

`artifacts/round7/next-probes/p5-valuechange-timeout-frames.aixml.xml` 写在 2026-10-22 的离线会话里，
注释里自己标着 `UNVERIFIED`，Round 11 的 LV010 顺手修掉了它的一个 `description` 缺陷，但**从未转换过**。

本轮第一次把它送进 composer，连拒两次：

```
errorCode 2  net '4203.ms' crosses a diagram boundary without a tunnel
errorCode 2  net '4205.one' crosses a diagram boundary without a tunnel
```

而本机闸门对同一份文件给的是 **0 error / 5 warning**（warnings 全是 `net-unconsumed` 与
`comment-may-be-clipped`，都是面板控件在事件结构里"不接线"的正常现象）。

### 1.1 两个缺陷，一个原因

| 缺陷 | 写法 | 为什么错 |
|---|---|---|
| a | 根级 `<Constant _name="Timeout ms" uid="4203" uid_parent="root">` 喂**事件结构**的 `In1` 隧道 | 事件结构在 While Loop 里，这根线要从根级穿进循环：循环上没有隧道 |
| b | 根级 `One` / `False` 被**事件帧内**的 `Add` 与 `Out` 隧道消费 | 帧是结构内部再一层，每个帧要有自己的隧道半截；根级的常量干脆得搬进帧里 |

修法（`artifacts/round12/p5-valuechange-timeout-frames-v2.aixml.xml`）：
`Timeout ms` 下沉到 While Loop 内；`One` / `False` 下沉到各自帧内，超时帧另用 4381/4382 两个新 uid。

修完：`errorCode 0`、**execState 1**、8,809 字节、`wired 23`。

> 这条规则本身的表述要精确：**一根线不能隐式穿过结构边界**。外层结构要有一个"外半截"隧道，
> 每个帧要有一个"内半截"，两半用 `_id` 对齐、各自只带一个方向（外半截 `inputs`，内半截 `outputs`）。
> 帧不用这个值时也必须写 `outputs="value:"`——空网，但半截得在。

### 1.2 闸门补丁：LV012

`tools/lvrule_check.py` 增 **LV012 `net-crosses-boundary`**，要点是**容器的判定不能照抄 `uid_parent`**：

- Tunnel 的**外半截**画在"拥有它的结构的父容器"里，**内半截**画在帧里；
- ShiftReg 的 `<Left>` / `<Right>` **不在检查范围**：左端种子本来就必须来自循环外（LV003 的另一面），
  把它们算成跨边界会让每个正确的循环都报错（第一版正是如此，见 §1.3）；
- 追源时**沿隧道改名**：帧内读 `INNER`，靠 `_id` 找到结构上的外半截，取出它的 `inputs` 作为外层的网名继续往上走。

判别力（同一份文件的前后两版）：

```
原件  6 error (5×LV012 + 1×LV013)
v2    1 error (1×LV013)      ← 剩下这条是 §2 的真结论，不是缺陷
```

### 1.3 闸门自己也被抓了一次

第一版 LV012 对正确文件误报 2 条（ShiftReg 种子），修掉之后全库复扫，出现 26 条 LV005——
点开一看是 `Structure 'Case Structure'` 被当成 While Loop 报。

原因很土：我用一次 `Edit` 把 `# LV005 - While Loop stop.` 这行注释和下一行 `if` 拼成了一行，
`if` 落进注释里，LV005 从那时起对**每个 Structure** 生效。修好后全库 grpc 口径 **26E/269W**，
与 Round 11 的 26E 基线一致（新增的 LV013 两条正好抵掉被误报掉的一条）。

> 教训写成工具约定：**闸门的改动必须用"已知红/已知绿"两份文件做回归**，
> 而不是只看它在新文件上报了什么。本轮 P5 原件/v2 正好充当了这一对。

### 1.4 顺手修掉的闸门自伤：`--json` 会把输入文件覆盖成报告

`audit_aixml.py` 只有 `--json-out`，而 argparse 默认允许**前缀缩写**，
于是 `audit_aixml.py --json <file>` 里的 `--json` 被解析成 `--json-out`，
**下一个位置参数（也就是第一个输入文件）被当成报告的输出路径**——
`research/artifacts/round10/lv009-probe.aixml.xml` 被 2,889 行 JSON 原地覆盖。

已修：`allow_abbrev=False`，并且**拒绝把报告写到任何输入路径上**（`refusing to overwrite input document`）。
现在同一句命令直接报 `unrecognized arguments: --json`，文件安然无恙。

---

## 2. 事件结构：帧活着，超时端子死了

### 2.1 上游文档说"整个事件结构写不出来"，实测是**一半**

`lvai_aixml_reference` 的 Event Structure 一节写着（NI 的转换器）：

> 帧全丢，`Event Data Node` 回成 `fields="Source,Type,Time"`，图上只剩一个 `[0] Timeout` 帧。

我们用 **pylabview** 的 composer 转换同一份 v2 文档，回导后的 `BDHb` 里：

```xml
<EventNodeEvents elements="3">
  <EventSpec><diagramIdx>0</diagramIdx><source>3</source><type>1073741826</type>
             <ddoUID>4201</ddoUID><eFlags>4</eFlags></EventSpec>   <!-- Go   : Value Change -->
  <EventSpec><diagramIdx>1</diagramIdx><source>4</source><type>1073741825</type>
             <ddoUID>0</ddoUID><eFlags>1</eFlags></EventSpec>       <!-- Timeout -->
  <EventSpec><diagramIdx>2</diagramIdx><source>3</source><type>1073741826</type>
             <ddoUID>4202</ddoUID><eFlags>4</eFlags></EventSpec>    <!-- Stop : Value Change -->
</EventNodeEvents>
```

三帧、三个事件规格、两个静态事件各自绑到了正确的控件 ddoUID。
`eventDataNode` 也是三个（每帧一个）。**在 pylabview 路线上，事件结构是写得出来的。**

### 2.2 但超时值写不进去

同一份回导里，`eventTimeOut` 端子的 dco（`uid=20069`）**没有被任何 signal 引用**：

```
terms whose dco is 20069 : ['20068','20126','20131','20136']   ← 只有端子自己的四个面
wires: 23 条，没有一条落在上面
```

25 条线里那根本该接 500 ms 的，被 composer 接成了**普通隧道**（`20268 selTun`）——
它老实照 `<Tunnel _id="In1" inputs="value:4203.ms">` 办事，而 AIXML 里**根本没有"超时端子"这个元素**。

上游文档在另一处承认了这一点（References to front-panel objects 一节）：

> **Not in an Event Structure Timeout frame**, which has no terminal in AIXML

### 2.3 运行时后果：静默地永不超时

```
runForMs=2200，Timeout ms=500，未发任何事件
  Go Presses = 0      ← 没信号，符合预期
  Timeouts   = 0      ← 预期应约 4 次；实际 0
  aborted=true, ran=true
```

即：**事件结构阻塞等待，超时帧永远不来，程序停在那里，全程零报错**。
这是本轮最贵的一条——它不制造错误，只制造"程序不动"。

→ 落成 **LV013 `event-timeout-unwireable`**（error）：文档里有 ` Timeout ` 帧就直接报，
并给出两条出路（IDE 里手接，或改用 `Wait (ms)` / `Wait on Notification` 配轮询）。

---

## 3. 两个 composer，对边界的态度相反

### 3.1 一次受控对比

同一份 `research/artifacts/round4/batch-averager.aixml.xml`（Round 4 的成品，历史上一直是"能跑"的参照物）：

| 路线 | 结果 |
|---|---|
| **grpc**（NI `ConvertAIXMLToVI`） | `errorCode 0`，写出 13,800 字节 VI |
| **pylabview**（本项目 composer） | `composerRefused`：`net '220.zero' crosses a diagram boundary without a tunnel` |

把 grpc 写出的 VI 用 pylabview 读回来，数隧道：

```
源 AIXML       43 个 <Tunnel>，按父：{200:1, 300:7, 310:7, 330:7, 350:7, 370:7, 400:7}
生成 VI 回导  154 个 <Tunnel>，按父：{200:4, 300:25, 310:25, 330:25, 350:25, 370:25, 400:25}
```

**NI 的转换器把缺的隧道全补上了**（每个 Case 结构 7→25，While 1→4）；pylabview 不肯猜，
直接退件——而且一次只点一根网。

### 3.2 于是"历史产物"和"新产物"的健康口径不同

全库 64 份 AIXML：

| 口径 | 结果 |
|---|---|
| 默认（grpc 语义，LV012 = warning） | **26 error / 269 warning** |
| `LVRULE_BACKEND=pylabview`（LV012 = error） | **187 error / 108 warning**（其中 161 条是 LV012） |

那 161 条不是"文档坏了"，是"这份文档**只**对 grpc 成立"。谁哪天把它推到 pylabview，就会当场被拒。

→ LV012 的严重级别因此**由目标后端决定**，并在消息里写清 43→154 这一条实测；
`tools/lvrule_check.py --backend pylabview`（或 `LVRULE_BACKEND=pylabview`）切到严格口径。

### 3.3 闸门现在比运行时错误更强

composer 的拒绝信息一次只给一根网（P5 花了 2 个往返，理论上 5 根就是 5 个），
LV012 一次列出**全部**越界点，并指明是"谁在哪个容器里消费了哪个网"。同样一类错误，
离线闸门从"事后一根一根猜"变成"事前一次列完"。

---

## 4. 面板保留移植（`lvai_graft_diagram`）：本机只能走 pylabview

这是"复杂程序交付"里最实用的一条路线：**面板是甲方给的、代码是生成的**。
Round 8 只能从上游文档转述它，本轮第一次真机跑。

### 4.1 grpc 路线：helper 被拒

```
allowNewControls=true, comparePanel=true
→ errorKind: helperAixmlInvalid
   The helper AIXML does not validate: 属性节点: 包含未连线或错误的接线端 / 调用节点: 无效方法 / For循环: N未连接…
```

同一台机器上，pylabview 路线：

### 4.2 pylabview 路线：全绿

输入：面板 = 我们生成的"仅面板"VI（7 个端子、**零节点**）；脚手架 = Round 5 的 `batch-averager-scaled`
（同样 7 个端子 + 多一个 `Scale`）。

```json
{"ok": true, "execState": 1, "controlsGrafted": 7, "newControls": ["Scale"],
 "leftoverDuplicates": [], "wiringMatchesScaffold": true,
 "nodeCountsMatch": true, "typedefsKept": true, "panelIdentical": false}
```

7 个 swap 记录的 `errorCode` 全 0：控件类（`Initial State`/`Items`）`sinksReconnected=1`，
指示器类 `sourcesReconnected=1`，`placed=true`，没有残留的 `… 2` 副本。
`panelIdentical=false` 是对的——新加了一个控件，面板本就不再逐字节相同。

### 4.3 跑一遍才算数

```
输入 Initial State=Init, Items=[2,4,6], Scale=1
Sum=12   Items Processed=3   Average=4   Final State=Stop(4)
Log = "Init; Load; Accumulate; Load; Accumulate; Load; Accumulate; Report; Stop; "
```

**"面板 + 生成的图 + 一个新控件"三合一之后行为正确** —— 这条路线确实能用。

### 4.4 两个会咬人的前置条件（都是实测）

1. **`panelDiagramNotEmpty`**：面板 VI 只要图上有节点就拒，且**报的是元素个数**（本次 35）。
   注意 `Batch Averager Empty.vi` 名字里的 "Empty" 指空**数组**，不是空图——它也报 35。
   真·空面板得自己造（本轮 `panel-supplied.aixml.xml`：7 个端子、0 个节点，pylabview 1 秒出 VI）。
2. `replaceDiagram=true` 这条"直接清空旧图再植"的路，在本机**走的是 helper**，因此被 §5 的
   `helperAixmlInvalid` 一起打死。想要"客户面板上本来就有半成品代码"的场景，本机暂时没路。

---

## 5. helper 家族：本站的第 4 个上限

本轮又点名了三个失效的 helper 文档，加上 Round 11 的一个，一共四个：

| helper 文件 | 挂掉谁 | 报错要点 |
|---|---|---|
| `lvai_run_and_read_typed.xml` | `lvai_run_vi_and_read_values`（grpc，Round 11） | 多类端子未连线 |
| `lvai_run_for_ms.xml` | 同上，`runForMs`/`signalsJson` 路 | `For循环: N未连接`、`属性节点: 无效属性` |
| `lvpane_probe.xml` | `lvai_connector_pane`（grpc） | `数值至十进制字符串转换`… |
| graft 的核心 helper | `lvai_graft_diagram`（grpc，含 `replaceDiagram`） | `调用节点: 无效方法`、`For循环: N未连接` |

`bin/scripts` 下共 **78 个 .xml**。四个失效文档有两个共同特征：都用了 `For循环`（N 未接）、
`属性节点`（部分属性名在本机被认为是"无效属性"）、`调用节点`。**这是版本/语言相关的写法问题，
不是我们传参的问题**——同一份 helper 在 pylabview 路线上被本项目 composer 重新合成，就能跑。

直接后果：**`signalsJson`（唯一能给运行中的 VI 打 Value(Signaling) 的手段）在本机不可达**。
所以 P5 的"真按一下 Go 看计数加一"没能验证——事件注册是对的（§2.1），但没人能替用户点那一下。

---

## 6. 测试层：卡在连接器窗格

为了让 Caraya 那条链（`generate_test` → `run_caraya_tests` → JUnit）能跑，先造了一个最小受测件：

`artifacts/round12/scale-double.aixml.xml` → `Scale Double.vi`（2 个 double 入、1 个出，`Multiply`），
pylabview 转换 `execState 1`、4,420 字节。

```
lvai_vi_terminals → 0 input / 0 output on the connector pane；x, factor, y 全在"NOT ON THE CONNECTOR PANE"
lvai_generate_test →
  failedAtStep: placeholder
  noTerminals: 'Scale Double.vi' has no terminals on its connector pane,
               so a call to it carries no wires and needs no placeholder.
```

即：**生成的 VI 在本机读不出窗格端子**，`inputs`/`expect` 无从键名，测试生成器直接停第一步。
与 Round 7 / Round 10 的 conpane 结论同源（LV2026 的 FPHb `cons` 数组为空，**连 NI 自带范例都是空**），
所以这既可能是"VI 真没窗格"，也可能是"本项目的读侧看不见窗格"，两者目前分不开——
分得开的办法只有一个：在 IDE 里打开这个 VI 用眼睛看一次。**本轮没做，明确挂着。**

---

## 7. 闸门模型：G0 需要两个口径

Round 9 的 G0 是"生成前跑 `audit_aixml.py`"。本轮之后它得带后端：

```
G0a  目标 grpc      → python tools/audit_aixml.py --summary <file>            （LV012 = warning）
G0b  目标 pylabview → LVRULE_BACKEND=pylabview python tools/audit_aixml.py …  （LV012 = error）
```

理由不是洁癖：Round 11 已把 pylabview 定为默认工作路线（grpc 的 run helper 坏了），
而 161 条 LV012 里**每一条**都是"pylabview 会退件"的预告。

新增/变更规则一览：

| 规则 | 级别 | 说什么 |
|---|---|---|
| **LV012** `net-crosses-boundary` | warning / error（按后端） | 线穿过结构边界却没有隧道；附 43→154 的两种 composer 事实 |
| **LV013** `event-timeout-unwireable` | error | 事件结构的超时端子不可写，` Timeout ` 帧永不触发 |
| LV005 修正 | — | 一次误合并行导致它对每个 Structure 生效（已修，回归见 §1.3） |

---

## 8. 下一步（按优先级）

1. **升级到 ≥ v2.2.0**（仍是唯一没做的动作）。理由现在更硬：§5 的 4 个 helper 若在新版本重写过，
   `signalsJson` / `connector_pane` / `graft(grpc)` 可能一起恢复。升完先跑
   `tools/audit_aixml.py --summary` 与 `lvai_dump_schema` 对差。
2. **在 IDE 里看一眼 `Scale Double.vi` 的连接器窗格**（§6）：有窗格 → 是读侧瞎，转去查
   `pylv-conpane.py` / `vi2aixml.py`；没窗格 → 是写侧不设窗格，得在 AIXML 里另找 conIdx 写法。
   这一步 30 秒，却决定测试层整条链的走法。
3. **P5 的事件驱动**：等 helper 修好，或在 pylabview 上自造一个"set control with signaling"的 driver VI，
   把 `Go Presses ≥ 1` 补上。
4. **`lvai_layout_diagram` 存疑**：v2.0.1 的 99 个工具里**没有**这个名字（Round 9 的 106→126 是 grep exe
   字符串的产物）。图面整理要么等 v2.2.0，要么用 `lvai_render_diagrams` + 手工坐标。
5. 把 LV012 接进 `tools/audit_aixml.py` 的默认报告标题行（现在只在明细里），
   并在 README 的闸门表里分成 G0a/G0b 两行。

---

## 9. 本轮产物

```
research/21-first-panel-and-boundary-round.md     本文
research/artifacts/round12/
  p5-valuechange-timeout-frames-v2.aixml.xml      修好的探针（execState 1 的那份）
  panel-supplied.aixml.xml                        仅面板 VI（7 端子 0 节点），graft 的甲方面板
  scale-double.aixml.xml                          测试层最小受测件
  Graft Demo.lvproj                               含面板 + 脚手架的工程（graft 需要活跃工程）
  lint-sweep.json / lint-sweep.txt                两种口径的全库复审
  out/  P5 Static Events And Timeout.vi           execState 1
        Supplied Panel.vi                         仅面板，execState 1
        Scaffold Scaled.vi                        grpc 生成（7+1 端子）
        Grafted Scaled.vi                         ★ 面板保留移植的成品，跑出 Sum=12/Average=4
        Scale Double.vi                           测试层受测件
        p5-extract/  averager-grpc-extract/       两个回导包（EventSpec、隧道计数的原始证据）
        averager-grpc-reexport-pylv.aixml.xml     43→154 的对照物
tools/lvrule_check.py                             新增 LV012 / LV013，修 LV005，加 --backend
tools/audit_aixml.py                              allow_abbrev=False + 拒绝覆盖输入（§1.4）
```
