# AI 借助 MCP 开发 LabVIEW 程序：可复用实践经验与最佳实践

> 第二轮研究（代码生成方向）。第一轮（`references/01-04`）解决"AI 美化 LabVIEW 前面板"，
> 本文解决"AI 从零写出可运行的 LabVIEW 程序代码"。两者共享同一套 MCP 服务器，能力互补。
>
> 结论标注惯例：**【实测】** = 本次在真实环境调用 MCP 工具取得的一手数据；
> **【源码】** = 来自 Zuehlke/labview-mcp 参考代码库及其文档的结论；
> **【经验】** = 来自 MCP 协议规范与社区生态的通用结论。

## 目录

1. [总体认知：AI 写 LabVIEW 为什么难，MCP 怎么解决](#1-总体认知)
2. [MCP 服务器选型与配置](#2-mcp-服务器选型与配置)
3. [典型工作流：需求 → VI 生成 → 静态检查 → 部署验证](#3-典型工作流)
4. [AIXML / VI 生成实战要点](#4-aixml--vi-生成实战要点)
5. [提示词工程：怎样写需求才能得到可用的 VI](#5-提示词工程)
6. [人机协作与代码审查清单](#6-人机协作与代码审查清单)
7. [常见失败模式与规避方法](#7-常见失败模式与规避方法)
8. [性能注意点](#8-性能注意点)
9. [安全注意点](#9-安全注意点)
10. [Round8 增补：五道闸门与六条新铁律](#10-round8-增补五道闸门与六条新铁律)
11. [Round9 增补：离线审计闸门、工具面变更与三处修订](#11-round9-增补离线审计闸门工具面变更与三处修订)
12. [Round10 增补：25 次冷构建语料，与第六道闸门](#12-round10-增补25-次冷构建语料与第六道闸门)
13. [Round11 增补：首次在线实测与四条硬规则](#13-round11-增补首次在线实测与四条硬规则)
14. [快速参考：一页纸](#14-快速参考一页纸)

---

## 1. 总体认知

### 1.1 问题的本质

`.vi` 是二进制文件：不能 grep，diff 两个版本只能看出"不一样"，任何语言模型都无法直接吐出
一个 `.vi`。所以过去的代码助手基本绕开 LabVIEW。【源码】

MCP 的解法是**借 IDE 的手**：让一个本地服务器驱动正在运行的 LabVIEW，把 VI 的方块图
转换成文本（AIXML）供模型阅读，再把模型写出的文本转换回 `.vi`。一旦"文本形态的东西"
可以发起请求，AI 开发 LabVIEW 就从不可能变为可行。【源码】

### 1.2 两种架构家族（选型前必须知道）

社区目前有两条技术路线，能力与适用场景截然不同：

| 家族 | 代表项目 | 原理 | 强项 | 短板 |
|---|---|---|---|---|
| **VI Scripting 系** | JanGoebel/G-AI、CalmyJane/wyxfhb labview_assistant、MeKo-Christian/labview_mcp | LabVIEW 内嵌 DQMH 模块 + VI Scripting，经 COM/HTTP 桥接给 MCP | 能操作**已打开的真实 VI**，改动现有代码 | 依赖 VI Scripting 许可；工具面小；多会话状态复杂 |
| **AIXML 系** | Zuehlke/labview-mcp（本仓库重点） | 方块图的文本化（AIXML）+ LabVIEW 内 NI 私有 gRPC 服务（`lvai.LVAI`）校验/转换 | 从零**生成** VI；99 个工具；读、写、跑、建类、建 DQMH、单测全覆盖 | 驱动的是 NI 未公开接口，版本升级有风险；生成物必须自包含 |

【经验】+【源码】。第一轮研究（`references/01`）已覆盖 VI Scripting 系（23+98 工具的环境
实录）；本文聚焦 AIXML 系的**代码生成**能力，因为这是"AI 写 LabVIEW 程序"的核心。

### 1.3 双引擎：为什么需要两个

AIXML 系服务器内部有两条引擎，理解它的分工是避免误用的关键：【源码】

| 引擎 | 依靠 | 职责 |
|---|---|---|
| `lvai.LVAI`（gRPC，跑在 LabVIEW 进程内，NI 开源 grpc-labview） | LabVIEW 2026 运行中 + AI 功能（Nigel）已启动 | **创建与命名**：唯一能从零生成 VI 的路线 |
| `pylabview`（内置 Python 包，拆/装 `.vi` 容器） | 无需 NI 服务、无需 LabVIEW 许可；仅在需要"可执行吗/算什么/图多大"时经 ActiveX 问运行中的 LabVIEW | **编辑与读取**：字节级改已有 VI；够不到 AIXML 表达不了的图标、布局、装饰、`.ctl`、连接器面板 |

依赖是单向的：pylabview 不能凭空发明节点和连线；`lvai` 不能改图布局。**改已有代码，
pylv 是常态、AIXML 是例外**——实测 900 个生产 VI 中仅 15% 能经 AIXML 重新生成，70% 调用
项目自己的 subVI，而生成器一律拒绝。【源码】

### 1.4 本次研究的关键突破（先说结论）

**【实测】2026-10-18，端到端生成并运行成功**：从一段自然语言需求出发，AI 撰写 AIXML →
离线检查（0.4 ms）→ LabVIEW 校验（118 ms）→ 转换为真实 `.vi`（381 ms，5487 字节）→
经 ActiveX 实际运行，两个测试用例输出全部正确：

| 输入 | Status 输出 | Alarm 输出 |
|---|---|---|
| Temperature=95, Threshold=80 | `ALARM: Over Temperature!` | `true` |
| Temperature=25, Threshold=80 | `Normal` | `false` |

完整实录见 [`07-measured-session.md`](07-measured-session.md)，材料见
[`examples/01-create-vi/`](examples/01-create-vi/)。**这证明"AI 经由 MCP 写出可正确
运行的 LabVIEW 程序"在当前工具链下已经成立**，剩余问题是可靠性工程而非可行性。

---

## 2. MCP 服务器选型与配置

### 2.1 传输方式：本地 stdio 是默认答案

【经验】MCP 协议（2026-07-28 修订版）是 JSON-RPC 2.0，两种传输：

- **stdio**：客户端把服务器当子进程拉起，走 stdin/stdout，无网络端口。适合需要本地
  文件系统/IDE 访问的场景——LabVIEW MCP 属于此类，**保持 stdio 即可，不要改成远程**。
- **Streamable HTTP**：远程共享场景，需 OAuth/Origin 校验等一套安全措施。社区里
  G-AI 用 `mcp-remote` 把本地的 `http://127.0.0.1:36987/mcp/server` 桥接给只支持
  remote 的客户端，属于兼容 trick，不是推荐架构。【经验】

【实测】本环境的正确配置形态（`.mcp.json`）：

```json
{
  "mcpServers": {
    "labview": {
      "command": "${CLAUDE_PLUGIN_ROOT}/bin/LabVIEWMCP.exe",
      "args": [],
      "env": {}
    }
  }
}
```

### 2.2 LabVIEW 版本匹配：三个必须记住的事实

1. **AI gRPC 服务随 NIGEL 启动，不随 IDE 启动。** 【实测】本次研究第一次
   `lvai_status` 失败：LabVIEW 2018 已在运行（PID 2080），但 49 个候选端口无一服务
   `lvai.LVAI`。错误信息明确写着"a running LabVIEW is not enough — the service starts
   with NIGEL, the AI assistant, not with the IDE"。**LabVIEW 开了二十分钟、30 个监听
   端口全开、服务一个没起**的案例都有实测记录；打开 Nigel 后数秒内服务出现。【源码】
2. **冷启动第一次调用必然超时，第二次才会话。** 【实测】`lvai_ensure_labview`
   第一次调用在 40 s 预算内返回 `state: starting`、`lastError: "The operation was
   canceled."`——这是**调用自身预算耗尽，不是故障**；第二次调用 857 ms 即
   `ready`（端口 27387）。【源码】记录的第二次就绪时间分布：1.2 s / 12.1 s / 27.7 s /
   1.2 s。**不要在第一次 starting 后重启任何东西。**
3. **版本新旧决定引擎选择。** 【实测】`lvai_list_labview_installations` 报告本机
   LabVIEW 2026（64-bit）与 LabVIEW 2018（32-bit，正在运行）；默认挑选规则
   "newest release first, 32-bit preferred within a release, NXG excluded"。
   【源码】后端自动规则：LabVIEW **老于 2026 → pylabview**，否则 grpc。

### 2.3 后端（backend）选择：优先级链

【源码】`lvai_validate_aixml`、`lvai_convert_aixml_to_vi`、`lvai_generate_vi` 等工具的
`backend` 参数按以下优先级决定（最高者胜）：

1. 调用参数 `backend`（`grpc` / `pylabview`）
2. 服务器命令行 `--aixml-backend`
3. 环境变量 `LABVIEWMCP_AIXML_BACKEND`
4. **`%USERPROFILE%\.labviewmcp\settings.json` 的 `"aixmlBackend"` —— 推荐的用户决策位置**
5. 规则：使用中的 LabVIEW 老于 2026 → `pylabview`
6. 默认 `grpc`

【实测】本机 settings.json 存在且为 `"auto"`，服务器默认 `grpc`，
`labviewInUse: 2026`、`partsRelease: 2026`。

**实践建议**：让 `auto` 替你决定；只有在"NI 服务起不来但要继续干活"或"目标机
LabVIEW 老于 2026"时，才显式指定 `pylabview`。【经验】

### 2.4 客户端权限模型：读放开，写确认

【源码】99 个工具中 37 个带 `readOnlyHint`、61 个带 `destructiveHint`。正确做法：

- **读工具（status、reference、index、convert_vi_to_aixml、check_aixml、describe_*、
  list_installations）允许列表放行**，让会话流畅；
- **写/跑工具（convert_aixml_to_vi、run_vi_*、build、close、add_to_library……）
  每次确认**。提示烦人是故意的——它们真的会覆盖文件、执行代码、驱动硬件。

【经验】MCP 规范明确：注解（annotations）只是提示，客户端必须当作不可信输入；
写操作一律按特权操作对待。本地服务器应只绑 127.0.0.1。

---

## 3. 典型工作流：需求 → VI 生成 → 静态检查 → 部署验证

### 3.1 标准八步循环（AIXML 路线）

```
① 需求描述（人 → AI）
② lvai_status                    确认连接（服务在不在，一眼定位冷启动问题）
③ lvai_example_index / palette_index   NI 写过现成的吗？有就改写，别从零发明
④ lvai_aixml_reference            查终端名与布线语法（猜终端名必错）
⑤ lvai_convert_vi_to_aixml        找一个相似的已有 VI，学它的方言
⑥ （AI 撰写/修改 AIXML）
⑦ lvai_check_aixml  →  lvai_validate_aixml   两级静态检查，先离线后在线
⑧ lvai_generate_vi / lvai_convert_aixml_to_vi  落成 .vi
⑨ lvai_run_vi_and_read_values     实际运行，读回输出值
```

【实测】第 ② 步的真实价值：本次第一次 `lvai_status` 就抓住了"LabVIEW 在跑但服务没起"
这个否则会浪费整个下午的问题。第 ③ 步的真实价值：查询 `temperature acquire` 无命中
（所有词必须同时出现），改查 `temperature` 得到 2/494 个示例——**教会 AI 先查再写**。

### 3.2 每一步的判据（什么算"过"）

| 步骤 | 通过判据 | 常见误读 |
|---|---|---|
| `lvai_status` | `ok: true`，服务列表含 `lvai.LVAI` | `ok: false` 时先分清是"IDE 没开"还是"Nigel 没开" |
| `lvai_check_aixml` | `errors: 0`（warnings 也要处理） | 它**不查**终端名/类型/连线——那必须靠 validate |
| `lvai_validate_aixml` | `errorCode: 0` | 失败会"烧掉"VI 名（见 §7.4） |
| `lvai_generate_vi` | `ok: true` 且 `paneViolations` 为 0 | `ok: false` 但文件已写入；面板/图布整理是附加步骤 |
| `lvai_run_vi_and_read_values` | `ran: true` 且**按 VI 自身输出判据**，不是 `errorCode` | 非字符串指示器在旧路线返回 Error 91 但 VI 其实跑完了 |

【实测】本次生成的 VI：validate 118 ms、convert 381 ms、图布 418×214（预算
1920×1080 内）、最长依赖链 2 级（预算 10 级内）——全部有量化判据。

### 3.3 项目级容器：没有 RPC 能创建 `.lvproj`

【源码】23 个 RPC 全部作用于已存在的 VI/项目；`ConvertAIXMLToVI` 只写 `.vi`。
新建项目要**手写最小 `.lvproj` XML** 再用 `lvai_open_file` + `lvai_describe_project`
验证（已实测可加载的骨架在参考库 `docs/guide/aixml-workflow.md`，`LVVersion=26008000`
对应 2026）。**不要手工编辑正在 IDE 里打开的项目**——窗口持有旧副本，保存时会把你的
改动覆盖掉。

---

## 4. AIXML / VI 生成实战要点

### 4.1 心智模型：两套正交的系统

- **层次**（谁套着谁）：`uid` + `uid_parent`（`root` 或另一个 uid）。
- **数据流**（谁流向谁）：`inputs`/`outputs` 里的 `终端:线名` 对。**同名线就是同一根线**；
   fan-out 就是多个输入引用同一线名。`inputs` **不指向**源元素。【实测】【源码】

```
<Control ... outputs="value:100.value" uid="100"/>      线 100.value
<Node    inputs="x:100.value" .../>                      读同一根线
```

### 4.2 终端名是字面量，必须查不能猜

【实测】【源码】`lvai_aixml_reference` 返回的铁律：

| 节点 | 终端名（反引号内为精确字符串） |
|---|---|
| Increment | `x+1` |
| Greater? | ``x > y?``（带空格） |
| Select | ``s? t\3Af``（`\3A` 是 `:` 的转义） |
| Or | ``x .or. y?`` |

猜错的下场：validate 报 `Object terminal not found for input`。**正确做法**：
`lvai_aixml_reference` 用 `node=` 参数**一次传多个逗号分隔的词**
（`node='Select,Index Array,Greater?'`），实测 18 次单查可并为 3 次批查。【源码】

### 4.3 转义与属性规则

【源码】【实测】

- `\3A`=冒号、`\2C`=逗号、`\0A`/`\0D`=换行——因为 `:` 和 `,` 在 terminal list 里是
  分隔符；XML 实体在此之上再加一层。
- **没有坐标属性**：位置/大小/图布整理不可表达。FreeLabel 注释控制在 ~45 字符内
  （【实测】46 字符被检查器判 `commentMayBeClipped`），长解释放进 VI `description`。
- `Control`/`Indicator`/`Constant` **必须有 `value` 属性**——缺了整篇文档
  Error -2628，什么都不写。【实测】本次初稿即被检查器抓到 uid 落入保留区（<42）与
  注释超长两处，修复后 0 错误 0 警告。

### 4.4 自包含约束：生成器能接受什么

【源码】【实测】生成的 VI **必须自包含**：

- ✅ 原语节点、全部结构类型、完整类型系统（`double`/`bool`/`string`/`array{…}`/
  `cluster{…}`/`ref{…}`……）
- ❌ 项目/库本地 subVI 的 `Call` → `Unsupported SubVI`（Express VI 同样拒绝）
- ❌ 因此**整个 DQMH 模块无法从零生成**

特例：【源码】若 validate 只报 `Unsupported SubVI` 且目标 VI **已在 LabVIEW 中加载**，
`lvai_generate_vi` 会照样转换并以"可执行"代替校验把关（`loadedSubVIs` 字段说明）。

### 4.5 结构三件套的正确写法

【源码】AIXML_Full.md 的完整正例（For Loop + Case + Tunnel + ShiftReg）可直接改编：

- 跨结构边界**只能**经 `Tunnel`（`mode` 空=最后值 / `index`=建数组 / `concat`=拼接）；
- 迭代间反馈**只能**经 `ShiftReg`（`Left`=初值/内读，`Right`=内写/终值）；
- Case 的**每个** Output Tunnel 在**每个** frame 都要有值，否则不完整；
- While Loop 的条件端子 `<Condition inputs="…" value="stop"/>`。

### 4.6 双后端的使用分工

| 任务 | 用什么 |
|---|---|
| 从零生成 VI | `grpc`（AIXML 创建是唯一路线） |
| 改已有 VI 的连线/节点 | `pylv_route` 先决策，通常 pylabview |
| 图标/布局/装饰/`.ctl`/连接器面板 | 只能 pylabview |
| 读 VI 学方言 | `lvai_convert_vi_to_aixml`（grpc；安装内 VI 有磁盘缓存，二次读是文件拷贝） |

【源码】pylabview 读回吻合度实测 392/747（连线 93.5%），往返测试 129/130 通过；
它**会按名拒绝**建不了的（`composerRefused`）——这是可以放心放在开关后面的原因。

---

## 5. 提示词工程：怎样写需求才能得到可用的 VI

### 5.1 需求描述模板（给 AI 的提示词应包含）

1. **功能契约**：输入（名字+类型+含义）、输出（名字+类型+含义）、处理逻辑。
2. **自包含声明**：明确"只用原语，不调用项目 subVI"——否则 AI 很可能写出
   `Unsupported SubVI`。【经验】
3. **类型与默认值**：`double`、`bool` 等 AIXML 原语类型；默认值合理。
4. **验收标准**：至少一组"输入→期望输出"，供 `lvai_run_vi_and_read_values` 验证。
5. **落地路径**：`.vi` 写到工作副本，不要覆盖用户代码。

### 5.2 让 AI 先查再写的三段式提示词

【经验】效果最好的提示词不是"给我写个 VI"，而是：

> 1. 先调 `lvai_example_index`（query='…'）和 `lvai_palette_index`，告诉我 NI 有没有
>    现成示例；有就基于它改写，没有再从零设计。
> 2. 对要用的每个节点，用 `lvai_aixml_reference` 的 `node=` 参数**一次批量**查终端名，
>    不要猜。
> 3. 写完 AIXML 后：先 `lvai_check_aixml`（fix 能修的修掉），再 `lvai_generate_vi`，
>    最后 `lvai_run_vi_and_read_values` 用我给的用例验证，把输出值报回来。

### 5.3 会话经济学：省轮次比省毫秒重要

【源码】实测 2641 次工具调用、2549 个模型回合：**模型延迟 : 工具耗时 = 3.6 : 1**，
每回合中位 7.1 s。`lvai_validate_aixml` 只要 0.08 s、`lvai_aixml_reference` 0.01 s。
**结论：优化调用次数，不是单次成本。** 三条可操作推论：

- 批量化：reference 查询逗号分隔一次多词（省 38.9% 字符）；批量转换用
  `lvai_convert_vis_to_aixml`；批量生成用 `lvai_generate_vis`。
- 不要为"吞吐"并发：LabVIEW 串行化 RPC，实测 6 个 generate 并发 559 ms vs 顺序
  543 ms——并发只在不碰 LabVIEW 的纯文件读取上有收益。
- 不要"为求稳"重启 LabVIEW：`lvai_ensure_labview` 中位 30.75 s，某会话调了 48 次
  = 25 分钟，大多在追一个一行代码就能修掉的 refnum 泄漏。

---

## 6. 人机协作与代码审查清单

### 6.1 分工原则

【经验】AI 负责：起草 AIXML、查终端名、跑标准检查、生成、执行用例。
人负责：需求定义与验收标准、**架构决策**（该不该用 subVI/类/DQMH）、安全相关常量
（阈值、硬件量程）、最终签收。**AI 生成的 VI 在合入真实项目前必须过人审**——它是
研究级工具链的产物，不是生产验证过的。

### 6.2 VI 审查清单（生成后逐项过）

- [ ] **结构**：`lvai_convert_vi_to_aixml` 回读，节点/连线与设计一致？
- [ ] **可执行**：`lvai_exec_state` = 1（eIdle）？0=eBad 必须打回；
      -1 = 引用没打开，不是 VI 坏，别误判。【源码】
- [ ] **连接器面板**：`lvai_generate_vi` 的 pane 测量有无违规？required output 是
      最坑的——VI 自身全绿，调用方全报 Error 1003。【源码】
- [ ] **常量与阈值**：报警阈值、量程、延时是不是设计值？AI 会把"合理默认"当事实。
- [ ] **强制转换点（coercion dot）**：占位符路线会留下它，validate/retarget/run 全
      绿也看不见，只有 `lvai_coercion_dots` 能发现。【源码】
- [ ] **图布尺寸**：超 1920×1080 预算要折叠成 subVI；三个连续构建曾交付 3306–4152 px
      宽的主 VI 而其它检查全绿。【源码】
- [ ] **注释**：FreeLabel ≤45 字符；长解释在 description。【实测】
- [ ] **运行验证**：至少一组正常 + 一组边界用例，输出值正确。【实测】

---

## 7. 常见失败模式与规避方法

> 详细排查路径（含诊断用提示词）见 [`examples/03-debug-playbook/`](examples/03-debug-playbook/)。
> 下表是速查。

| # | 症状 | 根因 | 规避 |
|---|---|---|---|
| 1 | `ok:false`，"Could not find a port serving lvai.LVAI" | LabVIEW 没开，**或开了但 Nigel 没开**（服务随 Nigel 启动） | 打开 Nigel 再调一次 `lvai_status`；LabVIEW  visibly running 且端口全 `Unavailable` 就是这个病 |
| 2 | `ensure_labview` 永远 `starting` | 冷启动预算 45 s 硬上限；第二次调用才是重试 | **再调一次**，别重启别杀人；`lastError: canceled` 是预算到期不是失败 |
| 3 | 启动的 LabVIEW 几秒后消失 | MCP 宿主 job object 杀掉子进程 | 服务器已改用 breakaway→explorer 交接→shell 启动，并按"2 秒后仍存活"判定；看到 `launch-did-not-survive` 才是真失败 |
| 4 | validate 报 `Unsupported SubVI: X` | 项目本地 subVI / Express VI，生成器不认 | 改成自包含；或把目标在 LabVIEW 里打开后重试 `generate_vi` |
| 5 | validate 报 `Object terminal not found` | 终端名拼错（猜的） | `lvai_aixml_reference node=` 批量查；照抄一个已导出 VI 的字符串 |
| 6 | Error -2628 "parsing the document" | 缺 `value` 属性或缺 `net` 属性（连未接线端子也要空 net） | `lvai_check_aixml` 能在毫秒级离线抓到，**先查后验** |
| 7 | 节点神秘跑到循环外，无任何报错 | `uid_parent` 指向不存在的元素，LabVIEW **静默**重挂到顶层 | `lvai_check_aixml` 专项检查；生成后回读 AIXML 核对层次 |
| 8 | 重复 `uid`，导出与文件对不上 | LabVIEW **静默**重编号 | 同上；uid 从 42 以上分配，避开保留区 |
| 9 | validate 失败后再 convert 同名 VI 报 Error 1051 | 失败的 validate 把名字注册进 LabVIEW 内存，"烧掉"到重启 | 用默认的 scratch 名机制（`validatedAs`）；别手改 `_name` 重试 |
| 10 | `ApplyAIXMLToVI` 无效/静默成功 | NI 该 RPC 从未对第三方客户端工作；2026-09-16 起返回 `errorCode 0` 但不写任何东西 | **改走重新生成**；工具默认拒绝它 |
| 11 | 生成的 `.ctl` 打不开 / `describe_vi` 报 5001 | `.ctl` 与加密码 VI 是硬墙，参数重试都过不去 | 换路线：`lvai_create_typedef` / `lvai_describe_ctl`（pylabview 直读） |
| 12 | 运行报 Error 91 但 VI 明明跑了 | 旧路线把非字符串指示器读成字符串 | 用 `lvai_run_vi_and_read_values`（VI Server 回读）；按 VI 自身输出判成功 |
| 13 | 辅助步骤全失败（面板/图布整理、面板测量、exec_state） | **安装目录里的辅助 VI 的 AIXML 不被本机 LabVIEW 接受**（【实测】本次即此：helperAixmlInvalid，属性节点无效属性+类型不匹配） | 核心链路（check→validate→convert）不受影响；运行验证改用 `backend:"pylabview"` 走 ActiveX；升级服务器版本 |

---

## 8. 性能注意点

1. **延迟主导**：模型回合 ~7.1 s vs 工具中位 ~1–2 s。省一个往返 = 省 7 s。【源码】
2. **批处理优先**：reference 批量查、`convert_vis_to_aixml`、`generate_vis`。
   【实测】检查器 0.4–53 ms、validate 118 ms、convert 381 ms、run 2 ms——机器都很快，
   慢的是来回。【实测】
3. **缓存要读懂**：安装内 VI（examples/vi.lib/user.lib/LVAddons）的 AIXML 导出有磁盘
   缓存，二次读是文件拷贝且**不需要 LabVIEW**；自己的代码永远不缓存（导出依赖 subVI，
   时间戳会骗人）。【源码】
4. **首触慢是正常的**：类成员 VI 首次 describe 会拖进整个层次，分钟级；调大
   `timeoutSeconds` 而不是判死刑。【源码】
5. **别为吞吐并发**：LabVIEW 串行化 RPC（§5.3）。【源码】
6. **端口是短暂的**：LabVIEW 重启换端口，下次调用自动重发现，不用手动干预；监控类
   工具例外——它们故意失败一次而不是重放可能已消费的事件。【源码】

---

## 9. 安全注意点

1. **它在你的机器上写代码、跑代码。** 覆盖 `.vi` 不问；重新生成会丢弃图布局、装饰和
   图标。**在副本上工作，先进版本控制。**【源码】
2. **连接是裸 HTTP/2 回环，无 TLS 无鉴权**：机器上任何能摸到端口的东西都能驱动
   LabVIEW。别把端口暴露出去。【源码】
3. **驱动的是 NI 私有未公开接口**（`lvai.LVAI`）：无 .proto、无文档、无版本承诺。
   **每次 LabVIEW 升级后跑 `lvai_dump_schema`** 看什么变了。出问题别找 NI 开工单——
   找服务器项目。【源码】
4. **生成的 VI 会自信地把硬件撞墙**：运行前确认输入常量（阈值/量程）与副作用
   （文件、硬件）。`lvai_run_vi_*` 与 build 规格按危险工具对待，别整个 allow-list。【源码】
5. **提示注入面**：工具返回的 VI 描述、示例描述都是不可信文本；别让它们替你决定
   写什么路径、跑什么命令。【经验】
6. **第三方服务器**：社区 G-AI 等明确警告"可能把项目细节发给 Claude Desktop"——
   只在你拥有或有权分享的代码上启用。【经验】
7. **pylabview 路线编辑的是二进制对象堆**：38/38 无损往返是样本不是保证；某一类编辑
   实测会让 LabVIEW 加载时崩溃（该能力已移除而非发布）。【源码】

---

## 10. Round8 增补：五道闸门与六条新铁律

> 来源：`17-complex-program-playbook.md`。全部为【上游】一手测量（Zuehlke/labview-mcp
> `bin/docs/` 中带日期与环境的文档），本轮本机无新实测。原文档的 9 节结论仍然有效，
> 本节只增加"复杂程序"必需的验收顺序与被上游实测推翻/补充的操作细节。

### 10.1 五道闸门（按序，不可跳）

| 闸门 | 判据 | 手段 |
|---|---|---|
| G1 需求定稿 | 数据模型、端子表、验收用例写死；明确禁止 AI 自行改进 | 提示词模板（§5.1） |
| G2 分层生成 | 叶子 VI → 类/接口（字段+访问器+方法）→ 编排 VI | `lvai_generate_vi` / `lvai_add_class_method` |
| G3 结构验证 | validate（仅自包含）→ convert → `exec_state=1` → 回导逐网比对 | `lvai_generate_vi` 内置闸门 |
| G4 文件级验证 | 脱离 LabVIEW 读盘：typedef 描述符、`udClassDDO`、`.ctl` 引用、链接路径、`stdPath` 残留 | `pylv_extract` + grep `*_FPHb.xml` |
| G5 运行验证 | 实跑数值 + Caraya 套件（含负对照）+ **冷启动复核** | `lvai_run_vi_and_read_values`、重建后重开 LabVIEW |

**G3 判读**：validate 的拒绝若**只有** `Unsupported SubVI:` 行，是"本地调用未加载"，走 convert；
出现其他行（类型文法拒 `.ctl`、端子名拼错 `Error 1`）才是真失败。
**G4 不可省**：Round7 的 typedef 竞态、上游的"一边链接"都只有读盘能抓。
**G5 不可省**：G4 全绿也不代表能编译（接口方法案例：所有文件自洽，整库仍 `Error 1003`）。

### 10.2 六条新铁律

1. **探针永不用真实文件名。** 一次失败的 convert 会烧掉该 `_name`（之后 `Error 1051`
   内存中已有同名文件），关项目/驱逐 VI 都清不掉，只有重启 LabVIEW。探针用
   `LVMCP Convert <hex>.vi` 一类一次性名。
2. **打开目标的上下文 = 调用方将被生成的上下文。** 项目开着就 `through project` 打开，无项目
   就 loose 打开；开错上下文照样 `Error 53`。**开一个类成员即可让整个类可解析**（类整体加载）。
3. **跨工件链接必须双端保存且顺序正确**：`AddItemFromMemory`（先成为成员）→ `Save.Instrument`
   （VI 落盘时带上 owning-library 记录）→ `{LV.LVClassLibrary} Save`。反序会写出"一边链接"，
   库会**锁死它的全部成员**（`Error 1003`，`{LV.SubVI} Replace` 报 `1154`），而每个文件单看
   都完好——读任一文件都验不出来，只能运行。
4. **测试 = 静态子 VI 调用 + `.xml` 报告 + 负对照 + 重建后跑两次。** 静态调用是默认路线
   （类代码也一样）；`.txt` 报告什么都不写；`7002` 是"套件失败"不是故障；重建后首跑必报
   `Error 1` 且不写报告（Caraya 陈旧 refnum），第二次才可信；故意错一条期望必须 FAIL。
5. **`Call` 的 `inputs` 只能出现连接板（pane）上的端子。** 面板上有但不在 pane 上的对象
   （事件帧里的锁存按钮等）会让生成器报 `Error 1` 且不点名；看 `refusal.notOnPane`。
6. **轮次优先。** 延迟占 3.6～9.7 : 1，每轮中位 7.1 s；省一次往返=7 s，省 1 ms 查找=0。
   批量提交往返；不 fan-out 提吞吐（LabVIEW 串行）；不"保险起见重启"（中位 30.75 s）；
   欠定需求用轮次付费——把数据模型写死比任何工具优化都省。

### 10.3 能力边界速查

可生成：叶子 VI、状态机、类（字段/访问器/方法）、接口与 override、多 VI 调用、用户事件+事件结构、
Caraya 单元测试。
半生成：DQMH 单个 request VI（差两个库限定 SubVI 解析目标）。
只读/不可生成：DQMH 完整模块、`.ctl` 作为 `type=`（任何拼写都被文法拒绝）、
malleable VI 凭空创建、Actor Framework（未测）。

### 10.4 本轮复查的版本事实

本机 v2.0.1 已落后上游 5 个 release，最新 **v2.2.0**（2026-10-21）；v2.1.8 起支持
control references（双后端），v2.2.0 起支持 Network Stream VIs + XControls（**仅 pylabview**）。
**下轮前置动作：升级 ≥ v2.2.0 后 `lvai_dump_schema` 核对 RPC。**

---

## 11. Round9 增补：离线审计闸门、工具面变更与三处修订

> 来源：`18-v220-capability-delta.md`。本轮为**离线轮**（LabVIEW 未运行），但拿到了上游 HEAD
> 源码（`git clone` SSH，commit `2c9f37d`），并把本文前 10 节的规则**写成了可执行检查**。
> 前 10 节结论继续有效，本节只做三件事：报告工具面变更、修订三条被推翻的写法、新增 G0 闸门。

### 11.1 工具面：106 → 126，新增 32、消失 12

**按老名字调用的工具，在 v2.2.0 上不存在了**（对照表：`research/artifacts/round9/tool-delta.csv`）：

| 旧名 | 新名 | 备注 |
|---|---|---|
| `lvai_run_and_read` / `_typed` | `lvai_run_vi_and_read_values` | 运行取值 |
| `lvai_cleanup_diagram` | `lvai_layout_diagram` | 不是改名，是换布局引擎（§11.4） |
| `lvai_wire_dyn_events` | `lvai_wire_dynamic_events` | 事件接线 |
| `lvai_discuss` | `lvai_discuss_file` | 文档生成 |
| `lvai_add_one_to_library` | `lvai_add_to_library` | 库成员 |
| `lvai_unload_vi` / `lvai_class_names` / `lvai_inventory` / `lvai_probe_relative` / `lvai_run_for_ms` / `lvai_cleanup_panel` | 无确认后继 | 升级后 `lvai_dump_schema` 现查 |

值得注意的新增（不止是"多了几个工具"）：

- `lvai_error_list` / `lvai_labview_state` / `lvai_vis_in_memory` —— 诊断（§11.5）
- `lvai_create_override` + `lvai_af_add_hook` / `_remove_hook` / `_read` —— **Actor Framework 覆盖**
  （AIXML 写不了 `Call Parent Class Method`，所以 override 必须由 NI 的 `CLSUIP_CreateOverride`
  产出，hook VI 再用 VI Server 摆上去接线）
- `lvai_create_library` / `lvai_move_to_folder*` / `lvai_member_callers` / `lvai_icon_*`（9 个）/
  `lvai_set_vi_description(s)` —— 交付物工程化
- `lvai_layout_diagram(s)` —— 整图布局

### 11.2 三处修订（推翻本文早先的写法）

1. **uid 不是 ≥100，是 ≥4200。** 面板堆上限随会话增长（132 个 block 观测 42…163，76% 高于 42），
   对照实验：4200–4230 → `dwarnCount` 7→7；10–13 → 7→11（每元素一个事件）。
   被改写的 uid 意味着**读侧坐标与写侧身份对不上**（Round 5 整条链的前提），
   而且只在长会话里复现——**这解释了我们此前没解释过的那类不稳定**。
   规则：手写 uid 从 4200 起；LabVIEW 导出件不动。
2. **裸网属性只写网名。** `count` / `maxin` / `maxout` / `selectin` / `selectout` / `cond`
   是裸网；只有 `inputs`/`outputs` 是 `terminal:net`。写成 `selectin="value:102.value"`
   不报错，但线找不到源头，LabVIEW 会指着**读端**说「Contains unwired or bad terminal」。
3. **`cond="true"` 是字面量。** 停止隧道的 `cond` 可以写字面 true/false（Round 4/6 的状态机
   就是这么写并被 NI 转换器接受、导出、运行的）。离线检查器目前把 `cond` 一律当网，
   会对它误报 `net-unproduced`——已知误报，已在 `tools/audit_aixml.py` 里按名字抑制并单独计数。

### 11.3 G0：生成前的离线审计闸门（新增，在 G1 之前）

Round 8 的 G1–G5 全部要 LabVIEW。本轮补一道**不需要 LabVIEW** 的：

```bash
python tools/audit_aixml.py --summary draft.aixml.xml   # 2.5 s / 50 文件，0 次 RPC
```

三脚本分工（`tools/README.md`）：`aixml_lint.py` 是 vendored 的上游 37 条规则（MIT，**不改**）；
`lvrule_check.py` 是我们自己的 7 条铁律（LV001 注释 / LV003 移位寄存器种子 / LV004 单框 Case /
LV005 While 无停止 / LV006 Call 目标非路径 / LV007 寄存器半对 / LV008 selector 重复）；
`audit_aixml.py` 合并、按文档类型分流、抑制已知误报、出表。

**首轮审的就是我们自己**：50 份 AIXML → 21 error / 92 warning。其中
`saturating-accumulator`（修复前）3 error，它的 `-v2`（修复后）0 error；Round 3 的
A/B/C/E 四个负对照全红、D（根级种子）全绿——**规则把"修好的"和"没修的"精确分开了**。
顺带抓到 Round 7 的 5 个 fixture 写了 `connection="required"`（自己不坏，但每个不接该端子的
调用方都变 `Error 1003`；新生成一律 `recommended`）。

### 11.4 布局：`lvai_layout_diagram` 的规则可以直接当写法用

NI 自己的 Clean Up Diagram 会把设计好的图摊开（DQMH `Main.vi` 1344×805 → **3805×1692**），
因为它只按全局数据流分列、不认识人给的形状。新引擎的规则值得在**写 AIXML 时就遵守**：

- 并行循环（生产者/消费者，彼此无连线）**同列上下叠放**，不要左右摊开；
- 一条直的 error 轨贴底，轨上节点的 error 端口对齐同一水平线；
- 同一节点的多个常量**上下堆叠**（并排会把整列推宽）；链上的常量最多上抬 120 px；
- 隧道/移位寄存器/case selector 与内侧接的那根线齐平；Event Structure 动态事件端子放顶部；
- While Loop 的 stop 与 `i` 必须在 `Frame Size` 写完之后、用 `Position`（不是 `Move`）放到右下/左下；
- 结构尺寸只能靠 `Frame Size` 改（`Bounds` 只读，`Auto Size` 只会变大）。

代价参考：45 个 VI 全量布局 62 s，单个应用 VI 中位 0.39 s。

### 11.5 诊断顺序改了：先读 `errors`，不要猜

`execState 0` 只说明坏，`lvai_error_list` 才给 Error List 那几行 + 解释。三条坑：
**实例不对等于没查**（ActiveX 是 IDE 主实例；`RunVIAsTopLevel` 是 addon 自己的实例，
同一个坏 VI 后者回空列表）；**读内存不读盘**（先 `lvai_open_file`）；**`errors: null` ≠ 无错**
（看 `errorsNotReadBecause`，并行调用下 `Get Errors` 偶发 `1026`）。

---

## 12. Round10 增补：25 次冷构建语料，与第六道闸门

上游把每一次"从零建一个完整应用"记录都入库了：`docs/cold-build-*.md` **25 篇、4409 行**，
覆盖 2026-09-14 → 09-30。逐篇读完能知道一堆坑，**普查之后才知道哪些是系统性的**。
（数据集与复现命令见 `research/19-cold-build-corpus.md` 与 `tools/cold_build_census.py`。）

### 12.1 硬数字

给出明确终态的 11 篇合计 **57 个 `.lvclass`、193 个 VI、112 个测试**；失败共 **3 个，
且 3 个全部是刻意的负对照**；25 篇里 **23 篇**跑了负对照、**14 篇**先进 `aixml_lint`
再进 LabVIEW、**6 篇**全程零重启（最多一篇 19 VI / 16 测试）。

> **这批语料的"绿"是校准过的绿** —— 下面 12.2.1 说明整整一类测试会空转通过，
> 而语料没被骗，靠的正是每次放一个"必须失败"的对照。

### 12.2 三条最该记住的

**12.2.1 常量先验存活，再放进测试。**
`timestamp` 字面量被**静默丢弃**（convert 回 `errorCode 0`，回导是空串），于是往返测试两边
同时变空、比较空与空而**通过**。实测存活表：`string`/`path`/`double`/`int32`/`bool` 保留，
`timestamp` 丢弃。**一个对着被丢弃值的绿测试，比没有测试更坏。**
（`docs/cold-build-alarmgate.md` §3，附两臂负对照）

**12.2.2 类阶段占一半成本，且是唯一真失败的那半。**
一次带时钟的构建：27 步 / 24 次往返 / 30.5 s，**类是 49 %**（typedef 那一半只占 10 % 且一次通过）。
配套两条：重跑 `lvai_add_class_method` 会**毁掉整个类**（`privateDataBytes` +40 字节，
所有访问器 `eBad`，重启不恢复，只能重建；症状是测试报 `Broken` 而非 `Failed`）；
`inheritsFrom` 会把**接口报成父类**（全站 437 个有父链接的类里 **46 个**如此，含 NI 自带范例）。
（`mixedrig`、`thermostat` §4、`valverig` §3）

**12.2.3 状态码两侧都可能撒谎。**
我们 Round7 测到"报成功、文件里 0 个 typedef"；语料反过来测到 **`ok:false` + `1055` +
`nodesSwapped:0`，而 swap 其实已经落地**（同一载荷里 `diagramSubVis` 列的是真目标、`execState 1`）。
判据只能来自载荷里的证据字段，不能来自 `ok`。

### 12.3 第六道闸门 G3.5，与新增规则 LV009

G0–G6 见 `research/19-cold-build-corpus.md` §7。相对 Round9 的两处变化：

- **G3.5 字面量存活**（插在 G3 与 G4 之间）：要进测试的常量先单独 convert→回导确认回来了。
  按**类型**付一次，可长期复用；G4 是按**文件**付的。
- **G5 细分**：套件跑两次（首跑 `Error 1` 是已知）；**`Broken` ≠ `Failed`**（前者意味着断言没跑，
  诊断方向立刻切到类/结构完整性）；**只读 JUnit 报告，永不读 Caraya 的 `error out.source`**
  —— 它会指向一个**通过的**套件。

**`LV009`（本轮写进 `tools/lvrule_check.py`）**：error 端子写 `required` 是 error
（调用方漏接即 `Error 1003`，而本 VI 自己完全正常）；`error out` 写 `optional` 是 warning
（调用点行为相同，但该标志进占位桩的签名，同一 pane 会克隆两份）。
**范围只取上游两条规则看不到的两处**（`error in` 无 `conIdx`、`error out` 的 `optional`）——
上游的 `conn-required-output` 与 `conn-error-in-not-recommended` 已覆盖其余情形，
重复实现是 LV002 退役时记下的那个错。**类端子与必填输入用 `required` 是正确的，不要笼统禁止。**
（另修正 Round9 的表述：那 5 个 fixture 的 `required` 落在 `obj in/out`、`Setpoint` 上，
规则不命中，也不该命中；伤到未接线调用方的是 **error 端子**上的 `required`。）

### 12.4 Round10 铁律速记

```
R10-1 常量先验存活，再进测试；丢弃型字面量不生成测试
R10-2 类建成即记 privateDataBytes 基线；重跑成员后必比对，变了就重建
R10-3 不信任派生摘要字段（inheritsFrom），解析 <Item Type="Parent"> 的 URL + IsInterface
R10-4 error 端子用 recommended；required 只给调用方必填的输入
R10-5 状态码是摘要，证据在载荷（回导 / diagramSubVis / callTargets / execState）
R10-6 样板达"帧×隧道"规模就写生成器（LabVIEW 侧便宜、作者侧贵）
R10-7 多代理：一代理一输出目录；代理只写 Call 然后停；swap 由编排方集中做；改名单靠重启验收
```

---

## 13. Round11 增补：首次在线实测与四条硬规则

前十个轮次全部离线。Round11 第一次在真机（LabVIEW 2026 26.3.1f1 + LabVIEWMCP 2.0.1）上跑通全链，
得到四条会立刻改变写法的规则，外加两处对前轮结论的修正。详细数据见 `research/20-first-online-round.md`。

### 13.1 工具面：99 个工具，架在 23 个 RPC 上

| 来源 | 数 | 用法 |
|---|---|---|
| `tools/list`（stdio 握手） | **94 个 `lvai_*` + 5 个 `pylv_*` = 99** | **判"有没有这个工具"只认它** |
| `lvai_dump_schema` | **23 个 rpc** | 判"NI 到底给了什么原语"只认它 |

**别再用 `grep` exe 里的 `lvai_` 字符串来数工具**：二进制里混着旧名、别名和文档片段。
Round9 那份"106→126、12 个消失"就是那么来的，实测 2.0.1 里 `lvai_cleanup_diagram`、
`lvai_run_and_read`、`lvai_discuss` 从来就不在工具面上。

> 方向仍然可靠的部分：`lvai_layout_diagram`、`lvai_error_list`、`labview_state` 在 2.0.1 里
> **确实不存在**——"不存在"这个方向的证据不受字符串噪声影响。

### 13.2 四条硬规则（都是真机拒绝出来的）

| 规则 | 现象 | 正确做法 |
|---|---|---|
| `<Constant>` 没有 `description` | Error **-2628**，解析期，整篇拒收 | 说明写到 `FreeLabel` 或 VI 的 `description`；`Control`/`Indicator` 才有 |
| 数值端子 `value` 不能是 `""` | Error 53 "Unrecognized or unsupported attribute set in **Indicator** with UID n"——**不说是 value** | string / timestamp 允许空串，数值必须给 `0` 这类可解析字面量 |
| `connection="recommended"` 合法 | 变体 C 通过 errorCode 0 | 新生成一律 recommended；只有 error 端子上的 `required` 是陷阱（LV009） |
| 导出会转义 `,` `:` `+` | 变成 `\2C` `\3A` `\2B`，再喂回不累积 | 文本级 diff 前先归一；导出文档本身是可再写回的合法输入 |

两条可离线判定的已写进闸门：`LV010`（Constant 的 description）、`LV011`（数值空 value）。
它们上线当天就抓到 `round7/next-probes/p5-*.aixml.xml` 的真缺陷——那份探针因为一直离线，
**从未被执行过**，错误潜伏了四轮。

### 13.3 `timestamp` 丢弃：三处一致（G3.5 强制）

| 阶段 | timestamp | string | double |
|---|---|---|---|
| AIXML | `3800000000` | `marker-r11` | `3.25` |
| 导出 | **`""`** | `marker-r11` | `3.25` |
| 运行时 | **`01/01/1904 08:00:00`**（LabVIEW 纪元零点） | `marker-r11` | `3.25000000000000` |

运行时的读数才是关键：**常量真的变成 0 了**，不是显示问题。所以带 timestamp 期望值的
往返测试必然"空对空通过"。

### 13.4 本机 `helperAixmlInvalid`：一个文件，一条绕行

坏的是服务器自带的 `bin/scripts/lvai_run_and_read_typed.xml`，本机验证器拒收它。连锁后果：
`lvai_exec_state` 报 `helperUnavailable`，`convert` 的 `executable` 恒为 `null`，
`lvai_run_vi_and_read_values` 默认路线直接失败。

**绕行（实测通过）**：

```
lvai_run_vi_and_read_values(viPath=..., backend="pylabview")
→ ok:true  via:"ActiveX"  ran:true  finished:true
```

代价：`xml` 恒 null（值以 AIXML 字面量给）、`signalsJson` 被拒（驱动事件仍需 grpc）。
**本机一切"跑一下"的验证，显式带 `backend:"pylabview"`**，G5 从"不可做"变成"可做"。

### 13.5 继承：读 `inheritsFrom`，永远别读 `ancestors[0]`

`describe_class` 的报告是**对的**（Round10 的"接口被报成父类 46/437"在 2.0.1 上不成立）：

| 类 | `inheritsFrom` | `ancestors` | `parentLinks[].kind` |
|---|---|---|---|
| `Box`（父是接口 `Pryable`） | `LabVIEW Object` | `[Pryable]` | `interface` |
| `Flathead`（接口 + 真类） | `Rotating Tool.lvclass` | `[Lever, Rotating Tool]` | `interface` / `class` |

**`ancestors` 是全集、顺序不代表优先级**——`Box` 和 `Flathead` 的 `ancestors[0]` 都是接口。
判基类只读 `inheritsFrom`；说接口只读 `parentLinks[].kind == "interface"`。
离线真相可用 `tools/lvclass_parent_scan.py`（本机 655 类 / 468 有父 / **13 个父是接口**）。

---

## 14. Round12 增补：边界、事件超时、面板保留移植

这一节的三条都只在真机上才能看见，离线阅档看不出任何一条。

### 14.1 一根线不能隐式穿过结构边界（LV012）

```text
根级 Constant ────┐            ← 线直接从根级进到循环/帧里
   While Loop     │
     Event Struct │
       CaseFrame ◄┘             composer: net '4203.ms' crosses a diagram boundary without a tunnel
```

规则：**外层结构要有"外半截"隧道，每个帧要有"内半截"，两半按 `_id` 对齐、各自单向**
（外半截 `inputs`、内半截 `outputs`）。帧不用这个值也必须写 `outputs="value:"`——空网，但半截要在。
常量被帧消费，就把常量搬进帧（本轮 `One`/`False` 各复制一份，uid 必须不同）。

- 例外：**ShiftReg 的 `<Left>` / `<Right>` 不算跨边界**，左端种子本来就必须来自循环外（LV003 的另一面）。
- 检查器 `tools/lvrule_check.py` LV012 的容器判定**不能照抄 `uid_parent`**：Tunnel 的两个半截分属两个容器。

### 14.2 两个 composer 的边界语义相反——选后端前先知道这件事

同一份 `round4/batch-averager.aixml.xml`：

| composer | 结果 | 隧道数 |
|---|---|---|
| grpc（NI `ConvertAIXMLToVI`） | `errorCode 0`，13,800 字节 VI | 源 43 → **成品 154**（缺的全补上） |
| pylabview（本项目） | `composerRefused`，一次点一根网 | 43（一个不补） |

所以"历史产物能跑"不代表"它对 pylabview 成立"。全库 64 份：grpc 口径 26E/269W，pylabview 口径 **187E/108W**。
闸门按目标后端切口径：

```bash
python tools/audit_aixml.py --summary <file>                          # 目标 grpc：LV012 只是 warning
LVRULE_BACKEND=pylabview python tools/audit_aixml.py --summary <file> # 目标 pylabview：LV012 是 error
```

好处是**离线一次列全**，而 composer 每次只报一根（P5 花了 2 个往返）。

### 14.3 事件结构：帧活着，超时端子死了（LV013）

pylabview composer 写的 Event Structure，回导 BDHb 里 `EventNodeEvents elements="3"`，
两个静态 Value Change 各自绑对了控件 ddoUID（`4201` / `4202`），` Timeout ` 帧也在。
**但 `eventTimeOut` 端子（dco 20069）没有被任何 signal 引用**——AIXML 里没有这个端子的写法，
写 `<Tunnel _id="In1" inputs="value:500">` 得到的是**普通隧道**。

后果是静默的：`runForMs=2200`、超时 500 ms → `Timeouts = 0`，零报错，程序就停在那里。
→ LV013 直接报 error；出路只有 IDE 手接，或换 `Wait (ms)` / `Wait on Notification` 配轮询。

### 14.4 面板保留移植 `lvai_graft_diagram`：本机只能 pylabview

```text
grpc      → helperAixmlInvalid（helper 文档在本机过不了 ValidateAIXML）
pylabview → ok:true  execState:1  controlsGrafted:7  newControls:["Scale"]
            leftoverDuplicates:[]  wiringMatchesScaffold:true  nodeCountsMatch:true
```

再跑一遍验收（`Initial State=Init, Items=[2,4,6], Scale=1`）：`Sum=12 / Items Processed=3 /
Average=4 / Final State=Stop`，日志 `Init; Load; Accumulate; … ; Stop`。

两条前置条件：面板 VI 图上**不能有节点**（`panelDiagramNotEmpty`，报的是元素个数）；
`replaceDiagram=true` 这条路走 helper，本机不可用。真·空面板要自己造（端子声明 + 零节点即可）。

### 14.5 本机上限清单（累计四条，都是 helper 类）

`bin/scripts` 下 78 个 helper XML，本轮又点名三个失效文档：

| helper | 挂掉谁 |
|---|---|
| `lvai_run_and_read_typed.xml`（R11） | `run_vi_and_read_values`（grpc） |
| `lvai_run_for_ms.xml` | `runForMs` / **`signalsJson`**（唯一能给运行中的 VI 打信号的路径） |
| `lvpane_probe.xml` | `connector_pane`（grpc） |
| graft 核心 helper | `graft_diagram`（grpc，含 `replaceDiagram`） |

共同写法特征：`For循环`（N 未接）、`属性节点`（"无效属性"）、`调用节点`（"无效方法"）。
**pylabview 路线现场合成自己的 helper，所以同一能力往往只剩这条路。**

### 14.6 测试层仍卡在连接器窗格

```
Scale Double.vi（2 double 入 / 1 出）→ lvai_vi_terminals: 0 input / 0 output on the connector pane
lvai_generate_test → failedAtStep: placeholder, noTerminals
```

与 Round 7/10 同源（LV2026 FPHb 的 `cons` 数组为空，NI 自带范例同样）。
是"VI 真没窗格"还是"读侧看不见"，**尚未分开**；唯一分法是在 IDE 里打开看一眼。
在分开之前，Caraya 那条链（`generate_test` → `run_caraya_tests` → JUnit）没有起点。

> **Round 13 已结案：写侧真没设窗格，因为 AIXML 里从没写过 `conIdx`。见 §15。
> 读侧不瞎——两个后端读数逐字相同。**

---

## 15. Round13 增补：连接器窗格 —— 缺的那一格

### 15.1 `connection` 管"必需与否"，`conIdx` 才管"在不在位上"

```xml
<!-- 只是"若在窗格上则推荐" —— 它一个字都没说"在位" -->
<Control _name="x" connection="recommended" type="double" uid="4200" .../>

<!-- 这一句才把它放上窗格，0 是槽位号 -->
<Control _name="x" connection="recommended" conIdx="0" type="double" uid="4200" .../>
```

composer 侧三行代码就是全部答案（`aixml2vi.py`）：

```python
con = el.get("conIdx")
conn.text = con if con is not None else "-1"      # 没有 → conNum=-1 → 不在窗格上
if con is not None:                               # 有 → 写 cons + pane_terms
    self.pane_terms.append((int(con), tree, is_ind, el.get("connection") or "required"))
```

同时骨架的面板根带着 `objFlags 0x10000`，其注释原话是 **"NO TERMINAL ON THE PANE"**，
且 `every AIXML-generated VI without a pane carries it`。所以"没窗格"是一个显式状态，不是漏了默认值。

### 15.2 四分支实验：conIdx 是槽位，不是顺序号

同一份 `y = x * factor`，只改 conIdx。四份都 `errorCode 0 / execState 1`：

| 变体 | 写法 | 字节 | 窗格 |
|---|---|---|---|
| A | 都不写 | 4 407 | **0 in / 0 out**，三个全 off |
| B | 0 / 1 / 2（文档序） | 4 447 | 2 in / 1 out，槽 0/1/2 |
| C | 打乱：y=0, x=1, factor=2 | 4 443 | **槽位按 conIdx**（y 在 0） |
| D | 只有 x 写 0 | 4 423 | **1 in / 0 out**，部分上窗格合法 |

- `conIdx` 决定槽位 → 可以按惯例排布（输出在上、`error out` 贴底），不必按"先控件后指示器"。
- 部分上窗格是合法的（D 能跑），所以 LV014 对"部分缺"只报 warning。
- B 组在 grpc 与 pylabview 下读数逐字相同 → **怀疑读侧之前，先用另一个后端问一遍**。

### 15.3 端到端：窗格不是给读侧看的

`Conpane Caller.vi`：常量 3 和 5 + 一个 Call 到 B + Result。
`composerReport` 里出现 `Call 'Conpane Probe B.vi' <- <TypeDesc ...> (pane 4833, 16 slots)`，
运行 `Result = 15.00000000000000`。窗格是**可链接的真窗格**。

### 15.4 无窗格 Call 的失败形态：静默，且结果看起来是对的

`Conpane Caller A.vi`（Call 无窗格的 A，`inputs="" outputs=""`）：
`execState 1`、可运行、**零报错**，输出 `Marker Out = 99` —— 这个 99 来自调用方自己的常量，
被调的 A 一个字节都没参与。

> **"图上有 Call、跑完无错误、值也读出来了"三件事同时成立，仍可能这个 Call 什么也没做。**
> 唯一可靠的判据是：让输出依赖它的输入。

### 15.5 `generate_test` 三连，与 Caraya 缺件

| # | 条件 | 结果 |
|---|---|---|
| 1 | Round 12，subject 无窗格 | `noTerminals`，连 placeholder stub 都生成不出 |
| 2 | 本轮 `backend:"grpc"` | 掉到 placeholder；`typedefFlatten` 21.6 s 后 gRPC 服务消失 |
| 3 | 本轮 `backend:"pylabview"` | **`route:"direct"`**，`subject 2 in/1 out, notOnPane: []`，卡在下一道墙 |

下一道墙是环境缺件，报得很准：`Call 4202: no Test.lvclass in the installation or near the caller`。
核查：LabVIEW 2026 目录 8 层深内无 `Caraya.lvlib`、无 `Test.lvclass`；`user.lib` 只有 `LV_MCP`；
VIPM 只有 `*.spec` 下载缓存；`VIPM/error/` 里 10-12 有一条 `HTTP Transport error ... jkisoft.com`
。**装 Caraya 必须有人在 VIPM 里点（联网），AI 替不了。**

顺带：pylabview 把路线判成 **direct**，grpc 反而掉 placeholder —— grpc 的 `openSubject` 要一个
本机生成不出的 helper。

### 15.6 绕开框架：纯原生节点的自包含测试

20 个对象 / 19 条线 / 7 061 字节：

```
3× Call ──> 3× Subtract(expected) ──> 2× Add ──> Equal?(0) ──> AllPass
                                      └──────────────────────> Total Error
```

用例 3×5、-2×4、0×7 都在 IEEE754 里精确，残差和严格为 0 当且仅当被测正确。

| 版本 | AllPass | Total Error |
|---|---|---|
| 正对照 | **true** | **0.00000000000000** |
| 负对照（expected -8 → -9） | **false** | **1.00000000000000** |

拼写坑：`Equal?` 的输出端子是 **`x = y?`**（等号两边有空格）。写 `x=y` 会被拒，但拒绝信息
把全部合法名列出：`(known: ?parm1, ?parm2, ?parmout, x, x = y?, y)`。
**pylabview 的拒绝信息可以直接当文档用**，比 NI 的 `Error 53` 好太多。

### 15.7 崩溃取证：`fpsane.cpp(1140)`

`generate_test(grpc)` 跑到一半，所有 RPC 转为 `Could not find a port serving lvai.LVAI`。现场：

```
[::1]:14596 -> [::1]:44136  SYN_SENT      <- 有人连，没人应答
[::1]:44134 / 44135         LISTENING 2348
2348 = NI.NigelLocalService.exe            <- 不是 LabVIEW.exe；44136 已不在监听
```

日志给出死因，**5 次同签名、4 个 minidump**：

```
DWarn 0x613A5C04: Fatal insanity (0x00000004) detected in 'lvai_typedef_tree.vi'
source\panel\fpsane.cpp(1140)
VI call stack: ConvertAIXMLToVI.vi <- LVAI.lvclass:Start Sync.vi <- ServiceBase:Start.vi <- RunService.vi
```

三条要记：

1. `fpsane.cpp` = front panel **sane** = 连接器窗格检查。这与 Round 5 的 `bind_pane_typedef` 竞态、
   Round 12 的 `conpane` 不可用是同一片区域：**凡把窗格当工作对象的 helper，在本机都不可靠**；
   而让它在"没有窗格的 stub"上干活，能把 IDE 打死。
2. **`dwarnCount: 0` 不是健康证明**。16:52 报 0/`looksDegraded: false`，16:55 就 5 条 Fatal insanity。
3. **这个日志以实例为生命周期，重启即被重写**（`lvai_ensure_labview` 在 16:59:36 把它冲回 2568 字节的
   启动态）。崩溃取证必须在重启之前做，否则只剩转录。
   恢复本身干净：`lvai_ensure_labview` 起新实例，新端口 14868，`state: ready`。

### 15.8 LV014，以及全库只有 9.9%

```
全无窗格 → INFO    lv014-no-connector-pane        （顶层 UI VI 的正常形态）
部分缺   → WARNING lv014-terminal-off-the-pane    （疏漏的样子；但 D 证明它合法，故不是 error）
每份文件只报一条
```

全库普查（70 份 AIXML / 383 个端子）：**带 conIdx 的只有 38 个 = 9.9%**；
端子全在窗格的 11 份 = round13 的 6 份 + round7 的 5 个 fixture（那 5 份是 NI 导出件）。
**这就是"前 12 轮生成的 VI 一个都不可被 Call"的量化版本。**

### 15.9 为什么 12 轮都没写

不是疏忽，是**命名误导**：`connection` 读起来就是"这个端子接不接"，写了它容易以为已经放进窗格；
真正的归属叫 `conIdx`，语义上没有任何提示，而且**少了不报错、不影响 execState、VI 依然 100% 合法**，
只让"能被别人调用"这个能力静默消失。

> **一个属性少了不报错、只让能力静默消失，它就不会被写。这类属性必须有闸门。**

---

## 16. Round14 增补：LVOOP 全链，与一颗装错的螺丝

### 16.1 先查 pylabview 认的是哪个安装

本机装了 LabVIEW 2018（32-bit）和 2026（64-bit）两套。pylabview 解析器的
`labview_root()` 先遍历 `Program Files (x86)` 并**返回第一个命中**，于是它认的是 2018：

```text
labview_root() -> C:\Program Files (x86)\National Instruments\LabVIEW 2018
```

后果是 `resource\Framework\Providers` 下那些 NI 自己的 provider 库全部"不在安装目录里"：

```text
Call 70: no Add Interface.lvlib in the installation or near the caller   （接口是 LV2020 才有的）
Call 70: no Add Class.lvlib ...                                          （2018 的 AddClass 也不在这个路径）
```

**建类、建接口、建访问器在这台机器上一条都走不通，而报错一直在怪路径。**

一句体检（不用 LabVIEW）：

```bash
python -c "import sys;sys.path.insert(0,r'C:\Users\<you>\labview-mcp\bin\scripts\aixml-pylabview');import resolve;print(resolve.labview_root())"
```

不是正在运行的那个版本？把 `LABVIEW_ROOT` 指向正确的安装，或改
`labview_root()` 为"跨两个 base 取版本号最大"，或直接补丁：
`best_key = int(digits)`、`key > best_key` 才算命中。

> 改脚本**不需要重启 MCP**：pylabview 每一步都是现读磁盘的脚本。改完同秒重跑即生效。
> 双安装机器上唯一还会错的情形是"跑 2018 而 2026 也在"，此时用 `LABVIEW_ROOT` 钉死。

### 16.2 方法源文件必须带 conIdx —— `panePattern` 救不了

`lvai_add_class_method` 会先盖 `panePattern: 4815`，读起来像"没写 conIdx 也会被分配槽位"。不会。
同一形状、同一次调用，只差 conIdx：

| 方法 | conIdx | conpane 步骤 |
|---|---|---|
| `Scale By.vi` | 0/1/2 | ok：`pattern 4833 -> 4815, 12 slots, no conIdx changed` |
| `Reset.vi` | 无 | **失败**：`no <cons> array in the front-panel heap` |

**这就是 Round 10 那句"LV2026 FPHb 的 `cons` 数组为空"的机制**：
`<cons>` 数组只在至少一个端子有 conIdx 时才存在。"空 cons" 与 "没窗格" 是同一件事。
失败的方法**不会成为类成员**（走不到 `member` 步），文件留在原地。

→ 闸门 **LV015**：有 `obj in`/`obj out` 路径替身 + 有端子缺 conIdx = error。

### 16.3 实现接口却缺 override：整个类坏，而报错不说

```text
前：execState 0, broken true    linkerErrors："VI 包括一个类型为 8 的错误。必须使用 LabVIEW 完整版…"
后：execState 1, broken false   （唯一改动：给类补上那个覆盖）
```

同一个文件、同一个路径，只因为类补了 override 就自己好了 —— 因果坐实。
但**报错文本一个字都没提接口**，而且这句"类型为 8 / 必须用完整版"
和 Round 6 retarget 失败时的报错**是同一句**。

诊断顺序：`execState 0` → 先问"实现接口了吗、每个声明方法都覆盖了吗" → 再看链接。

### 16.4 工具写进 .lvproj 的类条目会被 LabVIEW 的保存冲掉

`create_class` / `create_interface` 的条目是**工具自己写文件**的（LabVIEW 不参与）。
但 LabVIEW 可能仍持有该工程的**内存副本**，那份早于这次写入；下一次保存
（`close_active_project`、下一个类工具的 prologue、关 IDE）就把内存条目表写回，
**刚加的条目消失，零报错**。表现却是：

```json
"classIndex": -1,
"classPathsSeen": ["...\\Can Scale.lvclass"],     // 磁盘上明明有 4 个类
"hint": "classIndex -1 with classPathsSeen populated IS a path mismatch"   // ← 往路径上带
```

正确顺序：**先 `lvai_close_active_project`，再补条目，再调需要"类在工程里"的工具**。
落成闸门 `tools/lvproj_audit.py`（见 §16.6）。

### 16.5 三条读数坑

1. **`ancestors` 把接口排在真父类前面。**
   `Temp Sensor` → `ancestors ["Can Scale", "Sensor"]`，`inheritsFrom "Sensor"`。
   判父子用 `inheritsFrom` 或 `parentLinks[].kind`（`interface` / `class`）。
2. **访问器名字跟着 IDE 语言走。** 中文版生成 `读取Name.vi` / `写入Name.vi`。
   硬编码 `Read Name.vi` 的测试在中文版必然失败。名字从 `describe_class.members` 取。
3. **`vi_terminals` 把中文端子名解成乱码。** `读取` → `∂¡»°`，`输入` → `‰»Î`；
   同一时刻 `describe_class` 读同一批名字是正确的（它走 `.lvclass`，UTF-8）。
   它打印的 `<Call>` 片段是给 AI 抄的 —— **非 ASCII 端子名不要照抄**。

### 16.6 工程闸门 `lvproj_audit.py`（唯一读 .lvproj 的）

```bash
python tools/lvproj_audit.py "path/to/x.lvproj"      # 明细，exit 1 = 有 error
python tools/lvproj_audit.py --summary research/artifacts
```

| 级别 | 检查 |
|---|---|
| error | 列了条目但文件不在 |
| error | 条目排在 Dependencies/Build 之后 |
| warning | 磁盘上有 `.lvclass`/`.lvlib` 但没人列 —— **被冲掉条目的形状** |
| info | 磁盘上有 `.vi` 但没人列（常见正常态） |

URL 基准是本轮确认的：`/C/Users/...` 是绝对路径；`../lib/X` 相对**工程文件本身当作目录**
（从 `round14/Lvoop Demo.lvproj` 出发 `../lib` = `round14/lib`，不是 `artifacts/lib`）。
同一个约定也用于 `.lvclass` 的成员 URL。

### 16.7 建类链的可用配方（pylabview，全部实测通过）

```text
1  create_interface  Can Scale                                 1411 B, IsInterface true
2  add_class_method  接口方法 Scale By（conIdx 0/1/2 + path 替身）  terminalsRetyped 2
3  create_class      Sensor（fields + parentInterfaces）          fieldsAdded 2, interfacesLinked 1
4  add_class_method  Sensor 的覆盖 Scale By                      dynamicDispatchTerminals [0,2]
5  create_class      Temp Sensor（parentClassPath=Sensor）        inheritsFrom Sensor
6  create_accessors  Sensor, R/W, dynamic                        4 VI, members 1 -> 5
```

规矩：**接口（含全部方法）先完工，再建第一个实现类** —— 接口列表是 `create_class` 的
创建期输入，而且缺覆盖会打坏整个类（§16.3）。

---

## 17. 快速参考：一页纸


```
连接：   lvai_status               （starting 是正常的，再调一次；服务随 Nigel 起）
选型：   settings.json "aixmlBackend": "auto"   （LV<2026 自动切 pylabview）
查重：   lvai_example_index / lvai_palette_index   （先查 NI 有没有写过）
                                            离线等价：LabVIEWMCP --examples / --palette
方言：   lvai_aixml_reference node='A,B,C'          （终端名查不猜，逗号批量）
学样：   lvai_convert_vi_to_aixml <相似VI>          （照抄 NI 的布线）
G0 预检：python tools/audit_aixml.py --summary <file>（2.5 s，0 次 RPC，见 §11.3）
窗格：   Control/Indicator 一律写 conIdx="0,1,2..."   （不写=不在窗格上=不可被 Call，
         且 Call 它不报错、只是数据线空接，见 §15.1 / §15.4）
         方法源文件尤其如此：panePattern 4815 不创建 <cons>，缺 conIdx 直接死在
         conpane 步（"no <cons> array in the front-panel heap"，§16.2，LV015）
建类前：先确认 pylabview 认对安装 —— resolve.labview_root() 要是正在跑的那个版本，
         否则 Add Class.lvlib / Add Interface.lvlib 全"不在安装目录里"（§16.1）
建类序：interface(含全部方法) → class(实现它并覆盖) → child → accessors；
         条目被 LabVIEW 保存冲掉时先 lvai_close_active_project 再补（§16.4）
工程：   python tools/lvproj_audit.py <x.lvproj>    （唯一读 .lvproj 的闸门，§16.6）
预检：   lvai_check_aixml  [fix:true]               （0.4 ms 离线，抓静默错误）
校验：   lvai_validate_aixml                        （118 ms，失败不烧名）
生成：   lvai_generate_vi                           （validate+convert+面板测量）
布局：   lvai_layout_diagram                        （整图重排，规则见 §11.4）
回读：   lvai_convert_vi_to_aixml / lvai_describe_vi（结构对不对）
可执行： 本机 exec_state 不可用（helper 坏）→ 用 backend:"pylabview" 跑
诊断：   lvai_error_list                            （execState 0 时先问它，别猜）
存活：   常量先 convert→回导再进测试                （timestamp 会被丢弃，见 §12.2.1）
属性：   Constant 无 description · 数值 value 不能空（Error -2628 / 53，见 §13.2）
继承：   只读 inheritsFrom，别读 ancestors[0]       （Box/Flathead 的 ancestors[0] 是接口）
测试：   套件跑两次 · Broken≠Failed · 只读 JUnit 报告（Caraya 的 source 会指错套件）
运行：   lvai_run_vi_and_read_values                （backend:"pylabview" 可绕开辅助 VI）
纪律：   副本上干活 · git 先行 · 写操作每次确认 · 升级后 dump_schema · 手写 uid ≥4200
```

---

*本文所有【实测】数据采集于 2026-10-18，环境：LabVIEW 2026 (64-bit) + LabVIEW 2018
(32-bit, 运行中) + LabVIEWMCP server 2.0.1 (77eb0b22)，完整原始记录见
[`07-measured-session.md`](07-measured-session.md)。*
