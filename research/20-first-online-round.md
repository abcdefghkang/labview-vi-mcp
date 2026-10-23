# Round 11：首次在线实测 —— 环境复位、工具面真相、P10 三重确认、P11 修正

> 日期：2026-10-23
> 环境：LabVIEW 2026 (26.3.1f1) 64-bit 中文版，实例已运行 17 分钟；LabVIEWMCP **2.0.1**
> （`77eb0b22`），gRPC 服务在 `127.0.0.1:44136`（`discoveredVia: LabVIEW.exe listener`）。
> 本轮**全部为真机实测**，与前十个离线轮不同。凡引用前轮结论，都标了修正确认。

---

## 0. 一句话结论

前十轮之所以全是"离线轮"，不是环境坏了，而是 MCP 入口被关了（见 §1）。本轮把它打开后，
四件事被实测钉住：**工具面的真实规模是 99 个工具 / 23 个 RPC（不是 106 也不是 126）**；
**`timestamp` 字面量在"文档→导出→运行时"三处一致地被丢弃**；**`helperAixmlInvalid` 定位到了
具体文件，且 `backend:"pylabview"` 是可用绕行路线**；**`describe_class` 的继承报告是正确的，
真正的陷阱在 `ancestors[0]`**。

---

## 1. 环境为什么"离线"了十轮

不是自动禁用、不是信任失效。是 **2026-10-20 16:40:37/38 通过界面手动关闭**的：

```
16:40:23  wb:mcp:describe   "custom-mcp:labview"
16:40:37  wb:mcp:setEnabled "custom-mcp:labview-cli"   ← 关
16:40:38  wb:mcp:setEnabled "custom-mcp:labview"       ← 1 秒后关
mcp.json mtime = 16:40:38.789   ← 与第二条 setEnabled 同秒
```

诱因是 `labview-cli` 指向的脚本已被删除（桌面 `新建文件夹 (3)` 整个目录消失），当天
13:32 / 13:48 / 16:34 三次 stdio 探测都报 `can't open file ... [Errno 2]`。用户点开服务器
详情看了一眼，随后把 cli 和 exe 两个一起关了。**`labview`（exe 版）本身从未探测失败**，
是被连带关掉的。

> 排查方法值得留在流程里：`disabled: true` 只说明"被关了"，不说明为什么。原因藏在
> `daemon.log` 的 `McpAuth` stdio 探测日志里，**而"谁在什么时候关的"藏在 `wb:mcp:setEnabled`
> 两行日志里**，两者与 `mcp.json` 的 mtime 对得上，才构成完整证据链。

---

## 2. 工具面真相：99 个工具，23 个 RPC

两个独立的权威来源，互不矛盾，且都**否掉了 Round9 的那份数**。

### 2.1 stdio 握手报了什么（99 = 94 + 5）

`~/.workbuddy/mcp-tool-list.json` 按服务器配置哈希缓存了 `tools/list` 的结果：

| 类别 | 数量 | 说明 |
|---|---|---|
| `lvai_*` | **94** | 走 NI gRPC 服务的工具 |
| `pylv_apply` / `pylv_extract` / `pylv_rebuild` / `pylv_route` / `pylv_status` | 5 | 纯本地 pylabview 工具 |
| 合计 | **99** | 完整清单见 `artifacts/round11/tool-surface-2.0.1.txt` |

### 2.2 LabVIEW 自己的 gRPC 反射说了什么（23 个 RPC）

`lvai_dump_schema` 拿到的 `lvai.LVAI` 只有 **23 个 rpc**（原文见
`artifacts/round11/schema-2.0.1.txt`）。**这里面没有继承、没有访问范围、没有布局、没有错误列表**：

```
GetDescribeVIPromptInfo  GetDescribeProjectPromptInfo  OpenFile
FindPaletteItem          DropPaletteItem               SearchInfoCache
LookupInfoCacheItems     FilterPaletteSearchCandidates FilterExampleSearchCandidates
ApplyAIXMLToVI           ConvertAIXMLToVI              ConvertVIToAIXML
ValidateAIXML            RunVIAsTopLevel               BuildFromBuildSpecification
GetApplicationConfiguration  LogUsageData  Monitor*
```

这条比工具数更重要：**94 个工具架在 23 个 RPC 上**，所以差距不在"NI 给了多少原语"，而在
"这层封装补了多少"。凡 RPC 里没有的（继承、作用域、布局），只能靠读文件（`describe_class`
的 docstring 就明说 "the file is the only source"）。

### 2.3 修正 Round9 的"106 → 126"

Round9 用 `grep -aoE "lvai_[a-z_0-9]+" LabVIEWMCP.exe` 抓名字，把二进制里的字符串
（别名、旧名、文档片段、其他组件的名字）全算进了工具面。实测：

| Round9 的说法 | 实测（2.0.1 在线工具面） |
|---|---|
| 2.0.1 有 106 个工具 | **99** 个（94 lvai_ + 5 pylv_） |
| `lvai_cleanup_diagram` 在 2.0.1 存在，2.2.0 改名成 `lvai_layout_diagram` | **2.0.1 里根本没有 `lvai_cleanup_diagram`** —— 那个名字是二进制字符串，不是工具 |
| `lvai_run_and_read` 是 2.0.1 的旧名 | **2.0.1 里也没有**；在线名一直是 `lvai_run_vi_and_read_values` |
| `lvai_discuss` / `lvai_wire_dyn_events` 是旧名 | 同上，2.0.1 里都不存在 |

**结论：判工具面只能看 `tools/list`，不能 grep 二进制。** 上一份 `tool-delta.csv` 的
"消失的 12 个"应当整列视为不可靠。

反过来，**"2.2.0 新增"的判定仍然有效**——是"不存在于 2.0.1"这个方向的证据可靠：

| 工具 | 2.0.1 | 说明 |
|---|---|---|
| `lvai_layout_diagram` / `lvai_layout_diagrams` | 无 | 布局引擎，Round1"图面难看"的正解仍在 2.2.0 |
| `lvai_error_list` | 无 | `execState 0` 的原因诊断，仍在 2.2.0 |
| `labview_state` | 无 | — |
| `lvai_run_vi_and_read_values` | **有** | 但本机跑不起来，见 §5 |

---

## 3. 四条新 AIXML 规则（都是真机拒绝出来的）

### R11-1 `<Constant>` 不接受 `description`

```
Error -2628 ... Line 2, Column 164, Message: attribute 'description' is not declared
for element 'Constant'
```

`<Control>` / `<Indicator>` 有 `description`，`<Constant>` 没有。这是**解析期**错误
（attribute 未声明），不是语义错误 —— 说明 AIXML 对每个元素有固定的属性白名单，
写多余属性不会被忽略，而是整篇拒收。

### R11-2 数值端子的 `value` 不能是空串

```
Error 53 ... Unrecognized or unsupported attribute set in Indicator with UID 4206
```

`<Indicator type="double" value=""/>` 被拒。**报错完全没提 `value`**，只说"属性集合无法识别"，
于是最容易的误判是去删 `connection`。实测反证：

| 变体 | `connection` | `value`（double） | 结果 |
|---|---|---|---|
| 原始 | `recommended` | `""` | ❌ UID 4206 |
| A | 无 | `""` | ❌ UID 4206（**去掉 connection 无效**） |
| B | 无 | `0` | ✅ errorCode 0 |
| C | `recommended` | `0` | ✅ errorCode 0 |

**规则：string / timestamp 允许 `value=""`；数值类型必须给可解析的字面量。**
诊断时先看 `value`，不要先怀疑 `connection`。

### R11-3 `connection="recommended"` 在 Indicator 上合法（保留 LV009 边界）

变体 C 通过，说明 Round9/10 定的"新生成一律 `recommended`"没错，**LV009 的判定范围不用改**：
只有 error 端子上的 `required` 是陷阱，其余端子的 `required` 是正当表达。

### R11-4 导出会把 `,` `:` `+` 转义成 `\2C` `\3A` `\2B`，而且往返幂等

一次 `ConvertVIToAIXML` 的输出：

```
description="... three indicators\2C so one convert\2Bexport answers two questions\3A (a) ..."
```

把这份导出**再喂回 `ConvertAIXMLToVI`**（改名后），第二次导出的转义**完全一致**，
没有变成 `\5C2C`，`description` 内容不变。所以：

- 读侧拿到的 AIXML 是"可再写回"的合法输入（这对"读→改→写"的编辑链是好消息）；
- 但**按字符做 diff 会误报**：同一段描述，作者写 `,`，导出是 `\2C`。做文本级比对前必须先归一。

### 3.5 闸门立刻还债：LV010 抓到一份"从未跑过"的探针

R11-1 / R11-2 当场写进了 `tools/lvrule_check.py`（LV010 / LV011），跑全库时 LV010 命中一处
**历史真缺陷**：`research/artifacts/round7/next-probes/p5-valuechange-timeout-frames.aixml.xml`
的 `Constant 'Timeout ms'` 带着 `description`。这份探针是 Round7 为"事件结构 + 超时"准备的，
因为当时 LabVIEW 离线，**从来没被执行过**——所以错误一直潜伏着。

真机复核，判定完全对齐：

```
lvai_validate_aixml(p5-valuechange-timeout-frames.aixml.xml)
→ Error -2628
   Line 7, Column 189, Message: attribute 'description' is not declared for element 'Constant'
```

这就是 G0 的价值形态：**离线闸门在 2.5 秒内指出"这份文档根本进不了 LabVIEW"，而且指到了行**，
省掉的不是一次往返，是一次"跑错了方向"的调试（探针要测的是超时，失败原因却是属性拼写）。
该探针已修好，可以进下轮 P5。

---

## 4. P10：`timestamp` 字面量被丢弃 —— 三处一致

探针 `artifacts/round11/p10-final.aixml.xml`：三个常量（timestamp / string / double）各接一个
同类型指示器，字面量互不相同，防止读到旧文件假装通过。

| 阶段 | timestamp | string | double |
|---|---|---|---|
| 写入（AIXML） | `3800000000` | `marker-r11` | `3.25` |
| 导出（`p10-exported.aixml.xml`） | **`""`** | `marker-r11` | `3.25` |
| 运行时（pylabview 后端读值） | **`01/01/1904 08:00:00`**（LabVIEW 纪元零点） | `marker-r11` | `3.25000000000000` |

运行时那一列是关键：它证明丢弃不是"导出显示问题"，而是**常量真的变成了 0**。
`errorCode` 全程 0，`preCheck` 只给一条 warning（`timestampValueDiscarded`）。

> **G3.5 从"建议"升级为"强制"**：任何生成的往返测试，只要期望值里有 timestamp，
> 就在**同一份文档里写出两个空值**，断言比较空与空而通过。要么在测试里改用"运行时读值比较"，
> 要么把时间值以字符串（或数值秒）编码进出。

---

## 5. `helperAixmlInvalid` 定位：一个文件，一条绕行

前十轮反复记的"服务器自带助手 AIXML 被本机 LabVIEW 拒"，本轮落到了具体文件：

```
lvai_run_vi_and_read_values → helperAixmlInvalid
helper: C:\Users\heiyashi\labview-mcp\bin\scripts\lvai_run_and_read_typed.xml
验证器拒绝（节选）：
  转换为特定的类: 包含未连线或错误的接线端 / 多态接线端不支持该数据类型
  条件结构: 部分选择器值无对应分支
  属性节点: 无效属性 / 无效级联属性
  索引数组 / 搜索一维数组: 包含未连线或错误的接线端
  已连接两个不同类型的接线端
For循环: N未连接，并且不存在索引输入
```

这是**服务器发布的 helper 源文档**在本机 2026 中文版验证器下不通过 —— 不是我们的文档写错了。

连锁后果（都是实测，不是推断）：

| 调用 | 结果 |
|---|---|
| `lvai_exec_state` | `helperUnavailable`：可执行性**完全无法判定** |
| `lvai_convert_aixml_to_vi` | `execState: null` / `executable: null`（同一个 helper） |
| `lvai_run_vi_and_read_values`（默认 grpc） | `helperAixmlInvalid` |

### 绕行路线（实测通过）

```
lvai_run_vi_and_read_values(viPath=..., backend="pylabview")
→ ok:true, via:"ActiveX", ran:true, finished:true, runMs:2, 三个值全部正确
```

**新铁律**：本机一切"跑一下""能不能执行"的验证，一律显式带 `backend:"pylabview"`；
不带就必然撞 helper。这条把 G5 从"不可做"变成"可做"，代价是换执行通道（ActiveX），
不再是"只能等升级"。

> 注意能力差别：pylabview 路线 `xml` 恒为 null（值以 AIXML 字面量给，cluster/array 写成
> `[a,b,...]`），且 `signalsJson` 被拒 —— 要驱动事件仍需 grpc helper，或等升级。

---

## 6. P11：继承报告是对的，陷阱在 `ancestors[0]`

### 6.1 离线真相：655 个类里 13 个的"父"是接口

新工具 `tools/lvclass_parent_scan.py`（无 LabVIEW、无 MCP）扫 `LabVIEW 2026`：

| 指标 | 值 |
|---|---|
| `.lvclass` 总数 | 655 |
| 声明了父类的 | 468 |
| **父类其实是接口** | **13（2.8%）** |
| URL 解析失败 | 4 |

过程中踩到三个坑，都已写进工具：

1. 接口标记属性叫 **`NI.LVClass.IsInterface`**，不是 `IsInterface`。只读短名时 13 个全漏。
2 相对 URL 会**多退一级**（`Circle Message` 写 `../../Draw Message/...`，实际只需 `../`），
   所以要"直接→上退一级→唯一同名回退"三级解析，并记录 `resolvedBy`。
3. 别名有三类：`<vilib>`、`<resource>`、`<userlib>`。

### 6.2 在线对照：`describe_class` 没有撒谎

| 类 | `inheritsFrom` | `ancestors` | `parentLinks[].kind` |
|---|---|---|---|
| `Box`（父是接口 `Pryable`） | `LabVIEW Object` | `[Pryable.lvclass]` | `interface` |
| `Flathead`（接口 + 真类） | `Rotating Tool.lvclass` | `[Lever, Rotating Tool]` | `interface` / `class` |
| `Executable`（本身是接口） | `LabVIEW Object` | `[HasCommandLine]` | `interface` |

所以 Round10 记的"`inheritsFrom` 把接口报成父类、全站 46/437"**在 v2.0.1 上不成立**。
本轮另外验证 `describe_project`（pylabview）：返回的 classes 只有 `name/path/type`，
**连 `parent` 字段都没有**，也无从"报成父类"。

### 6.3 真正会骗人的是 `ancestors`

`Box` 的 `ancestors[0]` 就是接口 `Pryable`，而它的 `inheritsFrom` 是 `LabVIEW Object`。
`Flathead` 的 `ancestors[0]` 也是接口 `Lever`，真基类是 `Rotating Tool`。

> **铁律**：判"继承自谁"只能读 `inheritsFrom`；说"实现了哪些接口"只能读
> `parentLinks[].kind == "interface"`。**`ancestors` 是全集、顺序不代表优先级，
> 拿 `ancestors[0]` 当基类必错。**

---

## 7. 闸门表更新

| 闸门 | 之前 | 本轮之后 |
|---|---|---|
| **G0 离线预检** | `audit_aixml.py`（37+8 条） | 不变；但**要多抓两条**：`Constant` 上的 `description`、数值端子空 `value` |
| G1–G3 | 需求 / 分层 / 结构 | 不变 |
| **G3.5 字面量存活** | 建议 | **强制**（§4 三重确认） |
| G4 文件级验证 | 导出比对 | 比对前必须**归一转义**（`\2C` 等，§3 R11-4） |
| **G5 运行/可执行** | `lvai_exec_state` | 本机改为 **`backend:"pylabview"` 跑**；`exec_state` 在 helper 修好前不可用 |

---

## 8. 下轮优先级

1. **升级 2.2.0**，然后 `lvai_dump_schema` 与 `tool-surface-2.0.1.txt` 逐条 diff —— 这次有基线了。
2. `lvai_layout_diagram` 首测：拿 `round3/saturating-accumulator-v2` 作输入，量图面尺寸前后。
3. **P1–P5 事件结构**：帮助文档给的是 grpc 路线，但本机 helper 坏；先试 pylabview 能否驱动事件，
   不能就等升级。
4. **P6/P7 类与接口**：`describe_class` 既然可信，`create_class` + `add_class_method` + 接口 override
   的保存顺序 A/B 可以开始做（真实类，不是探针）。
5. 把 §3 的四条写进 `tools/lvrule_check.py`（R11-1/R11-2 可离线判定）。

---

## 附：本轮产物

| 文件 | 内容 |
|---|---|
| `artifacts/round11/tool-surface-2.0.1.txt` | 在线工具面 99 条（94 lvai_ + 5 pylv_） |
| `artifacts/round11/schema-2.0.1.txt` | gRPC 反射原文：23 个 rpc + 全部 message |
| `artifacts/round11/p10-final.aixml.xml` | P10 探针（含一个"故意会被丢弃"的 timestamp 字面量） |
| `artifacts/round11/p10-variant-{a,b,c}*.xml` | §3 R11-2/R11-3 的四变体对照 |
| `artifacts/round11/out/p10-exported.aixml.xml` | 导出：timestamp 变空、转义可见 |
| `artifacts/round11/lvclass-parents.json` | 468 个类的父类解析表（含 `resolvedBy`） |
| `tools/lvclass_parent_scan.py` | 离线父类/接口扫描器 |
