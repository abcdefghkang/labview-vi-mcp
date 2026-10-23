# Round 9：v2.0.1 → v2.2.0 的能力差，以及把我们的铁律变成闸门

日期：2026-10-23　环境：LabVIEW 未运行，两个 `labview` MCP 服务仍 `disabled:true`

本轮仍然**没有新的 LabVIEW 实测**。但和 Round 8 不同：那轮只能读本机 v2.0.1 的旧文档，
这轮拿到了**上游 HEAD 的完整源码**，并且找到了一件此前八轮都没做的事——把我们的结论变成
**可离线执行的检查**，然后拿它回头审自己的全部历史产物。

标注约定：`[上游源码]` 直接读到的代码/文档；`[上游文档]` 上游 `docs/` 的测量记录（不是我们测的）；
`[本机 CLI]` 本机 v2.0.1 可执行文件、无需 LabVIEW 的输出；`[本机审计]` 本轮用新工具审自己仓库的结果。

---

## 1. 取证方式：HTTPS 不通，SSH 通

`curl`/`git clone https://` 在本机全部失败于 `CRYPT_E_REVOCATION_OFFLINE`（schannel 吊销检查），
走代理也一样。但**推送用的 SSH 通道可以读公开仓库**：

```bash
git clone --depth 1 git@github.com:Zuehlke/labview-mcp.git
# HEAD = 2c9f37d "Read and compose Network Stream VIs on the pylabview backend (#96) (#97)"
```

这是本轮方法上的第一个结论，写下来因为下次一定会再遇到：
**离线机器上取上游资料，用 `git clone` 的 SSH，不要试 HTTPS 下载 release 包。**
仓库里带 `AIXML_Full.md`（914 行）和 71 篇 `docs/*.md`，比发布包更全。

许可证 MIT（Copyright (c) 2026 Zühlke），所以 `scripts/aixml_lint.py` 可以合规地 vendor 进本仓库。

---

## 2. 工具面：本地 106 → HEAD 126，新增 32、消失 12

方法：从本机 `LabVIEWMCP.exe` 抽出全部 `lvai_*` 字符串（106 个），与 HEAD `src/` 里引号内的
工具名（126 个）取差集。`[本机 CLI]` + `[上游源码]`

**这意味着一件事：我们 Round 1–8 文档里写的部分工具名，在 v2.2.0 上已经不存在了。**
其中两个是会直接改变打法的：

| 我们写过的 | HEAD 上 | 后果 |
|---|---|---|
| `lvai_run_and_read` / `_typed` | `lvai_run_vi_and_read_values` | 按老名字调用 = 工具不存在 |
| `lvai_cleanup_diagram` | `lvai_layout_diagram` | 不是改名，是**换了一整套布局引擎**（见 §3.1） |
| `lvai_wire_dyn_events` | `lvai_wire_dynamic_events` | 事件结构接线 |
| `lvai_discuss` | `lvai_discuss_file` | 文档生成 |
| `lvai_add_one_to_library` | `lvai_add_to_library` | 库成员 |
| `lvai_unload_vi` / `lvai_class_names` / `lvai_inventory` / `lvai_probe_relative` / `lvai_run_for_ms` / `lvai_cleanup_panel` | 无确认后继 | 需 `lvai_dump_schema` 现查 |

完整对照表：`research/artifacts/round9/tool-delta.csv`（44 行）。

新增的 32 个里，真正改变"能不能做复杂程序"的是四簇：

| 簇 | 工具 | 解决我们哪一轮的死结 |
|---|---|---|
| **布局** | `lvai_layout_diagram`、`lvai_layout_diagrams` | Round 1 的"图面难看"、Round 5–8 的"生成出来挤成一团" |
| **诊断** | `lvai_error_list`、`lvai_labview_state`、`lvai_vis_in_memory`、`lvai_save_modified_vis` | Round 4–8 反复出现的 `execState 0` 但**不说原因** |
| **AF 覆盖** | `lvai_create_override`、`lvai_af_add_hook`、`lvai_af_remove_hook`、`lvai_af_hook_read`/`_modified_members`/`_save_members` | Round 6 用 retarget 硬凑的"子 VI 改造"，Round 8 判定 DQMH"还不能整模块生成" |
| **库/图标/文档** | `lvai_create_library`、`lvai_move_to_folder*`、`lvai_member_callers`、`lvai_icon_*`（9 个）、`lvai_set_vi_description(s)`、`lvai_set_class_description` | 交付物"看起来像人做的"这一层 |

> **注意 `lvai_af_remove_hook` 的历史**：`[上游文档]` 明确记录它曾在移除 series hook 之后
> **保存了一个坏掉的 override 并回答 `ok: true`**，现在改为 **bypass**（把线的源重连到所有汇）。
> 这是一条通用教训：**一个工具"回答成功"和"文件是对的"之间没有必然联系**——Round 7 的
> `bind_pane_typedef` 竞态是同一个形状的第三例。

---

## 3. 五件改变做法的事实

### 3.1 布局有了引擎，而且它明确不做 NI 的 Clean Up

`[上游文档]` `docs/diagram-layout.md`（1123 行，本地旧版没有）。测量对象是 DQMH 的 `Main.vi`：
NI 自己的 Clean Up Diagram 把 1344×805 摊成 **3805×1692**，case 框宽了 4 倍，注释离开节点，
直的 error 线被掰弯。原因：NI 的算法是全局数据流列布局，**不知道人画图时留下的形状**。

引擎的做法（读一次就够用，写 AIXML 时按它摆，就不用等它兜底）：

- 三层：读（`lvbd_layout_dump.xml` 遍历每个 frame 的每个 object 和 wire）→ 算（纯 C#，不碰 LabVIEW）→ 写（8 趟 + `Save.Instrument`）。
- 列 = 数据流最长路径（Sugiyama 分层）；**并行循环同列上下叠放**（生产者/消费者就是两个无连线的 While Loop）。
- **一条直的 error 轨贴底**，轨上的节点让 error 端口中线对齐同一水平线；第二条 error 链不占轨。
- 常量挂在消费者身上；同一节点的多个常量**上下堆叠**（并排会把整列推宽）；链上的常量最多上抬 120 px（`MaxLift`）。
- 结构内部的隧道/移位寄存器/case selector **与它内侧接的那根线齐平**；Event Structure 的动态事件端子**放顶部**。
- 顺序陷阱：While Loop 的 stop 和 `i` 必须在 **`Frame Size` 写完之后**移动，且**写 `Position` 而不是 `Move`**——`Move` 是相对循环内部图的坐标，而且循环会把自己的端子钳到右下角（要 700,150 和 800,150 都落到 835,194）。
- 结构不能靠 `Bounds` 改大小（`Error 1029` 只读），`Auto Size`/`ShrinkWrapStructs` **只会变大**；能精确改的只有 `Frame Size`（Width/Height 的 u32 簇）。
- 每根线要 `CleanUpWire` **三遍**：一遍之内它会绕过后面才清理的旧线段。

**对我们的用法**：`lvai_layout_diagram` 是"生成后的整容"，不是"生成的替代"。写 AIXML 时按上面
几条摆，就等于把引擎的规则提前用掉；引擎再跑一遍是修正，不是救命。
真实代价：45 个 VI 全量布局 **62 s**（修复后；修复前 228 s），单个应用 VI 中位 0.39 s。

### 3.2 `execState 0` 现在有原因了

`[上游文档]` `docs/error-list.md`。`lvai_exec_state` 只回答"坏没坏"；`lvai_error_list` 回答
**Error List 窗口里那几行 + 每行的解释**，底层是 `{LV.VI}` `Get Errors` 与
`{LV.Application}` `Get Broken VI List` 两个不在公开 VI Server 目录里的方法。

三条会咬人的细节：

1. **实例不对就等于没查**：`Get Broken VI List` 只列**一个**应用实例的坏 VI。走 ActiveX 是 IDE 主实例；
   走 NI 的 `RunVIAsTopLevel` 是 addon 自己的实例——同一个坏 VI，后者回答**空列表、无错误**，
   读起来和"一切正常"一模一样。
2. 它读**内存**，不读磁盘。磁盘上的文件先 `lvai_open_file` 再问。
3. 并行调用会撞：`Get Errors` 偶发 `1026 VI Reference is invalid`（约 40 次并行里 4 次，从不单独发生），
   答案里现在有 `errorsNotReadBecause` 和一次重试。

**这直接改我们的诊断顺序**：`convert`/`generate` 回 `execState 0` 时，第一件事不是猜 wiring，
是读 `errors`；`errors: null` 时看 `errorsNotReadBecause`，不要当成"无错"。

### 3.3 Actor Framework 覆盖：AIXML 写不了 `Call Parent Class Method`，所以走 provider

`[上游文档]` `docs/af-override-tools.md`（371 行）。这是 Round 8 里"DQMH 消费侧最小闭环"
缺的那块拼图的一半：

- **AIXML 无法生成 `Call Parent Class Method`**，所以手工写出来的 AF override **一定是 `eBad`**。
  没有 Call Parent，Actor Core 没有消息循环，Stop Core 不会停子 actor，Handle Error 要自己处理 43。
- 正确路线：让 NI 的 `CLSUIP_CreateOverride`（IDE 的 New > VI for Override）**产出 override**，
  再用 VI Server 把 hook VI **摆上去、接上线**。`lvai_create_override` + `lvai_af_add_hook` 就是这条路线。
- 构建顺序是硬的：类 → typedef 字段绑定 → 访问器 → 方法 → pane-typedef 绑定 → 库 → 消息 → override → hook。
  **每个 hook VI 先成为类成员，才允许被挂。**
- 四种 hook 形状：`branch`(A) / `series`(B) / `seriesAfter`(B-after) / `branchFromNode`(C)，
  以及内置 pane（Pre Launch Init 无 `error in`；Actor Core 的 `Actor out` 是 Actor 类型；Stop Core 无 error 端子）。

### 3.4 离线能用的比我们以为的多：494 个范例、1569 个可调用 VI、36 种连接器面板

`[本机 CLI]` v2.0.1 的 `LabVIEWMCP.exe` 自带一堆**不需要 LabVIEW** 的子命令，我们前八轮只当它是
MCP 服务，从没在离线时用过：

```
--examples [query]   494 个自带范例，带 NI 的描述与 keyword，纯离线
--palette  [query]   1569 个调色板可达 VI / 407 个 .mnu，纯离线（220 ms 重建索引）
--pane               36 种连接器面板图案，32 种带实测槽位几何
--pylv-status        bundled pylabview 可用性（本机：python 3.12 x64，已 provision）
--pylv-extract <vi>  用 pylabview 把既有 VI 读成带坐标的 XML，不需要 LabVIEW
--describe-class     读 .lvclass 的血统/成员/作用域，不需要 LabVIEW
```

实测两条：

- `--examples "state machine"` → 494 里 4 个命中，`Design Patterns\State Machine\State Machine Fundamentals.vi`
  的完整路径与描述直接可读。**"先看 NI 怎么写"这件事，离线就能做。**
- `--palette "filter"` → 1569 里 52 个命中，带 `.mnu` 路径作为"这台机器确实有它"的证明。
  `filter 1d array` 三个词全中才返回，所以查不到时**删最窄的那个词重试**——工具自己会说这句。

这条把 Round 6 的死结换了个方向：以前是"生成失败才发现 target 解析不了"，现在可以
**先查索引确认它存在**（`--palette`），或者**先读范例确认 NI 已经写好了**（`--examples`）。
上游 CLAUDE.md 把这条写成一句更狠的话：
> 在 index 里查不到，**不是**"这个 Call 非法"的证明。解析靠的是名字能不能被安装树找到，调色板无关。

### 3.5 上游自己的 `CLAUDE.md`（3358 行）是一份"如何给 AI 写作业指导书"的样本

`[上游源码]` 根目录 `CLAUDE.md`，3358 行，292 KB。结构本身就是方法：
`Agents first` → `Generating LabVIEW code`（1100 行）→ `Which interface to reach for`（1470 行）
→ `When a tool call fails` → `When LabVIEW disappears` → `Where the knowledge lives`。

值得直接抄的三条写作原则：

1. **写实测，删掉"做不到"**。原文记录：某文档写了"这一层无法做得更好"，那是一句**推断**，
   却用测量的口吻写下，于是 18 天没人再看一眼；实际上补上只要四行。
   > 一条被当成事实写下的限制，就会被当成事实读。
2. **一个数字被推翻时，去改产生这个数字的东西，不是改你正在写的那一段。**
   `dwarnCount` 数的是日志行、每个事件写两行这件事**早在文档里**，但代码和别处段落都没跟着改。
3. **同一规则的第二份实现，比没有更糟。** `AixmlCheck.SafeUidBase`=4200 与 lint 的 `LOW_UID_CEILING`=5000
   分歧了几天，lint 一直告诉作者"你自己生成的文件违规"。

第 3 条直接决定了本轮 `tools/` 的写法（见 §5.1）。

---

## 4. 反过来打自己：三处需要修订的既有结论

### 4.1 `uid >= 100` 是错的，应该是 4200

我们的铁律 #5 写"uid 一律 ≥100（10–35 保留区会被自动改写）"。`[上游源码+文档]` 的实测是：

- LabVIEW 面板堆的 uid 上限**不是 42，而且会随会话增长**：132 个 block 里观测到 42/55/69/71/79/81/87/88/91/95/129/163，
  **76% 的 block 上限高于 42**。
- 对照实验（有 control，因为"没测到"什么也证明不了）：四个元素放 uid 4200–4230，
  `dwarnCount` 7→7；同样四个放 10–13，7→11（**每元素一个事件**）。
- 所以安全基准是 **4200**，是观测上限的 26 倍。

**为什么这条不是洁癖**：被改写的 uid 意味着**文件里的身份不是我们写文档时针对的那个身份**。
Round 5 的整条读侧/写侧链条建立在"uid 坐标跨 AIXML/RSRC 共享"上——一个落在 100–163 的 uid
在长会话里被 LabVIEW 重新编号，读回来的坐标就对不上写侧。**这解释了我们此前没有解释过的一类
不稳定：不是每次复现，取决于 LabVIEW 开了多久。**

修订后规则：**作者手写 uid 一律从 4200 起编号；导出件（LabVIEW 自己产出的）不用改。**

### 4.2 裸网属性只能写网名，不能写 `terminal:net`

`[本机审计]` Round 4 的 `probe-frame-sr-read.aixml.xml` 里写着 `selectin="value:102.value"`，
正确写法是 `selectin="102.value"`。`count` / `maxin` / `maxout` / `selectin` / `selectout` / `cond`
都是**裸网**属性；`inputs`/`outputs` 才是 `terminal:net` 列表。混用不会报错，只会让线找不到源头，
而 LabVIEW 报的是**读端**「Contains unwired or bad terminal」——把你指向错的那一端。
（本轮新工具抓出来的，见 §5.2 表第一行的 `net-unproduced`。）

### 4.3 `cond="true"` 是字面量，不是网——而离线检查器不知道

我们的状态机（Round 4/6）停止逻辑写的是 `cond="true"` 的隧道 + Condition 直读。
上游 lint 把 `cond` 归为"消费一个裸网"，于是把 `net "true"` 报成
`net-unproduced`（**7 处、4 个文件，全是误报**）。这些文件被 NI 转换器接受、导出、运行过。

处理方式：`tools/audit_aixml.py` 里**按名字抑制并单独计数**（`FP_CONDS`），不静默丢弃；
同时在文档里记下这是上游的盲点。**我们没有去改 vendored 文件**——理由见 §5.1。

---

## 5. 把铁律变成闸门：`tools/` 三个脚本

### 5.1 为什么不直接改上游 lint

上游 lint 有 37 条规则，覆盖我们从来没系统查过的东西：父子关系（`uid_parent` 指向**存在但错的那个**元素，
`validate` 会回 `errorCode 0`）、net 生产/消费、类型语法、VI Server 名字拼写、case 隧道完整性。
它是**别人的测量**，升级时应当整份替换。

所以我们分三层，各自只有一个职责：

| 文件 | 内容 | 允许改吗 |
|---|---|---|
| `tools/aixml_lint.py` | vendored 上游 37 条规则，MIT，文件头写明来源 commit | **不改**，刷新时整份覆盖 |
| `tools/lvrule_check.py` | 我们自己的 7 条铁律（LV001/003/004/005/006/007/008） | 只往这里加 |
| `tools/audit_aixml.py` | 跑两个、合并、按文档类型分流、抑制已知误报、出表格/JSON | 门面 |

这正是 §3.5 第 3 条的应用：**同一规则不要两份实现**。原本我写了 LV002（uid ≥ 4200），
跑出来发现与上游 `uid-low` 完全重合、每条告警翻倍，于是**退役 LV002 而不是留着**——
编号保留不复用，退役理由写进文件头。

我们的 7 条，每条对应一轮的实测：

| 规则 | 断言 | 来源 |
|---|---|---|
| `lv001-xml-comment` | AIXML 里不允许 XML 注释 | Round 7：`<VI>` 前有注释 → **空图 + errorCode 0**（静默那类）；子元素之间 → Error 42 |
| `lv003-sr-seed-inside-loop` | 移位寄存器 `Left inputs` 的种子必须由**循环外**产出 | Round 3 的 A–E 五分支、Round 4 |
| `lv004-single-frame-case` | 单框 Case Structure 直接判死 | Round 8：单选项枚举的 Case 必坏，composer 写空隧道桩，`execState 0` |
| `lv005-while-without-condition` | While Loop 必须有 `Condition` | Round 4 |
| `lv006-call-target-is-path` | `Call` 的 `target` 是名字不是路径 | Round 6：路径永不解析，`Error 53` |
| `lv007-shiftreg-incomplete` | `ShiftReg` 必须同时有 `Left` 和 `Right` | Round 4 |
| `lv008-duplicate-selector` | 两个 frame 不能同一个 selector | Round 4 |

### 5.2 首轮全量审计：审的是我们自己

```bash
python tools/audit_aixml.py --markdown --root research/artifacts \
       --out research/artifacts/round9/lint-sweep-report.md research/artifacts
```

`[本机审计]` 59 个 XML → **50 份 AIXML**（另 9 份是 `<RSRC>`/`<FPHb>` pylabview 转储，按文档类型跳过）。
结果：**21 个 error、92 个 warning**，6 处已知误报被抑制。耗时 2.5 s。

错误台账（21 条，逐条核过）：

| 文件 | E | 规则 | 判定 |
|---|---:|---|---|
| `round3/saturating-accumulator.aixml.xml` | 3 | `lv003` | **真缺陷**——这就是修复前的那一版 |
| `round3/variant-a/b/c` | 3×3 | `lv003` | **负对照**——A/B/C 本来就是"种在循环里"的反例 |
| `round3/variant-e-mixedseeds` | 2 | `lv003` | **负对照**——混合种子 |
| `round3/variant-d-rootseds` | 0 | — | **修复版**，干净 |
| `round3/saturating-accumulator-v2` | 0 | — | **修复版**，干净 |
| `round4/probe-frame-sr-read` | 1 | `net-unproduced` | **真缺陷**，§4.2 的 `selectin` 写法 |
| `round7/fixtures/*`（5 个） | 1×5 | `conn-required-output` | **真缺陷**，见下 |
| `round7/next-probes/p4` | 1 | `net-typo` | 探针稿，未上机 |

这个分布是本轮最有说服力的一件事：**规则把"修好的"和"没修的"精确分开了**——
`saturating-accumulator` 3 error，它的 `-v2` 0 error；A/B/C/E 全红，D（根级种子）全绿。
不是我们调的参，是 Round 3 那五分支实验的原始数据。

**顺带抓到一个 Round 7 的遗留**：5 个 fixture 的 indicator 上写了 `connection="required"`。
后果不是它自己坏，是**每一个不接这个端子的调用方都变 1003 不可执行**，而它自己
`validate`/编译/运行/导出全都完美——属于"读任一文件都验不出来"那一族（Round 7/8 同律）。
新生成一律写 `connection="recommended"`；已存在的 VI 用 `{LV.ConnectorPane}` `SetWireRule(conIdx, 2)` 修。

90 个 warning 里绝大多数是 `uid-low`（50 份文档用了 100–300 的 uid，正是 §4.1 那条规则要改的原因），
其余是 `net-unconsumed`（面板控件接了不读，多数是我们故意留的探针输入）。

### 5.3 用法

```bash
# 生成前必过：0 个 error 才进 LabVIEW
python tools/audit_aixml.py --summary draft.aixml.xml

# 只跑我们自己的 7 条
python tools/lvrule_check.py draft.aixml.xml

# 全仓库回归（2.5 s）
python tools/audit_aixml.py --summary research/artifacts
```

退出码：有 error 就是 1，可以直接挂进脚本/CI。

---

## 6. 闸门模型更新：G0

Round 8 的五道闸门是 G1 需求 → G2 分层生成 → G3 结构验证 → G4 文件级验证 → G5 运行+冷启动。
本轮在 G1 和 G2 之间插一道，并把 G3 的内容换掉：

| 闸门 | 问什么 | 工具 | 代价 |
|---|---|---|---|
| **G0 离线审计**（新） | 文档在没有 LabVIEW 的情况下能判定的错，全查过没有？ | `tools/audit_aixml.py` | **2.5 s / 50 文件**，0 次 RPC |
| G1 需求定稿 | 数据模型钉死了吗？ | 人 | — |
| G2 分层生成 | 叶子 → 类/接口 → 编排 | `lvai_generate_vis` 批量 | 一轮往返 |
| G3 结构验证 | 目标能不能被**找到**？ | `--palette` 先查、`lvai_validate_aixml` 后问 | 离线优先 |
| G4 文件级验证 | 文件里真的有吗？ | `pylv_extract` / `lvai_convert_vi_to_aixml` 回读 | 秒级 |
| G5 运行 + 冷启动 | 跑得起来吗？重启后还认吗？ | `lvai_run_vi_and_read_values` + `lvai_error_list` | 一轮往返 |

G0 的意义是**把一次 LabVIEW 往返换成 2.5 秒的本地检查**。上游自己的说法是：
一轮约 80 次工具调用里有 ~24 次是纠正性的，而其中三类**离线可判**——
`uid_parent` 指错元素、网被读但没人产出、网被产出但没人读（最后一条会伪装成前一条）。

---

## 7. 下一步

本轮把"离线能做的"榨干了，剩下的都必须有 LabVIEW。按优先级：

1. **升级到 ≥ v2.2.0**（本机 v2.0.1 落后 5 版），升完先 `lvai_dump_schema` 核对工具名，
   再跑一遍 `tools/audit_aixml.py` 确认工具名迁移没有漏。
2. **G0 进日常**：把 `audit_aixml.py` 挂到每次生成之前，观察一轮长会话里 `_dwarnCount` 是否因为
   uid ≥ 4200 而稳定（这会顺手验证 §4.1）。
3. **P6–P9 探针**（`research/artifacts/round8/probe-recipes.md`）：类方法自调访问器 / 接口保存顺序 A-B /
   Caraya / 冷启动复核。
4. **`lvai_layout_diagram` 首测**：拿 Round 3 的 `saturating-accumulator-v2` 当输入，
   比较"生成后直接布局"与"什么都不做"的图面尺寸，这是 Round 1 遗留问题的正式收尾。
5. **`lvai_error_list` 接进诊断**：把 Round 6/8 那些"`execState 0` 但查不出"的档案重跑一遍，
   看新的 `errors` 字段能不能给出一句原因。
6. 仍是降级项：字符串/路径节点覆盖、Network Streams、XControls（v2.2.0 才有）。

---

## 附：本轮新增文件

```
tools/aixml_lint.py                          上游 37 条规则（vendored, MIT）
tools/lvrule_check.py                        我们的 7 条铁律
tools/audit_aixml.py                         合并闸门 + 报告
tools/README.md                              来源、用法、规则表
research/18-v220-capability-delta.md         本文
research/artifacts/round9/tool-delta.csv      106→126 的逐条对照
research/artifacts/round9/lint-sweep-report.md 50 份 AIXML 的审计表
research/artifacts/round9/lint-sweep.json     同上，含每条消息
```
