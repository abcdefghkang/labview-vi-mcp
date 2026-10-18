# AIXML 与 VI 生成实战（research 05）

> 本文是「AI 写 LabVIEW 代码」的技术底册：AIXML 格式规则、生成流水线、双后端切换。
> 配套：[`06-best-practices.md`](06-best-practices.md)（实践方法论）、
> [`07-measured-session.md`](07-measured-session.md)（本次实测原始记录）。
> 标注惯例：**【实测】** 一手调用数据 / **【源码】** 参考库结论 / **【经验】** 生态通用结论。

## 1. AIXML 是什么

LabVIEW 方块图的文本形态：根元素 `<VI>`，内含 Control/Indicator/Constant/Node/Call/
FreeLabel/Structure；结构件里嵌 Tunnel/ShiftReg/CaseFrame/Condition。【源码】

**为什么需要它**：`.vi` 二进制不可读，模型无法直接产出；AIXML 让"读代码"变成读文本、
"写代码"变成写文本，再由 LabVIEW 自己把文本编译成真 VI（产出的 `.vi` 与手画的无法
区分——实测本次生成的 `Temperature Monitor.vi` 可直接运行）。【实测】

**它没有什么**：没有 XSD（规则是经验归纳的，见参考库 `docs/aixml-reference.md`，
服务器以 `lvai_aixml_reference` 工具和 MCP 资源 `labview://aixml-reference` 形式提供）；
没有坐标（布局、大小、图布整理不可表达）；没有编译代码。【源码】

## 2. 核心模型：两套正交的系统

### 2.1 层次：uid + uid_parent

```xml
<Structure _name="For Loop" uid="141" uid_parent="root">
  <Node _name="Add" uid="101" uid_parent="141"/>   <!-- 101 套在 141 里 -->
</Structure>
```

`uid_parent` 指向不存在元素的后果不是报错，是**静默重挂到顶层**——循环里的节点跑到
循环外，validate/convert/run 全不报告。【源码】【实测】`lvai_check_aixml` 专项抓这个。

### 2.2 数据流：线名（net），不是指针

`<uid>.<terminal>` 命名一根**线**；两个端子接了同一根线 iff 它们写同一个线名；
fan-out = 多个输入写同一线名。**`inputs` 不指向源元素**，元素甚至可以引用自己 uid
的线。【源码】

```xml
<Control _name="X" outputs="value:1306.value" type="int32" uid="1306" value="1"/>
<Node    _name="Add" inputs="x:1306.value,y:1274.value" outputs="x+y:143.x+y" uid="143"/>
```

格式：`terminal1:wire1,terminal2:wire2,terminal3:`（末尾空 = 未接线；顺序语义相关）。

### 2.3 终端名是字面 LabVIEW 标签

【实测】`lvai_aixml_reference` 原文：

> Terminal names are literal LabVIEW labels: `Increment` → `x+1`,
> `Greater?` → `x > y?` (with spaces), `Select` → `s? t\3Af`, `Or` → `x .or. y?`.
> Export a VI that already uses the node and copy the string.

**猜 = 收获一个 `Object terminal not found`。** 查法：一次批量
`lvai_aixml_reference(node='Select,Index Array,Greater?')`——单次查会重复返回同一段
文本，批查每段只印一次。【实测】

## 3. 转义、类型与属性规则

### 3.1 转义【源码】

| 序列 | 含义 | 原因 |
|---|---|---|
| `\3A` | `:` | `:` 分隔 terminal:wire |
| `\2C` | `,` | `,` 分隔条目 |
| `\0A` / `\0D` | 换行 / 回车 | 属性内不能有真换行 |

XML 实体（`&amp;` 等）在转义之上再加一层。属性名按字母序是格式惯例（不是强制）。

### 3.2 类型语法【源码】

| 形态 | 例 |
|---|---|
| 标量 | `bool` `int32` `uint32` `uint64` `double` `string` `path` |
| 数组 | `array{double}`、`array.2{double}`（二维） |
| 簇 | `cluster{double.X,double.Y}`、错误簇 `cluster{bool.status,int32.code,string.source}` |
| 引用 | `ref{UDClassInst}`、`ref{LV.VI}` |
| Ring 控件 | `style="Ring"` + `items` + `values` + `value`（默认值必须在 values 内） |

### 3.3 硬性属性规则【源码】【实测】

- `Control`/`Indicator`/`Constant` **必须有 `value`**；缺 → 整篇 Error -2628，什么都不写。
- **`net` 属性也是必须的**——未接线端子也要空 net（如 `outputs="value:"`）；接口声明的
  载荷端子就靠这个形状存活。
- `timestamp` 带非空 `value`：LabVIEW **静默丢弃**字面量（环回测试会"空比空通过"，
  什么都没钉住）。
- uid **从 42 以上分配**，避开 LabVIEW 保留区（否则日志刷
  `trying to override with non-reserved UID`，200 行 DWarn 日志会饱和）。【实测】
- FreeLabel ≤ ~45 字符，否则被静默截断。【实测】

## 4. 结构件速查

| 结构 | `_name` | 关键属性 / 子元素 |
|---|---|---|
| For Loop | `For Loop` | `count`（内部 i）、`maxin`（外部 N）、`maxout` |
| While Loop | `While Loop` | `count`；子 `<Condition inputs="…" value="stop"/>` |
| Case Structure | `Case Structure` | `selectin`；子 `CaseFrame selector="…"` |
| Tunnel In/Out | `Tunnel _id="In1/Out1"` | `mode` 空=最后值 / `index` / `concat` |
| Shift Register | `ShiftReg` | `Left inputs=初值,outputs=内读`；`Right inputs=内写,outputs=终值` |
| Property Node | `Node _name="Property Node"` | `fields="read+VI Path,write+VI Name"`，`type="{LV.VI}"` |

规则：跨边界只走 Tunnel；反馈只走 ShiftReg；**每个** Case 的**每个**输出隧道在
**每个** frame 都要有值。【源码】

## 5. 生成流水线（每一步的判据）

```
AIXML 文件
  │
  ├─① lvai_check_aixml        [离线, 0.4–53 ms, 无需 LabVIEW]
  │     抓 ValidateAIXML 放过、且会静默出错的东西：
  │     uid_parent 悬空 / 重复 uid / Ring 默认值越界 / enum 值是标签或越界 /
  │     连接器端子缺 connection（读作 required）/ 缺 value / 缺 net / 时间戳非空 /
  │     未知属性名。fix:true 可无歧义修复其中几类。
  │
  ├─② lvai_validate_aixml     [在线, 118 ms 实测]
  │     LabVIEW 本体校验：终端名、类型、连线、循环、Case 完整性。
  │     失败用 scratch 名（validatedAs），不烧真名。
  │
  ├─③ lvai_generate_vi        [在线, convert 381 ms 实测] = ②+④+面板测量 一趟
  │     或 lvai_convert_aixml_to_vi 单独转换。
  │     ⚠ 生成物必须自包含：项目本地 subVI / Express VI 一律 Unsupported SubVI。
  │
  ├─④ lvai_exec_state         [在线]  1=eIdle 过；0=eBad 打回；-1=引用没开（≠坏）
  │
  └─⑤ lvai_run_vi_and_read_values   [在线, 2 ms 实测]  按 VI 自身输出判成败
```

**【实测】流水线全绿的最小样例**见
[`examples/01-create-vi/temperature-monitor.aixml.xml`](examples/01-create-vi/temperature-monitor.aixml.xml)：
check 0 错误 0 警告（0.4 ms）→ validate errorCode 0（118 ms）→ convert 5487 字节
（381 ms）→ 图布 418×214（预算 1920×1080）→ 运行两用例输出全对。

## 6. 双后端切换

| 场景 | backend |
|---|---|
| 默认（LabVIEW ≥2026，Nigel 在线） | `grpc` |
| NI 服务起不来 / LabVIEW <2026 / CI 无许可 | `pylabview` |
| 改已有 VI / 读 `.ctl` / 动布局图标 | `pylv_*` 家族（`pylv_route` 先决策） |

【实测】本次 `run_vi_and_read_values` 在 `backend:"pylabview"` 下经 **ActiveX** 运行
成功（`via: "ActiveX"`，runMs 2）——它不需要辅助 VI，恰能绕开本机辅助脚本校验失败的
问题（见 §7.2）。优先级链与 settings.json 位置见
[`06-best-practices.md` §2.3](06-best-practices.md)。

pylabview 后端的能力边界（【源码】实测）：读回吻合 392/747（连线 93.5%）、往返
129/130；**按名拒绝**建不了的（`composerRefused`），不静默写坏 VI；为老版本 LabVIEW
按目标版本重写版本戳（LVSR/vers），避免 Error 1125。

## 7. 两个本机特有的实测发现

### 7.1 辅助 VI 的 AIXML 不被本机 LabVIEW 接受

【实测】`lvai_generate_vi` 的核心步骤（validate/convert）全绿，但三个附加步骤失败：
`cleanUpPanel`、`cleanUpDiagram`、`connectorPane` 均报 `helperAixmlInvalid`——
安装目录 `bin/scripts/` 下的辅助 AIXML（`lvai_cleanup_panel`、
`lvai_run_and_read_typed.xml`、`lvpane_probe.xml`）在本机 LabVIEW 2026 26.3.1f1
（中文）上 validate 失败，症状为「属性节点: 无效属性」「已连接两个不同类型的接线端」
等一串错误。连带 `lvai_exec_state` 报 `helperUnavailable`。

**影响面**：所有"生成辅助 VI 再驱动它"的工具（面板/图布整理、面板测量、
exec_state、run 的默认 helper）。**不影响**：check/validate/convert/describe/
convert_vi_to_aixml 等直接走 RPC 的工具，以及 pylabview 后端的运行路线。
**处置**：运行验证改用 `backend:"pylabview"`；持续出现则升级服务器版本。
（这与参考库文档记载的"某 LabVIEW 补丁级别拒绝辅助脚本属性名"同类，属版本兼容问题。）

### 7.2 CLI 后端与 VI Server 是两条独立通道

【实测】第二个 MCP 服务器（CLI 模式）`labview_get_status` 返回
`connected: true, backend: "cli"`，但同时报告 **「VI Server 连接: 失败」**，
`supports_control_io: false`、`supports_vi_scripting: false`。
**启示**：一个 MCP 服务器"连上了"不等于它宣称的能力可用；逐项看
`supports_*` 字段，别被顶层 `connected:true` 麻醉。【经验】

## 8. 从 AIXML 到项目：容器与边界

- **没有任何 RPC 创建 `.lvproj`/`.lvlib`/`.lvclass`**：手写 XML + `lvai_open_file`
  + `lvai_describe_project` 验证；已实测可加载的最小项目骨架（`LVVersion="26008000"`）
  在参考库 `docs/guide/aixml-workflow.md`。【源码】
- 类私有数据、访问器、消息类等"编译器产物"没有工具直接写，服务器改为**驱动 NI 自己
  的向导 VI**（`lvai_create_class`、`lvai_create_accessors`、`lvai_create_message_class`
  等）——这是 AIXML 系能在类/DQMH/Actor Framework 上走远的原因。【源码】
- `.ctl` 与加密码 VI 是硬墙（`errorCode 5001/5002`），参数和重试都过不去；读 `.ctl`
  用 `lvai_describe_ctl`（pylabview 直读文件）。【源码】

---

*格式规则以服务器内置参考（`lvai_aixml_reference`，16 个 section，实测可查）与参考库
`AIXML_Full.md`/`docs/aixml-reference.md` 为准；本文只收录实战高频规则。*
