# 研究看板：AI 借助 MCP 开发 LabVIEW 程序

> 本文件是**滚动看板**，只回答三个问题：方向在哪、走到哪了、现在能/不能做什么。
> 每轮研究结束更新本文件与 `06-best-practices.md`，详细论证仍在 `20~24-*.md` 等单轮文档里。
> 最近更新：Round 20（2026-10-30）。

---

## 0. 命题与答案的一句话

**命题**：AI 能不能只靠 MCP over gRPC / ActiveX，从零写出可编译、可运行、可测试的复杂 LabVIEW
程序——含类、接口、事件、状态机、多 VI 工程？

**当前答案**：**能，但有一条极窄的正确路径**。窄在三个地方：

1. **写法是硬约束**：AIXML 有 15 条铁律 + 37 条上游 lint 规则，违反其中约 6 条时
   **不报错、照样跑、结果是错的**（静默失败）。
2. **验收必须脱离工具自述**：`ok:true` 不等于做成了，`execState 0` 不等于没做成，
   唯一的判据是读盘 + 实跑。
3. **环境本身会撒谎**：装了两个 LabVIEW 时 pylabview 认的是 2018；MCP 服务器被关掉时
   表现和"工具不存在"一模一样；`lvai_status` 的端口可能是死的。

这三条构成了整个研究的骨架：**先把"假的成功"和"真的失败"分开，再谈生成能力。**

---

## 1. 研究方向（四竖一横）

| 方向 | 问题 | 现状 |
|---|---|---|
| **A. 生成（synthesis）** | 一份需求文档 → AIXML → `.vi`，能到多复杂？ | 单 VI / 状态机 / 多 VI / 事件结构 / 面板移植 全线打通 |
| **B. 编辑（editing）** | 已有 VI 上改，而不是重生成 | 读侧坐标 → 写侧补丁 / bundle 深编 / `pylv_apply` 四级手段已定型 |
| **C. 面向对象（LVOOP）** | 类、接口、继承、override、动态派发 | 建链全通 + **类调用方端到端跑出值**（2018 工位）；派发绑定在编辑期完成，**运行时派发观测不到**（边界已钉死） |
| **D. 测试（verification）** | AI 写的东西谁来判对错 | 无框架的自包含测试可用（含负对照）；Caraya 需装包，未通 |
| **E. 横向：闸门与工具化** | 把经验变成不依赖人记性的检查 | 16 条自研规则 + 上游 37 条 + 工程审计，全部离线可跑 |

横向这条是本研究最实的产出：**每一条踩过的坑，最终都要变成一条能在 2.5 秒内报出来的规则。**

---

## 2. 进度总表（Round 1–20）

| 轮 | 日期 | 在线 | 主题 | 一句话结论 | 提交 |
|---|---|---|---|---|---|
| 1 | 10-18 | 是 | 面板美化（HMI 复原） | 像素级验证闭环；10 条面板铁律 | `c56987c` |
| 2 | 10-18 | 否 | 单 VI 生成 | AIXML 两端（面板/程序）正交；终端名查不猜 | `10018bc` |
| 3 | 10-18 | 否 | 复杂程序 | ShiftReg 种子必须根级；多 VI 走 `loadedSubVIs`；`.lvproj` 要手写 | `10018bc` |
| 4 | 10-18 | 否 | 状态机 + `.ctl` + 读侧 | 状态类型必须内联枚举；终值必须经 SR；VI→AIXML 回导保真 | `d9e8fe0` |
| 5 | 10-19 | 否 | pylabview 编辑链 | uid 坐标系跨 AIXML/RSRC 共享；改动分四级 | `8607ddd` |
| 6 | 10-19 | 否 | retarget 根因 + 生成器 | 链接名 = 被调 VI **内部 Name**；单选项 Case 必坏 | `f9e5bf5` |
| 7 | 10-20 | 否 | typedef 竞态 + 上游追踪 | 双保存顺序错 = 库锁死且单看文件完好 | `1ed447d` |
| 8 | 10-20 | 否 | 五道闸门（上游汇总） | 分层生成 + 文件级验证 + 冷启动复核 | `f8703a1` |
| 9 | 10-21 | 否 | v2.2.0 能力差 + 铁律变代码 | 106→126 工具面；uid 基线是 4200 不是 100 | `3de9ffb` |
| 10 | 10-21 | 否 | 25 次冷构建语料普查 | 类阶段占 49% 成本；3 个测试失败全是负对照 | `356a4c9` |
| 11 | 10-22 | **是** | 首次在线实测 | 真实工具面 99 个/23 RPC；4 条属性规则由真机拒绝得出 | `21004e2` |
| 12 | 10-22 | 是 | 边界 / 事件超时 / 面板移植 | 线不能隐式穿结构边界；Event Timeout 端子无 AIXML 写法 | `f31f80a` |
| 13 | 10-23 | 是 | 连接器窗格 + 测试层 | **`conIdx` 才是"在不在位上"**，缺了静默空接 | `1b72a50` |
| 14 | 10-23 | 是 | LVOOP 全链 + 装错的螺丝 | pylabview 在这台机器上答的是 LabVIEW **2018** | `bbde2aa` |
| 15 | 10-26 | 是 | **2018 工位**：无 Nigel 的一天 | composer 写的 2026 戳 VI 被 2018 打开并跑对（versionWarning 被推翻）；类调用方端到端；**派发绑定在编辑期**，P15 钉死 | `3e1825a` |
| 16 | 10-26 | 是 | **gRPC 路线恢复**：2026-capable 工位 | 全链路 author→compile(grpc)→run(pylabview) 跑通（y=42）；三处新规则 LV017/018/019；遗留 p16 LVOOP 树验证为合法 2026 中文工程 | `0a5be93` |
| 17 | 10-27 | 是 | **gRPC 掉线也能跑**：pylabview-only 闭环 + 循环方言 | gRPC/Nigel 本会话未起，整条 AI→AIXML→compile(pylabview)→run(pylabview) 闭环照通；**LV020 循环边界规则落成**；首个真机跑通的"复杂程序"旗舰样例 `examples/complex-demo/Accumulator.vi`（四 shift register 累计 Sum/SumSq/Product，N=3/5 数值逐位吻合） | `b515485` |
| 18 | 10-28 | 是 | **HTML→VI 前面板移植 + 深度换肤** | 4 个 HTML 主界面移植为纯前面板 VI；bundle XML 换肤配方（坐标/颜色/字体/mojibake 中文管线）全钉死；**两条死路**（装饰件注入不渲染、克隆控件拒载）做实验排除；**绘图区黑底不在 XML 里**——自研 `helper_graph_style.vi` 运行时写 `Plot Area:Colors:BG Color` 解决；NI 校验器失效改走 pylabview 后端合成 | `39bc34d` |
| 19 | 10-28 | 是 | 单基座迭代法：图形控件内部几何 / `howGrow` / 验证工具的假象 | 控件写绝对坐标、零件写相对坐标；`howGrow`="加载时是否重算"；**自研打印助手导出 PNG 非 1:1**（量像素改用 PrintWindow 截真窗）；`scaleRect` 是轴位置的唯一杠杆 | `c9bf141` |
| 20 | 10-30 | 是 | **多 VI 编排（P6 关闭）+ 冷机无人值守闭环** | 顶层 Call ×2（迭代子 VI + 汇总子 VI）N=5/3 两点验证逐位吻合；**pylabview 对 Call 查磁盘不查 IDE 内存**（R6 的 `openVI:true` 前提属 gRPC 路线）；`ensure_labview` 自己拉起 LabVIEW；`scripts/mcp_call.py` 无 IDE 直驱（本轮 9 次调用全经它） | 本轮 |

**四次"环境/工具假象"结案**，这是最值得记住的部分——因为它们看起来都像工具缺功能：

| 症状 | 当时判断 | 真因 |
|---|---|---|
| 工具明明装了却调不到（R11） | MCP 版本旧 | 服务器在 UI 里被手动关了 |
| `generate_test` 报 `noTerminals`（R13） | 测试工具不支持 | 生成的 VI 没有连接器窗格（写侧从没设过 `conIdx`） |
| 建类报 `no Add Class.lvlib`（R14） | 工具缺能力 | pylabview 认错安装（2018 没有 AddClass/AddInterface） |
| convert 警告 "2018 refuses (Error 1125)"（R15） | 2018 打不开 2026 戳产物 | **静态版本比较的误判**：2018 经 VI Server 通道打开并运行了 2026 戳的 composer 产物（6×7=42 实测） |
| `run_vi_and_read_values(grpc)` 报 `helperAixmlInvalid`（R16） | run 工具坏了 | **gRPC 的 run helper 在中文 2026 下自身校验不过**（helper AIXML 损坏）；run 改走 `backend:"pylabview"` 即好（LV019） |
| `lvai_status` 报 "Could not find a port serving lvai.LVAI"（R17） | gRPC 全挂、工具全废 | **gRPC/Nigel AI 服务没起，但 LabVIEW.exe 在跑**；整条闭环改走 `backend:"pylabview"`（convert + run）照样通（R17 实证），这是掉线时的"逃生舱" |

---

## 3. 能力地图

### A. 已验证可交付（端到端跑过，且从文件侧复核过）

| 能力 | 证据 |
|---|---|
| 叶子 VI：数组 12 节点、簇（Bundle/Unbundle）、结构三件套、类型转换 | `artifacts/round6`、`14-*.md` |
| 状态机（状态表 → AIXML 生成器，帧×隧道全自动） | `artifacts/round6`、`gen_statemachine.py` |
| 多 VI + Call + 运行出值 | `artifacts/round5/6`，`Sum=12/Average=4` |
| 事件结构：帧与注册存活（含 Timeout 帧的存在） | `artifacts/round12`，3 个 EventSpec |
| 面板保留移植（supplied panel + 生成程序） | `artifacts/round12/out/Grafted Scaled.vi` |
| `.ctl` typedef + 描述符读回 | `artifacts/round4` |
| LVOOP：接口 + 接口方法 + 类 + 子类 + override + 4 访问器 | `artifacts/round14/lib/`，6179B 类文件 |
| **LVOOP 调用方端到端**：path 常量替身 → `swap_subvis` constantsJson → 类方法调用 → 实跑出值（`"Temp Sensor"` / 负对照 `"Sensor"`） | `artifacts/round15/p15/`，2018 工位 |
| 无框架自包含测试（正 `AllPass=true` / 负 `false`，误差 1） | `artifacts/round13` |
| `.lvproj` 容器手写 + 对账审计 | `artifacts/round14`，5 工程 0E/0W |
| **全链路 author→compile→run（gRPC 恢复后）**：AI 写 AIXML → NI 编译器出 .vi → 实跑读数（y=6×7=42）；run 走 pylabview 避开损坏的 gRPC helper | `artifacts/round16/scale-double-r16.aixml.xml` + `Scale Double R16.vi`，2026-capable 工位 |
| **全链路 pylabview-only 闭环（gRPC 掉线也能跑）**：`convert_aixml_to_vi(backend:"pylabview")` 写 .vi + `run_vi_and_read_values(backend:"pylabview")` 实跑；不依赖 NI 的 gRPC 服务 | `examples/complex-demo/Accumulator.vi` + `Accumulator.aixml.xml`，R17 |
| **复杂算法 VI（While Loop + 四 shift register + 条件终止）**：AI 写 AIXML 实跑出值 | `examples/complex-demo/`：N=3→Sum6/SumSq14/Product6；N=5→Sum15/SumSq55/Product120；循环方言 LV020 钉死 |
| **HTML→VI 前面板移植 + bundle 深度换肤**：4 个 HTML 主界面 → 纯前面板 VI；绘图区底色等引擎默认经 VI Server 属性运行时改写（渲染 PNG 像素级验证） | `examples/hmi-html-port/`（4 .vi）+ `artifacts/round18/`（换肤脚本、helper_fp_print、helper_graph_style + AIXML 源、渲染图），R18 |
| **多 VI 编排（顶层 Call ×2，P6）**：N 进 → 迭代子 VI（While Loop + 双 SR）→ 汇总子 VI（Divide）→ Sum/Count/Mean 出；int→DBL 提升穿越子 VI 边界与顶层窗格；N=5/3 两点与手算逐位吻合 | `examples/multi-vi-demo/`（3 AIXML + 3 .vi），R20 |
| **冷机无人值守闭环**：`lvai_ensure_labview` 自起 LabVIEW 2026（gRPC 仍死照跑）→ convert(pylabview) ×3 → run(pylabview) ×2 出值 | `artifacts/round20/`，R20 |

### B. 有条件可用（有坑，按配方走才行）

| 能力 | 条件 |
|---|---|
| 任何要被 `Call` 的 VI | **必须手写 `conIdx`**，否则窗格不存在，Call 静默空接（LV014/LV015） |
| 方法源 VI | 同上是硬要求：`panePattern 4815` 救不了，缺 `conIdx` 死在 `no <cons> array` |
| 类链 | 顺序：interface（含全部方法）→ class（实现并覆盖）→ child → accessors；条目被冲掉先 `close_active_project` |
| 实现接口的类 | **不能缺 override**，否则整类 broken，而报错说的是"要用完整版 LabVIEW" |
| `exec_state` / `run_and_read` / `add_class_method` / `swap_subvis` | 一律显式 `backend:"pylabview"`；**2018 工位同样全绿**（compose 纯 Python + ActiveX） |
| 类调用方 | 预期 `execState 0` 中间态；换常量后**调用目标随常量类重定界**（编辑期绑定，沿数据流溯源，静态洗涤器拦不住） |
| 事件 Timeout 帧 | 帧建得出来，但超时端子无 AIXML 写法 ⇒ 永不触发（LV013） |
| 中文版环境 | 4 个 helper 文档被拒（`helperAixmlInvalid`）⇒ `signalsJson`、`connector_pane`、`graft(grpc)` 不可用 |
| DQMH 单个 request VI | 半成品，差两个库限定 SubVI 的解析目标 |

### C. 当前做不到（不是没试，是表达不出来）

- `.ctl` 作为 `type=`（任何拼写都被文法拒）
- 单选项枚举的 Case 结构（composer 写空隧道桩，`execState 0`）→ 单态机改走直线逻辑
- `Split Array` 节点（composer 不认，用 Array Subset / Delete From Array 替代）
- `timestamp` 字面量常量（**被静默丢弃**，convert 回 0、回导空串 ⇒ 闸门 G3.5 强制）
- 凭空创建 malleable VI；DQMH 完整模块；Actor Framework（未测）
- 没有任何 RPC 能创建 `.lvproj`（只能手写容器）
- **运行时动态派发**：类值唯一可 author 的来源是常量，而常量喂进来的动态调用**编辑期即绑定到最派生实现**（沿数据流溯源、穿越成员边界、与声明线类型无关）；运行期设定父类型窗格端子这条路，AIXML 写不出类端子、run 工具也没有类实例字面量。残路：IDE 手搭调用方，或等上游补类说明符常量语法（`To More Generic Class` 的 `target class`）

---

## 4. 度量数字（可直接引用）

| 指标 | 值 | 出处 |
|---|---|---|
| 真实工具面 | **99**（94 `lvai_*` + 5 `pylv_*`）over **23** RPC | `artifacts/round11` |
| 上游冷构建语料 | 25 篇 / 4409 行 / 57 类 / 193 VI / 112 测试 | `artifacts/round10` |
| 语料里的测试失败 | 3 个，**全部是故意负对照**；23/25 跑了负对照 | `19-*.md` |
| 类阶段成本占比 | **49%**（且是失败集中的那一半）；typedef 仅 10% 且一次过 | `19-*.md` |
| 全库 AIXML 体检 | 75 份：30E / 278W / 59info（LV014 后）→ LV015 后 31E | `tools/audit_aixml.py` |
| `conIdx` 覆盖率 | **38 / 383 端子 = 9.9%** | `22-*.md` |
| 自研铁律 | 20 条（LV001–LV020）+ 上游 37 条，全部离线 | `tools/lvrule_check.py` |
| pylabview-only 闭环 | gRPC/Nigel 掉线时仍可 author→compile→run（只需 LabVIEW.exe 在跑） | `examples/complex-demo/`，R17 |
| 复杂算法 VI 实测 | Sum/SumSq/Product 在 N=3 与 N=5 下数值逐位吻合手工值 | `examples/complex-demo/Accumulator.vi` |
| 2018 工位闭环 | compose 0.5–1.5 s；类方法 20–50 s；swap 2–5 s；run 5–18 ms | `24-*.md` |
| 会话经济学 | 延迟占比 3.6~9.7 : 1，每轮中位 7.1 s，重启中位 30.75 s | `17-*.md` |
| 类父链接离线解析 | 468 个类，13 个"父类"其实是接口 | `artifacts/round11/lvclass-parents.json` |
| gRPC 权威接口面（dump_schema） | **23 RPC**（proto3，package lvai） | `artifacts/round16/dump_schema_summary.txt` |
| p16 继承扫描（per-tree） | 4 类 / 3 有父 / 父全为接口 / 0 未解析 | `artifacts/round16/p16-parent-scan.json` |
| 多 VI 编排实跑（R20） | Sum/Count/Mean 在 N=5（15/5/3.0）与 N=3（6/3/2.0）与手算逐位吻合；run 3 ms | `examples/multi-vi-demo/` |
| 冷启动→出值（R20） | ensure 45 s + convert 3.1 s（3 份）+ run 3 ms；全程无 IDE、无 Nigel | `29-*.md` |

---

## 5. 闸门现状（G0 → G5）

| 闸门 | 判据 | 手段 | 状态 |
|---|---|---|---|
| **G0** 离线预检 | 铁律全绿 | `python tools/audit_aixml.py --summary <f>`（2.5 s，0 RPC） | 已入日常 |
| **G1** 需求定稿 | 数据模型/端子表/用例写死 | 提示词模板 | 人肉 |
| **G2** 分层生成 | 叶子 → 类 → 编排 | `generate_vi` / `add_class_method` | 通 |
| **G3** 结构验证 | validate 只报 `Unsupported SubVI:` 才放行 → `execState 1` | `validate_aixml` / `generate_vi` | 通（grpc 需 pylabview 兜底） |
| **G3.5** 常量存活 | 常量 convert→回导后值不丢 | 自建往返探针 | 强制（`timestamp` 必死） |
| **G4** 文件级验证 | 读盘：描述符、`udClassDDO`、链接、`stdPath` | `pylv_extract` + grep `*_FPHb.xml` | 通 |
| **G5** 运行 + 冷启动 | 实跑数值 + 负对照 + 重建后重开 | `run_vi_and_read_values` | 通（测试层需 Caraya） |

另有 `tools/lvproj_audit.py`：**唯一读 `.lvproj` 的闸门**，专抓"工具写进去的条目被 LabVIEW
的旧内存副本冲掉"这个形状（表象是 `classIndex:-1`，看起来像路径拼错）。

---

## 6. 未解问题与下一轮优先级

| 优先 | 事项 | 为什么排这里 |
|---|---|---|
| **P1** | IDE 手搭一个"父类型窗格端子"调用方给人/AI 读 | R15 钉死了边界：运行时派发需要"父类型线+子类型值"，而类值只能来自常量（编辑期绑定）。一个手工样本就能让 AI 照着 graft/改写 |
| **P2** | 装 Caraya（VIPM，需联网）→ 再跑 `generate_test(pylabview)` | 测试层三级卡在最后一级；顺带观察 `lvai_typedef_tree.vi` 的 `fpsane.cpp(1140)` 崩溃是否复现 |
| **P3** | 升级 labview-mcp ≥ v2.2.0 → `lvai_dump_schema` 逐条 diff | 老名字有 12 个已失效；**升级会覆盖 `resolve.py` 补丁，必须重打**；上游已到 **v2.3.1（2026-10-28，114 工具）**（R20 网络调研），升级窗口成熟 |
| **P4** | `lvai_layout_diagram` 首测 | **本机 v2.0.1 工具面无此工具**；**上游 v2.2.x 已交付**（自研布局引擎，2026-10-16 起内置于所有写入流程）——升级后即测，补 AI 产物"人看不懂"的最后一块 |
| **P5** | `lvai_error_list` 回诊 Round6/8 那些 `execState 0` 的档案 | **同上，v2.0.1 无此工具**；R17 改用"编译+运行真机验证"替代其部分意图（循环样本已验） |
| **P6** ~~已关闭（R20）~~ | 多 VI 版复杂程序：顶层 VI Call 一个迭代子 VI + 一个汇总子 VI | **R20 关闭**：`examples/multi-vi-demo/` 两点验证逐位吻合；R6 配方在 pylabview 路线细化为"**查磁盘、按顺序**"（`openVI:true` 属 gRPC 路线） |
| **P7** | 测试层判据脚本（读 JUnit `.xml`，`Broken ≠ Failed` 即 fail-fast） | Caraya 的 `source` 字段会指向通过的套件，不能看状态码 |
| **P8** | 覆盖空白：字符串/路径节点、Network Streams、XControls | 后者 v2.2.0 + pylabview 才支持 |
| **P9** | 给上游报版本警告的误判（2018 经 VI Server 不拒开 2026 戳产物） | 我们改不了上游代码，但文档里的这句话正在把用户吓退 |
| **P10** | P1 的父类型调用方 / 运行时动态派发 | R20 网络调研：**上游 v2.3.1 仍无类端子语法**（类身份不编码进 AIXML 类型串，动态端子仅 `connection:"dynamic"` 标注）；等上游补类说明符常量语法 |

---

## 7. 当前环境（每轮开头核对）

| 项 | 值 |
|---|---|
| LabVIEW | **2026-capable（装 2015–2025 + 2026；pylabview 经 resolve.py 补丁认最高版本 = 2026）；2018 32-bit 也装着**；`LabVIEW.exe` 进程在跑、`LabVIEWMCP.exe` ×2 在跑 |
| MCP server | `LabVIEWMCP.exe` 2.0.1（`77eb0b22`），UI 开关已恢复（`disabled:true` 已除） |
| gRPC 服务 | R20 冷机起步：`lvai_status` 十一候选端口全不可用；`ensure_labview` 只把 IDE 拉起（服务随 Nigel 起，需人手动开）。**闭环不依赖它**——convert+run 走 `backend:"pylabview"` 照常通（R17/R20 双实证） |
| pylabview 安装解析 | **需本机补丁** `bin/scripts/aixml-pylabview/resolve.py`（两个 base 取最高版本），`resolve.py.orig-round14` 为备份 |
| 已知缺件 | Caraya / `Test.lvclass`（VIPM 只有 `.spec` 缓存，`HTTP Transport error ... jkisoft.com`） |
| 已知坏件 | 4 个 helper AIXML 被中文版拒收；`signalsJson` 在 pylabview 路线仍被拒；**gRPC run helper 在中文 2026 损坏**（LV019，run 走 pylabview 即可）；gRPC 路径须反斜杠（LV017）；pylabview 读侧中文乱码（LV018）；pylabview `versionWarning` 误报"2018 在跑"（cosmetic bug，忽略） |
| 死条目 | `mcp.json` 里 `labview-cli` 指向已删除的 `Desktop\新建文件夹 (3)\...`，建议在 UI 删除 |

**存活判据**（不要信 `lvai_status` 的缓存）：`tasklist` 有 `LabVIEW.exe` 即够 pylabview 路线跑；
要 author/compile 走 grpc 才需要 `lvai.LVAI` 端口 LISTENING（随 Nigel 起，需人手动开）。

---

## 8. 复现入口

```bash
# 0) 离线预检（永远先跑这个）
python tools/audit_aixml.py --summary research/artifacts/round13/conidx-probe-b.aixml.xml

# 1) 工程对账
python tools/lvproj_audit.py "research/artifacts/round14/Lvoop Demo.lvproj"

# 2) 冷构建语料普查（无需 LabVIEW，需上游 checkout）
python tools/cold_build_census.py <upstream>/bin/docs

# 3) 类父关系离线扫描
python tools/lvclass_parent_scan.py <dir> --json

# 4) 线上最小闭环（gRPC 在线时）
lvai_status → lvai_validate_aixml(backend:"grpc")
→ lvai_convert_aixml_to_vi(backend:"grpc", 反斜杠 viPath)   # LV017：路径必须反斜杠
→ lvai_convert_vi_to_aixml(backend:"grpc", 回读比对)          # LV018：中文工程回读用 grpc
→ lvai_run_vi_and_read_values(backend:"pylabview")            # LV019：gRPC run helper 损坏，run 走 pylabview

# 5) 2018 工位类调用方闭环（Round15 配方，详见 24-*.md §6）
generate_vi(path替身方法AIXML, backend:pylabview)
→ add_class_method(lvclassPath, methodsJson, projectPath, backend:pylabview)
→ generate_vi(调用方AIXML)            # 预期 failedAtStep:"convert"
→ swap_subvis(constantsJson:[{label,class}], backend:pylabview)
→ run_vi_and_read_values(backend:pylabview)   # 读出值

# 6) gRPC/Nigel 掉线也照样跑（pylabview-only 闭环，Round17 配方）
#    lvai_status 报 "Could not find a port serving lvai.LVAI" 时不要慌：
lvai_convert_aixml_to_vi(backend:"pylabview",           # pylabview 自带 composer 写 .vi，不调 NI 的 gRPC RPC
    aiXmlFilePath:"<repo>/examples/complex-demo/Accumulator.aixml.xml",
    viPath:"<repo>/examples/complex-demo/Accumulator.vi")   # 路径反斜杠（Windows）
lvai_run_vi_and_read_values(backend:"pylabview",         # 经 LabVIEW ActiveX 实跑，只需 LabVIEW.exe 在跑
    viPath:"<repo>/examples/complex-demo/Accumulator.vi", inputsJson:'{"N":"5"}')
#   → Sum=15, SumSq=55, Product=120, Done=true（循环方言见 LV020）
```

# 7) 多 VI 编排（Round20 配方，P6 已关闭；冷机无人值守）

```bash
# 0) 冷机起步：LabVIEW.exe 不在跑？先拉起（gRPC 不来也无妨，run 走 ActiveX）
lvai_ensure_labview(waitSeconds:45)     # startedByThisCall:true → LabVIEW 2026 起来了

# 1) 子 VI 先、调用方后——顺序是硬约束；openVI:true 在 pylabview 路线被接受且被忽略
#    （composer 对 Call 查磁盘不查 IDE 内存，R6 的 openVI 前提属 gRPC/NI 路线）
lvai_convert_aixml_to_vi(backend:"pylabview", aiXmlFilePath:"<repo>/examples/multi-vi-demo/Accumulate N.aixml.xml", viPath:"<repo>/examples/multi-vi-demo/Accumulate N.vi")
lvai_convert_aixml_to_vi(backend:"pylabview", aiXmlFilePath:"<repo>/examples/multi-vi-demo/Mean Of Pair.aixml.xml",  viPath:"<repo>/examples/multi-vi-demo/Mean Of Pair.vi")
lvai_convert_aixml_to_vi(backend:"pylabview", aiXmlFilePath:"<repo>/examples/multi-vi-demo/Multi VI Demo.aixml.xml", viPath:"<repo>/examples/multi-vi-demo/Multi VI Demo.vi")

# 2) 两点实跑验证
lvai_run_vi_and_read_values(backend:"pylabview", viPath:"<repo>/examples/multi-vi-demo/Multi VI Demo.vi", inputsJson:'{"N":"5"}')   # → Sum=15, Count=5, Mean=3.00000000000000
lvai_run_vi_and_read_values(backend:"pylabview", viPath:"<repo>/examples/multi-vi-demo/Multi VI Demo.vi", inputsJson:'{"N":"3"}')   # → Sum=6,  Count=3, Mean=2.00000000000000

# 3) 本会话 IDE 没挂载 lvai_* 工具？用 scripts/mcp_call.py 直驱（stdio JSON-RPC，纯标准库）：
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" call lvai_status
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" list --out tools.json
```

---

## 9. 这份研究的方法论（可迁移到别的工具链）

1. **先证伪环境，再证伪工具，最后才怀疑自己的写法。** 三次环境假象都是这个顺序救回来的。
2. **每个结论都要有两种证据**：工具自述 + 独立读数（读盘/实跑）。只有一种的，标"未验证"。
3. **坑先记录，再规则化。** 记在 `06-best-practices.md` 是给人看的，落到 `tools/lvrule_check.py`
   才是给下一轮的 AI 看的——它不会记得上一轮为什么不能用 `Split Array`。
4. **A/B 只改一个变量。** conIdx 四分支、panePattern 二分支、单态机 vs 状态机，都是这么定的。
5. **负对照是测试的一半。** 语料里 3 个失败全是故意的；自己写的测试第一个要写的是"应该失败的那个"。
