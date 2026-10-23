# Round 13：缺的那一格 —— 连接器窗格，以及压在它下面的整个测试层

> 一句话：`connection` 决定端子是 required / recommended / optional，**只有 `conIdx` 决定它在不在连接器窗格上**。
> 这个项目前 12 轮写过的 383 个端子，只有 38 个带过 `conIdx`（9.9%）。于是所有生成的 VI 都不可被 Call，
> 而 LabVIEW 对此**不报任何错**：图上照画 Call，跑起来数据线是空的，结果还是"对的"——只是那个值来自调用方自己的常量。
>
> 这一轮把它补上了，并顺带拿到三件事：`generate_test` 从 `noTerminals` 走到 `direct` 路线（卡在下一道墙）、
> 一个不依赖第三方框架的自包含测试 VI（正负对照都成立）、以及一份 LabVIEW 被 MCP 自己的 helper 打死的崩溃取证。

---

## 1. 起点：`noTerminals` 到底是什么

Round 12 结尾留了一句话：测试层卡在 `noTerminals`，并对 `Scale Double.vi` 提了一个 30 秒能验证的问题——
"有窗格说明是读侧瞎，没窗格说明写侧不设窗格"。

问法本身是好的，但当时的备选只有两个。实测下来是**第三个**：读侧不瞎，写侧确实没设窗格，而写侧之所以没设，
是因为 AIXML 里从来没写过那个属性。

两份独立的读者给出同一个答案：

```
lvai_vi_terminals(backend="pylabview")
  Scale Double.vi - 0 input terminal(s), 0 output terminal(s) on the connector pane.
  3 more front-panel object(s) are NOT on the pane and cannot be named in a Call.

lvai_vi_terminals(backend="grpc")
  （同样 0/0，同样三个 off-pane，末行 "Exported from LabVIEW, NOT cached"）
```

pylabview 的读法是自研 reader（`vi2aixml.py`，不碰 LabVIEW），grpc 的读法是 **NI 自己的导出**。
两条完全独立的实现、同一个答案 → 排除读侧。这条"双后端互证"本身就值得记成纪律：
**怀疑读侧之前，先用另一个后端问一遍**，一次调用就能省掉一轮翻源码。

## 2. 源码级根因：缺的是 `conIdx`，不是 `connection`

`aixml2vi.py`（composer）里三处代码合起来就是全部答案：

```python
con = el.get("conIdx")                       # 只有它非空，后面整条路才成立
...
conn = fpdco.find("conNum")
conn.text = con if con is not None else "-1" # 没有 conIdx → conNum = -1，即"不在窗格上"
...
if con is not None:
    c = ET.SubElement(self.cons, "SL__arrayElement", {"class": "ConpaneConnection"})
    self.pane_terms.append((int(con), tree, is_ind, el.get("connection") or "required"))
```

而 `connector_pane()` 里那段注释把另一半也说清了：骨架的面板根节点带着 `objFlags 0x10000`，
它自己的注释是 **"NO TERMINAL ON THE PANE"** —— `every AIXML-generated VI without a pane carries it`。
所以"没窗格"不是漏写某个默认值，而是 composer 明确的"这个 VI 没有窗格"状态。

`connection="recommended"` 只写进 `objFlags`（`0x10000 | 0x200`），管的是**这个端子在窗格上时是否必需**，
它一个字都没说"在位"。**名字像窗格配置，其实不是** —— 这是这轮最大的认知陷阱。

## 3. 四分支实验：conIdx 是真槽位，不是装饰

同一份 `y = x * factor`，只改 conIdx 的写法。四份都 `errorCode 0 / execState 1`，
但窗格结果完全不同（`make_probes.py` 生成，文件在 `artifacts/round13/`）：

| 变体 | 写法 | 生成字节 | 窗格读数 |
|---|---|---|---|
| **A** | 三个端子都不写 conIdx | 4 407 | **0 in / 0 out**，三个全 off-pane |
| **B** | `conIdx` 0 / 1 / 2（文档序） | 4 447 | 2 in / 1 out，槽位 0 / 1 / 2 |
| **C** | `conIdx` 打乱：y=0, x=1, factor=2 | 4 443 | 2 in / 1 out，**槽位按 conIdx**：y 在 0，x 在 1，factor 在 2 |
| **D** | 只有 x 写 `conIdx="0"` | 4 423 | **1 in / 0 out**，x 在槽 0，另两个 off-pane |

四件事就此定下：

1. **`conIdx` 是开关**：没有它 = 不在窗格上，有它 = 在。字节差只有 16–40，差别全在 `cons` 数组和 `pane_terms` 里。
2. **`conIdx` 是槽位，不是顺序号**：C 组把 y 放到槽 0、x 放到槽 1，读回来就是 y 在 0。文档顺序完全不影响。
   所以它可以用来做**语义化布局**（输出在上、错误簇贴底），而不是被迫按"先控件后指示器"排列。
3. **部分上窗格是合法的**：D 组只有 1 个端子在窗格上，`execState 1`、能跑。这推翻了我原本"全有或全无"的猜测。
4. **B 组在 grpc 与 pylabview 下读数逐字相同**，包括 `conIdx 0, recommended` 这种细节。

## 4. 端到端：窗格不是给读侧看的，是真能 Call

读侧看得见不等于调用链通。所以写了一份 `Conpane Caller.vi`：两个常量 3 和 5，
一个静态 `Call` 到 B，一个 `Result` 指示器。

```
composerReport: ["Call 'Conpane Probe B.vi' <- <TypeDesc at 0x...> (pane 4833, 16 slots)"]
运行：Result = 15.00000000000000   (execState 1, runMs 3)
```

`pane 4833, 16 slots` 是 composer 从目标 VI 的窗格读出来的图案编码 —— 它真的解析了 B 的窗格。
**conIdx 生成的窗格是可链接的真窗格。**

## 5. `generate_test`：从死在门口，到死在第二道墙

同一个 subject，同一个 casesJson（3 组、含负数与零），三次结果：

| # | 条件 | 结果 |
|---|---|---|
| 1 | Round 12，subject 无窗格 | `failedAtStep: generate`，卡在 `noTerminals` —— 连 stub 都生成不出来 |
| 2 | 本轮，`backend:"grpc"` | `route: placeholder`（direct 没成立）；`typedefFlatten` 跑了 21.6 s 后**整个 gRPC 服务消失** |
| 3 | 本轮，`backend:"pylabview"` | **`route: "direct"`**，`subject: 2 in / 1 out, notOnPane: []`，卡在 `Call 4202: no Test.lvclass ...` |

三件事：

- **窗格一修好，`subject` 步骤立刻报 2 in / 1 out / `notOnPane: []`** —— 第一道墙是真拆了。
- pylabview 直接把路线判成 **direct**（grpc 反而掉到 placeholder，因为它的 `openSubject` 要一个 helper，
  而那个 helper 在本机生成不出来 —— 就是 Round 12 记的"78 个 helper 里 4 个失效"那条）。
- **第二道墙是 Caraya 压根没装**，工具报得很准，naming 也准：

```
Call 4202: no Test.lvclass in the installation or near the caller
```

查证：LabVIEW 2026 安装目录 8 层深内没有 `Caraya.lvlib`、没有 `Test.lvclass`；`user.lib` 只有 `LV_MCP`；
VIPM 里只有 `jki_lib_caraya-1.4.3.147.spec` / `1.4.4.148.spec` 这种**下载缓存**（spec，不是安装），
而 `C:\ProgramData\JKI\VIPM\error\` 里 10 月 12 日正好有一条 `HTTP Transport error ... jkisoft.com/packages/...`。
**这不是 MCP 的缺陷，是环境缺件。** 装 Caraya 需要人在 VIPM 里点一下（联网），本轮不能替用户做。

## 6. 绕开框架：一个纯原生节点的自包含测试

"缺框架"不该等于"测试层停摆"。于是用纯 AIXML + 纯原生节点写了个测试 VI，20 个对象、19 条线、
7 061 字节、`execState 1`：

```
3 次 Call ──> 3 次 Subtract(expected) ──> 2 次 Add ──> Equal?(0) ──> AllPass
                                        └──────────────────────────> Total Error
```

用例是 3×5、-2×4、0×7 —— **全都能在 IEEE754 里精确表示**，所以残差和严格等于 0 当且仅当被测 VI 正确
（这正是 Round 8 那条"浮点相等是精确的，选精确值"的用法）。

| 版本 | AllPass | Total Error |
|---|---|---|
| 正对照 | **true** | **0.00000000000000** |
| 负对照（只把 expected -8 改成 -9） | **false** | **1.00000000000000** |

负对照是必须的：正对照通过只能说明"没炸"，负对照失败才说明"这个判定真的在判定"。

顺带一条拼写坑：`Equal?` 的输出端子名是 **`x = y?`**（等号两边各一个空格）。写 `x=y` 会被拒，
而且报错会把全部合法端子名列出来——`Node 'Equal?' has no terminal 'x=y' (known: ?parm1, ?parm2, ?parmout, x, x = y?, y)`。
**pylabview 的拒绝信息可以直接当文档用**，这一点比 NI 的 `Error 53 "Unrecognized or unsupported attribute set"` 好太多。

## 7. 无窗格 Call 的失败形态：静默，而且结果看起来是对的

这条比"报错"危险得多。写 `Conpane Caller A.vi` 去 Call **A（无窗格）**：

```
<Call inputs="" outputs="" target="Conpane Probe A.vi" uid="4210" uid_parent="root"/>
```

结果：`errorCode 0` / `execState 1` / 可运行 / **零报错**。运行输出 `Marker Out = 99.00000000000000`
（这个 99 来自调用方自己的常量，被调的 A 一个字节都没参与）。

也就是说：**"图上有一个 Call、跑完没有错误、值也读出来了"这三件事同时成立，仍然可能是这个 Call 什么也没做。**
判断"子 VI 真的被调用了"的唯一可靠办法，是让输出依赖于它的输入——这正是自包含测试做的事。

一个意外的收获：上游 linter 的 `terminal-list-empty` 会在这个形态上报 2 个 error（`Call 'Conpane Probe A.vi'` 报了两次，
一次针对 inputs 一次针对 outputs）。所以"Call 一个完全没有端子的 VI"并不是完全没人管。
但它只管**两张列表同时为空**这一种情形：如果被调 VI 有 3 个端子而调用方只接 1 个（D 变体 + 漏接），
上游 linter 与我们的闸门都沉默，LabVIEW 也不报错，未接的端子就用被调方的默认值。
**这才是最需要人盯的形态**，而它恰好是"少写一个 conIdx"之外最容易发生的事。

## 8. 崩溃取证：`fpsane.cpp(1140)`，5 次 DWarn，4 个 minidump

`generate_test(grpc)` 跑到一半，`lvai_status` 之外的一切 RPC 开始报
`Could not find a port serving lvai.LVAI. Tried 40 candidate(s)`。当时的现场：

```
netstat:  [::1]:14596  [::1]:44136  SYN_SENT       <- 有人在连 44136，没人应答
          [::1]:44134  [::]:0      LISTENING 2348
          [::1]:44135  [::]:0      LISTENING 2348  <- 44136 不在监听列表了
tasklist: 2348 = NI.NigelLocalService.exe          <- 不是 LabVIEW.exe
```

LabVIEW.exe 已经没了；NigelLocalService 成了孤儿，只守着 44124/44134/44135。
而 `lvai_status` 仍然缓存着 `44136`（`discoveredVia: "LabVIEW.exe listener"`）—— 状态缓存和现实脱节了。

LabVIEW 的日志给出了直接死因，**5 次记录，同一个签名**：

```
2026/10/23 16:55:10.983
DWarn 0x613A5C04: Fatal insanity (0x00000004) detected in 'lvai_typedef_tree.vi'
source\panel\fpsane.cpp(1140)

VI call stack:
- LV AI gRPC Service.lvlibp:gRPC Implementations.lvlib:ConvertAIXMLToVI.vi
- LV AI gRPC Service.lvlibp:LVAI.lvclass:Start Sync.vi:5930001
- LV AI gRPC Service.lvlibp:gRPC-servicer-release.lvlib:ServiceBase.lvclass:Start.vi:1880001
- LV AI gRPC Service.lvlibp:gRPC Implementations.lvlib:RunService.vi
```

四个 minidump id，五条 DWarn，全在 `ConvertAIXMLToVI.vi` 的调用上下文里，全由 `lvai_typedef_tree.vi` 触发，
全落在 `fpsane.cpp`（**f**ront **p**anel **sane**，连接器窗格检查）。

注意时间关系：`lvai_status` 在 16:52 报 `dwarnCount: 0, looksDegraded: false`，5 分钟后就是这 5 条 Fatal insanity。
status 自己那句免责声明（"an instance reading 0 has been measured crashing minutes later"）这一轮被完整演示了一遍。
**`dwarnCount: 0` 不是健康证明，只是"到目前为止还没写过日志"。**

这件事和本轮的窗格主题是同一片区域：`lvai_typedef_tree.vi` 干的事就是"读 stub 的端子 typedef 是否与 subject 一致"，
它要摸的正是连接器窗格。Round 5 记的 `lvai_bind_pane_typedef` 竞态、Round 12 记的 `conpane` 不可用，
现在可以合成一句：**凡是把窗格当工作对象的 helper，在本机都不可靠；而给"没有窗格的 stub"跑它们，能把 IDE 打死。**

恢复路径倒是干净：`lvai_ensure_labview` 成功拉起新实例（`launchMethod: breakaway`，新端口 **14868**，`state: ready`），
不需要人工干预 —— 前提是 Nigel 的 gRPC 服务随实例起来了（这次起来了）。

## 9. 闸门：LV014，以及全库 9.9% 这个数字

新规则 `LV014`，判别力在三份文件上验证过：

| 文件 | 输出 |
|---|---|
| A（无 conIdx） | `INFO lv014-no-connector-pane  uid=4200 Control 'x'` |
| B（全有） | 干净 |
| D（部分有） | `WARNING lv014-terminal-off-the-pane uid=4201 Control 'factor'` |

分级不是随手定的：**全都不在窗格是顶层 UI VI 的正常形态**（因此 info），**部分在部分不在才是疏漏的样子**
（因此 warning，但 D 证明它合法，所以不是 error）。而且每份文件只报一条，避免 383 个端子刷屏。

全库普查（70 份 AIXML、383 个端子）：

```
Control/Indicator total: 383   with conIdx: 38  => 9.9%
files where EVERY terminal has conIdx: 11   (round13 的 6 份 + round7 的 5 个 fixture)
```

**这就是"前 12 轮生成的 VI 一个都不可被 Call"的量化版本。** round7 那 5 个 fixture 有 conIdx，
说明当时那份文件是从别处（NI 导出）拿来的，不是我们写的——恰好反过来印证了：只有 NI 导出带 conIdx，
手写 AIXML 从来不带。

闸门现在的读数：**75 份文档 / 30 error / 278 warning / 59 info**（LV014 贡献 59 info + 4 warning）。

## 10. 为什么 12 轮都没写 conIdx

不是疏忽，是**命名误导**。AIXML 里一个端子的"窗格相关"属性叫 `connection`，取值
`required / recommended / optional` —— 读起来就是"这个端子接不接"。于是写 `<Control connection="recommended">`
的时候，人会以为已经把它放进窗格了，而它其实只说"如果它在窗格上，那它是可选的"。

真正的窗格归属是另一件更"机械"的事，叫 `conIdx`（槽位号），没有任何语义提示。它在 AIXML 里也从不报错、
从不警告、从不影响 `execState` —— 少了它，VI 依然 100% 合法，只是**做不了任何别人的子 VI**。

这是这一轮唯一一条"文档里根本看不出来"的教训：
**一个属性少了不报错、只让能力静默消失，它就不会被写。** 所以它必须有闸门（LV014），否则下一个 12 轮还会漏。

## 11. 副产品：两条工具面的观察

1. **`lvai_vi_terminals` 的双后端一致性可以当诊断纪律用**。grpc 走 NI 的导出，pylabview 走自研 reader，
   两者对同一份文件给出逐字相同的读数（含 `conIdx 0, recommended`）。意见不一致时，先看是不是缓存
   （grpc 对安装目录内的 VI 用缓存，pylabview 从不用缓存）。
2. **状态缓存会和现实脱节**。`lvai_status` 报 `port 44136` 时，那个端口已经不 LISTENING 了；
   报 `dwarnCount: 0` 时，5 分钟后 IDE 就死了。判断存活要看 `netstat` 里那个端口是否 LISTENING、
   要看 `tasklist` 里 `LabVIEW.exe` 在不在（`NigelLocalService.exe` 活着不代表 LabVIEW 活着）。

## 12. 产物清单

```
research/22-connector-pane-the-missing-slot.md          本文件
research/21-first-panel-and-boundary-round.md           Round 12（上一轮）

research/artifacts/round13/
  make_probes.py                      A/B/C/D 四份探针的生成器（唯一变量是 conIdx）
  conidx-probe-a/b/c/d.aixml.xml      四份探针
  conpane-caller.aixml.xml            端到端：Call B，3×5
  conpane-caller-a.aixml.xml          反证：Call 无窗格的 A
  selfcheck-test.aixml.xml            自包含测试（纯原生节点）
  selfcheck-negative.aixml.xml        负对照（只改一个期望值）
  Conpane Tests.lvproj                subject 所在工程（direct 路线用）
  lint-sweep.json                     全库扫描（含 LV014）
  out/Conpane Probe A|B|C|D.vi        四份探针的 VI（4.4 KB 级）
  out/Conpane Caller.vi               Result = 15
  out/Conpane Caller A.vi             Marker Out = 99（静默空接）
  out/Selfcheck Conpane Probe B.vi    AllPass = true, Total Error = 0
  out/Selfcheck Negative Control.vi   AllPass = false, Total Error = 1
  out/_labview-crash-16-55.txt        LabVIEW 崩溃日志节选（5 DWarn + 4 minidump）

tools/lvrule_check.py                 新增 LV014（全无窗格 = info；部分缺 = warning）
```

## 13. 仍未解决

1. **Caraya 没装**。这是测试层剩下的唯一硬缺口。装好之后 `generate_test` 应当能一路走完（前提是它别再触发
   `lvai_typedef_tree` 的 insanity —— 那是下一个要盯的点）。
2. **`lvai_typedef_tree.vi` 的 Fatal insanity 没有稳定复现配方**。目前只知道"在 ConvertAIXMLToVI 上下文里、
   对着 stub 干窗格活"时会发生，5 次连发。要复现得先有一个"没有窗格的 stub"，而本轮把 conIdx 修好之后，
   这个前提可能已经消失了 —— 这本身是个好消息：**修 conIdx 也许同时拆掉了这颗雷**。
3. **`generate_test` 的 grpc 路线在本机仍然走 placeholder**，因为 `openSubject` 要的那个 helper 生成不出来。
   pylabview 的 direct 路线已经通了，所以这不是阻塞项，但"为什么那个 helper 失败"值得单独查一次。
4. **窗格布局的语义**：既然 `conIdx` 决定槽位、且支持部分上窗格，那就可以按 `error out` 贴底、输出在上的
   惯例来排——这一点本轮只验证了机制，没做惯例约定。下一轮可以定一份"端子排布规范"。
