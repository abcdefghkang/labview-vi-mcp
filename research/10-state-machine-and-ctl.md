# 10 — Round4：状态机模板化、.ctl 类型定义与读侧闭环

> 标注惯例：【实测】= 本机一手测量数据；【源码】= 参考代码库/官方示例结论；【经验】= 通用工程结论。
> 环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1；生成走 grpc AIXML 通道
> （validate → convert），运行与 .ctl 创建走 pylabview（ActiveX），读侧导出走 grpc。
> 产物：`research/artifacts/round4/`（清单见该目录 README）。

Round4 的目标是把"复杂程序"从 round3 的"嵌套循环 + 子 VI"推进到工业界最常见的复杂形态——
**状态机**，并补上两块基础设施：**.ctl 类型定义**（让状态/数据有名字）与
**读侧闭环**（VI → AIXML，让 AI 能回读自己生成的代码）。三项均已完成实测。

---

## 1. 为什么先打状态机

LabVIEW 的"复杂程序"在工业现场绝大多数是状态机形态：While + Case(枚举选择) +
ShiftReg(状态) 构成最小内核，外围套数据寄存器、事件、超时。round3 已验证了
While + Case + SR 的**部件级**拼法（saturating-accumulator-v2），但当时留下三个
未回答的问题，Round4 逐一击破：

1. Case 帧内的节点能不能**直读**循环级的 SR 网（不经隧道）？——决定帧内代码密度；
2. 状态选择器用什么类型？字符串 Case 能不能手写？——决定状态机的可生成性；
3. 每帧对 Out 隧道负有什么义务？停止条件怎么接？——决定模板能否参数化。

## 2. 先行探针：帧内直读循环级 SR 网【实测】

在写状态机之前先用最小探针 `probe-frame-sr-read.aixml.xml`（38 行）验证问题 1：
Case Structure（260）在 While（200）内，SR（230）在循环级，Accumulate 帧内的
Add 节点直接读 SR Left 的输出网：

```xml
<Structure _name="Case Structure" selectin="value:102.value" uid="260" uid_parent="200">
  <CaseFrame label="Accumulate" selector="True" ...>
    <Node _name="Add" inputs="x:240.acc,y:268.step" outputs="x+y:262.new" uid="262" uid_parent="261"/>
    <Tunnel _id="Out1" inputs="value:262.new" uid="263" uid_parent="261"/>
  </CaseFrame>
  <CaseFrame label="Pass through" selector="False" ...>
    <Tunnel _id="Out1" inputs="value:240.acc" uid="265" uid_parent="264"/>
  </CaseFrame>
```

结果：**validate errorCode 0 → convert 成功（7099 字节）→ pylabview 运行 2/2 通过**
（Mode=true → Final=11/Iter=3；Mode=false → Final=2，与手推一致）。

**结论**：帧内节点可以直读循环级 SR 网（网模型下 SR Left 输出网对帧内可见），
不需要为每个数据寄存器建输入隧道。这把状态机帧的写法从"全隧道"简化为
"读直连、写隧道"——只有**跨帧回写**才走 Out 隧道。这正是 NI 官方状态机的形态。

## 3. 状态选择器：字符串 Case 不可手写，必须用内联枚举【实测】

### 3.1 失败的尝试

最初想用字符串状态（`selectin` 读字符串网，帧 `selector="&quot;Init&quot;"`），
因为字符串状态在 G 语言状态机教材里最常见。最小探针
`probe-string-case.aixml.xml`（含 Default 帧）**validate 仍报
"部分选择器值无对应分支"**；加/不加引号、加/不加 Default 帧四种拼法全部失败。

### 3.2 NI 规范解法：内联枚举

从 NI 官方示例导出的参考文件
`ref-state-machine-fundamentals.aixml.xml`（`examples/Design Patterns/State Machine/
State Machine Fundamentals.vi`，10010 字节）揭示了规范拼法——状态类型是**内联枚举**：

```xml
type="uint16{Init,Load,Accumulate,Report,Stop}"
```

- 类型声明直接写在 Control/Constant/Indicator 的 `type=` 属性里，value 写**项索引**
  （Init=0, Load=1, Accumulate=2, Report=3, Stop=4）；
- Case 的 `selectin` 读该枚举网；帧的 `selector="&quot;Init&quot;"` 用**项名加引号**
  （XML 实体 `&quot;`）；
- 该形态本机全链路通过：validate 0 → convert → 运行 → 读侧回导，类型往返不丢失。

**规则（写进模板）**：AIXML 手写状态机的状态类型必须用内联枚举
`uint16{项1,项2,...}`；字符串 Case 现阶段不可手写。这也解释了 round3 里
Case 用 bool 选择器能过、字符串不能过的现象——bool 是两种框架都支持的特例。

## 4. 最终模板：Batch Averager 状态机

### 4.1 骨架（`batch-averager.aixml.xml`，约 130 行）

```
While Loop (200)
├── In 隧道: Items 数组进循环
├── Array Size (250)：循环级算一次，供 Accumulate 帧比较
├── ShiftReg 230 state     Left←Initial State(100)   Right←Case Out1
├── ShiftReg 236 sum       Left←ZeroD(221)           Right←Case Out3
├── ShiftReg 239 index     Left←Zero(220)            Right←Case Out4
├── ShiftReg 242 item      Left←ZeroD(221)           Right←Case Out5
├── ShiftReg 245 log       Left←EmptyLog(222)        Right←Case Out6
├── ShiftReg 248 avg       Left←ZeroD(221)           Right←Case Out7
├── Condition (201)：读 Case Out2 的停止标志网
└── Case Structure (300)  selectin="231.state"
    ├── Out1..Out7（结构级隧道，网名即回写目标）
    ├── CaseFrame Init(310)      → ToLoad(1)
    ├── CaseFrame Load(330)      → ToAccumulate(2)
    ├── CaseFrame Accumulate(350)→ Select(Less?(new_index,size), BackToLoad, ToReport)
    ├── CaseFrame Report(370)    → ToStop(4)，Divide(sum,index)→avg
    └── CaseFrame Stop(400)      → StayStopped(4)，Out2=true
```

### 4.2 手写规则（全部实测踩坑得出）

| # | 规则 | 违背后现象 |
|---|---|---|
| 1 | SR `Left inputs` 种子必须来自**根级**元素 | 成环误报（round3 复测仍成立） |
| 2 | `selectin` 写**裸网名**（`231.state`）；NI 读侧规范形式是 `<Case自身uid>.value` | 带 `value:` 前缀 validate 失败 |
| 3 | 状态常量 `type="uint16{...}"` + `value="项索引"` | 字符串 Case 无对应分支（§3） |
| 4 | **每帧必须给所有 Out 隧道显式赋值**：非 Stop 帧 Out2 接 false 常量；非 Report 帧 Out7 接 SR 均值网（`249.avg`）或 0 | 空 `inputs="value:"` 报"隧道未赋值"×N |
| 5 | 停止条件用**条件隧道**：Stop 帧 Out2 经 `cond="true"` 置 true，Condition 直读该网 | Condition 直读 SR Right 的 outputs 网触发"连线成环"误报 |
| 6 | 跨迭代保留的值必须过 **SR**：Case 隧道输出是"每次迭代的线"，Indicator 要读 SR Right 的输出网 | 见 §4.3 事故记录 |
| 7 | 条件转移用 `Select`：`Less?(353.new_index,250.size)` → `Select(t,s,f)` 两个状态常量 | — |
| 8 | uid 全部 ≥100 | 低 uid 触发保留区改写（round2 规则） |

关于规则 5 的细节：手写文档里 `cond="true"` **不能**让空网合法（规则 4 仍然生效）；
`cond` 的语义是"该隧道携带循环条件"，NI 导出文件里条件隧道同样带 `cond="true"`
（见 `batch-averager-exported.aixml.xml` 第 197–203 行 Out2 与读侧 §5 对照）。

### 4.3 功能测试与一次典型事故【实测】

convert 产物 `Batch Averager.vi`（13754 字节），pylabview 路线 4 组功能测试：

| 测试 | 输入 | 结果 |
|---|---|---|
| 1 正常批处理 | Items=[1.5,2.5,3.5,4.5]，Initial=Init | Average=3.0 ✓，Log 轨迹与手推逐字一致 |
| 2 单项 | Items=[2]，Initial=Init | Average=2.0 ✓ |
| 3 中途启动 | Initial State="Accumulate"（按项名赋值，pylabview 路线支持） | 从 Accumulate 起跑，轨迹正确 ✓ |
| 4 空数组 | Items=[] | 受运行路线限制：pylabview 把 `[]` 具体化为单个 0 元素（读侧同样），非 VI 缺陷；结构覆盖由 `Batch Averager Empty.vi`（默认 `[]`）承担 |

**事故记录（Average=0）**：第一版 Indicator 直读 Case 的 Out7 隧道输出网
（`307.avg`），结果测试 1 得 Average=0（预期 3）。原因是**隧道值是每次迭代的线**——
最后一帧是 Stop，其 Out7 填 0，Indicator 读到的是停止那一 iteration 的值。
修法：给平均值单独建 SR（248），Indicator 改读 SR Right 的输出网
（`252.final_avg`）。这是状态机模板最重要的一条数据流规则：**任何要活过循环结束的值，
都必须过 Shift Register**。

## 5. 读侧闭环：VI → AIXML【实测】

### 5.1 导出实测

`lvai_convert_vi_to_aixml`（grpc 路线）导出本轮两个 VI：

| 源 VI | 结果 | 字节 | fromCache |
|---|---|---|---|
| `Batch Averager.vi` | errorCode 0 | 21844 | false |
| `Batch Averager Empty.vi` | errorCode 0 | 21835 | false |

`fromCache=false` 意味着 LabVIEW **真实加载**了我们用 pylabview 路线（无 LabVIEW
环境）组合出的 VI——**跨路线兼容性就此证明**：AIXML 生成物不是"只有组合器自己认得
的半成品"，而是真 LabVIEW 可加载、可序列化的一等公民。

### 5.2 uid 保真度：手写主要元素 100% 保留

| 元素 | 手写 uid | 回导 uid |
|---|---|---|
| While Loop | 200 | 200 ✓ |
| Case Structure | 300 | 300 ✓ |
| 5 个 CaseFrame | 310/330/350/370/400 | 全 ✓ |
| 结构级 Out 隧道 ×7 | 301–307 | 全 ✓ |
| 6 个 ShiftReg | 230/236/239/242/245/248 | 全 ✓ |
| Condition | 201 | 201 ✓ |
| 控件 Initial State/Items | 100/101 | 全 ✓ |
| Indicator ×5 | 500–504 | 全 ✓ |
| 常量 Zero/ZeroD/EmptyLog | 220/221/222 | 全 ✓ |

内联枚举类型 `uint16{Init,Load,Accumulate,Report,Stop}` 在常量、控件、Indicator
三类元素中往返保留。**结论：AI 可以用自己写出的 uid 在回导文件里定位每一个元素**——
读侧闭环成立，这为"生成 → 回读 → 增量修改"的迭代循环提供了坐标系。

### 5.3 读侧形式 vs 写侧形式（回导时要注意的差异）

| 维度 | 手写（生成） | 回导（序列化） |
|---|---|---|
| Case 选择器 | `selectin="231.state"`（裸网名） | `selectin="300.value"`（Case 自身 uid，NI 官方参考同形式） |
| 网名 | 语义名（`231.state`、`302.stop`） | `<终端uid>.value`，按终端重新派生 |
| 帧内隧道 | 只写本帧用到的 | 每帧枚举**全部** In 隧道，未用者 `outputs="value:"` 留空 |
| 自动 uid | 手写 100–504 | 帧内隧道自动占 13xx–19xx |
| 空 outputs | Out 隧道不接受空（规则 4） | SR Right 无消费者时 `outputs="value:"` 合法 |

读侧导航规则：回导文件里不要按记忆中的网名找网，应按 **Case 的 selectin** 定位
状态网、按 **SR Right 的 outputs** 定位寄存器终值。隧道方向记忆法：
In 隧道 = 结构级 `inputs`（外）/ 帧级 `outputs`（内）；Out 隧道 = 结构级 `outputs`（外）/
帧级 `inputs`（内）。

## 6. .ctl 类型定义【实测】

### 6.1 两条路线

`lvai_create_typedef` 的 grpc 路线在本机报 `helperGenerationFailed`
（`lvtd_make_typedef.xml` 助手不 validate，与 round2 运行助手同源的问题）；
切 `backend:"pylabview"` 后一次成功。两个 .ctl 均经 `describe_ctl` 验证 +
`lvai_open_file` 让 LabVIEW 本身打开：

| 文件 | 形态 | describe_ctl | LabVIEW 打开 |
|---|---|---|---|
| `Batch Averager State.ctl` | strict typedef，内联枚举 5 项 | isTypedef=true, isStrictTypedef=true, controlVIType=2, wrappedType=TypeDef, needsLabviewSave=false, bindable=true | errorCode 0 |
| `Sample Stats.ctl` | plain typedef，cluster{double.Sum, int32.Count} | isTypedef=true, isStrictTypedef=false, controlVIType=1, bindable=true | errorCode 0 |

### 6.2 AIXML 无形 referring 言引用 .ctl——边界与出路

参考文档明确 AIXML 语法里**没有 typedef 引用机制**：`.ctl` 既不能作 Call target
也不能作 `type=`。实测的两个变通方向：

1. **值层面**：把 .ctl 包着的类型用 `describe_ctl` 读出来（wrappedType/fields），
   按等价的内联形式写进 AIXML（如 `type="uint16{Init,Load,...}"`）——本次状态机
   即此路线，`.ctl` 与 AIXML 内联枚举保持同构；
2. **绑定层面**：`lvai_bind_pane_typedef` 可把已生成的控件/Indicator 绑到 .ctl，
   但该工具要求类成员上下文（class field），本轮未扩测，列为下一步。

**结论（现阶段）**：.ctl 解决"类型有名字、可绑定、可被 NI 工具链识别"；
AIXML 内联类型解决"生成时能写"。两者通过 describe_ctl 读出的类型描述对齐，
是当前唯一打通的桥。

## 7. Round4 新增规则汇总（可复用清单）

1. 状态机 = While + Case + SR；帧内**直读** SR 网，只把**回写**走 Out 隧道；
2. 状态类型必须内联枚举 `uint16{...}`；字符串 Case 不可手写；
3. 每帧给全部 Out 隧道显式赋值；停止走 `cond="true"` 隧道 + Condition 直读；
4. 活过循环的值必须过 SR（Average=0 事故）；
5. SR 种子根级（round3 规则复测成立）；
6. 回导文件 uid 与手写 100% 对应，可按 uid 定位；网名会按终端重派生；
7. .ctl 走 pylabview 路线创建；AIXML 无 typedef 引用，用内联同构类型桥接；
8. 运行路线（pylabview）会把 `[]` 具体化为单元素——空数组类输入的结构覆盖
   用"默认值为 `[]` 的独立 VI"承担。

## 8. 下一步方向

1. **pylabview 编辑链**：用 `mcp__labview__pylv_*`（extract/apply/rebuild/route）
   对生成的 VI 做增量修改，验证"读侧坐标 + 写侧补丁"的编辑循环；
2. `lvai_bind_pane_typedef` 的类成员上下文扩测，打通 .ctl 绑定；
3. 状态机模板参数化：把 §4.1 骨架抽象成"状态表 → AIXML"的生成器输入格式
   （状态名/转移条件/每寄存器动作），让 AI 从表格直接产状态机；
4. 引用未打开的既有 subVI（round3 遗留边界）随编辑链再评估。
