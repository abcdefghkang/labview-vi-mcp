# 实测记录：2026-10-18 MCP 会话全记录（research 07）

> 本文是 [`06-best-practices.md`](06-best-practices.md) 与
> [`05-aixml-vi-generation.md`](05-aixml-vi-generation.md) 的证据底稿：每一次调用的
> 真实返回（节选关键字段）。环境如下。

## 0. 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-18 |
| LabVIEW | **2026 (64-bit)**（`C:\Program Files\National Instruments\LabVIEW 2026`）+ **2018 (32-bit)**（运行中，PID 2080） |
| LabVIEWMCP server | **2.0.1 (77eb0b22)**，scriptsDirectory `C:\Users\heiyashi\labview-mcp\bin\scripts` |
| 服务 | `grpc.reflection.v1alpha.ServerReflection`、`grpc.health.v1.Health`、`lvai.LVAI` |
| MCP 客户端 | WorkBuddy（mcp__labview / mcp__labview-cli 两个服务器在会话中） |
| pylabview | Python 3.12 x64，pinned commit `69768647c18d…`，provisioned 2026-10-13 |
| settings.json | `%USERPROFILE%\.labviewmcp\settings.json` 存在，`"aixmlBackend": "auto"` |

---

## 1. `lvai_status` —— 第一次调用失败（服务的真实启动条件）

```json
{ "ok": false, "errorKind": "InvalidOperationException",
  "error": "Could not find a port serving lvai.LVAI. Tried 49 candidate(s)…" }
```

**实测结论**：LabVIEW 2018 在运行，但 49 个候选端口无一服务 `lvai.LVAI`。错误信息给出
判据：`LabVIEW.exe listener` 端口答 `Unavailable` = IDE 起着但服务没起（**服务随
Nigel 启动**）；答 `DeadlineExceeded` = 服务在但没及时响应（ busy 与 hung 要用
`(Get-Process LabVIEW).Responding` 区分）。

## 2. `lvai_list_labview_installations` —— 版本盘点

```json
{ "installationCount": 2,
  "alreadyRunning": [{ "pid": 2080, "path": "…LabVIEW 2018\\LabVIEW.exe" }],
  "selection": "LabVIEW 2026 (64-bit)",
  "rule": "newest release first, 32-bit preferred within a release, NXG excluded" }
```

**实测结论**：挑选规则可预期；2018 虽在运行，服务器默认目标是 2026。

## 3. `lvai_ensure_labview` ×2 —— 冷启动的"两次调用"规律

第一次（waitSeconds=40）：

```json
{ "ok": false, "state": "starting", "waitedMs": 40022,
  "lastError": "The operation was canceled.",
  "runningProcesses": 2 }
```

第二次（同一参数）：

```json
{ "ok": true, "state": "ready", "port": 27387,
  "discoveredVia": "LabVIEW.exe listener", "applicationLanguage": "Chinese",
  "waitedMs": 857 }
```

**实测结论**：第一次的 `lastError` 是**调用自身 40 s 预算耗尽**（工具说明：这是冷启动
的正常答案，第二次几乎必然 ready）。第二次 857 ms 就绪。**没有重启任何东西。**

## 4. `lvai_status` —— 就绪后的完整画像

```json
{ "ok": true, "address": "http://127.0.0.1:27387", "port": 27387,
  "serverVersion": "2.0.1 (77eb0b22)",
  "services": ["grpc.reflection.v1alpha.ServerReflection",
               "grpc.health.v1.Health", "lvai.LVAI"],
  "labviewHealth": { "dwarnCount": 0, "labviewUpSeconds": 51,
                     "note": "…an instance reading 0 has been measured crashing minutes later" } }
```

**实测结论**：健康计数为 0 **不是**健康证明（日志随实例启动重置）；要看
`labviewUpSeconds` 一起读。

## 5. `lvai_aixml_reference` —— AIXML 铁律（节选原文）

```
1. NETS, NOT POINTERS. A `uid.terminal` string names a *net* (a wire)…
2. LOOK UP TERMINAL NAMES. They are literal LabVIEW labels: `Increment` -> `x+1`,
   `Greater?` -> `x > y?` (with spaces), `Select` -> `s? t\3Af`, `Or` -> `x .or. y?`.
3. ESCAPES. `\3A` = colon, `\2C` = comma, `\0A`/`\0D` = newline…
4. NO LAYOUT. There is no coordinate attribute anywhere…
5. GENERATED VIs MUST BE SELF-CONTAINED. A `Call` to a project- or library-local
   subVI is rejected as "Unsupported SubVI".
6. ALWAYS lvai_validate_aixml BEFORE generating.
```

Sections 1–16 可经 `section=` 参数按需取（`section 8 alone is 54 kB`——不要整读）。

## 6. `lvai_example_index` —— 先查再写（含一次查询失败的教学案例）

- `query="temperature acquire"` → **无命中**。返回同时说明：494 个示例 / 1360 个 VI 文件
  / 9 个因需 FPGA/RT/工具箱被扣住 / 索引缓存于 2026-10-14 / **所有词必须同时出现**
  （每个词可来自不同字段）。
- `query="temperature"` → 2/494 命中（均为 PDE 热方程类，非 DAQ 采集）。

**实测结论**：查询是 AND 语义，词越多越查不到；查不到就退化到
`lvai_palette_index` 查单个 VI，再不行才从原语重建。

## 7. `pylv_status` —— 第二引擎体检

```json
{ "ok": true, "pythonVersion": "3.12", "pythonArch": "x64",
  "pylabviewCommit": "69768647c18d2d792a259b69884b2433761c3a4f",
  "primitiveNamesTable": "…\\primitive-names.tsv",
  "terminalNamesTable": "…\\terminal-names.tsv", "canAnnotate": true,
  "aixmlBackend": { "serverDefault": "grpc", "settingsFileExists": true,
                    "settingsAixmlBackend": "auto",
                    "labviewInUse": 2026, "partsRelease": 2026 } }
```

## 8. `lvai_convert_vi_to_aixml` —— 读一个真实类成员 VI

输入：`tests/LabVIEWMCP.Tests/Fixtures/reader/Sensor/Scaled Value.vi`
（`Sensor.lvclass` 成员，Value×Gain）。

```json
{ "errorCode": 0, "xmlWritten": true, "xmlBytes": 1883,
  "fromCache": false,
  "cacheNote": "not cached: this VI is outside the LabVIEW installation…",
  "backend": "grpc" }
```

导出的 AIXML（全文见
[`examples/02-aixml-snippet/measured-scaled-value.aixml.xml`](examples/02-aixml-snippet/measured-scaled-value.aixml.xml)）展示了：
类访问器 `Call`（target `Sensor.lvclass\3A\01\0DRead Value.vi`，转义冒号与 CR）、
错误簇贯穿（`error in (no error)` / `error out`）、`ref{UDClassInst}` 对象直通、
`Multiply` 的 `x/y/x*y` 端子、`conIdx` 与 `connection`（`recommended`/`dynamic`）。

**实测结论**：这个 VI 正好示范了"不可自包含生成"的反面——它调用项目本地 subVI，
属于那 85% 不能经 AIXML 重生成的类型；读它学方言可以，生成它不行。

## 9. `lvai_check_aixml` —— 离线预检的两次真实拦截

**第一次**（我的初稿 AIXML，uid=10，注释 46 字符）：

```json
{ "ok": true, "errors": 0, "warnings": 1,
  "findings": [
    { "severity": "warning", "code": "commentMayBeClipped",
      "message": "…a comment over about 45 characters is measured being CUT OFF in silence…" },
    { "severity": "info", "code": "uidInReservedRange",
      "message": "1 uid(s) below 42 (10)…" } ],
  "elapsedMs": 2.2124, "labviewNeeded": false }
```

**第二次**（修复后：uid 1000+，注释 "Compare temp vs threshold"）：

```json
{ "ok": true, "errors": 0, "warnings": 0, "findings": [],
  "elapsedMs": 0.4025, "labviewNeeded": false }
```

**实测结论**：2 ms 内抓到两个"LabVIEW 会静默犯错"的问题；它故意**不查**终端名/类型/
连线（那是 LabVIEW 的强项，第二判据源会漂移）。

## 10. `lvai_generate_vi` —— 端到端生成（核心实验）

输入：修复后的 AIXML → 输出 `Temperature Monitor.vi`。

```json
{ "ok": true, "failedAtStep": null,
  "viPath": "…\\labview-mcp-research\\Temperature Monitor.vi",
  "viExistsNow": true, "viBytes": 5487,
  "diagramSize": { "width": 418, "height": 214,
                   "withinBudget": true, "longestChainStages": 2 },
  "steps": [
    { "step": "validate",  "errorCode": 0,
      "answer": { "validatedAs": "LVMCP Validate.vi", "elapsedMs": 118 } },
    { "step": "convert",   "errorCode": 0,
      "answer": { "viBytes": 5487, "elapsedMs": 381 } },
    { "step": "cleanUpPanel", "ok": false,
      "note": "The clean-up helper could not be generated." },
    { "step": "cleanUpDiagram", "ok": false,
      "error": { "errorKind": "helperAixmlInvalid",
                 "detail": { "aiXmlPath": "…\\lvai_run_and_read_typed.xml" } } },
    { "step": "diagramSize", "measured": true, "elapsedMs": 159 },
    { "step": "connectorPane",
      "answer": { "errorKind": "helperAixmlInvalid",
                  "detail": { "aiXmlPath": "…\\lvpane_probe.xml" } } } ],
  "totalElapsedMs": 1959 }
```

**实测结论**：

1. **核心链路全绿**：validate（118 ms，scratch 名 `LVMCP Validate.vi`）→ convert
   （381 ms，5487 字节真 VI）→ 图布 418×214 在 1920×1080 预算内。
2. **三个附加步骤失败且根因相同**：安装目录自带辅助 VI 的 AIXML 不被本机 LabVIEW
   2026 26.3.1f1（中文）接受（`helperAixmlInvalid`，症状「属性节点: 无效属性」
   「已连接两个不同类型的接线端」）。详见
   [`05-aixml-vi-generation.md` §7.1](05-aixml-vi-generation.md)。
3. `ok: true` 但 pane 未测——**这个 answer 不证明端子摆放正确**，工具自己也这么说。

## 11. `lvai_exec_state` —— 被同一个根因挡住

```json
{ "ok": false, "errorKind": "helperUnavailable",
  "error": "The executability helper could not be generated or run, so nothing is
            known about this VI. That is not a clean bill of health." }
```

**实测结论**：可执行性未知 ≠ 可执行。换证据来源（下一步用运行证明）。

## 12. `lvai_run_vi_and_read_values`（backend=pylabview）—— 运行验证，两用例

**用例 A（超限）**：`{"Temperature":"95","Alarm Threshold":"80"}`

```json
{ "ok": true, "via": "ActiveX", "ran": true, "finished": true, "runMs": 2,
  "values": { "Status": { "value": "ALARM: Over Temperature!" },
              "Alarm":  { "literal": "true" } } }
```

**用例 B（正常）**：`{"Temperature":"25","Alarm Threshold":"80"}`

```json
{ "ok": true, "via": "ActiveX", "ran": true, "finished": true, "runMs": 2,
  "values": { "Status": { "value": "Normal" },
              "Alarm":  { "literal": "false" } } }
```

**实测结论**：**AI 生成的 VI 计算正确**（两个分支都与设计一致）。注意此路线绕开了
辅助 VI（ActiveX 直跑），恰好不受 §10 故障影响——这就是"双后端"的实战价值。

## 13. `lvai_describe_vi` —— 回读验证结构

返回 `viXml` 与 authored AIXML 一致（`Greater?` 的 `x > y?`、`Select` 的
`s? t\3Af`、四个 Control/Constant、两个 Indicator，uid 与线名全部对得上），
并带 `viImage`（方块图 base64 PNG）。

**实测结论**：回读是结构审查的客观依据；"描述"与"导出"选 export（同一张图，内容
1/3.5，17 532 B vs 62 091 字符——参考库 issue #19 实测）。

## 14. CLI 服务器 `labview_get_status` —— "connected"的含金量

```json
{ "connected": true, "backend": "cli",
  "version": "LabVIEWCLI: … (VI Server 端口 3363)  |  VI Server 连接: 失败",
  "supports_control_io": false, "supports_vi_scripting": false }
```

**实测结论**：顶层 connected=true 掩盖了 VI Server 通道失败；逐项看 `supports_*`。

---

## 附：本次产生的文件

| 文件 | 说明 |
|---|---|
| `Temperature Monitor.vi`（5487 B） | 端到端生成的 VI 成品（复制于 `research/artifacts/`） |
| `temperature-monitor.aixml.xml` | 生成所用的 AIXML 源（`examples/01-create-vi/`、`examples/02-aixml-snippet/`） |
| `measured-scaled-value.aixml.xml` | 本机真实导出的类成员 VI AIXML（1883 B） |
| `prompt.txt` / `run-output.log` | 任务原始工单（`labview-mcp-research/`，未入库） |
