# round6 产物清单（研究第六轮：retarget 根因 + 状态机生成器 + 数组/簇节点覆盖）

对应文档：`../../12-retarget-root-cause.md`、`../../13-state-machine-template-generator.md`、
`../../14-array-cluster-node-coverage.md`。

环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1。
生成走 grpc AIXML 通道（validate → convert），运行走 pylabview（ActiveX）。

## 一、状态机生成器（doc 13）

目录 `state-machine/`：

| 文件 | 说明 |
|---|---|
| `gen_statemachine.py` | 状态表 JSON → AIXML 生成器（含 n=1 直线变体 `gen_single`） |
| `traffic-light-table.json` / `.aixml.xml` / `Traffic Light.vi` | 3 态交通灯，18 迭代，History=[0,0,0,1,2,2]×3 |
| `washing-machine-table.json` / `.aixml.xml` / `Washing Machine.vi` | 4 态洗衣机，22 迭代 |
| `heartbeat-table.json` / `.aixml.xml` / `Heartbeat.vi` | 单态心跳（直线变体，规避单帧 Case 盲区） |

复现：`python gen_statemachine.py <table.json> <out.aixml.xml>` → `lvai_convert_aixml_to_vi`
→ `lvai_run_vi_and_read_values(backend="pylabview")`。

## 二、数组 / 簇节点覆盖（doc 14）

目录 `node-probe/`（7 AIXML + 5 VI）：

| 文件 | 说明 |
|---|---|
| `array-ops.aixml.xml` / `Array Ops Probe.vi` | 数组 8 节点 |
| `array-extra.aixml.xml` / `Array Extra Probe.vi` | 数组 4 节点（Replace/Max&Min/Reverse；Split Array 已证不支持） |
| `cluster-ops.aixml.xml` / `Cluster Ops Probe.vi` | 簇 4 节点（正确追加范式） |
| `cluster-literal.aixml.xml` / `Cluster Literal Probe.vi` | 簇字面量常量 |
| `bundle-typed-base.aixml.xml` / `Bundle Typed Base Probe.vi` | 正例：类型化空簇基 + 追加 |
| `bundle-only.aixml.xml` | 反例：裸 element: 被提升为基（证据） |
| `bundle-empty.aixml.xml` | 反例：cluster{} 未定型被拒（证据） |

## 三、retarget 根因证据（doc 12）

目录 `retarget-evidence/`：

| 文件 | 说明 |
|---|---|
| `Clamp Demo Swapped.vi` / `Clamp Value.vi` / `Clamp Value Alt.vi` / `Clamp Demo Regen.vi` | 运行证据；Alt 即"文件名≠内部Name"的目标 |
| `export-callerF.xml` / `export-swapped.xml` | 决定性 diff：坏者 Call 无端子、三线丢失 |
| `Kappa.vi` / `Caller N.vi` / `kappa.aixml.xml` / `caller-n.aixml.xml` | openVI 配方例一（全值通过） |
| `Sub Zeta.vi` / `Caller Zeta.vi` / `zeta.aixml.xml` / `caller-z.aixml.xml` | Test M：移走子 VI 仍能跑，证 ActiveX=gRPC 同进程 |
| `caller-p2.aixml.xml` | `target="Sub Alpha.vi"` → convert 报 Error 53，证 rebuilt/open_file 子 VI 不可按名解析 |

> 完整中间稿（含 x-* 二进制 bundle 转储、memprobe 备份）保留在本地
> `labview-mcp-research/round6/`，未全部入库以免仓库膨胀；上面是足以复现结论的最小证据集。

## 复现要点

1. 多 VI 稳定配方：子 VI `convert(openVI:true)` → 主 VI `convert` → `run(backend="pylabview")`；
   **调用方链接名必须与被调 VI 内部 Name 一致**（retarget 只改链接记录、不动目标内部 Name，
   遇"文件名≠内部Name"必悬空）。
2. 状态机可参数化生成；**单态机不生成 Case**（单选项枚举 selector 的 Case 必坏，走直线逻辑）。
3. Bundle 是纯追加：建簇必须用 `value=""` 的类型化空簇常量作 `cluster:` 基 + `element:` 追加；
   `cluster{}` 与裸 `element:` 都错。
4. 数组 12 节点可表达；`Split Array` 当前不被 composer 支持，用 `Array Subset`/`Delete From Array` 替代。
5. 终端名须以 `lvai_aixml_reference` 为准，不可猜（含空格/标点，如 `new element/subarray`）。
