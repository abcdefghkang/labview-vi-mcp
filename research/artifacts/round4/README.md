# round4 产物清单（研究第四轮：状态机模板化 + .ctl 类型定义 + 读侧闭环）

对应文档：`../../10-state-machine-and-ctl.md`（结论与方法论）。

环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1。
生成走 grpc AIXML 通道（validate → convert），运行走 pylabview（ActiveX），.ctl 创建与读侧导出分别见下表。

## AIXML 源码（手写）

| 文件 | 说明 | validate |
|---|---|---|
| `probe-frame-sr-read.aixml.xml` | 探针：Case 帧内节点直读循环级 SR 网 | **errorCode 0** ✓ |
| `probe-string-case.aixml.xml` | 探针：最小字符串 Case（含 Default 帧） | errorCode 1（字符串 Case 不可手写，见文档 §2.2） |
| `batch-averager.aixml.xml` | **最终状态机**：枚举形态 5 状态批量平均器，6 个 SR，7 个 Out 隧道 | **errorCode 0** ✓ |
| `batch-averager-empty.aixml.xml` | 边界变体：Items 默认 `[]`（空数组） | **errorCode 0** ✓ |
| `ref-state-machine-fundamentals.aixml.xml` | NI 官方参考导出：`examples/Design Patterns/State Machine/State Machine Fundamentals.vi` | （导出物，用于对照规范拼法） |

## 生成的 VI / .ctl（LabVIEW 2026 实测）

| 文件 | 字节 | 说明 |
|---|---|---|
| `Batch Averager.vi` | 13754 | 状态机主产物，功能测试 3/3 通过（第 4 项受运行路线限制，见文档 §4.3） |
| `Batch Averager Empty.vi` | 13780 | 空数组边界变体 |
| `Probe Frame SR Read.vi` | 7099 | 帧内读 SR 探针，运行 2/2 通过 |
| `Batch Averager State.ctl` | 3805 | 严格类型定义（strict typedef，内联枚举 5 项） |
| `Sample Stats.ctl` | 4077 | 普通类型定义（plain typedef，cluster{double,int32}） |

两个 .ctl 均经 `describe_ctl` 验证（bindable=true）并经 `lvai_open_file`
让 LabVIEW 本身打开（errorCode 0）。.ctl 创建走 **pylabview** 路线
（grpc 路线 `lvai_create_typedef` 报 helperGenerationFailed，见文档 §3.1）。

## 读侧闭环（VI → AIXML）

| 文件 | 字节 | 说明 |
|---|---|---|
| `batch-averager-exported.aixml.xml` | 21844 | `Batch Averager.vi` 回导出（grpc 路线，fromCache=false） |
| `batch-averager-empty-exported.aixml.xml` | 21835 | 空数组变体回导出 |

**uid 保真度：手写主要元素 100% 保留**（While=200 / Case=300 / 帧=310·330·350·370·400 /
Out 隧道=301–307 / SR=230·236·239·242·245·248 / Condition=201 / 控件=100·101 /
Indicator=500–504 / 常量=220·221·222）。内联枚举类型
`uint16{Init,Load,Accumulate,Report,Stop}` 在常量、控件、Indicator 中往返保留。
差异仅装饰性：自动生成的帧内隧道 uid（13xx–19xx）、网名改署为 `<uid>.value`、
序列化器为每帧枚举全部隧道（未用时 `outputs="value:"` 留空）。

## 复现要点

1. 状态类型用 NI 规范内联枚举 `type="uint16{Init,Load,...}"`，value 写**项索引**；
   字符串 Case 在本机不可手写（两种拼法 + Default 帧均 validate 失败）；
2. `selectin` 写**裸网名**（如 `231.state`）可通过 validate；NI 序列化规范形式是
   `<Case自身uid>.value`（见 ref 文件第 14 行），读侧导出均为后者；
3. 每帧必须给**所有** Out 隧道显式赋值（非 Stop 帧 Out2 接 false 常量；
   非 Report 帧 Out7 接 SR 均值网或 0）——空 `inputs="value:"` 报"隧道未赋值"；
4. Stop 帧经 `cond="true"` 隧道置停止标志，Condition 直读该网（NI 官方同形态）；
5. 跨迭代保留的值必须过 SR：Case 隧道输出是"每次迭代的线"，
   Indicator 要读 SR Right 的输出网（本次 Average=0 事故的修法）；
6. ShiftReg `Left inputs` 种子必须来自根级元素（round3 规则，本机复测仍成立）；
7. .ctl 创建用 `lvai_create_typedef` + `backend:"pylabview"`；
   AIXML 无形 referring 言引用 .ctl（不能作 Call target 也不能作 `type=`），
   绑定须走 `lvai_bind_pane_typedef` 且要求类成员上下文。
