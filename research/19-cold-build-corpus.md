# Round 10：冷构建语料 —— 25 次"从零建一个完整应用"的实测普查

> **本轮性质：离线轮（第 3 次）。** LabVIEW 未运行，`~/.workbuddy/mcp.json` 中两个 labview
> server 仍为 `disabled`，无法产生本机新实测。
>
> **证据来源**：上游源码克隆 `git@github.com:Zuehlke/labview-mcp.git`（HEAD `2c9f37d`，SSH 通道；
> 本机 HTTPS 因 schannel 吊销检查失败不可用）中 `docs/cold-build-*.md` **25 篇**。
> 这些是上游把每一次"从零构建一个完整应用"的实测记录直接入库的产物，共 4409 行。
>
> **标注惯例**：**【上游实测】** = 该文档自己记录的仪器测量，注明文件名与节号；
> **【本机实测】** = 我们在本机取得的；**【推断】** = 我们的归纳，未经验证。
> 本轮**没有**任何【本机实测】，全部为前两类。
>
> **可复现**：`python tools/cold_build_census.py <upstream>/docs --out research/artifacts/round10`
> 重新生成 `cold-build-census.csv` / `.json`；本报告所有计数来自该数据集，不靠肉眼。

---

## 1. 为什么这一批文档值得单独立一轮

前九轮我们读的是"单个工具怎么用"和"单条规则为什么成立"。这批文档回答的是另一个问题：

> **一个 AI 从空目录开始，把关卡全走完，最后到底拿到什么、在哪一步付了钱、哪些缺陷会重复出现？**

25 篇覆盖 2026-09-14 → 09-30 的 17 个连续工作日。它们不是教程，是**事故记录**：
读完一篇知道一个坑，读完整批才知道**哪些坑是系统性的**。

语料形态分布（按构建目标归类，非文档自述）：

| 形态 | 构建 | 说明 |
|---|---|---|
| 类 + 接口 + 测试的"工程件" | thermostat、alarmgate、datalogger、pumpstand、samplebench、valverig、kilnrig、filterbench、torquebench、weighbridge、conveyorrig、shakerrig、coolantloop、mixedrig | 主体是 `.lvclass` 层级、访问器、override、mock、单元测试 |
| 事件驱动 / UI | sensor-monitor-events、carwash-pc、carwash-graft | 用户事件、超时、pane 与调用方 |
| 认证考题式整体程序 | atm-cld（760 行，最长）、atm-no-stubs、atm-agents-3/4/7/8、atm-agents-pc | 一个主 VI + 多子 VI，含多代理并行 |
| 单一能力专题 | typedef-gdevcon（6 次连续构建）、mixedrig（typedef 全变体） | 只为回答"这条路线值不值" |

---

## 2. 普查：这批构建到底做出了什么

`cold-build-census.csv` 逐篇记录。**12 篇**明确写了终态（其中 11 篇的字段能被脚本解析成数字；
thermostat 写的是 "all five classes"，人工可读、机器不认，脚本如实留空）；其余 13 篇没有终态段。

| 指标 | 值 |
|---|---|
| 构建数 | 25 |
| 总行数 / 章节数 | 4409 / 148（其中 37 节讨论故障、修复或撞墙） |
| 写明终态 | 12（可解析成数字 11） |
| 这 12 篇的产物合计 | **57 个 `.lvclass`、193 个 VI、112 个测试** |
| 零失败 | 10 |
| 有失败 | 2（conveyorrig 2 个、shakerrig 1 个），**3 个失败全部是刻意的负对照** |
| 跑过负对照 | **23 / 25** |
| 先过 `aixml_lint` 再进 LabVIEW | 14 / 25 |
| 零 LabVIEW 重启 | 6 篇明确记为零重启，最多的一篇（torquebench）16 个测试、19 个 VI 全程未重启 |

**第一条结论，也是本轮最硬的一条：语料的"绿"是校准过的绿。**
112 个测试、3 个失败、全部来自负对照 —— 说明"0 失败"这个数字在 23 篇里都不是空转得出的。
这条不能只看结论，要看它靠什么保证：下一节 L1 说明**恰恰有整整一类测试会空转通过**，
而语料之所以没被骗，是因为每次都放了一个"必须失败"的对照进去。

---

## 3. 五条改变做法的定律

### L1 常量存活表：`timestamp` 字面量被静默丢弃，于是生成的测试空转通过

**【上游实测】** `cold-build-alarmgate.md` §3。

一个控件、一个指示器、`type="timestamp" value="3800000000"`：

| 步骤 | 结果 |
|---|---|
| `scripts/aixml_lint.py` | `[clean]` |
| `lvai_convert_aixml_to_vi` | **`errorCode 0`**，4119 字节 |
| 回导该 VI | 两个元素的 `value` 都是 `""` |

字面量被接受、被丢弃、全程无人报警。**为什么比拒绝更糟**：生成的往返测试把"写入值"和
`Expected` 常量写成同一个值，两边**同时**被丢成空 —— 测试比较空与空，**通过**。

实测的存活表（一个探针、六个类型、convert 后回导）：

| 类型 | 写入 | 回读 | 结论 |
|---|---|---|---|
| `string` | `PT-101` | `PT-101` | KEPT |
| `path` | `run.csv` | `run.csv` | KEPT |
| `double` | `21.5` | `21.5` | KEPT |
| `int32` | `7` | `7` | KEPT |
| `bool` | `true` | `true` | KEPT |
| **`timestamp`** | `3800000000` | *(空)* | **DISCARDED** |

负对照同时跑在同一个套件里：把 `Tag` 那条的 `Expected` 改成 `DELIBERATELY WRONG`，
恰好报一条失败并给出 `Expected:DELIBERATELY WRONG(String) / Actual: PT-101(String)`，
而 `Last Seen` 那条仍然绿 —— 证明"绿"不是因为框架不能失败。

上游的修复方式值得抄：`lvai_check_aixml` 与 `aixml_lint.py` 各加一条 **warning**
（`timestampValueDiscarded` / `timestamp-value-discarded`），**故意不自动修**
（没有"正确的非空值"可换成，静默清空恰好制造那个空转测试）；
`lvai_lunit_scaffold_class_tests` 改为**跳过这一个文件**并把原因列在 `roundTripsSkipped`，
而不是拒绝整个调用 —— 判定依据是"这条测试声称什么"：

| 生成的测试 | 它的声称 | 在丢弃型字面量上 |
|---|---|---|
| `Test <field> Round Trip` | 写进去了、读回来了 | 写入什么都没存的写也满足 → **不生成该文件** |
| `Test Field Defaults` | 新对象读到的就是默认值 | 与丢弃后完全一致 → **保留，不受影响** |
| `Test Write Independence` | 别的写没有扰动本字段 | 仍然成立 → **保留，但两侧都按默认值写** |

**对我们的意义**：Round8 的 G4（文件级验证）只要求"回读确认结构"，**不足以发现这一类**。
必须加一条**字面量存活检查**：任何被生成进测试的常量，先单独走一次 convert→回导，
确认它回来了。这句话的另一半更重要：**一个对着被丢弃值的绿测试，比没有测试更坏** ——
它把"没测"伪装成"测过"。

### L2 类阶段占一半成本，且是唯一真正失败的那半

**【上游实测】** `cold-build-mixedrig.md`「Where the 30.5 s went」。

一个刻意的成本实验：27 步、24 次往返、30 519 ms 墙上时间、20 729 ms 落在工具内。

| 阶段 | ms | 占比 |
|---|---|---|
| 1 — 三个 typedef `.ctl` 与嵌套绑定 | 3 096 | 10 % |
| 2 — `Acquire.vi` 与三处绑定 | 788 | 3 % |
| **3 — 类：创建、绑字段、访问器** | **15 099** | **49 %** |
| 4 — 三种 placeholder 模式 | 9 804 | 32 % |
| 5 — 调用方与 retarget | 1 733 | 6 % |

原话："**一半的构建是类阶段，而它正是失败的那一半。**"typedef 那一半 —— 这次实验的全部目的 ——
只占 10 % 且**一次通过**。

这条与 L3 合起来决定了收缩顺序：**优化 typedef 是错的，先收缩类和样板**。

#### L2a `lvai_add_class_method` 重跑会毁掉整个类，而所有回执都是绿的

**【上游实测】** `cold-build-thermostat.md` §4。

1. 套件 4/4 通过，`privateDataBytes` **5691**，五个成员全部 `execState 1`；
2. 改一个比较符（作负对照）后重跑 `lvai_add_class_method`，回执 **`ok: true`**、
   `terminalsRetyped: 4`、`verifiedOnDisk: true`、`memberAlreadyExisted: true`；
3. 套件随即报四条测试 **`Broken`** —— 不是 `Failed`。

`Broken` 而非 `Failed` 就是全部线索：**断言根本没跑**，所以这不是负对照在起作用。
实际损坏：`Evaluate.vi` 的 AIXML 回导**完全正确**、`lvai_describe_class` 结构也正常，
但 `privateDataBytes` 变成 **5731**（+40 字节）；连**从未被点名的访问器**也 `eBad`；
`lvai_exec_state` 报 error type 2000008 / 8；**重启 LabVIEW 后依旧 eBad** —— 损坏在磁盘上。

修复：就地路线全不通（`lvai_create_accessors` 带 `fromField` 不是修复而是**复制**，
NI 向导会追加数字而非拒绝重名 —— 工具自己发现并返回 `ok: false` 加清理说明，这点是好行为）；
唯一有效的是**重建**：删成员 `.vi`、`lvai_create_class` + `overwrite`、重建访问器、
重加方法、重做 swap，之后 `privateDataBytes` 回到 5691。

**推论（我们的）**：这条把 Round8 的"跨工件链接读任一文件都验不出来"扩展到了**同一工件内部**——
类成员单独看全部完好，坏的是它们共同绑定的那个私有数据控件，而唯一的观测面是
`privateDataBytes` 的**字节数变化**和 `execState` 的 **`eBad` vs `1`**。
"文件写得出来"和"类还是原来那个类"是两件事。

#### L2b `inheritsFrom` 会说谎，而且不是边缘情况

**【上游实测】** `cold-build-valverig.md` §3。

`Test Valve` 实现 `IOpenable` 与 `ILoggable`、不继承任何类，校验却报
`inheritsFrom: "ILoggable.lvclass"`。根因：**接口链接和父类链接是同一种 item 类型**，
`Ancestors` 把两者混在一起，**顺序**决定这个单值字段说什么。

上游没有停在"那就别读这个字段"，而是把它修好了，靠两条测量：

| 测量（2026-09-15） | |
|---|---|
| 每个 `<Item Type="Parent">` 都带 `URL` | 在 `vi.lib`、`user.lib`、`instr.lib`、`examples` 里 **432/432** |
| URL 相对 **`.lvclass` 自身**（把它当目录）解析 | 同级是 `../../Name/Name.lvclass`；NI 自己的 `Mock Serial.lvclass` 写成 `../../Serial/Serial.lvclass/Serial.lvclass`，扩展名出现两次 |

第二次尝试成功的原因就是这个"扩展名重复"：第一次按**文件夹**解析，所有相对链接都 not-found，
读数成了"URL 不可用"，本该关掉唯一可行的那条路。

全站扫描结果：**449 条父链接全部解析成功**（400 类、49 接口、0 未解析）；
**437 个带父链接的类里有 46 个把非类当成了父类**（约 10.5 %），其中**包括 NI 自带范例**。

**对我们的意义**：这是一条"验证面本身会撒谎"的实例，与 Round7 的 typedef 竞态同族。
判据必须落在**可解析的物理地址**上（`<Item>` 的 `URL` + 目标自身的 `IsInterface`），
不能落在派生摘要字段上。

### L3 样板会膨胀成 O(帧×隧道)，这时该写生成器而不是写 AIXML

**【上游实测】** `cold-build-atm-cld.md` §5。

`Handle ATM Action.vi` 是一个 11 帧的 case 结构，5 个输入隧道、6 个输出隧道。
**每一帧都要声明每一个隧道** → **121 个 `<Tunnel>` 元素**，约 280 行，
占该 VI 的 27 900 字节 AIXML 里的一大块，"没有一行是有意思的，全是打错字的机会，
而报错会指向错误的元素"（`Contains unwired or bad terminal`）。

它由一个 **260 行的 Python 脚本**从紧凑的帧表生成，**首次 validate 就通过**，两个 VI 共用 2 次
generate 调用。对照：5 个手写叶子子 VI 用了 1 次批量调用 + 1 次重试；手写主 VI 用了 **3 轮
validate/fix，其中两次是生成器不会犯的错**。

上游的判据（引自 `docs/workflow-economics.md`）：**一步在 LabVIEW 侧便宜（convert 1.4 s）、
在作者侧贵（某次 208 k 输出 token）→ 就该写成工具。**

> 这与我们 Round6 的 `gen_statemachine.py`（状态表 → AIXML）是同一条路，而本轮给了它
> **首个量化回报**：生成器产物首次通过，手写同规模产物 3 轮。

### L4 状态码两侧都不可信：成功可能是假的，失败也可能是假的

两条独立观测，正好构成一对：

| 方向 | 观测 | 出处 |
|---|---|---|
| **报成功，其实没做** | `lvai_bind_pane_typedef` 回 `terminalsBound=2`、error 全 0，文件里 **0 个 typedef** | 我们 Round7【本机实测】 |
| **报失败，其实做完了** | swap 回 `ok:false`、`errorCode 1055`、`errorKind:noActiveProject`、`nodesSwapped:0`，但同一载荷里 `diagramSubVis` 列出的是**真正的目标** `Get Controls By Label.vi`，且该 VI `execState 1` | `cold-build-atm-cld.md` §13e【上游实测】 |

第二例的前提是"工程确实活着"——同批 4 个调用都成功。**结论：状态码只是摘要，判据必须来自
载荷里的证据字段。** 具体到这两个工具：
`bind_pane_typedef` 要看导出回读，`swap_subvis` 要看 `diagramSubVis` / `callTargets`。

### L5 多代理编排的四条硬约束

**【上游实测】** `cold-build-atm-cld.md` §12d。

一个被要求"调用同级工程 VI"的代理对 `lvai_placeholder_subvi` 答 `No such tool available`，
于是**自己用 AIXML 手工克隆了一个 socket VI** 并塞进 `user.lib\LV_MCP\`。它成功了
（克隆精确、swap 落地、`socketsLeft: 0`），但这恰恰是**最不该让它自己发明的东西**：
克隆不精确就是 `Error 7, Bad Linkage`，而它当时并不知道这条规则。

根因不是提示词：`lvai_placeholder_subvi` / `lvai_swap_subvis` **不在该代理的 `tools:` 名单里**，
而上游自己的文档把它们称为"生成的 VI 调用工程内代码的唯一路线"。
上游的表述可以直接当定律用：

> **定义里描述了、名单里没给的能力，读起来就是"这个能力不存在"。**

同节还给出三条只能靠"多代理"才暴露的约束：

1. **代理定义在会话启动时读取** —— 改完文件不算生效，**验收测试是重启**。这与 §7 的
   "served schema 也是会话启动时取一次"是同一形状。
2. **一个代理一个输出目录**（写进了 CLAUDE.md，并在 8 个代理定义里各放一份相同文本）。
3. **swap 需要一个活跃工程，而多个代理不能共享一个工程** → **swap 必须由编排方集中做**，
   代理只负责"写出 Call 然后停下"（生成-后-swap 协议）。

上游修正后：把这对工具加进 `labview-vi-generator`、`labview-vi-editor`、
`labview-vitester-unit-test` 三个会写 `Call` 的代理；`labview-doc-generator` 与
`labview-dqmh-module` **故意不给**（它们不写对工程内代码的调用）。

---

## 4. 复发缺陷表：哪些坑是系统性的

按语料出现频次排序。频次来自关键词在 25 篇中的命中构建数（`tools/cold_build_census.py`
的同类统计），**每条都在上表所列文档里逐条核对过表述**，不是纯关键词。

| 频次 | 缺陷 | 首次记录 | 现状（上游） |
|---:|---|---|---|
| 23/25 | 负对照被当作常规步骤而非可选项 | 全程 | 惯例 |
| 17/25 | Caraya 报告诊断力不足（见 §5） | filterbench §4 | 框架属性，非缺陷 |
| 13/25 | placeholder + swap 协议（生成-后-swap） | — | 已成文规则 |
| 12/25 | 先跑 `aixml_lint` 再进 LabVIEW | — | 惯例 |
| 10/25 | `.lvproj` 被塞入**游离 VI**（含工程树之外的目录） | weighbridge §4 | 未修工具，只有人工检查 |
| 8/25 | `Error 1055` 的各种变体（含"假失败"，见 L4） | — | 部分收敛 |
| 7/25 | `inheritsFrom` 把接口报成父类 | valverig §3 | **已修**（解析 `URL` + `IsInterface`） |
| 5/25 | `timestamp` 字面量被丢弃 | alarmgate §3 | **加检查、故意不修**，生成器跳过 |
| 3/25 | 失败的生成**烧掉 VI 名**（`Error 1051`），`lvai_close_vi` 无法释放（`Error 1149`：没有窗口可关） | atm-cld §12b | 两条出路：改名，或先 `open_file` 给它窗口再 close |
| 3/25 | `lvai_add_class_method` 重跑毁类 | thermostat §4 | 唯一修复=重建 |
| 2/25 | 测试报 `Broken` 而非 `Failed`（结构坏，断言没跑） | thermostat §4 | 诊断信号 |
| 2/25 | `connection` 标志在代理间分歧（`optional` vs `recommended`） | atm-cld §13d | **未修**：它进了 placeholder 缓存的签名，同样语义产生两个克隆 |

两张补充证据：

- **游离 VI（weighbridge §4）**：`lvai_create_class` 有 `strayVisRemoved`，而**真正会生成 VI 的
  swap-and-run 路径没有**。两次发生：两个 override swap 后进了两个 `user.lib\LV_MCP\` 桩；
  负对照跑完后进了 **`C:\temp\wb-negctl\Neg Control.vi`** —— 来自**工程树之外**。
  所以"扫工程目录里不该在的 VI"不够，得按"这个工程应该包含什么"判。
  两次 `ok:true`、`socketsLeft:0`、`callTargets` 全对，**没有一个回执提到这次收编**。
- **`connection` 分歧（atm-cld §13d）**：十个代理建的子 VI 里，两个代理的四个声明
  `error in: recommended`，另两个代理的六个声明 `optional`。两种在调用点行为**完全相同**，
  `lvai_connector_pane` 0 违规、`lvai_check_aixml` 静默。可见后果只有一个：
  **`PlaceholderTools.Signature` 把该标志算进哈希**，于是同一个 pane 出现两个克隆，
  11 个 socket 里 5 个是"本来就有的 pane 的重新克隆"，编排方还得把 AIXML 重新指向新名字。
  上游不肯为它重生成 7 个 VI（"不要为一句注释重生成"），给出的便宜修法是
  **在错误簇规则里直接写明：`error in` 用 `recommended`**。

  > 这一条与我们 Round9 的发现拼起来才完整：Round9 抓到 5 个 fixture 写了
  > `connection="required"`，它**自己不坏**，但**每个不接该端子的调用方都变 `Error 1003`**。
  > 三条证据合起来给出完整规则（见 §7 R10-4）。

---

## 5. 测试层：LUnit 与 Caraya 的真实差别

Round8 只记了"只认 `.xml`、7002 是判据"。语料把两个框架的**诊断成本**量化了。

| 维度 | LUnit | Caraya | 出处 |
|---|---|---|---|
| 失败正文 | `Pass If Equal.vim` 写 `Expected:bisque firing 12(String) / Actual:  (String)` | 只有字面量 **`"FAIL"`** | filterbench §4 |
| 失败定位 | 断言级 | **只给用例名，不给原因** | 同上 |
| 判据 | 报告 | `error out` = **7002**（"套件失败"），修好后回 0 | 同上 |
| `error out.source` | — | **指向错误的套件**：失败的是 `Test Pump Describe`，`source` 却写数组里第一个 `Test Pump Accessors.vi` | coolantloop §4b |
| 首次运行 | 重建后首跑必报 `Error 1`（Round8） | 同类：新生成套件首跑 `Error 1`，源 `Caraya.lvlib:Basic Test Manager.lvclass:Send Test Event.vi`，**不写报告**；第二次即绿 | coolantloop §4d |

结论不是"选 LUnit"：Caraya 的 `error out` 集群**不是不完整，而是会主动指错文件**，
信任它的人会去调试一个通过的套件。**规则：只读 JUnit 报告，永不读 `error out.source`。**

另一个必须记住的判据来自 thermostat §4：**`Broken` ≠ `Failed`**。
`Broken` 意味着断言根本没执行——它不是"测试失败"，是"测试不存在"。
一条 `Broken` 应当把诊断方向从"被测逻辑"立刻切到"类/结构完整性"。

---

## 6. 与前九轮的交叉验证

| 结论 | 我们此前 | 本轮语料 | 判定 |
|---|---|---|---|
| 失败会烧 VI 名（1051），只有重启能清 | Round8【上游文档】 | atm-cld §12b：`generate_vi_with_events` **故意跳过 validate**，用真名 convert，失败即注册；`close_vi` 报 1149 | **补强**：给出两条实测出路（改名 / 先 `open_file` 给窗口） |
| `connection="required"` 害调用方 | Round9【本机】5 个 fixture | atm-cld §13d：该标志还进 placeholder 缓存签名 | **补强**：影响面从"调用方"扩到"桩身份" |
| `Bundle` 不可纯追加，需类型化空簇基座 | Round6【本机】 | atm-cld §13c：`Bundle` 三个重复 `element:` 只得到**两元素**簇，validate 拒绝；正解是 `Bundle By Name` | **不矛盾**：我们测的是"追加到既有簇线"，上游测的是"新建多元素簇"；共同结论是 **`Bundle` 的 arity 是固定的**，"IDE 里可展开 ≠ AIXML 里可展开" |
| 类方法可自调访问器（无需 stub） | Round8【上游文档】 | thermostat / pumpstand 全程用 placeholder + swap 路线 | 并存：两条路线都被实测过 |
| 错误簇为零 ≠ 已持久化 | Round5/7【本机】 | L4 的反向：`ok:false` 也可能已经做完 | **升级为对称定律** |
| 五道闸门 G1–G5 | Round8【推断】 | 语料 25 次的共同形状 | 需要新增一道闸门与两条判据（§7） |

---

## 7. 模型修订：G0–G6

Round9 已把 G0（离线预检）插在 G1 前面。本轮再插一道，并把 G5 拆细：

| 闸门 | 内容 | 成本 | 判据 |
|---|---|---|---|
| **G0 离线预检** | `tools/aixml_lint.py` + `tools/lvrule_check.py`（本轮新增 LV009） | 2.5 s / 50 文件，0 次 RPC | 0 error（探针的刻意错误除外） |
| G1 需求定稿 | 数据模型、错误簇、pane 约定先钉死 | 一次往返 | 无"待定"项 |
| G2 分层生成 | 叶子 → 类/接口 → 编排；样板用生成器 | — | 每层 validate 过 |
| G3 结构验证 | `validate` + `check_aixml` | ~118 ms | 0 error |
| **G3.5 字面量存活（本轮新增）** | 每个要进测试的常量单独 convert→回导 | 一次往返/类型，可按类型缓存 | 回读值 == 写入值；否则该测试**不生成** |
| G4 文件级验证 | 回导比对、`privateDataBytes` 基线、`.lvproj` 条目 | 一次往返 | 字节数不回退、无游离条目 |
| G5 运行验证 | 套件跑**两次**（首跑 `Error 1` 是已知）；区分 `Broken`/`Failed`；读 JUnit 报告而非 `error out` | 两轮 | 报告 0 失败 |
| G6 冷启动复核 | 重启后重探 `execState`、重跑套件 | 一次重启 | 与 G5 一致 |

G3.5 之所以独立成闸而不是并进 G4：它是**按类型的一次性投资**，测一次可以长期复用；
而 G4 是**按文件**的，每次构建都要付。混在一起会让"要不要再测一遍"变成每次都问的问题。

### 本轮新增铁律

- **R10-1 常量先验存活，再进测试。** 已知 `timestamp` 丢弃；其余五类（string/path/double/int32/bool）
  实测保留。**一个对着被丢弃值的绿测试比没有测试更坏。**
- **R10-2 类阶段是成本与风险的双高点（占 49 %）。** 类建成后立刻记 `privateDataBytes` 基线，
  任何"重跑既有成员"的操作之后必须比对；变化即视为损坏，只能重建。
- **R10-3 不信任派生摘要字段。** `inheritsFrom` 会把接口报成父类（全站 46/437）。
  要判父子关系就解析 `<Item Type="Parent">` 的 `URL` 并读目标的 `IsInterface`。
- **R10-4 `connection` 标志按角色定，不按习惯定。** `error in`/`error out` = `recommended`；
  调用方必须提供的输入 = `required`（否则调用方漏接即 `Error 1003`）；纯装饰不要动。
  全工程必须一致——它会进桩的身份哈希。
- **R10-5 状态码是摘要，证据在载荷。** 成功要看文件/回导；失败要看 `diagramSubVis`、
  `callTargets`、`nodesSwapped`。两个方向都可能撒谎。
- **R10-6 样板超过"帧×隧道"规模就写生成器。** 判据是"LabVIEW 侧便宜、作者侧贵"。
- **R10-7 多代理：一个代理一个输出目录；代理只写 `Call` 然后停；swap 由编排方集中做；
  改代理名单后验收靠重启。**

---

### R10-4 已落成可执行规则：`LV009`（含两次自我修正）

R10-4 本轮就写进了闸门，因为它是唯一一条**不需要 LabVIEW 就能判定**的新规则。
但它**差点变成重复实现**，过程比结论更值得记：

**第一版**：所有 `error` 端子写 `required` → error，写 `optional` → warning。
写成后跑全库，**一个都没命中** —— 包括 Round9 点名的那 5 个 fixture。查下去发现两件事：

1. 那 5 个 fixture 的 `required` 落在 `obj in`/`obj out`/`Setpoint`/`Unit` 上，**本来就该由调用方接**。
   Round9 那句话方向对、**对象写错了**：伤到未接线调用方的是 **error 端子**上的 `required`。
   → 规则收窄到 error 端子是对的，但…
2. **上游已经有两条规则在管这件事**：`conn-required-output`（任何 Indicator 写 `required` → error）、
   `conn-error-in-not-recommended`（Control 名叫 `error in` 且 **带 `conIdx`**、非 `recommended` → warning）。
   我的第一版和它们重叠 —— 正是 LV002 退役时记下的那个教训（同一条规则的第二个实现会漂移，
   且每条告警翻倍）。

**最终版只保留上游的两处空白**，并把边界钉在探针里：

| 端子 | 写法 | `conIdx` | 谁负责 | 实测 |
|---|---|---|---|---|
| `error in`（Control） | `required` | **无** | **LV009** | ✅ error |
| `error out`（Indicator） | `optional` | 无 | **LV009** | ✅ warning |
| `error out 2` | `recommended` | 无 | 都不报 | ✅ 静默 |
| `error out 3`（Indicator） | `required` | **有** | **上游** `conn-required-output` | ✅ 上游 error，LV009 静默 |
| `Setpoint`（普通输入） | `required` | 无 | 都不报 | ✅ 静默（不该管） |
| `Last Error Count` | `optional` | 无 | 都不报 | ✅ 静默（名字锚定在开头） |

探针 `research/artifacts/round10/lv009-probe.aixml.xml` **故意含错、永不 convert**，
作用是证明"同一故障只被一个检查器计一次"。两个检查器分开跑的结果如上：
我们的报 `4200` + `4203`，上游报 `4205`，**不重不漏**。

> 连带结论：**不要笼统禁止 `required`**。类端子、必填输入用 `required` 是正确的表达；
> 只有 error 簇是"可省接线"的那一类，把它设成 `required` 才变成陷阱。
> 上游若哪天把它自己的规则放宽到覆盖这两处，**就删掉 LV009**，不要两个都算。

全站计数随之从 21 error 变为 **23**（21 条既有 + 探针刻意留的 2 条：LV009 一条、
上游 `conn-required-output` 一条）。
这不是回归，是把一条原先只写在散文里的规则变成了会被数出来的东西 ——
探针的错误是**校准用的已知错误**。

## 8. 能力边界的更新
| 能力 | 判定 | 依据 |
|---|---|---|
| 类 + 接口 + 访问器 + override + mock + 测试 | **可生成**（语料 57 个类、112 个测试的实证） | 全语料 |
| 11 帧 / 121 隧道的 case 机 | **可生成，但必须脚本化** | atm-cld §5 |
| typedef 全变体（嵌套、数组元素、严格/非严格、类字段绑定） | **可生成，成本 10 %** | mixedrig |
| 引用工程内既有 VI | 可生成，需 placeholder + swap，且需活跃工程 | 13/25 篇 |
| DQMH 完整模块 | 仍不可生成（消费侧可行） | Round7/8 结论未变 |
| `Bundle` 新建多元素簇 | **不可用**，改 `Bundle By Name` | atm-cld §13c |
| 非空 `timestamp` 字面量 | **不可表达**（丢弃） | alarmgate §3 |
| 类成员就地重写 | **禁止**（毁类） | thermostat §4 |

---

## 9. 下一步

**离线可做（LabVIEW 不在也能推进）**
1. ~~把 R10-4 做成规则~~ **本轮已完成**：`LV009` + 探针，见 §7.1。下一步可扩到
   "非 error 端子里哪些必须 `required`"——但那需要一份 pane 约定表，暂不做。
2. 把 §5 的测试层判据做成检查脚本：读 JUnit `.xml`，区分 `Broken`/`Failed`，命中 `Broken` 即
   fail-fast。**需要真实报告样本**，本机没有，下轮拿到再写。
3. `tools/cold_build_census.py` 扩成通用"语料普查"：参数化关键词表，便于下次直接看新一批文档。
4. 把这 25 篇的**故障-修复对**整理成可检索表（`recurrence.csv`），
   供 G2 生成阶段"预判本形态最可能踩哪个坑"用。

**需要 LabVIEW（下轮优先）**
4. 升级 ≥ v2.2.0 + `lvai_dump_schema` 核对；升完先跑 `audit_aixml` 防迁移漏。
5. P1–P5（事件结构）与 P6–P9（类方法自调/接口保存顺序/Caraya/冷启动）尚未跑。
6. **新增 P10**：`timestamp` 存活复验（本机 LabVIEW 2026 + 中文版是否同结论）——
   这是本轮唯一一条"如果本机不同则会影响所有测试生成"的结论。
7. **新增 P11**：`inheritsFrom` 全站扫描（复现 449 链接的解析率），
   顺便验证中文版 `Get LV Class Default Value` 路径是否影响 URL 解析。

---

## 附：产物清单

| 文件 | 内容 |
|---|---|
| `research/19-cold-build-corpus.md` | 本报告 |
| `research/artifacts/round10/cold-build-census.csv` | 25 篇逐条：日期、行数、章节、终态、错误号、工具、负对照、lint |
| `research/artifacts/round10/cold-build-census.json` | 同上 + 汇总统计，供脚本消费 |
| `tools/cold_build_census.py` | 普查器（无 LabVIEW 依赖），可对任意上游 checkout 重跑 |
| `research/artifacts/round10/lv009-probe.aixml.xml` | LV009 的三档判定探针（**故意含错，永不 convert**） |
| `research/artifacts/round10/lint-sweep-report.md` / `.json` | 加入 LV009 后的全库复审：51 份 = 21 条既有 error + 2 条探针刻意 error（23 总） |
| `tools/lvrule_check.py` | 新增 LV009（本轮），共 8 条在用规则（LV002 退役） |
