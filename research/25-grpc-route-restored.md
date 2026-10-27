# Round 16 — gRPC 路线恢复：2026-capable 工位、三处新规则、p16 验证

> 本轮在线（2026-capable 工位）。一句话：**gRPC 路线恢复**，本机会话从 2018 工位回到 2026-capable；
> 全链路 author→compile→run 实测跑通（y = 6 × 7 = 42）；并由此钉死三处纯工具/环境层的新规则
> （LV017/018/019）。上一未完成会话留下的 `p16` LVOOP 树被验证为合法的 2026 中文工程，从"孤儿"变成证据。

---

## 1. 环境：从 2018 工位回到 2026-capable

Round 15 收尾时本机是 **LabVIEW 2018（32 位，无 Nigel，gRPC 全灭）**。本轮三个独立读数都显示会话已切换回 2026：

| 读数 | 值 | 含义 |
|---|---|---|
| `pylv_status` | `labviewInUse: 2026`, `partsRelease: 2026` | pylabview 解析到的是 2026 安装 |
| `lvai_status` | `port: 44148` LISTENING，services 含 `lvai.LVAI` / `grpc.reflection` / `grpc.health` | **gRPC（Nigel）在线**，NI 的 AI 服务可达 |
| `ConvertVIToAIXML(grpc)` 打开 `读取Name.vi` | 成功，且该 VI 的 `LVVersion="26008000"` | 当前进程能打开**2026 格式**产物 |

**一个澄清（避免被日志骗）**：`lvai_status` 报告的崩溃日志路径仍是 `LabVIEW_32_18.0_heiyashi_cur.txt`，
但那条日志是**上一会话的残片**（NI 按版本命名崩溃日志，且日志在实例启动时重置）。
当前实例（已运行约 64 分钟、`labviewUpSeconds: 3874`）能打开 2026 戳 VI，说明当前进程是 2026-capable，
不是 2018。存活判据依旧：以 `netstat` 有 LISTENING + `tasklist` 有 `LabVIEW.exe` 为准，不要信 `lvai_status`
里那条陈旧日志路径。

**结论**：本会话是 **2026-capable 工位，gRPC 与 pylabview 两条路线同时在线**。这正是 Round 15 之后
挂在"观察点"上的那个问题——**环境换回了 2026**。

---

## 2. 全链路闭环实测（canonical AI→VI→run loop）

目标：证明"AI 写 AIXML → 编译器生成 .vi → 实跑读数"这条主线在本会话是通的。

**输入** `research/artifacts/round16/scale-double-r16.aixml.xml`（`y = x × factor`，三端子全带 `conIdx`，
过 G0 离线闸门 **0E/0W**）：

```xml
<VI _name="Scale Double R16.vi" description="...">
  <Control _name="x" conIdx="0" connection="required" outputs="value:4200.value" type="double" uid="4200" uid_parent="root" value="0"/>
  <Control _name="factor" conIdx="1" connection="required" outputs="value:4201.value" type="double" uid="4201" uid_parent="root" value="0"/>
  <Indicator _name="y" conIdx="2" connection="recommended" inputs="value:4210.out" type="double" uid="4210" uid_parent="root" value="0"/>
  <Node _name="Multiply" inputs="x:4200.value,y:4201.value" outputs="x*y:4210.out" uid="4211" uid_parent="root"/>
</VI>
```

| 步骤 | 调用 | 结果 |
|---|---|---|
| 校验 | `lvai_validate_aixml(backend:"grpc")` | `errorCode 0`（无报错，且失败不烧名） |
| 编译 | `lvai_convert_aixml_to_vi(backend:"grpc", 反斜杠 viPath)` | 创建 `.vi`，4592 B，`errorCode 0` |
| 运行 | `lvai_run_vi_and_read_values(backend:"grpc")` | **失败**：`helperAixmlInvalid`（见 §3 LV019） |
| 运行（兜底） | `lvai_run_vi_and_read_values(backend:"pylabview")` | **`y = 42.00000000000000`（DBL）**，`runMs 2`，`ran/finished: true` |

**判据**：读盘（`.vi` 落盘 4592 B）+ 实跑（数值 42）= 真成功，不看任何 `ok` 自述。

**关键事实**：author 与 compile 走 **gRPC（NI 转换器）**，run 走 **pylabview（ActiveX，无 helper）**。
所以"AI 直接开发并运行 LabVIEW 程序"在本会话成立——只是 run 这一步要避开损坏的 gRPC helper。

---

## 3. 三处新规则（纯工具/环境层，已写入仓库闸门）

### LV017 — gRPC 文件打开必须传**反斜杠**路径（Windows）

`lvai_*` 走 grpc 且带 `viPath / aiXmlFilePath / projectPath` 时，若传**正斜杠**，NI 的 `OpenVIReference`
会把路径拼成 `C:\/Users/...` 报 **Error 7 "未找到文件"**（表象像"文件不存在/权限问题"）。
第一次 `ConvertVIToAIXML` 用正斜杠 → `errorCode 7`；改成**反斜杠** → `errorCode 0`。
pylabview 读侧两种斜杠都收。

> **规则**：凡 `lvai_*` 走 grpc 且有文件路径参数，一律传反斜杠（`C:\Users\...`）。写 AIXML/脚本时用正斜杠无所谓，
> 只有工具调用的路径参数要反斜杠。

### LV018 — pylabview 读侧对**中文标签乱码**，中文工程回读一律用 grpc

同一份 `读取Name.vi`：
- `convert_vi_to_aixml(backend:"pylabview")` → VI 名导出成 `\u2202\u00A1\u00BB\u00B0Name.vi`（UTF-8 字节被当 Latin-1 解，乱码）；
- `convert_vi_to_aixml(backend:"grpc")` → 正确还原 `读取Name.vi`、`Sensor输入`、`Sensor输出`、`无错误`、`错误`。

> **规则**：中文版 IDE 工程，`describe_vi / convert_vi_to_aixml / 回导比对` 一律 `backend:"grpc"`。
> pylabview 的读侧在 CJK 上有编码 bug，会污染标签、控件名、终端名。

### LV019 — gRPC 的 run helper 在**中文 2026** 下损坏，run 改走 pylabview

`run_vi_and_read_values(backend:"grpc")` 报 `helperAixmlInvalid`：helper 文档
`bin/scripts/lvai_run_and_read_typed.xml` **自身校验失败**（一整串"未连线/类型不匹配/条件结构缺默认分支"）。
这不是目标 VI 的问题，是 helper 在这个中文 2026 环境下不通过。

pylabview 路线**不经过 helper**——它用 ActiveX 直跑，面板名/类型从文件读，照常工作（见 §2）。

> **规则**：`run_vi_and_read_values(grpc)` 报 `helperAixmlInvalid` ⇒ 立即 `backend:"pylabview"` 重试。
> 这也是 §1 里"中文版环境 4 个 helper 被拒"那一条的同一根因（`labviewInUse` 是 2026 时依然成立）。

---

## 4. 遗留 p16 树验证（把"孤儿"变成证据）

**发现**：`research/artifacts/round16/p16/` 是上一未完成会话留下的 LVOOP 工程，**未提交**、无对应研究文档。
内容：`Can Scale`（**接口**，`IsInterface=true`）+ `Sensor`/`Temp Sensor`/`No Override`（实现类）
\+ 4 个访问器（中文名 `读取Name`/`写入Name`/`读取Last Reading`/`写入Last Reading`）。
所有 `.lvclass` 的 `LVVersion="26008000"` ⇒ **2026 格式**。

**验证**：
- `convert_vi_to_aixml` 双后端都 `errorCode 0` → 文件合法、可解析（grpc 正确还原中文标签，pylabview 乱码但能解）。
- **继承扫描（per-tree，避免 basename 歧义）**：`python tools/lvclass_parent_scan.py research/artifacts/round16/p16`
  → 4 类，3 有父，**父全是接口 `Can Scale`**，`parent_is_interface 3`，`parent_unresolved 0`，`parent_file_missing 0`。

> 这个扫描顺带印证了 P11 的核心命题：工具若只报"父名"`Can Scale` 会把接口当基类，本扫描额外读父文件的
> `IsInterface` 二次确认，所以能正确标出"父类其实是接口"。

**处置**：保留并提交 `p16`，作为**2026 中文 LVOOP 树**的自包含样例（访问器名随 IDE 语言、接口+三实现类的继承结构都齐）。

---

## 5. dump_schema：权威接口面（P3 第一步）

`lvai_dump_schema(format:"summary")` 已取到（gRPC 在线才能取），落盘
`research/artifacts/round16/dump_schema_summary.txt`。NI 私有 gRPC 接口（`proto3`，package `lvai`）共 **23 个 RPC**，
与 R11 实测的 23 RPC 计数一致。关键 RPC：

- 生成/编辑：`ConvertAIXMLToVI`、`ApplyAIXMLToVI`、`ConvertVIToAIXML`、`ValidateAIXML`
- 运行：`RunVIAsTopLevel`（MCP 封装为 `run_vi_and_read_values`）
- 工程/面板：`OpenFile`、`BuildFromBuildSpecification`、`FindPaletteItem`、`DropPaletteItem`
- 上下文：`GetDescribeVIPromptInfo`、`GetDescribeProjectPromptInfo`、`SearchInfoCache`、`LookupInfoCacheItems`

注意：这是 **NI 私有接口**，MCP server 2.0.1 的 `lvai_*` 是其封装；**server 仍是 v2.0.1（未升 v2.2.0）**，
所以四个 v2.2.0 helper 仍未出现——P3 的"升级并 diff"项继续挂起（且升级会覆盖 `resolve.py` 补丁，须重打）。

---

## 6. 对看板的影响与遗留项

**环境假象第五例**（外表像"run 工具坏了"）：
gRPC 的 run helper 在中文 2026 下自身校验不过 → `helperAixmlInvalid`。根因同 R11 的"4 个 helper 被中文版拒收"。

**优先级推进**：
- **P11 完成**（per-tree 继承扫描，见 §4）。
- **P3 第一步完成**（dump_schema 取到权威接口面，见 §5）；"升级 ≥ v2.2.0"仍挂起。
- P9（给上游报 versionWarning 误判）：R15 已用 2018 推翻，R16 进一步确认**2026 工位能开 2026 戳**——
  版本警告在该工位自然不成立，但"2018 也能开 2026 戳"那条实测（R15，6×7=42）仍是给上游的唯一硬证据。

**下一步**：
1. **P1**：IDE 手搭一个"父类型窗格端子"调用方做样本——gRPC 在线后 `graft`/`describe` 都可用，比 2018 工位更可行。
2. 升级 ≥ v2.2.0：先查 `resolve.py` 补丁存亡 → `dump_schema` diff 工具面 → 验四个 helper；升级会覆盖补丁，须重打。
3. 装 Caraya（VIPM，需联网）→ 跑 `generate_test(pylabview)`，把测试层最后一级打通。
4. `lvai_layout_diagram` 首测（Round1"图面难看"的正式收尾）。

---

## 7. 本会话复现条目

```bash
# 0) 环境确认（gRPC 在不在，看 port 是否 LISTENING）
lvai_status                                  # port 非空 + services 含 lvai.LVAI ⇒ gRPC 在线
pylv_status                                  # labviewInUse / partsRelease 看认的是哪个版本

# 1) 全链路闭环（author→compile 走 grpc，run 走 pylabview）
lvai_validate_aixml(backend:"grpc", aiXmlFilePath:"C:\\...\\scale-double-r16.aixml.xml")
lvai_convert_aixml_to_vi(backend:"grpc",
    aiXmlFilePath:"C:\\...\\scale-double-r16.aixml.xml",
    viPath:"C:\\...\\Scale Double R16.vi")    # 注意反斜杠（LV017）
lvai_run_vi_and_read_values(backend:"pylabview",   # grpc 报 helperAixmlInvalid 就换这条（LV019）
    viPath:"C:\\...\\Scale Double R16.vi", inputsJson:'{"x":"6","factor":"7"}')

# 2) 中文工程回读（务必 grpc，否则标签乱码，LV018）
lvai_convert_vi_to_aixml(backend:"grpc", viPath:"C:\\...\\lib\\读取Name.vi",
    aiXmlFilePath:"C:\\...\\读取Name.aixml.xml")

# 3) 继承扫描（per-tree，避免 basename 歧义）
python tools/lvclass_parent_scan.py research/artifacts/round16/p16 --json p16-parent-scan.json

# 4) 权威接口面
lvai_dump_schema(format:"summary", outputPath:"research/artifacts/round16/dump_schema_summary.txt")
```

---

## 8. 一句话带走

> **本会话回到 2026-capable 且 gRPC 在线**，AI 写 AIXML → NI 编译器出 .vi → 实跑读数（y=42）全链路打通；
> 唯一坑是 gRPC 的 run helper 在中文 2026 下损坏，run 改走 pylabview 即可。
> 另记三处纯工具层规则：gRPC 路径要反斜杠（LV017）、中文工程回读用 grpc（LV018）、run 遇 helperAixmlInvalid 换 pylabview（LV019）。
> 遗留的 p16 LVOOP 树验证为合法的 2026 中文工程，已收编为样例。
