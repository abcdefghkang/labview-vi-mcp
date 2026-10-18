# AIXML 复杂程序生成实战：循环、移位寄存器、子 VI 与项目容器（research 08）

> 第三轮研究（复杂程序方向）。第二轮（`05`/`06`/`07`）解决了"AI 从零生成**单个简单**
> VI"；本文解决"AI 从零生成**复杂程序**"：带循环 + 移位寄存器 + 条件结构的算法 VI、
> 调用子 VI 的多 VI 程序、以及容纳它们的 `.lvproj` 项目容器。
>
> 结论标注惯例：**【实测】** = 本次在真实环境（LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP
> 2.0.1）调用 MCP 工具取得的一手数据；**【源码】** = 来自 Zuehlke/labview-mcp 参考代码库
> 及其文档的结论；**【经验】** = 来自 MCP 协议规范与社区生态的通用结论。
>
> 配套：[`09-measured-session-2.md`](09-measured-session-2.md)（本轮全部实测原始记录）、
> [`artifacts/round3/`](artifacts/round3/)（本轮生成的 VI、AIXML 源码与对分实验文件）。

## 目录

1. [复杂度的分级与本轮战果](#1-复杂度的分级与本轮战果)
2. [核心发现一：ShiftReg 种子规则（本轮最大坑）](#2-核心发现一)
3. [核心发现二：While Loop 的后置条件语义](#3-核心发现二)
4. [核心发现三：多 VI 程序（Call 子 VI）](#4-核心发现三)
5. [核心发现四：手写 .lvproj 项目容器](#5-核心发现四)
6. [核心发现五：uid 保留区与编号策略](#6-核心发现五)
7. [本机环境故障模式全集](#7-本机环境故障模式全集)
8. [已验证合法的复杂结构清单](#8-已验证合法的复杂结构清单)
9. [生成复杂程序的推荐流程](#9-生成复杂程序的推荐流程)
10. [尚未解决的边界与下一轮方向](#10-尚未解决的边界与下一轮方向)

---

## 1. 复杂度的分级与本轮战果

### 1.1 复杂度分级

参考库实测结论：900 个生产 VI 中仅 15% 能经 AIXML 重新生成，70% 调用项目自己的 subVI，
而生成器一律拒绝。【源码】本轮的目标就是把"15%"里最难的那部分——**自包含的算法型
VI**（循环 + 移位寄存器 + 条件结构 + 数组收集）——打成正例，并试探子 VI 边界。

| 级别 | 形态 | 状态 |
|---|---|---|
| L1 直线型 | 控件 → 节点 → 显示器 | 第二轮已解决（`Temperature Monitor.vi`）【实测】 |
| L2 算法型 | While/For + ShiftReg + Case + 索引隧道 | **本轮解决**：`Saturating Accumulator.vi`，4/4 功能测试通过【实测】 |
| L3 多 VI 型 | 主 VI 循环内 Call 子 VI | **本轮解决**：`Clamp Demo.vi` + `Clamp Value.vi`，2/2 测试通过【实测】 |
| L4 项目型 | `.lvproj` 容器 + 多 VI + 依赖 | **本轮解决**：手写 lvproj 被 LabVIEW 接受并打开【实测】 |
| L5 引用外部既有库 | 调用未打开的 subVI、.ctl、XControl | 未解决（ValidateAIXML 一律拒绝）【实测】 |

### 1.2 本轮三个端到端成果

1. **饱和累加器**（单 VI，L2）：While 循环 + 3 个 ShiftReg（累加值/迭代计数/饱和标志）+
   Case 双帧饱和逻辑 + 索引输出隧道收集历史数组 + 循环内自算停止条件。生成后运行
   4 组参数全部符合预期（详见 §3.3 与 `09-measured-session-2.md`）。【实测】
2. **钳位程序**（L3+L4）：`Clamp Value.vi` 子 VI（两个**嵌套** Case 实现区间钳位）被
   `Clamp Demo.vi` 主 VI（While 循环内 Call）调用，2 组参数全部通过，其中下界钳位路径
   （第一个候选值 1.5 被向上钳到 2）精确命中。【实测】
3. **项目容器**：手写 `Clamp Demo.lvproj` 通过 `describe_project`（errorCode 0）与
   `open_file`（errorCode 0）。【实测】

---

## 2. 核心发现一：ShiftReg 种子规则（本轮最大坑）

### 2.1 故障现象

一个语法"显然正确"的 While + 3×ShiftReg + Case 设计，`lvai_validate_aixml` 一律拒绝：

```
errorCode 1
While循环: 属于循环成员
连线: 属于循环成员 ×3
详情：由于连线形成一个循环……两部分均无法执行
```

报错说"连线成环"，但图上是教科书式的标准模式（累加器、计数器、标志位各一个 SR），
没有任何真实环路。

### 2.2 对分实验：五个变体锁定根因

用同一设计的变体逐个排除嫌疑因素（全部文件见 `artifacts/round3/`）：

| 变体 | 改动 | validate 结果 | 排除的嫌疑 |
|---|---|---|---|
| 基线 `saturating-accumulator` | — | errorCode 1（1 结构 + 3 连线成环） | — |
| A `variant-a-nocase` | 去掉 Case 结构，SR 直连 | errorCode 1（同样报错） | **不是 Case 的锅** |
| B `variant-b-noindex` | 去掉 `mode="index"` 输出隧道 | errorCode 1 | **不是索引隧道的锅** |
| C `variant-c-panelstop` | Condition 改读面板 Stop 控件经隧道 | errorCode 1 | **不是 Condition 数据来源的锅** |
| D `variant-d-rootseds` | 三个 SR 种子全部移到**根级** | **errorCode 0** ✓ | 锁定：**种子来源** |
| E `variant-e-mixedseeds` | 只把 SR230 种子移到根级，另两个仍循环内 | errorCode 1（2 连线成环） | **任一**循环内种子即触发，无侥幸 |

### 2.3 规则陈述

> **【实测】ShiftReg 的 `Left inputs`（种子）必须来自根级元素（`uid_parent="root"`），
> 不允许来自循环内任何元素——包括循环内常量和循环内节点的输出网。**
>
> 违反时 LabVIEW 校验器把该连线判为"属于循环成员"从而成环，报错文案具有误导性
> （说的是"连线成环"，实际是"种子寄生在循环体内"）。

错误写法（基线，失败）：

```xml
<!-- 220 是循环内常量（uid_parent="200"），作种子即非法 -->
<Constant _name="Zero" outputs="value:220.zero" type="int32" uid="220" uid_parent="200" value="0"/>
<ShiftReg uid="233" uid_parent="200">
  <Left inputs="value:220.zero" outputs="value:241.iter" .../>
```

正确写法（`saturating-accumulator-v2`，通过）：

```xml
<!-- 种子常量放根级 -->
<Constant _name="Zero" outputs="value:220.zero" type="int32" uid="220" uid_parent="root" value="0"/>
<ShiftReg uid="233" uid_parent="200">
  <Left inputs="value:220.zero" outputs="value:241.iter" .../>
```

两种容易混淆的**合法**情况（防止把规则记错）：

- 种子是**根级控件**（如 `Start Value`），SR230 直读 `value:100.value` 不过隧道——合法；
- **循环内常量喂普通节点**（如 `One` 喂 Add）——合法，本轮与参考库 t24 先例双重确认。
  非法的只有"循环内元素 → SR Left inputs"这一种组合。

### 2.4 为什么会这样（机理假设）

AIXML 的 ShiftReg 语义上是一次"跨迭代的直读"：Left outputs 网在循环内被消费
（如 `240.acc` 被 Add 读），Left inputs 提供初值。若初值也定义在循环内，LabVIEW 认为
该网"每一迭代重新定义却要跨迭代存活"，构成无法定序的环。根级定义则明确"只定义一次"。
这与 LabVIEW 手工编程时" shift register 初值必须来自循环外"的规矩一致——**AIXML 没有
放松它，只是报错文案指错了方向**。【经验】

---

## 3. 核心发现二：While Loop 的后置条件语义

### 3.1 语义

> **【实测】While Loop 的条件端子在迭代体执行完之后检查，因此循环至少执行 1 次。**
> 把 Maximum Iterations 设为 0 **不会**阻止执行——实测 `MaxIter=0` 时循环跑了整整
> 1 次（Final=1.5, Iterations=1, History=[1.5]）。

这是 LabVIEW 的原生语义（条件接线端子默认"Stop if True"后置），AIXML 如实传递了它。
对 AI 的实践含义：

- 需求说"最多 N 次"→ 用循环内计数比较（本轮做法：`iter_next >= MaxIter → stop`），
  而不是指望 Maximum Iterations 端子；
- 需求说"可能 0 次执行"→ 必须先判断再包循环，或改用 Case 守卫；
- 写功能测试的预期值时，**别忘了第 0 次边界**（本轮 Test 4 就是作者预期写错，VI 行为
  本身正确）。

### 3.2 迭代端子 count 的两种用法

- 不读迭代序号：`count=""`（本轮两个 VI 均如此）；
- 读迭代序号：`count="net"` 把 i 接到某网上（参考库 hello world 先例）。【源码】

### 3.3 功能测试结果（饱和累加器，4/4）

| # | 参数 | 预期 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | Start=0, Inc=1.5, Limit=10, MaxIter=8 | Final=10, Iter=8, Sat=true, History=[1.5,3,4.5,6,7.5,9,10,10] | 完全一致 | ✓ |
| 2 | Start=0, Inc=1, Limit=100, MaxIter=3 | Final=3, Iter=3, Sat=false, History=[1,2,3] | 完全一致 | ✓ |
| 3 | Start=5, Inc=2.5, Limit=10, MaxIter=8 | Final=10, Iter=8, Sat=true, History=[7.5,10,10,10,10,10,10,10] | 完全一致 | ✓ |
| 4 | MaxIter=0 | （作者预期 0 次） | 跑 1 次：Final=1.5, Iter=1, History=[1.5] | VI 正确，预期错（§3.1） |

Test 3 同时验证了饱和判断的严格性：候选值**等于** Limit（10）时不饱和（`Greater?`
严格大于），下一轮 12.5 才饱和——Case 谓词语义精确传递。【实测】

---

## 4. 核心发现三：多 VI 程序（Call 子 VI）

### 4.1 模式

```xml
<Call inputs="x:250.candidate,lo:212.lo,hi:213.hi"
      outputs="clamped:280.new_acc"
      target="Clamp Value.vi" uid="260" uid_parent="200"/>
```

- `target` 写**文件名**（与子 VI 同目录即可解析）；
- `inputs`/`outputs` 按子 VI 的参数名映射到本图的线名；
- Call 可以嵌在循环内（本轮主 VI 即如此），每次迭代调用一次。【实测】

### 4.2 双后端的分歧与解法

> **【实测】ValidateAIXML 一律拒绝本地 SubVI（`Unsupported SubVI: Clamp Value.vi`），
> 但 ConvertAIXML 对已在 LabVIEW 中打开的目标 VI 可以解析。**

即"校验"与"转换"走的是两条路：

| 步骤 | 对本地 SubVI 的态度 |
|---|---|
| `lvai_validate_aixml` | 拒绝（`Unsupported SubVI`）——**预期行为，不是错误** |
| `lvai_convert_aixml_to_vi` / `generate_vi` | 若目标 VI 已在 LabVIEW 打开（`openVI:true` 生成），可解析并生成调用 |

**实践流程**：先 `openVI:true` 生成子 VI（保持在编）→ 再生成主 VI（服务器走
loadedSubVIs 路线解析 Call）→ 两者即构成可运行的程序。本轮 `Clamp Demo.vi`
8462 字节、调用链 5 级，2/2 测试通过。【实测】

这与第二轮结论互为补充：**能改的（已打开）和能生成的（自包含）各走各路；引用一个
既没打开、又不自包含的既有 subVI，仍然无解**。【源码】+【实测】

### 4.3 子 VI 内部可以嵌套结构

`Clamp Value.vi` 用了两个**嵌套 Case**（外层判 `x > hi`，内层在外层 False 帧内判
`x < lo`），frame 内再嵌结构是合法的：

```xml
<Structure _name="Case Structure" selectin="26.over_hi" uid="20" uid_parent="root">
  <CaseFrame label="Not above hi" selector="False" uid="23" uid_parent="20">
    <Structure _name="Case Structure" selectin="27.under_lo" uid="30" uid_parent="23">
      ... <!-- 内层结构直接嵌在 CaseFrame 里 -->
```

嵌套结构的隧道靠 `_id` 跨层匹配（frame 级隧道只有 `inputs`，结构级隧道只有
`outputs`，同名 `_id` 即连通——与第二轮 Case 用法一致）。【实测】

---

## 5. 核心发现四：手写 .lvproj 项目容器

### 5.1 为什么需要它

生成的 VI 散在磁盘上，用户双击单个 `.vi` 能跑，但"程序"通常以项目形式交付。本轮验证
AI 可以直接手写项目文件并被 LabVIEW 接受。【实测】

### 5.2 格式要点（踩坑三次后总结）

对照 LabVIEW 自写的项目样板（`Documents/LabVIEW Data/LVAutoSave/...lvproj`），最小
可用格式：

```xml
<?xml version='1.0' encoding='UTF-8'?>
<Project Type="Project" LVVersion="26008000">
  <Property Name="NI.LV.All.SaveVersion" Type="Str">26.0</Property>
  <Property Name="NI.LV.All.SourceOnly" Type="Bool">true</Property>
  <Item Name="My Computer" Type="My Computer">
    ...（server.* 属性组，可从样板抄）...
    <Item Name="Clamp Value.vi" Type="VI" URL="/C/Users/.../Clamp Value.vi"/>
    <Item Name="Clamp Demo.vi"  Type="VI" URL="/C/Users/.../Clamp Demo.vi"/>
    <Item Name="Dependencies" Type="Dependencies"/>
    <Item Name="Build Specifications" Type="Build"/>
  </Item>
</Project>
```

| 要点 | 违反的后果 |
|---|---|
| 必须有 `NI.LV.All.SaveVersion` 属性 | `describe_project` 报 errorCode 5000 "Error loading project" |
| VI 条目必须排在 `Dependencies`/`Build Specifications` **之前** | 同上 |
| 文件带 **UTF-8 BOM** | 同上 |
| `LVVersion="26008000"`（LabVIEW 2026 = 26.0） | 版本不匹配 |
| Item URL 格式 `/C/Users/...`（绝对路径、正斜杠、盘符变一级目录） | VI 条目无法解析 |

修好后的验证：`describe_project` errorCode 0（正确列出两个 VI），`open_file` errorCode 0。
（`lvai_open_file` 打不开项目时的报错见 §7.1 的 GBK 故障。）【实测】

---

## 6. 核心发现五：uid 保留区与编号策略

> **【实测】AIXML 的 uid 落在 10–35 会触发 LabVIEW 保留区自动修复（`uidInReservedRange`），
> 被改写到 4200+；uid ≥ 100 不触发。**

本轮 `Clamp Value.vi` 用了 10/11/12/20/21……等低 uid，生成虽成功（5623 字节），但 uid
被重写，**源文件与生成物的 uid 不再一一对应**，给后续按 uid 的增量编辑埋雷。

**编号策略**（建议写入提示词规范）：

- 所有 uid ≥ 100，控件/节点/结构各占一段（如控件 100+、节点 250+、结构 200+、隧道 210+）；
- 同一次生成内 uid 唯一，跨层不冲突；
- 线名（`terminal:wire`）全局唯一，同名即同线。

---

## 7. 本机环境故障模式全集

以下均为**本机环境特异性**问题，不是 AIXML 或服务器逻辑错误；记录它们是为了下次
遇到时不再重复排查。

### 7.1 中文版 LabVIEW 的 gRPC 错误消息崩溃 .NET 客户端（新故障模式）

`lvai_open_file` 打开一个格式错误的 `.lvproj` 时，LabVIEW 返回中文错误消息，
**以 GBK 编码上线**，而 .NET 客户端按 UTF-8 解析，直接崩：

```
InvalidProtocolBufferException: String is invalid UTF-8 ... bytes [D6] at index 393
```

（`D6D0` 正是"中"的 GBK 首字节。）**这不是调用方错误，是 LabVIEW 中文版的编码缺陷**：
同样的错误在英文版会正常返回文本。判据：看到 `bytes [D6]` 基本可确诊。
修复方式是修好被打开的文件（本例即 §5.2 的 lvproj 格式问题），让 LabVIEW 返回
"No Error"（ASCII）即可绕过。【实测】

### 7.2 服务器自带助手 AIXML 不被本机 LabVIEW 接受（已知持续）

`generate_vi` 的辅助步骤（`cleanUpPanel`/`cleanUpDiagram`/`connectorPane`）使用服务器
自带的助手 AIXML（`lvpane_probe.xml`、`lvai_cleanup_panel.xml`、`lvai_run_and_read_typed.xml`），
被本机 LabVIEW 2026 26.3.1f1（中文）以 `helperAixmlInvalid` 拒绝——**这些步骤必失败，
但不影响 VI 生成本体**（validate/convert 均 errorCode 0）。生成物不含面板整理与连接器
面板定义，需事后手工或经 pylabview 补。【实测】

### 7.3 ValidateAIXML 杀 LabVIEW 的 NI bug（第二轮已记录）

对含未知 VI Server 类的输入，ValidateAIXML 可能杀死 LabVIEW 进程；详见参考库
`docs/ni-bug-validateaixml-crash.md`。【源码】

---

## 8. 已验证合法的复杂结构清单

本轮正面确认（可安全写入提示词模板）：

| 结构 | 形态 | 证据 |
|---|---|---|
| While Loop | 后置停止条件、循环内自算条件、`count=""` | 累加器、Clamp Demo |
| ShiftReg | 多个并存、根级种子、根控件直读种子 | 3×SR 全部通过 |
| Case Structure | 双帧、谓词严格大于、帧输出喂 SR Right | 饱和逻辑 |
| 嵌套 Case | Case 嵌在 CaseFrame 内 | Clamp Value.vi |
| 索引输出隧道 | `mode="index"` 收集每次迭代的值成数组 | History 输出 |
| 循环内常量 | 喂普通节点、喂 CaseFrame 隧道 | 222/223/224 |
| fan-out | 一线多名读者（`new_acc` 同时喂 SR Right 与索引隧道） | v2 与 Clamp Demo |
| 跨迭代 Call | 循环内 Call 子 VI | Clamp Demo |
| Condition 读循环内网 | Condition inputs 指向循环内节点输出 | 254.stop |

---

## 9. 生成复杂程序的推荐流程

1. **先设计数据流再写 AIXML**：把每个跨迭代量标出来（值、计数、标志），**它们的种子
   全部提升到根级**（常量或控件），这是本轮最大教训；
2. **分 VI 生成，自底向上**：先生成子 VI（`openVI:true` 保持在编），再生成主 VI；
   主子 VI 放同一目录，`target` 写文件名；
3. **validate 预期管理**：含 Call 时 validate 拒 SubVI 是**正常**的，看 convert 结果；
   纯自包含 VI 才要求 validate errorCode 0；
4. **uid 从 100 起编**，控件/节点/结构/隧道分号段；
5. **生成后必须功能测试**：至少覆盖"正常路径 + 饱和/边界路径 + 计数路径"，
   边界别忘 While 至少跑一次；
6. **多 VI 程序补一个手写 .lvproj**：按 §5.2 清单自检（SaveVersion/顺序/BOM/URL）。

---

## 10. 尚未解决的边界与下一轮方向

**未解决**：

- 引用**未打开**的既有 subVI（生产代码的主流形态）——validate 拒绝、convert 无法解析；
- 类型定义（.ctl）、LVClass、DQMH 模块经 AIXML 从零生成（参考库有对应工具但未实测）；
- 事件结构、状态机（While+Case 组合的手工等价物）的规模化生成；
- 数组/字符串/簇的复杂操作（索引数组、拼接、簇打包）节点覆盖面。

**建议下一轮方向**（按价值排序）：

1. **状态机模板化**：While + Case(字符串选择) + ShiftReg(状态) 是 LabVIEW 最常用复杂
   模式，把本轮 seed 规则套上去应可解；
2. **.ctl 类型定义生成**：解一半"自定义类型"依赖；
3. **既有多 VI 程序的 AIXML 导出→修改→回写**（读侧），补上"改已有程序"这一半；
4. **pylabview 字节级编辑链**：对 AIXML 表达不了的（图标、布局、连接器面板）用
   pylabview 补，与 AIXML 生成链拼接成完整工作流。
