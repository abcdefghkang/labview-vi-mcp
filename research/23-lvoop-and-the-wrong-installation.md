# Round 14：LVOOP 全链，以及一颗被装错的螺丝

> 起止：2026-10-23 18:1x–19:1x（在线轮 4）
> 环境：LabVIEW 2026 26.3.1f1 中文版（pid 22200）+ LabVIEW 2018 32-bit 并存；
> LabVIEWMCP **2.0.1**；gRPC 端口 14868。
> 起点：Round 13 收尾时整条测试链卡在 Caraya 没装。本轮换靶——**类与接口**，
> 冷构建语料里占 49% 成本、并且是"失败的那一半"。

---

## 0. 一句话

建成了一条完整的 LVOOP 链（接口 + 方法 + 实现类 + 子类 + 4 个访问器），
但它一开始**一步都动不了**，原因不在 LabVIEW，而在 MCP 自带的 pylabview 解析器
挑错了安装目录：这台机器上它认的是 **LabVIEW 2018**，不是正在运行的 2026。
改一行后全链通。随后在这条链上量到四条新事实，并落成两条闸门。

---

## 1. 根因：`labview_root()` 在双安装机器上选错

### 1.1 现象

三次调用，三种失败，全都指向同一个看不见的东西：

| 调用 | 后端 | 结果 |
|---|---|---|
| `lvai_create_interface(Can Scale)` | grpc | `helperAixmlInvalid` —— 本机老问题，中文版拒收自带 helper XML |
| 同上 | pylabview | `helperNotComposable`：**`Call 70: no Add Interface.lvlib in the installation or near the caller`** |
| `lvai_create_class(Sensor)`（未改之前未试，同因） | pylabview | 会撞 `no Add Class.lvlib`（同类库） |

"in the installation" 这句话是假的：库就在安装目录里。

```text
C:\Program Files\National Instruments\LabVIEW 2026\resource\Framework\Providers\AddInterface\Add Interface.lvlib
C:\Program Files\National Instruments\LabVIEW 2026\resource\Framework\Providers\AddClass\Add Class.lvlib
```

### 1.2 取证

解析器 `bin/scripts/aixml-pylabview/resolve.py` 的搜索根由 `labview_root()` 决定：

```python
for base in (r"C:\Program Files (x86)\National Instruments",
             r"C:\Program Files\National Instruments"):
    for d in sorted(glob.glob(os.path.join(base, "LabVIEW 20*")), reverse=True):
        if os.path.exists(os.path.join(d, "LabVIEW.exe")):
            return d          # <- 第一个命中就返回
```

`reverse=True` 只在**每个 base 内部**排序，而 x86 的 base 排在前面。
这台机器装了 LabVIEW 2018（32-bit，在 x86 下）和 2026（64-bit），于是：

```text
labview_root() -> C:\Program Files (x86)\National Instruments\LabVIEW 2018
roots[0]       -> ('<vilib>', '...\LabVIEW 2018\vi.lib')
```

而 2018 里：

```text
LabVIEW 2018\resource\Framework\Providers\   （有 LVClassLibrary、ActorMessageMaker …）
AddClass/        MISSING
AddInterface/    MISSING      <- 接口是 LabVIEW 2020 才有的东西
MessageMaker/    MISSING
```

所以"找不到 Add Interface.lvlib"完全成立——它在找的那个安装里从来没存在过。

### 1.3 为什么它到现在才暴露

`Resolver` 的搜索根覆盖 `vi.lib / user.lib / instr.lib / resource` 四类。
前十三轮生成的 VI 几乎只 Call **同目录**的子 VI（"near the caller" 分支命中），
唯一需要库解析的是 Round 13 的 Caraya，而 Caraya 是真没装。
本轮是第一次要靠 `resource\Framework\Providers` 里的库干活，一下就撞上。

### 1.4 修法（一行逻辑，三行注释）

```python
best, best_key = None, None
for base in (x86, x64):
    for d in glob.glob(os.path.join(base, "LabVIEW 20*")):
        if not os.path.exists(os.path.join(d, "LabVIEW.exe")):
            continue
        key = int("".join(c for c in os.path.basename(d) if c.isdigit()))
        if best_key is None or key > best_key:
            best, best_key = d, key
return best
```

保留 `LABVIEW_ROOT` 覆盖（原代码已有）。改完立刻生效：

```text
labview_root() -> C:\Program Files\National Instruments\LabVIEW 2026
Add Class.lvlib found:     ...\2026\resource\Framework\Providers\AddClass\Add Class.lvlib
Add Interface.lvlib found: ...\2026\resource\Framework\Providers\AddInterface\Add Interface.lvlib
```

**同一秒内重跑 `lvai_create_interface` 就成功了**——说明服务对 pylabview 脚本是
**每次现读磁盘**的，不是启动时导入。这条本身有用：改脚本不需要重启 MCP。

> 备份在 `bin/scripts/aixml-pylabview/resolve.py.orig-round14`。
> 正确修法应是"优先运行中的实例"，但拿不到它就跑不了；版本号取最大是保守近似，
> 双安装机器上唯一会错的场景是"跑 2018 而 2026 也在"，此时用 `LABVIEW_ROOT` 钉死。

---

## 2. 建成的链

全部走 `backend: "pylabview"`，顺序按上游要求"接口先完工，再建实现类"：

| # | 动作 | 读数 |
|---|---|---|
| 1 | `create_interface` **Can Scale** | `ok`, 1411 B, `isInterface: true`, provider 156 ms |
| 2 | `add_class_method` 接口方法 **Scale By** | `terminalsRetyped: 2`, `listedInClassFile: true`, `sourceOnly: true` |
| 3 | `create_class` **Sensor**（`string.Name=unset, double.Last Reading=0`，实现 Can Scale） | `fieldsAdded: 2`, privateData 6179 B, `interfacesLinked: 1`, `parent opened: false` |
| 4 | `add_class_method` Sensor **Scale By**（覆盖） | ok, `dynamicDispatchTerminals: [0,2]` |
| 5 | `create_class` **Temp Sensor**（父 Sensor，`double.Calibration Offset=0.5`） | `inheritsFrom: Sensor.lvclass`, `parent opened: **true**` |
| 6 | `create_accessors` Sensor，R/W，dynamic | 4 个 VI，members 1 → 5，全部 sourceOnly |

`parent opened` 这个布尔正好是父/无父的判别位（Sensor 无父为 `false`，
Temp Sensor 有父为 `true`）——比旧文档里的 `parent index` 好读。

### 2.1 接口方法读完是"真窗格"

```text
Can Scale.lvclass:Scale By.vi - 2 input terminal(s), 1 output terminal(s) on the connector pane.
  obj in   [ref{UDClassInst}] conIdx 0, dynamic
  Factor   [double]            conIdx 1, required
  obj out  [ref{UDClassInst}] conIdx 2, dynamic
```

对照 Round 13：**前十二轮所有 AIXML 直出的 VI 都不在这张表里**（全库 383 个端子只有
9.9% 带 conIdx）。方法走 `add_class_method` 出来的就有窗格，因为它的 conpane 步骤真的
在编辑窗格——但**前提仍然是源文件写了 conIdx**（见 §3）。

`exec_state` 对 `Sensor/Scale By.vi` 回答 `1`（eIdle，可执行）。

---

## 3. A/B：`panePattern 4815` 救不了缺 conIdx 的端子

上游说 `add_class_method` 会先"盖"窗格图案 4815（"ConvertAIXMLToVI takes no pattern,
so a new VI otherwise carries the station default"）。听起来像"没写 conIdx 也会被分配槽位"。
同一份 AIXML 形状、同一轮调用里，只改一件事：

| 方法 | conIdx | conpane 步骤 |
|---|---|---|
| `Sensor/Scale By.vi` | 0 / 1 / 2 | ok：`pattern 4833 -> 4815, 12 slots, no conIdx changed - no caller has to be touched` |
| `Sensor/Reset.vi` | **无** | **失败**：`no <cons> array in the front-panel heap` |

**这是 Round 10 那个悬案的答案。** 当时记的是"LV2026 FPHb 的 `cons` 数组为空，
NI 官方示例同样，规避=生成时写 `connection="recommended"`"，并留了一句
"是 VI 真没窗格还是读侧看不见，尚未分开"。Round 13 分开了读侧（不瞎），
本轮补上机制：**`<cons>` 数组只在至少一个端子有 conIdx 时才存在**。
"空 cons 数组"和"没窗格"是同一件事，不是 2026 的回归。

后果分级要说清楚：`Reset.vi` 那一步**没有走到 `member`**，所以它连类成员都不是
（文件留在 `out/failed-ab/`）。而如果不看返回值，这次失败只表现为一个 JSON 字段 ok:false。

→ 落成 **LV015**（error）：出现 `obj in`/`obj out` 路径替身、又有端子缺 conIdx，就报错。
判别力：负例 1 error，正例 0，全库 30E → 31E（只多出这一份负例）。

---

## 4. 缺 override = 整个类坏，而报错不说这一点

上游断言"缺 override 是 Error 1003 打在整个类上"。做法：建 **No Override** 类实现
Can Scale，只加一个与接口无关的 `Ping.vi`，然后问 `Ping.vi` 的执行状态。

```text
前：execState 0, broken true
    linkerErrors: "VI 包括一个类型为 8 的错误。必须使用 LabVIEW 完整版开发系统才可以解决该错误。"
后：execState 1, broken false   （唯一的改动：给 No Override 补上 Scale By 覆盖）
```

**同一个文件、同一个路径，只因为类补了一个 override 就自己好了**——因果关系坐实。

但要注意报错文本：它说"类型为 8 的错误"、要"完整版开发系统"，**一个字都没提接口或缺覆盖**。
这句正是 Round 6 retarget 失败时的同一句话，也就是说这串文字对至少两种完全不同的病因
都出。诊断顺序应是：`execState 0` → 先问"这个类实现接口了吗、接口声明的每个方法都覆盖了吗"
→ 再去看链接。

`No Override` 这个名字在实验后就名不副实了（它现在有覆盖）。保留原名，因为
重命名 `.lvclass` 会牵动成员 URL 和工程条目，为一次实验不值得。

---

## 5. 陷阱：类条目会被 LabVIEW 自己的保存删掉

第一次跑 `create_accessors(Sensor)`：

```json
"classIndex": -1,
"classPathsSeen": ["...\\round14\\lib\\Can Scale.lvclass"],
"errorCode": 1055,
"hint": "classIndex -1 with classPathsSeen populated IS a path mismatch: compare..."
```

提示把人往"路径拼写"上带，但真正的原因在工程文件里：

```text
调用前（工具自己报告的）：projectEntry action=added  url=../lib/Sensor.lvclass
                          projectEntry action=added  url=../lib/Temp Sensor.lvclass
实际文件：                <Item Name="Can Scale.lvclass" .../>      <- 只剩这一个
```

`create_class` / `create_interface` 的类条目是**工具自己写进 .lvproj 的**（LabVIEW 不参与，
文档里明说）。但 LabVIEW 可能仍持有同一工程的**内存副本**，那份副本早于这次写入；
下一次保存（`lvai_close_active_project`、下一个类工具的 prologue、或关 IDE）
就把内存里的条目表写回文件，**刚加的条目没了**，全程零报错。

上游其实知道这件事，`classEntriesRestored` 那句注释就是它：
"counts entries LabVIEW's own save had deleted from the .lvproj and this step put back"。
但它是事后统计，不是拦截。

### 5.1 正确顺序（本轮实测有效）

1. `lvai_close_active_project`（先让 LabVIEW 把内存副本落盘并释放）
2. 补 .lvproj 条目（或交给工具重写）
3. 再调需要"工程里必须有这个类"的工具（accessors / 继承 / 覆盖）

按这个顺序第二次调用：`classIndex: 1`、`membersAfter: 5`、4 个访问器全部 sourceOnly。

### 5.2 落成闸门 `tools/lvproj_audit.py`

这是本仓库**唯一读 .lvproj 的闸门**（其余都读 AIXML）。检查四件事：

| 级别 | 检查 | 为什么 |
|---|---|---|
| error | 列了条目但文件不在 | 目录搬过、或条目指向旧副本 |
| error | 条目排在 Dependencies/Build 之后 | 手写工程时最容易犯 |
| warning | 磁盘上有 `.lvclass`/`.lvlib` 但没人列 | **就是被冲掉条目的形状** |
| info | 磁盘上有 `.vi` 但没人列 | 常见正常态（Round 3 的工程按绝对路径指向旧副本） |

两种 URL 形式都支持，且**基准模型是本轮确认的**：

- `URL="/C/Users/..."` —— 绝对路径（开头的 `/` 是 Windows 根，`C` 是盘符）
- `URL="../lib/X.lvclass"` —— **相对"工程文件本身当作目录"**，所以从
  `round14/Lvoop Demo.lvproj` 出发 `../lib` 指 `round14/lib`，不是 `artifacts/lib`

第 5.1 节说的那条就是这个：同一个约定也用在 `.lvclass`/`.lvlib` 的成员 URL 上
（`../Sensor/Scale By.vi` 从 `lib/Sensor.lvclass` 出发指 `lib/Sensor/Scale By.vi`）。

负对照：把 `No Override` 条目删掉 → 恰好 1 条 warning 点名它；补回 → clean。
全库 5 个工程（round3/7/12/13/14）0E/0W。

---

## 6. 三条读数上的坑

### 6.1 `ancestors` 把接口排在真父类前面

```text
Sensor:      ancestors ["Can Scale.lvclass"]            inheritsFrom "LabVIEW Object"
Temp Sensor: ancestors ["Can Scale.lvclass", "Sensor.lvclass"]  inheritsFrom "Sensor.lvclass"
```

`ancestors[0]` 是接口。要判父子，用 `inheritsFrom` 或 `parentLinks[].kind`
（`interface` / `class`）。这是 Round 11 那条修正的再确认，这次是我们自己造出来的类。

### 6.2 访问器名字跟着 IDE 语言走

中文版 IDE 生成的访问器叫：

```text
读取Name.vi / 写入Name.vi / 读取Last Reading.vi / 写入Last Reading.vi
```

**任何硬编码 `Read Name.vi` 的测试或调用方在中文版上必然失败。** 要拿名字，就读
`describe_class` 的 `members`；不要拼。

### 6.3 `vi_terminals` 会把中文端子名解成乱码

同一个访问器：

```text
Sensor.lvclass:∂¡»°Name.vi
  Sensor ‰»Î   [ref{UDClassInst}] conIdx 11, dynamic
```

`读取` → `∂¡»°`，`输入` → `‰»Î`：**按单字节编码解了 UTF-8/GBK 字节**。
而同一时刻 `describe_class` 读 `.lvclass` 的中文名是完全正确的
（`读取Last Reading.vi`），说明问题在 pylabview 读 VI 前端面板堆的那条路上，
不在 MCP 传输层。

后果具体：`vi_terminals` 打印的 `<Call>` 片段是给 AI 直接抄的，
抄到乱码端子名，Call 就解析不了。**规则：非 ASCII 端子名不要照抄输出，
用 `describe_class` 的名字或自己起 ASCII 名。**

---

## 7. 本轮的闸门增量

| 工具 | 变化 |
|---|---|
| `tools/lvrule_check.py` | 新增 **LV015**（method 源文件的路径替身缺 conIdx = error），共 13 条在用 |
| `tools/lvproj_audit.py` | **新增**。唯一读 .lvproj 的闸门；4 类检查，有负对照 |
| `tools/audit_aixml.py` | 未改；全库现 79 份 31E/284W/60I |

`lvrule_check` 的 13 条：LV001/003/004/005/006/007/008/009/010/011/012/013/014/015
（编号不连续是历史原因：002 已并入 014）。

---

## 8. 产物清单

```text
research/artifacts/round14/
  Lvoop Demo.lvproj                       4 个类，全部条目齐（闸门 clean）
  interface-scale-by.aixml.xml            接口方法源（conIdx 0/1/2 + path 替身）
  sensor-scale-by.aixml.xml               Sensor 的覆盖（同形状）
  sensor-reset-noconex.aixml.xml          A/B 负例：故意不带 conIdx
  no-override-ping.aixml.xml              缺 override 实验用的无关方法
  lib/Can Scale.lvclass  (1411 B)  + Can Scale/Scale By.vi
  lib/Sensor.lvclass     (11568 B) + Sensor/Scale By.vi
  lib/Temp Sensor.lvclass(10844 B)
  lib/No Override.lvclass(10290 B) + No Override/{Ping,Scale By}.vi
  lib/读取Name.vi  lib/写入Name.vi  lib/读取Last Reading.vi  lib/写入Last Reading.vi
  out/failed-ab/Reset (no conIdx, never a member).vi   A/B 的失败产物，留证
tools/lvproj_audit.py                     新闸门
tools/lvrule_check.py                     +LV015
bin/scripts/aixml-pylabview/resolve.py.orig-round14   补丁前的原始文件（本地备份）
```

---

## 9. 未验证 / 下一步

1. **动态派发没有在运行时验过。** 两个类都有 `Scale By` 覆盖、面板端子都标了 `dynamic`，
   但"传一个 Temp Sensor 进去，调 Scale By 走子类实现"需要一个**带类端子的调用方 VI**，
   而 AIXML 写不出类类型端子（`Control with type=UDClassInst is not supported`）。
   要验，得先解决"造一个类端子的顶层 VI"——`add_class_method` 只能把 VI 变成**成员**，
   不能把顶层 VI 的端子改成类。这是下一轮最该攻的点（P15）。
   一条可能的路：`lvai_graft_diagram` 把方法图搬到"已有类端子"的面板上（Round 12 验过 graft）。
2. **Temp Sensor 是否可执行未测**（它自己没有成员，无从读 `execState`；
   没有自己的覆盖、靠 Sensor 的覆盖满足接口，这一点上游没写，我们也还没量）。
3. **`resolve.py` 的补丁是本地改的**，升级 labview-mcp 会被覆盖；
   升级前先记 `LABVIEW_ROOT` 或重新打补丁。
4. **`lvai_create_accessors` 的 `nextFromField` 成功后回答 0**，而文档说那是"续做位置"。
   本轮只跑了单次切片（2 字段一次做完），多切片语义仍未验。
5. 仍是降级项：字符串/路径节点覆盖、Network Streams、XControls。
