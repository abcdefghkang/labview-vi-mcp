# 17 — Round8：从叶子 VI 到完整应用——上游一手测量汇总与"五道闸门"模型

> 标注惯例：【实测】= 本机一手测量；【上游】= Zuehlke/labview-mcp 官方 `bin/docs/` 中标注了
> 日期与环境的一手测量；【经验】= 通用工程结论；【待验证】= 已备好未跑。
>
> **本轮性质：离线汇总轮。** 2026-10-22 ～ 10-23 期间本机 LabVIEW 未运行、两个 labview MCP
> server 在 `~/.mcp.json` 中 `disabled:true`，无法产生新实测。因此本轮做三件事：
> ① 把本机 v2.0.1 安装包 `bin/docs/` 下 **73 篇文档中此前未挖掘的 21 篇**读完，只提取与
> "AI 直接开发复杂 LabVIEW 程序"直接相关的、有日期与环境的一手测量；
> ② 与我们的 Round1–7 实测做交叉印证，找出**同一缺陷的不同面孔**；
> ③ 归纳出可执行的"五道闸门"验收模型 + 6 条新铁律 + 4 个待跑探针。
>
> 上一轮（Round7）的两个交付物已推送：`15-bind-pane-typedef-race.md`（.ctl 绑定竞态根因与
> 一条边修复）、`16-upstream-tracking-and-event-structures.md`（事件结构打法 + 上游版本追踪），
> commit `1ed447d`。上游最新版本仍为 **v2.2.0**（2026-10-21），本轮复查无新 release。

---

## 1. 五个改变做法的新事实

### 1.1 `Call` 到项目本地代码：目标"已加载"即可解析——但只有 convert 认，validate 不认【上游】

这是全库最重要的一条，直接决定多 VI / 类 / 库调用的写法。上游四臂实验（2026-09-25，
LabVIEW 2026 32-bit，fixture 全在 `vi.lib/user.lib/instr.lib/LVAddons` 之外）：

| 臂 | 调用时目标的状态 | `ValidateAIXML` | `ConvertAIXMLToVI` |
|---|---|---|---|
| A | 未加载、无项目 | `Error 53` Unsupported SubVI | `Error 53`，不写文件 |
| B | 项目开着、目标是成员但未打开 | `Error 53` | `Error 53` |
| C | 目标**通过项目打开** | `Error 53`（裸名/`\`/`/` 全拒） | **`errorCode 0`，写出 9 490 B** |
| D | 目标**松散打开**、无项目 | 未测 | **`errorCode 0`，写出 6 365 B** |

C/D 产物四重验证：`execState 1`、回导 `Call` 网完整、实跑数值正确、**新开一个什么都没加载的
LabVIEW 从磁盘打开仍是 `execState 1`**（链接写进了文件，不是借内存）。

三个衍生事实，都是我们踩过或必将踩到的：

1. **开一个类成员 = 整个类可解析**。`IMC Counter.lvclass` 三个调用（New/Write/Read），只打开
   `Read Count.vi` 一个成员，convert 三个全解；类类型导线**不需要任何占位/替换**——线的类型
   来自端子，占位路线上的 `path` 替身、swap、`{LV.Constant}` `Replace` 全部可以省掉，只要
   **链条从一个返回对象的成员开始**（AIXML 没有类常量）。
2. **`Error 53` 与保存期错误的判别器**：`53` 来自 `VI generator.vi` = 根本没解析到；
   `1051 / 1357 / 7` 来自 `Save:Instrument` = **已经解析成功**，只是命名或路径有问题。
   以后看到 1051 不要再去查"是不是没加载"。
3. **一次失败的 convert 会"烧掉"调用方的名字**：A 臂的 `53` 之后，即使目标已加载，同名
   `_name` 再写会得到 `Error 1051 内存中已有同名文件`，且关闭项目/驱逐 VI 都清不掉，**只有重启
   LabVIEW**。所以：**永远不要用真实文件名做探针**，探针用 `LVMCP Convert <hex>.vi` 这类
   一次性名。上游的 `lvai_generate_vi` 已经内置了这条（抛名转换 + `exec_state` 闸门 +
   `loadedSubVIs.resolvedAtConversion/executable` 字段）。

**对照我们的 Round6**：我们观测到"validate 拒本地 SubVI 属预期、convert 走 loadedSubVIs、
多 VI 稳定配方 = 子 VI `convert(openVI:true)` → 主 VI convert"。与上游完全一致，并且上游补上了
两个我们没测的边界：**松散打开（无项目）也行**，以及**上下文必须匹配**——项目开着就把目标
`through project` 打开，没项目就 loose 打开；开错上下文照样 53（上游同日 A/B 对照）。

> 【新铁律】开目标的上下文 = 调用方将被生成的上下文；探针永不用真名。

### 1.2 类方法调用自己的访问器：不需要 stub——Round6 遗留问题的答案【上游】

`aixml-call-loaded-vi.md` §8 曾把"同一类的方法调用自己的访问器"列为未测；2026-09-25 的
`cold-build-sensor-monitor-events.md` §2 给出了首测可行路线（"needs no stub - measured,
first time"）：

1. 通过项目**打开该类的一个访问器**（一个就够，见 1.1）；
2. 用 **`path` 替身**写该 override 的类端子，直接 `Call`
   `Simulated Sensor.lvclass\3ARead Current.vi` 等；
3. `lvai_generate_vi` 到成员的最终路径——validate 拒绝（Unsupported SubVI）、convert 全部解析、
   **`failedAtStep: execState` 是预期的**（path 替身喂给类输入），文件仍然写出；
4. `lvai_add_class_method` 拿**这个已存在的 vi**做重定型 + 动态分派 + 成员归属：
   `ok: true`、`terminalsRetyped: 2`，之后 `execState 1`。

唯一的手工步骤（上游同日修了工具）：第 3 步时项目开着，LabVIEW 会把新 VI 记成 loose 项目项，
随后 `lvai_add_class_method` 报 **56002**（项目里已存在同路径项）；关项目、手删 `.lvproj` 里那行
`<Item>` 即可。修复后工具会自己 `dropLooseProjectEntries`。

**对我们的意义**：Round6 我们用的是"子 VI convert → 主 VI convert → pylabview 运行"，
这条 1.2 路线是**同一目标的更少活动件版本**（没有 retarget、没有换名、没有运行期链接悬空），
而且它当场解决了 Round6 的 retarget 运行不过问题（被指向 VI 的内部 Name 必须等于调用方链接名）。
下轮 P6 就用我们自己的类 fixture 复跑这条。

### 1.3 两个工件之间的链接，读任何一个都验不出来——Round7 竞态的同一定律【上游 × 实测】

上游的接口方法实验（`lvclass-interfaces.md` §3，2026-08-31 冷重建）记录了一个和我们 Round7
一模一样的失败形态：

- 症状链：全部 VI 能加载、能导出正确图、所有工具读回正常 → **但整个类不编译**
  （`Error 1003`，且**库里所有成员都被拖死**，包括健康的向导访问器）；`{LV.SubVI}` `Replace`
  对脚本化成员报 `Error 1154`。
- 文件级证据全部"通过"：`pylv_extract` 看不出任何异常；**连"缺 `LIvi` 块"都是相关性不是病因**
  ——修好之后的 override 提取出来同样缺 `LIvi`、同样有 `LIfp ... exceeds limit` 警告。
- 真正的病因只有 LabVIEW IDE 说得出：`"X.vi" is at the expected path but is not part of
  "Y.lvclass"`，错误列表写 **`Owning library has blocked execution of the VI`**——成员链接
  只写了**一边**（库里有条目，VI 文件里没有 owning-library 记录）。
- 修复 = **双保存 + 正确顺序**：

  ```
  1. {LV.LVClassLibrary} AddItemFromMemory   （先让它成为成员，内存中）
  2. {LV.VI}            Save.Instrument      （此时 VI 才带上 owning-library 记录落盘）
  3. {LV.LVClassLibrary} Save                （再写库这一侧）
  ```

  顺序反了（先 Save.Instrument 再 AddItemFromMemory）就写出上述"一边链接"，且**反序恰好是
  原始文档写的规则**——它防的是小失败，制造了大失败。

同类细节还有三条，直接补进我们的操作清单：

- `AddItemFromMemory` 收的是**字符串 = VI 在内存中的裸名**；接 refnum 会在校验期报类型不匹配，
  接完整路径运行期报 `Error 1004`。
- `{LV.Control}` `Replace` **在 addon 自己的应用实例里是静默 no-op**（报 `terminals retyped: 2`、
  error 全 0，实际什么都没改）；必须落在 IDE 的实例里。
- `Save.Instrument` **单独不持久化类成员上的 `Replace`**——同一次运行里必须再 `{LV.LVClassLibrary} Save`。

**对照我们 Round7**：我们的 `lvai_bind_pane_typedef` 竞态是"改内存 → 保存"两条支路无数据流边，
工具报全成功、文件里 0 个 typedef；上游是"成员链接只写一边"，工具报全成功、库锁死。
**同一个定律的两种面孔：artifact-to-artifact 的链接，读其中任何一个都验不出来；只有
"运行"或"脱离 LabVIEW 读被链接的那个文件"能验。**

> 【新铁律】凡建立或修改跨工件链接（类成员、typedef 绑定、subVI 调用、项目项）：
> 双端保存 + 正确顺序；判据用运行或独立读盘，绝不用内存读回。

### 1.4 测试层：静态子 VI 调用是唯一推荐路线，负对照是强制项【上游】

我们此前 7 轮完全没有覆盖测试层，而这是"复杂程序"从"能跑"到"可交付"的分界。上游
`labview-unit-testing.md` 的 0 号规则写得很硬：

> **测试永远把被测对象当普通子 VI 静态调用，类代码也不例外。VI Server 路线是 fallback，
> 且必须说明为什么用不了静态路线。**

三代路线的演进（全部实测）：

| 代 | 做法 | 代价 |
|---|---|---|
| ① VI Server（§3c） | `Open VI Reference → Ctrl Val.Set → Run VI → Ctrl Val.Get` | 每个用例 3 个 Invoke Node + 2 根线；断言比较**格式化字符串**；改名/移目录**运行期**才炸 |
| ② socket + `{LV.SubVI}` `Replace`（§3d） | 按访问器 pane 写 socket（类端子→`path`，数据端子→`variant`），生成测试后换节点、最后换类常量 | 每字段两套 socket + 两次节点替换；`SubVIs[]` 每次 Replace 后重排；节点引用 Replace 后即失效 |
| ③ 直接 Call（2026-09-25 起） | 开一个成员 → 直接 `Call Class.lvclass\3AWrite X.vi` → 生成 → 关项目 | 只省活动件，**不更快**（单字段 18.0 s vs socket 路线 11.9 s + 7.4 s 开项目）；多字段才摊薄 |

必须记住的硬事实（每条都由一次失败换来）：

- **Caraya 的 target 拼写**（`vi.lib\addons\_JKI Toolkits` 里的 `.mnu` 不在调色板索引范围内，
  `lvai_palette_index` 查不到 Caraya **不代表不能用**；可靠拼写来自回导 NI 自带示例
  `Caraya\examples\tests\Test Addition.vi`）：
  `Caraya.lvlib\3ATest.lvclass\3ADefine Test.vi`、
  `Caraya.lvlib\3AAssert.lvclass\3AAssert Equal Value_Variant.vi`、
  `Caraya.lvlib\3ARun Tests.vi`（instance `...\3ARun Test (Scalar Path).vi`，`adapt="true"`）。
- **报告格式由扩展名决定，`.txt` 什么都不写**（掉进 `Default` 分支，`Create DefaultReport.vi`，
  实测两次无文件）；**用 `.xml`**（JUnit），且只有它带**每一条**断言。
- **`7002` 是"套件失败"的判据不是故障**；全绿返回 `errorCode 0`。
- **重建后第一次跑必报 `Error 1`、不写报告**（Caraya 测试管理器持有旧 VI 副本的用户事件，
  来自 `Generate User Event`）。跑第二次即绿——CI 里"重建后只跑一次"会得到假失败。
- **断言是精确相等**（`Assert Equal Value_Variant`），浮点要挑 IEEE754 下精确的用例
  （100/0/-40 经 `C*1.8+32` 精确）。
- **负对照强制**：故意写一条错期望，必须 `FAIL`；"首跑全绿"本身不构成证据。
  （我们 Round7 的教训在测试层的镜像：工具报成功 ≠ 真成功。）
- **测试与被测对象要放在同一目录**：placeholder 路线的 pylabview retarget 跨目录会写出
  LabVIEW 跟不上的链接（`failedAtStep: retarget`、`Missing subVI`）；直接 Call 路线可以跨目录。
- **`Call` 的 `inputs` 只能用连接板上的端子**（2026-10-12 起强制）：面板上但不在 pane 上的对象
  （例如事件结构帧里的锁存按钮）会让生成器报 `Error 1`，且**报错不点名是哪个端子**；拒绝时
  回答带 `refusal.notOnPane / wrongDirection / unknown` + 实际 pane 列表。

> 【新铁律】测试 = 静态调用 + `.xml` 报告 + 负对照 + 重建后跑两次。

### 1.5 经济学：延迟占 3.6～9.7 : 1，轮次是唯一指标【上游】

上游对 2 641 次工具调用 / 2 549 个模型轮次（6 个会话）的统计：

| 项 | 数值 |
|---|---|
| 模型延迟合计 | **12.90 h** |
| 工具内耗时合计 | 3.63 h |
| 比值 | **3.6 : 1**（单个复杂构建会话可达 9.7 : 1） |
| 每轮中位延迟 | **7.1 s** |
| `lvai_validate_aixml` | 0.08 s |

推论（与我们 `06-best-practices` §5.3 一致，但有了大样本）：

1. **省一次往返 = 省 7 s；省 1 ms 的服务端查找 = 0**。不要优化工具速度。
2. **不要 fan-out 提吞吐**：六个 generate 并发 559 ms vs 串行 543 ms——LabVIEW 串行。
   但**批量提交往返**仍然值得（六个 `lvai_swap_subvis` 放一条消息里，6 轮变 1 轮）。
3. **不要"保险起见重启"**：`lvai_ensure_labview` 中位 30.75 s，某会话调了 48 次 = 25 分钟；
   那次真正的原因是泄漏的类 refnum（一行修复）。
4. **一次超时 ≠ 失败**：客户端放弃后，工作**仍在 LabVIEW 里继续**（随后 `describe_class`
   看到成员数继续增长）；此时紧接着的调用可能返回 `ok:false, classIndex:-1` + 满屏
   `DeadlineExceeded`，那是**假警报**。先看文件和进程。
5. **欠定的提示词用探索轮次付费**：同一任务，定了数据模型并明说"不要改进它"的一轮用了
   10 次调用，没定的一轮用了 34 次。**写需求时把数据模型钉死，比任何工具优化都省。**

---

## 2. "五道闸门"模型：复杂程序的可执行验收路径【经验，本轮归纳】

把 7 轮实测 + 上游一手测量压成五个必须依次通过的闸门。每个闸门都有**明确的判据**和
**失败长什么样**，避免"工具说 ok 就 ok"。

| 闸门 | 判据 | 手段 | 失败长什么样 | 依据 |
|---|---|---|---|---|
| **G1 需求定稿** | 数据模型、端子表、验收用例全部写死，不允许 AI 自行改进 | 提示词模板（`06` §5.1） | 轮次暴涨、反复重构 | 上游 §1.5-5 |
| **G2 分层生成** | 叶子 VI（纯计算）→ 类/接口（字段+访问器+方法）→ 编排 VI（状态机/多 VI） | `lvai_generate_vi` / `lvai_add_class_method` / 我们 Round6 的状态机生成器 | 一次生成一个巨型 VI | Round6、上游 §1.2 |
| **G3 结构验证** | `validate`（仅对自包含有效）→ `convert` → `exec_state=1` → 回导与原稿逐网比对 | `lvai_generate_vi` 自带闸门 + `lvai_convert_vis_to_aixml` | validate 拒绝但 convert 成功（=本地调用，正常） | Round5 回导 100% 保真 |
| **G4 文件级验证** | 脱离 LabVIEW 读盘：typedef 描述符数、`udClassDDO` 数、`.ctl` 引用、链接路径、`stdPath` 残留 | `pylv_extract` + grep（`*_FPHb.xml`） | 工具报成功、文件里什么都没有 | Round7、上游 §1.3 |
| **G5 运行验证** | 实跑数值 + Caraya 套件（含负对照）+ **冷启动复核**（新 LabVIEW 从磁盘打开仍 `execState 1`） | `lvai_run_vi_and_read_values`、`lvai_generate_caraya_test_runner` | 内存正确、磁盘错误；首跑绿但没测到东西 | 上游 §1.4、§1.1 |

三条与闸门配套的操作纪律：

1. **G3 的"validate 拒绝"不是失败信号**——只要拒绝理由**全是** `Unsupported SubVI:` 行，
   就走 convert；出现别的行（类型文法拒绝 `.ctl`、端子名拼错 `Error 1`）才是真失败。
2. **G4 必须做，且必须在 G5 之前**：Round7 的竞态、上游的"一边链接"都是 G4 才能抓到的；
   反过来 G4 也不能替代 G5（接口方法那个案例里，所有文件都自洽）。
3. **G5 的冷启动复核**是最便宜也最容易被跳过的一步：关掉 LabVIEW、重开、从磁盘打开
   产物看 `execState`。上游用它证明了"链接写进文件而不是借内存"。

---

## 3. 交叉印证表（本轮新增 6 行）

| 我们的结论（轮次） | 上游对应一手测量 | 关系 |
|---|---|---|
| R6：validate 拒本地 SubVI 属预期；convert 走 `loadedSubVIs`；子 VI 先 `openVI:true` 再生成主 VI | `aixml-call-loaded-vi.md` 四臂实验 + `lvai_generate_vi` 三步（抛名 convert + exec_state 闸门） | **同结论**。上游补：松散打开也行；**上下文必须与生成时一致**；**失败烧名** |
| R6：retarget 运行不过，根因是内部 Name ≠ 调用方链接名 | `cold-build-sensor-monitor-events.md` §2：类方法自调访问器**根本不需要 retarget** | **替代路线**。P6 复跑 |
| R7：bind_pane_typedef 保存链竞态，工具全绿、文件 0 typedef | `lvclass-interfaces.md` §3：成员链接只写一边，工具全绿、库锁死 | **同一定律的另一面**（§1.3） |
| R4：Case 输出隧道 `cond="true"` | `FINDINGS` §4d：selTun 位 0x300000 | 已印证（doc16） |
| R5：布局/引用走 `pylv_apply`；`placeLabels` 可靠 | `class-method-tooling.md` §1c/1d：`Replace` 在 addon 实例里是 no-op；`Save.Instrument` 单独不持久化 | **新增限制**：pylv 之外还有"实例归属"这一层 |
| 本轮：五道闸门 | `workflow-economics.md` + 三个 cold-build 案例（15:35 出可执行、22:24 套件全绿，零 stub，四 agent 三波） | 上游用"四 agent 三波 + 零 stub + 全套件绿"作为复杂程序交付的样板 |

---

## 4. 新增铁律（已同步进 `06-best-practices.md` §11）

1. **探针永不用真实文件名**——一次失败的 convert 会烧掉该名（`Error 1051`），只有重启能清。
2. **开目标的上下文 = 调用方将被生成的上下文**；项目开着就 through project，无项目就 loose。
   开一个类成员即可让整类可解析。
3. **跨工件链接要双端保存且顺序正确**（成员先入内存 → VI `Save.Instrument` → 库 `Save`）；
   读任一文件都验不出来，只能用运行或独立读被链接文件。
4. **测试 = 静态子 VI 调用 + `.xml` 报告 + 负对照 + 重建后跑两次**。
5. **`Call` 的 `inputs` 只能出现连接板（pane）上的端子**，面板上有但不在 pane 上的对象会被拒，
   且报错不点名（用 `refusal.notOnPane` 看）。
6. **轮次优先**：批量提交往返、不 fan-out 提吞吐、不"保险起见重启"；欠定需求=用轮次付费。

---

## 5. 能力边界：哪些能生成、哪些只能半生成、哪些只能读【上游 + 经验】

| 对象 | 判定 | 依据 |
|---|---|---|
| 叶子 VI（纯计算、自包含节点） | **可生成 + 可测试** | Round2/3、上游 cold-build 系列 |
| 状态机（枚举 selector、多帧 Case） | **可生成**（模板化） | Round4、我们 `gen_statemachine.py` |
| 类（字段 + 访问器 + 静态/动态方法） | **可生成**（`lvai_create_class` + `lvai_create_accessors` + `lvai_add_class_method`）；字段默认值需 `<type>.<name>=<value>` | 上游 §1.2，`cold-build-*` |
| 接口（无私有数据）+ 实现类的 override | **可生成**（`lvai_create_interface`；父接口**只能在创建时**指定，事后加要走模态对话框 → 不可脚本化） | `lvclass-interfaces.md` §2 |
| 多 VI 调用 / 类方法自调访问器 | **可生成**（1.1 + 1.2 路线） | 上游 §1.1/1.2 |
| 事件结构 + 用户事件（自建） | **可生成**（pylabview 一次成型；9 条写法见 doc16 §3.2） | doc16 |
| 单元测试（Caraya） | **可生成**（三代路线，推荐直接 Call） | 上游 §1.4 |
| DQMH 完整模块 | **不可生成**（NI not-yet-supported 明确点名；`UDClassInst` 类型文法无法表达；scripting VI 密码保护 5002） | `dqmh-patterns.md` §5 |
| DQMH 单个 request VI | **半生成**（只差两个库限定 SubVI 解析目标） | 同上 §5 |
| Malleable VI（`.vim`） | **不能凭空创建**，但有实测路线（标志位分段 + Type Specialization Structure 可写） | `malleable-vis.md` §2-§4 |
| Actor Framework 模块 | **未测**（上游 v2.1.2 并入 Jørgen Steen 的 AF 改动，需升级后验） | release notes |

**判断原则**：只要目标 VI 的**连接板出现类对象（`UDClassInst`）**，AIXML 就表达不了，
必须走"path/簇替身 + `{LV.Control}` Replace + 双保存"这条带副作用的路；只要绑定的是
**库限定 SubVI**，就必须先让目标"已加载"（1.1）。其余一律走自包含生成。

---

## 6. 下轮探针（离线已备，LabVIEW 在线即跑）【待验证】

放在 `research/artifacts/round8/probe-recipes.md`。四个探针都针对本轮新事实，且都能用我们
自己的 Round6/7 fixture 改造：

| 探针 | 测什么 | 判据 |
|---|---|---|
| P6 类方法自调访问器 | 1.2 四步在**我们自己的类**上成立与否；`failedAtStep: execState` 是否仍写出文件；56002 是否复现 | `add_class_method ok` + `execState 1` + 文件里 `udClassDDO` 计数正确 |
| P7 接口 override 保存顺序 A/B | 错序（VI 先存）vs 正序（成员先入内存）对整库可执行性的影响 | 错序应得 `Error 1003` / `Replace 1154`；正序应全绿 |
| P8 Caraya 最小套件 | 直接 Call 路线 + `.xml` 报告 + 一条故意错期望 | 报告 `failures="1"`，负对照 FAIL，其余 PASS |
| P9 冷启动复核 | 关 LabVIEW → 重开 → 从磁盘打开产物 | `execState 1` 且数值正确 |

前置动作（下轮第一件事）：**升级到 ≥ v2.2.0**（v2.1.8 的 control references、v2.2.0 的
Network Streams/XControls 都只在更新版本里有），升级后先 `lvai_dump_schema` 核对 RPC 变化，
再跑 P1–P9。

---

## 7. 本轮结论与方向记录

1. **能交付"复杂程序"的完整链路已经存在**，但它的正确顺序不是"生成 → 跑"，而是
   **五道闸门**：需求定稿 → 分层生成 → 结构验证 → 文件级验证 → 运行（含冷启动）验证。
   我们前 7 轮分别在补其中几道闸，本轮把它们串成了流程。
2. **两条最重要的新事实**：① 目标"已加载"即可 `Call`，开一个类成员即可解整类（但上下文必须
   一致、探针不能用真名）；② 跨工件链接读单个文件验不出来，必须双保存 + 运行验证。
   后者与我们 Round7 的竞态是同一定律。
3. **测试层从零到有**：静态调用 + `.xml` + 负对照 + 跑两次，四条都是硬规则；Caraya 的
   target 拼写与"重建后首跑假失败"是最容易浪费半天的两个坑。
4. **经济学结论要落到工作方式上**：轮次是唯一指标；批量提交；不重启；需求钉死数据模型。
5. **下轮方向（优先级）**：① 升级 v2.2.0 + `dump_schema`；② 跑 P1–P5（事件结构）与 P6–P9
   （类方法/接口/测试/冷启动）；③ 若 P6/P7 通过，把"类方法 + typedef + 测试"固化成我们自己的
   端到端生成脚本（对标上游四 agent 三波）；④ DQMH 消费侧最小闭环（mock 模块）。
6. **本轮无新实测**，所有【上游】条目在正文里都带日期与文档名，便于复核；不把上游测量
   当作我们的实测（`06-best-practices` 的标注惯例继续有效）。
