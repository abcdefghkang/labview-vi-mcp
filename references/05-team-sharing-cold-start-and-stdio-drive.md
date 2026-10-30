# 团队技术分享：AI 无人值守开发 LabVIEW —— 冷启动闭环与无 IDE 直驱

> 依据：Round 20（2026-10-30，`research/29-multi-vi-orchestration-pylabview.md`）。
> 全部数字来自当轮真机实测，可复现。读完你将能在一台冷机上，用 6 条命令让 AI
> 从零写出一个多 VI LabVIEW 程序并跑出验证值——不需要打开 LabVIEW IDE，
> 不需要任何支持 MCP 的 agent 框架。

---

## 1. TL;DR

| 指标 | 实测值 |
|---|---|
| 冷机（无 LabVIEW.exe）→ 首个 run 出值 | **~50 秒**（ensure 45 s + convert 3.1 s + run 3 ms） |
| 单 VI 合成 | 0.7–1.6 s/份 |
| 实跑取值 | 3 ms/次 |
| 驱动方式 | 一个 60 行的纯标准库 Python 脚本（`scripts/mcp_call.py`） |
| 本轮成果 | 顶层 VI 调 2 个子 VI，N=5/3 两点验证与手算逐位吻合 |

两个核心认知，先说结论：

1. **gRPC 服务不来 ≠ 环境不可用。** 只要 `LabVIEW.exe` 在跑（哪怕是被一个工具调用
   自己拉起来的），`convert`/`run` 走 pylabview 后端照常通。
2. **MCP 服务器就是一个可执行文件。** agent 的 IDE 没挂载 MCP 工具？无所谓——
   它说的是换行分隔的 JSON-RPC over stdio，任何会写 60 行 Python 的人（或 agent 自己）
   都能直接驱动它。

---

## 2. 背景：这套系统是什么（30 秒版）

```
AI（agent）──MCP──> LabVIEWMCP.exe（99 个 lvai_*/pylv_* 工具）
                        │
                        ├─ backend:"pylabview"：纯 Python 读写 .vi 二进制（RSRC 格式）
                        │    · convert：AIXML（文本中间表示）→ .vi 文件
                        │    · run：经 LabVIEW ActiveX 实跑 + 读回指示器值
                        └─ backend gRPC：NI 官方服务（需 Nigel 启动，本机常年未开）
```

- **AIXML**：LabVIEW 程序框图的 XML 中间表示。AI 写 AIXML → 服务器合成 .vi → 实跑取值。
- **闸门体系 G0–G5**：离线体检 → 合成 → validate → 文件级回读 → 实跑 → 负控。
  本分享聚焦其中与"环境"相关的 G3（合成）和 G5（实跑）。
- 详细方法论见仓库 `research/00-status.md`（看板）与 `research/06-best-practices.md`（最佳实践）。

## 3. 痛点：两个"隐性前提"

在此之前，每一轮实验都默认两个前提，缺一个就做不了：

| 前提 | 表现 | 后果 |
|---|---|---|
| A. agent 的 IDE 挂载了 lvai_* MCP 工具 | 换台机器/换个框架，工具列表里没有 lvai_* | 一切研究无法复现 |
| B. LabVIEW.exe 已经在跑 | 冷机上 `lvai_status` 十一个候选端口全不可用 | 连环境体检都过不了 |

Round 20 把这两个前提都打掉了。

## 4. 突破一：冷启动闭环

### 4.1 现象与诊断

冷机上 `lvai_status` 返回 "Could not find a port serving lvai.LVAI"。**这不是失败，
只是 gRPC 服务未启动**（它随 Nigel 起，需要人手动开 IDE 插件）。pylabview 后端的
`convert` 是纯 Python 写文件，根本不需要它；`run` 走 ActiveX，只需要 `LabVIEW.exe`
进程存在。

### 4.2 关键调用：`lvai_ensure_labview`

```json
{ "waitSeconds": 45 }
```

它做了三件事（返回体里都有据可查）：

- `startedByThisCall: true` —— **自己把 LabVIEW 2026 (64-bit) 拉起来了**（`launchMethod: "explorer"`）；
- 自动清 LVAutoSave —— 避免恢复对话框以模态方式卡死后续 ActiveX 调用；
- 等 gRPC 服务等满 45 s 预算后返回 "starting" —— **这个"失败"预期内，不是故障**。

### 4.3 完整时序（冷机 → 出值）

```
t=0      冷机：无 LabVIEW.exe，gRPC 死
t=0      lvai_ensure_labview(45) → LabVIEW.exe 起来（PID 就位，Responding=True）
t≈45s    convert ×3 (backend:"pylabview")：786 / 698 / 1588 ms
t≈48s    run ×2 (backend:"pylabview", 经 ActiveX)：各 3 ms
         → Sum=15, Count=5, Mean=3.00000000000000   ← N=5
         → Sum=6,  Count=3, Mean=2.00000000000000   ← N=3
```

**认知纠偏**：`ensure_labview` 返回 "starting"/错误，但 LabVIEW.exe 已经在跑——
返回体的 `startedByThisCall` 和任务管理器才是判据，不要被 gRPC 等待超时吓退。

### 4.4 为什么这很重要

之前的结论是"pylabview-only 闭环，前提是 LabVIEW.exe 在跑"。现在这个前提被
推进到**"装了 LabVIEW 的机器"即可**——CI 节点、夜间批跑、别的同事的电脑，
都可以无人值守。

## 5. 突破二：无 IDE 直驱（`scripts/mcp_call.py`）

### 5.1 原理：MCP stdio 就是换行分隔的 JSON-RPC

`LabVIEWMCP.exe` 以 stdio 模式运行时（仓库根 `.mcp.json` 就是这么配的），
每行一条 JSON-RPC 消息。客户端要做的事只有：

```
1. spawn 进程，接好三根管子（stdin/stdout/stderr）
2. initialize 握手（protocolVersion + capabilities + clientInfo）
3. 发通知 notifications/initialized
4. tools/list / tools/call，按 id 匹配响应
```

没有 SDK 依赖，纯标准库。**agent 不需要被"赋予"MCP 工具——它自己就能成为 MCP 客户端。**

### 5.2 三条命令上手

```bash
# 列出全部 99 个工具（顺便存档工具面，用于 diff 上游版本）
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" list --out tools.json

# 环境体检
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" call lvai_status

# 调一个工具：参数用 JSON（复杂参数写进文件，避免 shell 转义地狱）
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" call lvai_convert_aixml_to_vi ^
    --args-file args.json --timeout 300
```

`--args-file` 的内容（注意 Windows 路径的 JSON 转义）：

```json
{
  "aiXmlFilePath": "C:\\LV_AUTOTEST\\gen\\p6\\Multi VI Demo.aixml.xml",
  "viPath": "C:\\LV_AUTOTEST\\gen\\p6\\Multi VI Demo.vi",
  "backend": "pylabview",
  "timeoutSeconds": 240
}
```

### 5.3 实现要点（60 行核心逻辑）

- **reader 线程**：后台逐行读 stdout、解析 JSON；带 `id` 的进响应队列，不带的按通知记日志。
- **id 匹配 + Event**：`_request()` 登记一个 `threading.Event`，响应到达即唤醒；超时则摘除。
- **退出码约定**：0 成功；2 传输/握手错误；3 工具返回 `isError`；4 超时——CI 可直接分支。
- **stderr 全程留痕**：每次调用即一份 transcript，天然满足"证据进 artifacts"的仓库纪律。

### 5.4 为什么这很重要

| 场景 | 之前 | 现在 |
|---|---|---|
| agent 框架不支持 MCP 挂载 | 做不了 | `mcp_call.py` 直驱 |
| CI / 裸 shell / 定时任务 | 做不了 | 同上 |
| 换语言/换框架 | 等适配 | 任何能 spawn 进程的环境 |
| 复现某轮研究 | 要搭一样的 IDE 环境 | `git clone` + 三条命令 |

## 6. 组合拳：从零到出值的最短命令序列

```bash
# 0) 冷机起步：拉起 LabVIEW（gRPC 不来也无妨）
python scripts/mcp_call.py --server <SRV> call lvai_ensure_labview --args-file args-ensure.json

# 1) 先子 VI、后调用方 —— 顺序是硬约束（见第 8 节坑位 #1）
python scripts/mcp_call.py --server <SRV> call lvai_convert_aixml_to_vi --args-file conv-accumulate.json
python scripts/mcp_call.py --server <SRV> call lvai_convert_aixml_to_vi --args-file conv-mean.json
python scripts/mcp_call.py --server <SRV> call lvai_convert_aixml_to_vi --args-file conv-top.json

# 2) 两点实跑验证
python scripts/mcp_call.py --server <SRV> call lvai_run_vi_and_read_values --args-file run-n5.json
#   → Sum=15, Count=5, Mean=3.00000000000000
python scripts/mcp_call.py --server <SRV> call lvai_run_vi_and_read_values --args-file run-n3.json
#   → Sum=6, Count=3, Mean=2.00000000000000
```

Round 20 的 9 次调用（status/ensure/convert×3/run×2/extract/list）**全部**经此脚本完成。

## 7. 本轮实测数据（可直接引用）

| 环节 | 数值 | 备注 |
|---|---|---|
| `lvai_status`（冷机） | 11 个候选端口全不可用 | 预期现象，非故障 |
| `lvai_ensure_labview` | 45 s（烧满预算），`startedByThisCall:true` | LabVIEW 2026 64-bit 自启 |
| convert（3 份 AIXML） | 786 / 698 / 1588 ms，全部 `execState=1` | 与 R15 的 0.5–1.5 s 吻合 |
| run（ActiveX） | 3 ms/次，`via=ActiveX` | 两个输入点 |
| 验证 | N=5 → 15/5/3.0；N=3 → 6/3/2.0，逐位吻合 | Call 双向接线被数值证明 |
| 工具面 | 99（94 lvai_* + 5 pylv_*），v2.0.1 | 上游 v2.3.1 已到 114 |

## 8. 边界与坑位清单（划重点）

1. **Call 解析查磁盘，不查 IDE 内存。** pylabview composer 从被调 .vi **文件**读连接器
   窗格来对上 Call 端子。所以：**子 VI 必须先转出 .vi、调用方后转**——顺序错了就
   解析不到。R6 配方里的 `openVI:true` 属 gRPC/NI 路线，pylabview 路线接受并忽略它。
2. **`ensure_labview` 的 gRPC 等待超时是正常返回**，判据是 LabVIEW.exe 进程
   与 `startedByThisCall`，别把 "starting" 当失败。
3. **gRPC-only 工具在冷启动闭环里不可用**（validate/generate/graft 等）——合成与实跑
   都有 pylabview 等价物，损失的是 NI 官方校验器。
4. **PowerShell 传 JSON 参数是转义地狱**：一律用 `--args-file`，别手拼命令行 JSON。
5. **上游升级会覆盖本地补丁**（`resolve.py` 选版补丁，决定 pylabview 读哪个 LabVIEW
   版本的语料）。升级 v2.3.1 后必须重打，否则读库回落到旧版本。
6. **类端子语法至今缺失**（上游 v2.3.1 仍未支持 AIXML 写类说明符常量）——面向对象
   动态派发的程序目前仍做不出来，这不是环境问题，是表达力边界。
7. **indicator 默认值是负控哨兵**：若 Call 空接（静默失败），Sum/Count 会读 0。
   两点不同输入 → 两个不同手算输出，是最便宜的"接线证明"。

## 9. 团队上手 checklist

1. 确认机器装了 LabVIEW（64-bit，2026 语料最佳）与 `LabVIEWMCP.exe`（本机 `C:\Users\heiyashi\labview-mcp\bin\`）。
2. `git clone` 本仓库，内置 Python 在 `%LOCALAPPDATA%\LabVIEWNativeMCP\runtime\python.exe`（3.12，无需装任何包）。
3. 复制 `research/00-status.md` §8 的复现命令块，替换 `<SRV>` 与路径。
4. 先跑 `call lvai_status` 看环境，再 `call lvai_ensure_labview` 冷启动。
5. 每步输出存进 `research/artifacts/roundNN/`——证据链是这个仓库的立身之本。

## 10. 仓库内延伸阅读

- `research/29-multi-vi-orchestration-pylabview.md` —— 本分享的数据来源（Round 20 全记录）
- `research/00-status.md` —— 看板：能力地图 / 闸门 G0–G5 / 优先级 P1–P10 / 环境存活判据
- `research/06-best-practices.md` —— 37 条已固化铁律（端子名查不猜、SR 种子在根层、conIdx 等）
- `examples/multi-vi-demo/` —— 可直接重建复跑的多 VI 示例（3 AIXML + 3 .vi）
- `scripts/mcp_call.py` —— 本文第 5 节的直驱脚本（60 行，纯标准库）
