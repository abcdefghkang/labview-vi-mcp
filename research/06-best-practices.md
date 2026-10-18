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
10. [快速参考：一页纸](#10-快速参考一页纸)

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

## 10. 快速参考：一页纸

```
连接：   lvai_status               （starting 是正常的，再调一次；服务随 Nigel 起）
选型：   settings.json "aixmlBackend": "auto"   （LV<2026 自动切 pylabview）
查重：   lvai_example_index / lvai_palette_index   （先查 NI 有没有写过）
方言：   lvai_aixml_reference node='A,B,C'          （终端名查不猜，逗号批量）
学样：   lvai_convert_vi_to_aixml <相似VI>          （照抄 NI 的布线）
预检：   lvai_check_aixml  [fix:true]               （0.4 ms 离线，抓静默错误）
校验：   lvai_validate_aixml                        （118 ms，失败不烧名）
生成：   lvai_generate_vi                           （validate+convert+面板测量）
回读：   lvai_convert_vi_to_aixml / lvai_describe_vi（结构对不对）
可执行： lvai_exec_state = 1                        （0=坏，-1=引用没开）
运行：   lvai_run_vi_and_read_values                （backend:"pylabview" 可绕开辅助 VI）
纪律：   副本上干活 · git 先行 · 写操作每次确认 · 升级后 dump_schema
```

---

*本文所有【实测】数据采集于 2026-10-18，环境：LabVIEW 2026 (64-bit) + LabVIEW 2018
(32-bit, 运行中) + LabVIEWMCP server 2.0.1 (77eb0b22)，完整原始记录见
[`07-measured-session.md`](07-measured-session.md)。*
