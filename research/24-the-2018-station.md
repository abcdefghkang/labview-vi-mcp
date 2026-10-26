# Round 15 —— 2018 工位：没有 Nigel 的一天，与一条被推翻的版本警告

> 本篇为 Round15 的完整记录。结论先进：**本机 LabVIEW 换成了 2018（32 位，用户今早 10:00 启动），
> NI 的 gRPC 服务起不来（2018 没有 Nigel），但整条"AIXML → VI → 运行"管线在 pylabview 路线上
> 照常工作，且 composer 写出的 2026 戳 VI 被 2018 打开并正确执行**——服务器自己的
> versionWarning（"2018 refuses Error 1125"）在本机被实测推翻。以此为基础，LVOOP 全链
> （动态方法 + 静态成员 + 类常量 + 调用方）在 2018 上端到端跑通，并由此钉死了 P15
> （运行时动态派发观测）的边界：**绑定发生在编辑期，沿着数据流溯源，静态"类型洗涤器"也拦不住**。

---

## 1. 环境：这一轮是在一台"没有 Nigel"的工位上做的

| 事实 | 证据 |
|---|---|
| 运行中的 LabVIEW 是 **2018 32 位**（`C:\Program Files (x86)\...\LabVIEW 2018\LabVIEW.exe`，PID 1284，今日 10:00:58 启动） | `Get-Process LabVIEW` |
| 2026 仍装着（`C:\Program Files\National Instruments\LabVIEW 2026`），另装有 2015–2025 | 目录列举 |
| **gRPC 服务（lvai.LVAI）不在**：43→44 个候选端口全失败；两个 LabVIEW.exe listener（3364/14438）答 `Unavailable` | `lvai_status`、两次 `lvai_ensure_labview`（各 25 s / 40 s）均回 `state:"starting"` |
| 服务随 **Nigel** 启动，2018 没有 Nigel → 本会话 grpc 路线全灭 | 上游 `docs/aixml-backends.md` + 实测 |
| MCP server 2.0.1 在线，两个 `LabVIEWMCP.exe` 进程（15:03 一个残留、15:12 本会话） | 进程列举 |
| `~/.workbuddy/mcp.json` 里两个 server 的 `disabled:true` 已消失（用户已重新打开 `labview` 开关；`labview-cli` 死条目仍在） | 文件读取 |
| pylabview 包健康（v2.0.1, 77eb0b22, python 3.12 x64），**serverDefault=pylabview**，理由 "LabVIEW 2018 is older than 2026" | `pylv_status` |
| Round14 的 `resolve.py` 补丁**仍在**（两个 base 取版本号最大者） | 源码核对 |

**没有 LabVIEW 2026 在场这一事实，本身成了本轮最大的实验变量。**

---

## 2. 主结果：composer 写的 2026 戳 VI，2018 打开并运行了

### 2.1 三段实测

用 round14 的 `sensor-scale-by.aixml.xml`（已知良好）与 round13 的 `conidx-probe-b.aixml.xml`（`y = x * factor`）走
`lvai_convert_aixml_to_vi(backend:"pylabview")`：

| 探针 | compose | 运行（backend pylabview） | 结果 |
|---|---|---|---|
| Scale By（直通） | 749 ms，4533 B，`execState 1` | `ran:true finished:true runMs:5` | `obj out=""`（直通正确） |
| y=x·factor | 533 ms，4447 B，`execState 1` | `ran:true finished:true runMs:4` | **x=6, factor=7 → y = 42.00000000000000** |
| 同上，负对照 | — | `ok:false errorKind:"unknownControl"` | `'nonexistent control' is not a control on this VI's panel, so nothing ran.`（并列出面板真实端子 `x, factor`） |

composer 复制的字节数与 round13 grpc 路线**逐字节相同**（4447 B）——两条 composer 对同一份 AIXML 的产物尺寸一致。

### 2.2 服务器自己的警告说这会失败——它错了

每次 convert 都附带：

> `versionWarning`: "LabVIEW 2018 is in use and the composer writes files for LabVIEW 2020 and
> later only, so this VI carries the LabVIEW 2026 stamp, which LabVIEW 2018 refuses (Error 1125).
> Compose it with backend grpc on that station."

而文件头里确实躺着 2026 戳（`LBVW` 记录内 `26 00 80 00`，见 §7.1 的字节解剖）。**实测：2018 不仅打开了，
还跑了，还算对了。** 该警告是静态版本比较的产物，没有在本机测量过；本机的 2018 对 2026 戳文件
在 VI Server/ActiveX 通道上并不拒开。

> 边界备注：以上都是**自动化通道**（VI Server 引用打开）。IDE 里 File>Open 手动打开一个更新版本
> 文件仍可能弹版本对话框——本机没有、也无法无人值守地测 GUI 路径。写进能力地图时按"自动化通道可用"记。

### 2.3 为什么 execState 会先回来

convert 的 `execState:1 / executable:true` 与运行成功是两回事：前者在本机由 ActiveX 通道读出
（`via:"ActiveX", route:"helper"`——助手 VI 也是现场 compose 进 `%TEMP%\LabVIEWMCP\helpers-pylabview`
再跑）。真正说明问题的是运行：**面板名从文件读、输入写进去、图跑完、值读回来**，负对照证明这条
路真的碰到了面板。

---

## 3. 没有 gRPC 的工具面真相（本机实测）

| 工具 | pylabview 路线 | 本回合实测 |
|---|---|---|
| `lvai_convert_aixml_to_vi` | ✅ compose 纯 Python | 多次，全成 |
| `lvai_generate_vi` | ✅ validate 跳过，改读 execState 守门 | 5 次（含预期失败 2 次） |
| `lvai_exec_state` | ✅ 助手 compose+ActiveX | 6 次，全 1，linkerErrors 可读 |
| `lvai_run_vi_and_read_values` | ✅ ActiveX 直跑，无助手 VI | 5 次 |
| `lvai_swap_subvis`（含 constantsJson） | ✅ 助手 compose+ActiveX | 4 次 |
| `lvai_add_class_method` | ✅ 转换纯 Python + retype 走 ActiveX | 3 次 |
| `lvai_open_file` | ⚠️ **只能开项目**（"a VI is refused"） | 未直接调（类工具自己 Sequencing） |
| `lvai_convert_vi_to_aixml` | ✅ 自带 reader（vi2aixml.py） | 3 次 |
| `lvai_status` / `lvai_ensure_labview` / `lvai_dump_schema` 等一切 grpc 工具 | ❌ 服务不在 | 确认失败 |

**结论：一台只有 2018 的工位，仍然拥有完整的"写侧 + 读侧 + 运行侧"。** 这对能力地图是实质性
升级：此前"运行验证"记在"有条件"层，前提是 2026 在线；现在 2018 也行（自动化通道）。

---

## 4. LVOOP 全链在 2018 上端到端跑通（P15 的半场）

在 round14 类树的**副本**（`research/artifacts/round15/p15/`，副本自包含：拷贝后
`Sensor/Scale By.vi` 独立 `execState 1`，类链接是相对的）上新增三个成员：

| 成员 | 类型 | 做法 | 磁盘验证 |
|---|---|---|---|
| `Sensor:Tag` | **动态**方法，返回 `"Sensor"` | path 替身 AIXML → `generate_vi` → `add_class_method(classTerminals:["obj in"], dispatchTerminals:["obj in"])` | `classTypedTerminals:1, pathStandInsLeft:0, listedInClassFile:true` |
| `Temp Sensor:Tag` | **动态**覆盖，返回 `"Temp Sensor"` | 同上，`classTerminals` 用对象形式指向 `Temp Sensor.lvclass` | 同上 |
| `Sensor:Carrier` | **静态**直通（obj in→obj out） | 同上，**不给 dispatchTerminals** | `dynamicDispatchTerminals:[]`，两端子类类型化 |

调用方三连（同一份 AIXML 的迭代，均 `generate_vi(backend:pylabview)` 写出、`execState 0` 是预期
中间态——path 常量喂类端子）：

1. **v1**：`seed`（path 常量）→ `Call Sensor.lvclass:Tag.vi` → `answer`。
   `swap_subvis constantsJson=[{label:"seed",class:"...\\Temp Sensor.lvclass"}]` 后：
   `constantsSwapped:1`，**运行 → `answer="Temp Sensor"`**。负对照（常量换 `Sensor.lvclass`）→ `"Sensor"`。
   类常量在导出里现形：`<Constant _name="seed" type="ref{UDClassInst}" .../>`。
2. **v2**（类型洗涤企图一）：`seed → Sensor:Scale By（obj out 是 Sensor 类型动态端子）→ Sensor:Tag`。
   常量一换，**两个 Call 全部重定界**到 Temp Sensor 作用域（含没有覆盖的 Scale By——链接改名为
   `Temp Sensor.lvclass:Scale By.vi`，指向继承成员）。
3. **v3**（类型洗涤企图二）：`seed → Sensor:Carrier（静态）→ Sensor:Tag`。
   Carrier 的调用**锚在 Sensor 没动**（静态调用无可重解析），但 Tag 调用**照样重定界**到
   `Temp Sensor.lvclass:Tag.vi`。运行 → `"Temp Sensor"`。

### 4.1 重定界规则（本回合最重要的单条发现）

> **一个类常量换入动态派发调用的上游，LabVIEW 就把该调用重链到常量所属类的最派生实现——
> 沿数据流溯源、穿越成员边界、与声明线类型无关。**

v3 是钉死"与声明线类型无关"的那一环：`Carrier.vi` 的二进制里**只有 `Sensor.lvclass`**
（6 处引用，无 `Temp Sensor`，见 §7.2），obj out 确实是 Sensor 类型；Tag 的输入线因此是
Sensor 类型；**它仍然被重定界了**。另两个佐证：v1 中把 Call 节点用 `swapsJson` 换回
`Sensor:Tag.vi`（`nodesSwapped:1`），保存后的文件链接仍指向 `Temp Sensor:Tag.vi`；
v2 中无覆盖的 Scale By 也被改名为 Temp Sensor 作用域。

### 4.2 P15 结论：运行时派发在本管线里**观测不到**

- 类值的唯一可 author 来源就是**类常量**（AIXML 写不出类类型端子：`Control with type=UDClassInst
  is not supported`；类说明符常量也没有 AIXML 语法，所以 `To More Generic Class` 喂不了
  `target class`）。
- 而常量喂进来的动态调用，绑定在**编辑期**就完成了（§4.1）。
- 要观测运行时派发，需要"父类型线 + 子类型值"——值只能来自运行期设定的父类型窗格端子，
  而 run 工具的输入只能是字面量（`"3.5"`, `"[1,2,3]"`），**类实例没有字面量**。
- 剩下的路：IDE 手搭调用方；或把方法图 graft 到已有父类型端子的面板上（graft 在 pylabview 上
  可用，round12 验过）——但 graft 进来的图仍然只能拿常量当类值源，同样过不了 §4.1。
  **P15 状态：边界已钉死，记为"表达不出来"，留待 v2.2.0 或手搭。**

---

## 5. 其他实测细节

### 5.1 编辑器行为

- `lvai_generate_vi` 的 repair 步把输出的 `connection="required"` 自动改成 `recommended`
  （`outputTerminalIsRequired`），并提示回写 AIXML 源——本轮 6 份新 AIXML 已按修正后的形态存档。
- 连接器窗格：方法源 `obj in=0 / tag=1` 被判 1 条 warning（tag 落在中间列，建议 conIdx 4）；
  `add_class_method` 随后把 pane 从 4833 改到 4815（12 槽），**conIdx 不变、调用方无需改**。
- `projectBecomeActive` 每次都为 true——round14 记忆里"前台焦点导致 1055"的坑本轮一次都没踩
  （助手自己 `Project.Open plus its window`）。
- 类操作的经济学：`add_class_method` 20–50 s/次（conpane+retype+verify+cleanup 全算上），
  `generate_vi` 带 cleanup 54 s、不带 13 s；compose 0.5–1.5 s；swap 2–5 s；run 5–18 ms；
  `exec_state` 约 2.6 s。**结论同 round8：批量化、别 fan-out、类改动逐个来。**

### 5.2 读侧

- reader 导出类常量为 `type="ref{UDClassInst}"` 但**不解码其值**：
  `<!-- vi2aixml: constant 71: value of type Refnum.UDClassInst not decoded -->`。
  类成员的导出同样只有类型没有类身份（`the class identity is not encoded`）——**读侧对
  "哪个类"是盲的，类身份只能从二进制里的类名/链接字节读**（§7.2 就是这么做的）。
- VITS 块的 `LVVariant has ver set to size=0x000015` / `size is 53 and does not match parsed
  size 32` 两条 raw fallback warning 每步都出现，无害（原样拷贝，往返才因此无损）。
- 图面渲染时好时坏：Carrier 渲染出 205×19，两个 Tag 方法 `could not be rendered`。

### 5.3 门禁：LV016（误报修复 + 负对照）

类限定目标 `Sensor.lvclass\3ATag.vi` 含 `\3A`（转义冒号），被 LV006 当成路径误报。
修法：**先剥掉所有 `\XX` 十六进制转义再判断路径性**。负对照：真路径 `C:\cls\X.vi` 仍然报警；
`..\lib\X.vi` 也报（`\l` 不是转义）。已写进 `tools/lvrule_check.py` 头部与规则体。

新 AIXML 全部过闸：6 份 0 error（2 条 warning 是方法不读 obj in 的 `net-unconsumed`，预期）。
`lvproj_audit.py` 对 p15 工程：0E/0W，3 条 info（三个探针未列入工程，scratch 应有样子）。

---

## 6. 可复用配方（写进 best-practices §17）

**2018 工位（或任何 <2026 工位）的标准环**：

1. `convert_aixml_to_vi(backend:"pylabview")` —— 不需要任何 NI 服务；忽略 versionWarning。
2. `exec_state(backend:"pylabview")` / `run_vi_and_read_values(backend:"pylabview")` 验证。
3. 类成员：`generate_vi` → `add_class_method(backend:"pylabview", projectPath:...)`。
4. 类调用方：AIXML 里用 path 常量替身 → `generate_vi`（预期 `failedAtStep:"convert"`/
   `execState 0`）→ `swap_subvis(backend:"pylabview", constantsJson:[{label,class}])` → 跑。
5. 预期：调用目标随常量类重定界（§4.1）——这是特性不是 bug：产物对种子类是正确的。
6. 每次生成前 `python tools/audit_aixml.py --summary <file>`；工程用 `lvproj_audit.py`。

---

## 7. 附录：字节级证据

### 7.1 2026 戳确实在文件里

```
$ python -c "data=open('probe-scale-by.vi','rb').read(); print(data[:64])"
b'RSRC\r\n\x00\x03LVINLBVW\x00\x00\x0eT\x00\x00\x03a\x00\x00\x00 \x00\x00\x0e4\x00\x00\x00\xa0&\x00\x80...'
```

偏移 36 起：`26 00 80 00` = 26.0.128.0 = LabVIEW 2026。全文件搜 `1a 00 80 00`(26)、
`19 00 80 00`(25)、`12 00 80 00`(18) 四个版本字：只有头部 LBVW 里这一个（展平 variant 的
版本字不在，因为本 VI 没有 variant 常量）。

### 7.2 Carrier 的 obj out 是 Sensor 类型（重定界与线类型无关的物证）

```
$ python -c "..."
Sensor.lvclass      -> [41, 307, 355, 439, 2079, 2171]   # 6 处
Temp Sensor.lvclass -> NOT FOUND
Can Scale.lvclass   -> NOT FOUND
```

### 7.3 导出快照（v1 探针，换常量后）

```xml
<VI _name="Dispatch Probe.vi" ...>
  <Indicator _name="answer" type="string" uid="4210" ... conIdx="0" connection="recommended" inputs="value:76.tag"/>
  <Constant _name="seed" type="ref{UDClassInst}" uid="71" ... outputs="value:71.value"/>
  <Call uid="76" target="Temp Sensor.lvclass:Tag.vi" inputs="obj in:71.value" outputs="tag:76.tag"/>
  <!-- vi2aixml: constant 71: value of type Refnum.UDClassInst not decoded -->
</VI>
```

完整原始输出见 `research/artifacts/round15/p15/out/`（两份导出）与 `scratch/`（两个 2018 运行探针）。

---

## 8. 留给下一轮

1. **用户很可能想用 2026**：本机 2026 装着。若下次 LabVIEW 2026 在跑，第一件事是
   `lvai_dump_schema` + 工具面与 round11 存档 diff，然后回到 round14 的优先级表。
2. **P15 的两条残路**：① IDE 手搭"父类型窗格端子"调用方（人做一次，AI 读）；② 上游若补了
   类说明符常量的 AIXML 语法，`To More Generic Class` 即可 author，洗涤器真正成立。
3. **`lvai_graft_diagram` 在 2018 上未测**（round12 只在 2026 上测过 pylabview graft）。
4. **`signalsJson` 在 pylabview 路线上仍被拒**（工具描述明说），P5 事件驱动探针依旧过不去。
5. Caraya 仍未装（VIPM 需用户联网点）——自包含测试范式（round13）继续顶替。
6. 版本警告本身值得给上游报一句：2018 在 VI Server 通道上并不拒开 2026 戳的 composer 产物，
   "LabVIEW 2018 refuses (Error 1125)" 这句在本机是错的；降级只支持到 2020 的限制仍然真实。
