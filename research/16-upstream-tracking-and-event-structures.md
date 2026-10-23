# 16 — Round7（补）：上游 v2.x 版本追踪、事件结构打法与下轮探针

> 标注惯例：【实测】= 本机一手测量数据；【上游】= Zuehlke/labview-mcp 官方文档/发布说明的
> 已发布测量（本机安装 v2.0.1 的 `bin/docs/` + GitHub releases + 源码树 FINDINGS.md）；
> 【待验证】= 已备好但尚未在本机运行的探针。
> 本会话（2026-10-22）环境限制：LabVIEW 未启动、两个 labview MCP server 在
> `~/.workbuddy/mcp.json` 中 `disabled:true`，无法做新实测；本篇为离线整理 + 联网调研 +
> 下轮探针预制。

---

## 1. 上游版本追踪：本地 v2.0.1 已落后 5 个 release【上游】

本机安装：**v2.0.1**（built 2026-10-13，commit 77eb0b2）。截至 2026-10-22 上游最新：
**v2.2.0**（2026-10-21）。中间版本及与本调研的相关性：

| 版本 | 日期 | 内容 | 对我们的意义 |
|---|---|---|---|
| v2.0.5 / 2.0.6 / 2.0.7 | 10-14 ~ 10-15 | pylabview reader 修 ShiftReg/常量；布局 | 读侧保真度提升（我们 Round5 回导 100% 保真的基础） |
| v2.1.0 | 10-16 | 内置 BD.Cleanup | 布局整理不再依赖 helperAixmlInvalid 的官方 helper |
| v2.1.2 | 10-17 | 并入 Jørgen Steen 的类/AF 改动 | Actor Framework 支持增强 |
| v2.1.4 ~ 2.1.6 | 10-18 ~ 10-20 | 更紧的 diagram 布局；自有 Cleanup 特性 | 生成物布局更紧凑 |
| **v2.1.8** | 10-20 | **control references 支持（grpc + pylabview 双路线）** | 推翻上游 9-16 的结论"AIXML 无法创作绑定控件引用"——该墙已翻；对照 `control-reference-binding.md` |
| **v2.2.0** | 10-21 | **Network Stream VIs（pylabview 路线可读写组合）；XControls 支持** | XControls **仅 pylabview**，grpc 不支持（工业 HMI 自定义控件的新通道，需升级后在 pylabview 路线验证） |

**行动项（下轮 LabVIEW 在线时）**：升级到 ≥ v2.2.0 再跑探针（XControls / Network Streams
是 v2.0.1 没有的能力）；升级后重跑 `lvai_dump_schema` 核对 RPC 变化。

---

## 2. 我们的实测结论 vs 上游文档：交叉印证【实测 × 上游】

| 我们的结论（轮次） | 上游对应文档 | 关系 |
|---|---|---|
| Round6：rebuild/open_file 的子 VI 不可按名解析（Error 53）；多 VI 稳定配方 = 子 VI `convert(openVI:true)` → 主 VI convert | `aixml-gap-census.md`：生产代码库 **70.4% 的 VI 调用自己的代码**，AIXML 全部 `Error 53`；NI 示例 corpus 独立测得 70% | **同病同因**。我们撞的是第一大鸿沟；上游统计确认这是普遍现象而非个例 |
| Round6：Error 53 是链接解析问题 | `FINDINGS.md` §4b：自有代码链接**相对于调用方文件**写（`TpVal 1, ["", "X.vi"]`），composer 的 resolver 覆盖 90.6% 的 NI 调用 | 上游给出了链接记录的完整规则，可解释我们全部 Error 53 现象 |
| Round7：`helperAixmlInvalid`（grpc 路线拒 bundled helper） | `ni-bug-validateaixml-crash.md` + FINDINGS：NI converter 遇未知属性名/类会 crash；ValidateAIXML 对 helper AIXML 严格 | 同属"NI 校验器墙"；pylabview 路线（我们 composer，无 NI 校验）是通行做法 |
| Round4-7：uid ≥100 | FINDINGS §7a：uid **4200+ 不产生 DWarn**（低于 LabVIEW 保留上限每个元素一次 DWarn） | 我们的 ≥100 可用但每次生成有 DWarn 噪音；下轮起新探针改用 4200+ |
| （新规则）AIXML 里 **`<VI>` 前的 XML 注释 → 空图（errorCode 0）；`<VI>` 子节点间的注释 → Error 42** | `aixml-skeletons/user-event-two-loops.md`（2026-09-11 实测） | **新增铁律**，已并入 §5；我们此前的 AIXML 从未写注释，属侥幸未爆 |
| Round4：Case 输出隧道 `cond="true"` | FINDINGS §4d：`cond="true"` = "Use Default If Unwired"（selTun 0x300000 位；输入隧道同规则） | 上游给出堆位级解释，印证我们用例 |
| Round6：单选项枚举 selector 的 Case 必坏 | 上游事件结构规则：**至少两帧**，否则无 `dIdx`、注册无法发生 | 同源思想：结构里"无可选择"时 LabVIEW 不建选择机制 |

---

## 3. 事件结构：上游已实测"pylabview 路线一次调用成型"【上游】

这是下轮主攻方向，上游测量（2026-10-10 ~ 10-11，suite t118-t121）结论：

### 3.1 用户事件三件套在 pylabview 路线合并为一次调用

grpc 路线需要三调用（`lvai_generate_vi_with_events` → `lvai_wire_dynamic_events` →
`lvai_set_event_data_fields`），且第三步原先不是 shipped tool。**pylabview 路线一次
`lvai_convert_aixml_to_vi(backend="pylabview")` 即写出可执行 VI**：动态事件终端的接线和
Event Data Node 的 payload 字段选择都由 composer 完成。实测 `Ticks Received = 5`、
`Error Out.status = false`（suite `t118_user_event` / `t119_user_event_payload`）。

### 3.2 必须遵守的 AIXML 写法（写探针的规格）

1. **事件名 = 数据类型常量的标签**：`<Constant _name="Tick" type="bool">` 喂
   `Create User Event` → refnum 标签 `Tick`；帧选择器必须是 ` &lt;Tick&gt;\3A User Event `
   （注意 XML 转义与 `\3A`）。两处必须严格一致。
2. **注册 refnum 必须经 `<Tunnel>` 进 Event Structure**——无隧道的用户事件帧被 composer
   **按名拒绝**。隧道即使帧内不读也要写（`sourceFrom: "tunnel"` 是每次实测的报道值）。
3. **至少两个帧**：`dIdx` 属于帧选择器列表，只有一帧时 LabVIEW 不建选择机制，注册失败
   （`AssertionError: no dIdx`）。便宜的第二帧 = 静态 ` "Stop": Value Change `。
4. **EventSpec 数值**（composer 内部，写 AIXML 不需要，但读堆/排障要知道）：用户事件帧
   source 1, regFlags 1, eSource 25, type 1000, dynIndex = 该事件在注册中的 1-based 位置
   （静态事件为 0）；Value Change：source 3, type 1073741826, eFlags 4, ddoUID = 控件；
   Timeout：source 4, type 1073741825。
5. **用户事件数据簇字段序**：`0 Source, 1 Type, 2 Time, 3 UsrEvtRef, 4+ payload`。
   **簇 payload 是拍平的**——两元素簇 `{Last,N}` 的数据簇就是
   `Source, Type, Time, UsrEvtRef, Last, N`，NI 导出里 `fields="Source,Last,Time"` 逐个点名。
6. **每个帧都有 Event Data Node**（LabVIEW 不允许删除；AIXML 没写时 composer 会合成一个）。
7. **多个用户事件共用一个注册**：重复输入名 `event source:…,event source:…`，每事件一帧，
   每帧 dynIndex = 其在注册中的位置（t121 实测：Tick+Count 两事件，handler 存 Count
   0,1,2 后停于 Tick）。
8. **控件引用作事件源**：`Register For Events` 的 source 可以是 VI Server 引用（pylabview
   路线；一个引用注册**一个事件每项**，AIXML 不写是哪个事件——composer 从帧选择器反推，
   帧顺序即事件顺序）。（class, event）码表在 `parts/control-events.json`（8 对，扫了 40 553
   个 VI 只找到 10 个引用源注册），**表外的一律拒绝不猜**。
9. **grpc 路线的旧约束**（pylabview 不需要，记录备查）：payload 需要 placeholder 常量 +
   prim 汇（Indicator/隧道作汇会因无 typeDesc 失败；placeholder 常量保留不删，删了
   `LabVIEW load error code 6`）。

### 3.3 DQMH：生成完整模块仍不可行，但路径已清晰【上游】

- **完整 DQMH 模块不能生成**：NI 官方 not-yet-supported 清单点名 DQMH + Event Structure；
  `Main.vi` 回读后重喂 ValidateAIXML 三类错（~20 个库限定 SubVI、`UDClassInst` 类对象
  AIXML 类型文法无法表达、连带 fixup 失败）。DQMH 的 scripting 工具还是密码保护的
  （errorCode 5002），无法经服务器驱动。
- **但单个 request VI 离可生成只差两个解析目标**：`Show Panel.vi` 的导出重验只有两条错
  （两个库限定 SubVI），其余结构（Case+隧道、Generate User Event、Bundle/Unbundle By Name、
  类型簇字符串、typedef 参数常量）全部可表达。
- **消费侧模式已明确**：`Start Module → Synchronize Module Events → Register For Events →
  Event Structure（广播帧 + 控件帧 + Panel Close? 过滤帧）→ Unregister → Stop Module`。
- **读侧完全可行**：`.lvlibp` 打包库也能整模组读出；`.lvlib` 成员清单可按 XML 解析
  （`Main.vi` + `Obtain */Request Events.vi` 即 DQMH 模块的指纹）；40 模块统计：27 核心
  成员 40/40 齐全，clone 套装 14/14 或 0/14 双峰（13 cloneable / 27 singleton）。
- **现实路线**：生成自包含叶子 VI（纯计算）+ 人工/脚本接线进模块；或下轮先攻"消费侧
  最小闭环"（Start/Sync/Register/Event/Unregister/Stop 六件套对**我们生成的** mock 模块）。

---

## 4. 鸿沟普查：下一步该攻什么【上游】

上游对生产代码库 900 VI 的结构普查（pylabview 离线检测，无 LabVIEW）：

| NI not-yet-supported 条目 | VI 占比 |
|---|---|
| **调用项目自有代码（Error 53 墙）** | **70.4%** |
| Property Node（非默认属性） | 11.8% |
| In Place Element Structure | 8.7% |
| Global/Local 引用 | 4.6% |
| **Event Structure** | **3.8%**（34/900，其中 14 个同时踩自有代码墙） |
| Timed Loop | 0.1% |
| XNode/XControl | 0% |

判断：**自有代码调用是唯一"量大面广"的鸿沟**（我们 Round6 的多 VI 配方正是攻它，且
pylabview composer 已跨过——FINDINGS §4b 90.6% 解析率）；Event Structure 占比小但正是
DQMH/交互式 HMI 的前置，且上游已证明 pylabview 路线可一次成型——**投入产出比最高**。
字符串/路径节点（我们原定方向三）降级：查 `aixml-node-gaps.tsv` 后多数已有模板节点
（Concatenate Strings / Format Into String / Scan From String 均在模板节点清单里）。

---

## 5. 新增铁律（入 best-practices 与 SKILL）【上游 + 本轮归纳】

1. **AIXML 严禁 XML 注释**：`<VI>` 前有注释 → 空图（errorCode 0，最毒）；`<VI>` 子节点间
   有注释 → Error 42。自文档化写在同级 `.md`。
2. **uid 从 4200 起**（新生成物），规避每次生成的 DWarn 噪音；既有 ≥100 规则仍有效。
3. **事件结构探针一律 pylabview 路线**（grpc 需三调用且本机 helperAixmlInvalid 风险）。
4. **用户事件命名三处一致**：常量 `_name` = refnum 标签 = 帧选择器。
5. **注册 refnum 走隧道进结构；至少两帧；每帧有 Event Data Node**。
6. 判据依旧：**文件级校验（pylv_extract，无 LabVIEW）是唯一可信判据**（Round7 竞态教训，
   对事件结构同样适用——composer 报 success 也要回读文件）。

---

## 6. 下轮探针（已预制，待 LabVIEW 在线直接跑）【待验证】

目录 `research/artifacts/round7/next-probes/`。P1 为上游已实测文档的字节级副本
（上游 2026-10-10 实测 `Ticks Received = 5`，本机 v2.0.1 composer 即该版本代码）；
P2-P5 为按 §3.2 规格改写的变体，**未经本机运行，结果以实测为准**。

| 探针 | 文件 | 测什么 | 预期 |
|---|---|---|---|
| P1 | `p1-user-event-two-loops.aixml.xml` | 上游 skeleton 字节级复跑（For 源 + While handler + Tick 用户事件 + Stop 静态帧） | `Ticks Received = 5`，Error Out 全 false |
| P2 | `p2-payload-direct-form.aixml.xml` | 直接点名 payload 字段（`fields="Source,Tick,Time"`，Tick 直入 Or），不走 placeholder | 同 P1；证 composer 字段点名路径 |
| P3 | `p3-cluster-payload.aixml.xml` | 簇 payload `{Last,N}` 拍平读两个元素，仅 `Last` 可停 | `Ticks Received = 3`，`Last N = 2`（Ticks To Send=3） |
| P4 | `p4-two-events-one-registration.aixml.xml` | 一个注册两个用户事件（Tick+Count），重复 `event source:` | handler 存 Count 0,1,2，停于 Tick |
| PP5 | `p5-valuechange-timeout-frames.aixml.xml` | 静态帧打法：面板控件 Value Change + Timeout 帧（t88 形状，交互 HMI 最小件） | 加载 execState 1，帧可响应 |

运行方式（LabVIEW 在线后）：

```text
lvai_convert_aixml_to_vi(aixmlPath=<probe>, backend="pylabview", openVI=true)
  → lvai_run_vi_and_read_values(viPath=<probe .vi>, backend="pylabview",
                                controls={Ticks To Send: 5})
  → pylv_extract 回读文件核验（判据铁律 6）
```

P1 通过后，P2-P5 逐个跑；任一失败先查 LabVIEW 日志（`%TEMP%\LabVIEW_32_*_cur.txt`，
注意 ~100 DWarn 后日志停写，需重启 LabVIEW）。

---

## 7. 本会话结论与下轮方向

1. Round7（bind_pane_typedef 竞态）已成文入库（doc 15 + artifacts/round7）。
2. 本会话新增：上游版本追踪（落后 5 release，升级 v2.2.0 是下轮前置）、事件结构完整
   打法（§3）、鸿沟普查（§4）、5 条新铁律（§5）、5 个待跑探针（§6）。
3. **下轮方向（优先级）**：① LabVIEW 在线 + 升级 v2.2.0；② 跑 P1-P5 事件探针，补齐
   "交互式 VI"能力；③ XControls（pylabview only）与 Network Streams 覆盖面；④ 若事件
   结构全过，尝试 DQMH 消费侧最小闭环（§3.3）对我们生成的 mock 模块。
