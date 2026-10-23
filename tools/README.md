# tools/ — 生成前的离线闸门

这三个脚本回答同一个问题：**在没有 LabVIEW 的情况下，这份 AIXML 里哪些错已经可以确定？**
答完再花一次 LabVIEW 往返，而不是用往返去发现一个拼写错误。

全部只依赖 Python 3 标准库。不需要 MCP，不需要网络，不需要 LabVIEW。

第四个脚本（`cold_build_census.py`）不查文档，查**语料**：把上游 25 篇冷构建记录变成数据集，
回答"哪类缺陷会复发"。见文末。

```bash
# 一份文档（有 error 时退出码 1，可直接挂 CI）
python tools/audit_aixml.py --summary draft.aixml.xml

# 全仓库回归
python tools/audit_aixml.py --summary research/artifacts

# 出 markdown 报告 + 完整 JSON（含每条消息）
python tools/audit_aixml.py --markdown --root research/artifacts \
       --out research/artifacts/round9/lint-sweep-report.md \
       --json-out research/artifacts/round9/lint-sweep.json research/artifacts

# 只跑我们自己的铁律
python tools/lvrule_check.py draft.aixml.xml
```

实测耗时：50 份 AIXML **2.5 s**（两个检查器各起一个进程；逐文件起进程会变成 80 s，
因为上游 lint 每次启动都要加载 VI Server 目录）。

---

## 分工，以及为什么不让一个脚本干完

| 文件 | 内容 | 能不能改 |
|---|---|---|
| `aixml_lint.py` | **vendored** 上游 [Zuehlke/labview-mcp](https://github.com/Zuehlke/labview-mcp) `scripts/aixml_lint.py`，37 条规则 | **不改**。上游更新时整份覆盖，文件头记着来源 commit |
| `lvrule_check.py` | 我们自己的 8 条铁律（LV001/003/004/005/006/007/008/009） | 只往这里加 |
| `audit_aixml.py` | 跑两个、合并、按文档类型分流、抑制已知误报、出表格 | 门面，逻辑尽量薄 |
| `cold_build_census.py` | **不是闸门**：把上游 `docs/cold-build-*.md` 变成 CSV/JSON 数据集 | 语料普查 |

理由来自上游自己踩的坑：同一个规则的第二份实现会漂移，`AixmlCheck.SafeUidBase`=4200 与
`LOW_UID_CEILING`=5000 曾分歧数日，lint 一直告诉作者"你自己生成的文件违规"。
所以 LV002（uid ≥ 4200）在这里**退役**了——上游 `uid-low` 已经覆盖，重复实现只让每条告警翻倍。
编号保留不复用，退役理由在 `lvrule_check.py` 文件头。

---

## `aixml_lint.py` 的 37 条规则覆盖什么

上游测量得到的、不需要 LabVIEW 就能判定的三类主错：

| 类 | 规则 | 为什么值得离线查 |
|---|---|---|
| `uid_parent` 指向**存在但错的**元素 | `parent-mismatch` / `parent-dangling` / `parent-not-a-container` | LabVIEW 会**静默**把元素放进它指的那个图 —— 一个 CaseFrame 落进另一个 Case Structure，validate 还回 `errorCode 0` |
| 网被读但没人产出 | `net-unproduced` / `net-typo` | LabVIEW 报的是**读端**「Contains unwired or bad terminal」，把你指向错的那一端 |
| 网被产出但没人读 | `net-unconsumed` | 本身合法（面板控件），但和上一条同时出现时，就是一个拼错的网名 |

另有：`uid-duplicate`、`uid-low`、类型文法（`type-grammar` / `type-braces` / `array-nested`）、
VI Server 名字（`property-name-unknown` / `method-name-not-known` / `vi-server-class-unknown`）、
case 隧道完整性（`case-frame-missing-out-tunnel` / `-orphan-tunnel`）、连接器面板
（`conn-required-output` / `conn-missing-input` / `conn-error-in-not-recommended`）等。

`property-name-unknown` 是**防崩**规则，不是风格建议：写错的属性名（`read+Version Number`，
真名是 `Application\3AVersion Number`）会让 `ConvertAIXMLToVI` **直接把 LabVIEW 杀掉**，
4 次 4 次，且没有任何错误返回。

---

## `lvrule_check.py` 的 8 条，每条来自一轮实测

| 规则 | 断言 | 来源 |
|---|---|---|
| `lv001-xml-comment` | AIXML 中不允许 XML 注释 | Round 7：`<VI>` 之前有注释 → **空图 + errorCode 0**（静默失败）；子元素之间 → Error 42 |
| `lv003-sr-seed-inside-loop` | 移位寄存器 `Left inputs` 的种子必须由**循环外**产出 | Round 3 的 A–E 五分支、Round 4 |
| `lv004-single-frame-case` | 单框 Case Structure 判死 | Round 8：单选项枚举的 Case 必坏，composer 写空隧道桩，`execState 0` |
| `lv005-while-without-condition` | While Loop 必须有 `Condition` | Round 4 |
| `lv006-call-target-is-path` | `Call` 的 `target` 是名字，不是路径 | Round 6：路径永不解析（`Error 53`） |
| `lv007-shiftreg-incomplete` | `ShiftReg` 必须同时有 `Left` 和 `Right` | Round 4 |
| `lv008-duplicate-selector` | 两个 frame 不能同一个 selector | Round 4 |
| `lv009-error-terminal-required` / `lv009-error-out-optional` | **上游两条规则看不到的** error 端子写法 | Round 9（本机抓到）+ Round 10（补上游空白） |

**LV009 的范围是刻意窄的**，因为上游已经管了一部分：`conn-required-output` 管任何 Indicator 的
`required`，`conn-error-in-not-recommended` 管带 `conIdx` 的 `error in`。LV009 只补两处空白 ——
无 `conIdx` 的 error Control、以及 `error out` 的 `optional`。探针
`research/artifacts/round10/lv009-probe.aixml.xml` 把这条边界钉死：同一台机器上，
我们的报 `4200`/`4203`，上游报 `4205`，**不重不漏**。上游若放宽，**删掉 LV009**。

这条纪律的由来就是 LV002 的退役：同一条规则的第二个实现会漂移，且每条告警翻倍。

验证锚点：Round 3 的 `saturating-accumulator.aixml.xml`（修复前）报 3 条 `lv003`，
它的 `-v2`（修复后）与 `variant-d-rootseds`（根级种子）**0 条**。
这不是调出来的参数，是那轮五分支实验的原始数据。

---

## 已知误报（已抑制，但单独计数）

`cond="true"` / `cond="false"`：上游 lint 把 `cond` 归为"消费一个裸网"（`BARE_NET_ATTRS`），
没有为字面量留例外，于是 `net "true" is read ... but no element writes it`。
我们 Round 4/6 的状态机停止逻辑就是这么写的，NI 的转换器接受、导出、并跑过。
`audit_aixml.py` 的 `FP_CONDS` 按名字抑制它们，报告末尾单独给出条数——**不静默丢弃**。

非 AIXML 文档（`<RSRC>` / `<FPHb>` 的 pylabview 转储）按根元素识别后跳过，
不计入错误统计。仓库里现有 9 份。

---

## 刷新上游规则

```bash
git clone --depth 1 git@github.com:Zuehlke/labview-mcp.git /tmp/lvmcp-upstream
cp /tmp/lvmcp-upstream/scripts/aixml_lint.py tools/aixml_lint.py
# 然后把文件头的来源 commit 改成新的那一个
```

HTTPS 在这台机器上不可用（schannel 吊销检查失败，`CRYPT_E_REVOCATION_OFFLINE`），用 SSH。
许可证 MIT，Copyright (c) 2026 Zühlke。

---

## `cold_build_census.py` — 查语料，不查文档

上游把每一次"从零建一个完整应用"的实测记录都入库了（`docs/cold-build-*.md`，25 篇 4409 行）。
一篇读下来是一个故事，整批读下来才知道**哪些坑是系统性的**。这个脚本只做提取，不做解释：

```bash
python tools/cold_build_census.py /tmp/lvmcp-upstream/docs \
       --out research/artifacts/round10
# -> cold-build-census.csv / .json
```

它抓的是有固定写法的字段：构建日期、`Final state:` 那一行、章节标题、Error 编号、工具名、
是否跑了负对照、是否先过 lint。抓不到的**留空**而不是猜 —— 25 篇里只有 11 篇写了明确终态，
空白本身就是信息。分析结论在 `research/19-cold-build-corpus.md`。

用途：下次上游新增冷构建，重跑一次就能看出"这批准的是同一批坑还是新坑"。
