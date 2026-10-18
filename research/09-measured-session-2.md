# 实测记录：第三轮 MCP 会话全记录（research 09）

> 本文是 [`08-complex-programs.md`](08-complex-programs.md) 的证据底稿：每一次
> validate / generate / run 调用的真实返回（节选关键字段）。环境同第二轮
> （[`07-measured-session.md`](07-measured-session.md)）：LabVIEW 2026 26.3.1f1 中文版
> 运行中，LabVIEWMCP 2.0.1，WorkBuddy 双 MCP 服务器在会话中。

## 1. 会话目标

把第二轮"单 VI 生成"推进到"复杂程序"：循环 + 移位寄存器 + Case 的子包含算 VI、
调用子 VI 的多 VI 程序、`.lvproj` 容器。

## 2. 饱和累加器：五个变体的对分实验

设计：While 循环，3 个 ShiftReg（acc / iter / sat 标志），Case 双帧饱和逻辑，
索引输出隧道收集 History，循环内自算停止条件（`iter_next >= MaxIter → stop`）。

### 2.1 基线（失败）—— `saturating-accumulator.aixml.xml`

```
lvai_validate_aixml → errorCode 1
  While循环: 属于循环成员
  连线: 属于循环成员 ×3
  详情: 由于连线形成一个循环……两部分均无法执行
```

三个 SR 种子全部取自循环内：SR230 ← 隧道输出网 `210.start`；SR233 ← 循环内常量
`220.zero`；SR236 ← 循环内常量 `221.false`。

### 2.2 对分变体（全部失败，同一报错）

| 变体 | 文件 | 改动 | 结果 |
|---|---|---|---|
| A | `variant-a-nocase.aixml.xml` | 去掉 Case，SR 直连 | errorCode 1（同报错） |
| B | `variant-b-noindex.aixml.xml` | 去掉 `mode="index"` 输出隧道 | errorCode 1 |
| C | `variant-c-panelstop.aixml.xml` | Condition 改读面板 Stop（经隧道） | errorCode 1 |
| E | `variant-e-mixedseeds.aixml.xml` | 仅 SR230 种子移根级，另两个仍循环内 | errorCode 1（2 连线成环） |

### 2.3 正例（通过）—— `variant-d-rootseds.aixml.xml` → `saturating-accumulator-v2.aixml.xml`

唯一改动：三个种子全部移到根级（常量 `220.zero`/`221.false` 改 `uid_parent="root"`；
SR230 直读根控件 `value:100.value` 无隧道）。

```
lvai_validate_aixml → errorCode 0
```

v2 完整恢复 Case + 索引隧道 + 内部停止条件后仍 errorCode 0，随后：

```
generate_vi → Saturating Accumulator.vi（8354 字节，图 675×386，链路 4 级）
  （辅助步骤 cleanUpPanel/cleanUpDiagram/connectorPane 仍 helperAixmlInvalid，
    已知环境问题，见 08 §7.2，不影响本体）
```

关键源码（v2）：

```xml
<Constant _name="Zero" outputs="value:220.zero" type="int32" uid="220" uid_parent="root" value="0"/>
<Constant _name="False" outputs="value:221.false" type="bool" uid="221" uid_parent="root" value="false"/>
<Structure _name="While Loop" count="" uid="200" uid_parent="root">
  <ShiftReg uid="230" uid_parent="200">
    <Left inputs="value:100.value" outputs="value:240.acc" uid="231" uid_parent="230"/>
    <Right inputs="value:280.new_acc" outputs="value:290.final_acc" uid="232" uid_parent="230"/>
  </ShiftReg>
  ...
  <Tunnel _id="Out3" inputs="value:280.new_acc" mode="index" outputs="value:270.history" uid="270" uid_parent="200"/>
</Structure>
```

### 2.4 运行测试（4/4 通过）

| # | 输入 | 预期 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | Start=0, Inc=1.5, Limit=10, MaxIter=8 | Final=10, Iter=8, Sat=true, History=[1.5,3,4.5,6,7.5,9,10,10] | 完全一致 | ✓ |
| 2 | Start=0, Inc=1, Limit=100, MaxIter=3 | Final=3, Iter=3, Sat=false, History=[1,2,3] | 完全一致 | ✓ |
| 3 | Start=5, Inc=2.5, Limit=10, MaxIter=8 | Final=10, Iter=8, Sat=true, History=[7.5,10,10,10,10,10,10,10] | 完全一致 | ✓ |
| 4 | MaxIter=0 | （预期 0 次迭代） | Final=1.5, Iter=1, History=[1.5] | VI 正确（While 后置条件至少跑 1 次），作者预期错 |

Test 3 细节：候选值**等于** Limit 时 `Greater?` 为 False 不饱和，验证了谓词严格性。

## 3. 多 VI 程序：Clamp Value + Clamp Demo

### 3.1 子 VI 生成

`clamp-value.aixml.xml` → `Clamp Value.vi`（5623 字节，两个嵌套 Case）：

- validate errorCode 0；
- uid 10–35 被自动修复到 4200+（`uidInReservedRange`）——低 uid 教训入库（08 §6）；
- `openVI:true` 保持在编，供主 VI 的 Call 解析。

### 3.2 主 VI 生成（Call 路线）

`clamp-demo.aixml.xml`（While + 3 SR + 双 Or + 循环内 Call）：

```xml
<Call inputs="x:250.candidate,lo:212.lo,hi:213.hi" outputs="clamped:280.new_acc" target="Clamp Value.vi" uid="260" uid_parent="200"/>
```

```
lvai_validate_aixml → 拒绝: Unsupported SubVI: Clamp Value.vi   （预期行为）
loadedSubVIs 路线 convert/generate → Clamp Demo.vi（8462 字节，链路 5 级）✓
```

### 3.3 运行测试（2/2 通过）

| # | 输入 | 预期 | 实测 | 判定 |
|---|---|---|---|---|
| A | Start=0, Inc=1.5, lo=0, hi=10, MaxIter=8 | Final=10, Iter=8, Sat=true, History=[1.5,3,4.5,6,7.5,9,10,10] | 完全一致 | ✓ |
| B | Start=0, Inc=1.5, lo=2, hi=10, MaxIter=8 | Final=10, Iter=8, Sat=true, History=[2,3.5,5,6.5,8,9.5,10,10] | 完全一致 | ✓ |

Test B 命中下界钳位路径：第一个候选 1.5 < lo=2，被子 VI 向上钳到 2。

## 4. 项目容器：手写 Clamp Demo.lvproj

三次失败后成功：

| 尝试 | 缺失 | describe_project / open_file 结果 |
|---|---|---|
| 1 | 无 `NI.LV.All.SaveVersion` | errorCode 5000 "Error loading project" |
| 2 | Dependencies/Build 排在 VI 前、无 BOM | 同上 |
| 3 | SaveVersion + 条目顺序 + UTF-8 BOM 全补 | **errorCode 0 / errorCode 0** ✓ |

`open_file` 在 lvproj 损坏时还触发了一次 GBK 崩溃（见 §5）。

## 5. 新故障模式：GBK 错误消息崩溃 .NET 客户端

```
lvai_open_file（指向损坏的 .lvproj）
→ InvalidProtocolBufferException: String is invalid UTF-8 ... bytes [D6] at index 393
```

`D6D0` = "中"的 GBK 编码。LabVIEW 中文版把中文错误消息以 GBK 上线，.NET 客户端 UTF-8
解析即崩。修复 lvproj 后返回 ASCII "No Error" 正常。判据：`bytes [D6]` ≈ 中文版
LabVIEW 在通过 gRPC 报中文错。

## 6. 辅助步骤失败（已知环境问题）

`generate_vi` 内部三个辅助步骤（cleanUpPanel / cleanUpDiagram / connectorPane）
均报 `helperAixmlInvalid`——服务器自带助手 AIXML 不被本机 LabVIEW 2026 26.3.1f1（中文）
接受。VI 本体（validate/convert）不受影响；代价是生成物无面板整理与连接器面板。

## 7. 调用耗时样本（validate）

本轮 validate elapsedMs 观测值：541 / 904 / 802 / 125 / 112 / 109 / 104 / 90 / 89 /
83 / 79 / 23.3（ms）。含 Call 的校验在拒绝前也要解析全部结构，耗时偏上限；
单 VI 纯语法校验在百毫秒内。生成（convert）整体在秒级。

## 8. 本轮结论索引

- ShiftReg 种子必须根级（对分表见 08 §2.2）→ 写入 08 §2.3 规则；
- While 后置条件至少执行一次 → 08 §3.1；
- 多 VI：validate 拒 SubVI 属预期，convert 走 loadedSubVIs → 08 §4.2；
- .lvproj 五要点 → 08 §5.2；
- uid 保留区 10–35 → 08 §6；
- GBK 崩溃判据 → 08 §7.1；
- 助手 AIXML 不兼容 → 08 §7.2。
