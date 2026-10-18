# 13 — Round6（二）：状态机模板参数化——状态表 → AIXML 生成器

> 标注惯例：【实测】= 本机一手测量数据；【经验】= 通用工程结论。
> 环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1；生成走 grpc AIXML 通道
> （validate → convert），运行走 pylabview（ActiveX）。
> 产物：`research/artifacts/round6/state-machine/`（生成器 + 3 个状态表 + 3 套 AIXML/VI）。

Round4 证明了"手写出一个正确的状态机 AIXML"可行（内联枚举、SR 直读、每帧全 Out 隧道、cond
隧道 + Condition 直读）。但手写不可复用。本轮把状态机**参数化**：喂一张状态表 JSON，
即可产出可运行的状态机 AIXML——让 AI 从"画状态机"降级为"填表"。

---

## 1. 输入格式（状态表）

```json
{
  "name": "Traffic Light",
  "vi_name": "Traffic Light.vi",
  "max_cycles": 3,
  "states": [
    {"name": "Green",  "duration": 3},
    {"name": "Yellow", "duration": 1},
    {"name": "Red",    "duration": 2}
  ]
}
```

- `states` 按**转移顺序**排列；第 i 态的下一态 = `(i+1) % n`（循环机）。
- `duration` = 该态停留的 tick 数（态内计时）。
- `max_cycles` = 跑满几个完整循环后停止（`cycles+1 >= MaxCycles` 触发 cond 停止）。

调用：`python gen_statemachine.py <table.json> <out.aixml.xml>`。

---

## 2. 生成器产出的 AIXML 结构（全部遵循 Round4 实测规则）

```
<VI>
  Control  Max Cycles                       ; 根级控件，种子网 value:100.value
  Constant Init State (enum value=0)        ; 根级种子
  Constant Zero / One
  FreeLabel
  Structure "While Loop" uid=200
    Tunnel In1   (Max Cycles 进循环)        ; 输出网 211.max
    Tunnel Out1  mode="index" (History 收集当前状态网)
    ShiftReg state  (Left 种子 Init State; Right 接 Case 隧道 422.value)
    ShiftReg tick  (Left 种子 Zero;     Right 接 423.value)
    ShiftReg cycles(Left 种子 Zero;     Right 接 424.value)
    Structure "Case Structure" selectin="202.value" uid=202
      CaseFrame "Green"  selector="&quot;Green&quot;"  uid=1000
        Add(tick+1) → GreaterOrEqual(tick+1>=duration)
        Select next_state  (t: Next态常量, s: 到时, f: 当前态网 202.value)
        Select tick_out    (t: 0,        s: 到时, f: tick+1)
        末态额外：Add(cycles+1)→Select(cycles)
                  GreaterOrEqual(cycles+1>=Max)→Select(cond)
        4 个 Out 隧道全部显式赋值
      CaseFrame "Yellow" uid=1010 ...
      CaseFrame "Red"    uid=1020 ...（末态，含 cycles/cond 计算）
      Tunnel Out1..Out3 (state/tick/cycles 隧道输出)
      Tunnel Out4 cond="true"  (cond 隧道)
    Condition inputs="425.value" value="stop"   ; 直读 cond 隧道输出网
  Indicator Final State / Final Tick / Cycles / History
```

**关键设计点（与 Round4 规则一一对应）**：

1. **状态类型 = 内联枚举 `uint16{Green,Yellow,Red}`**（字符串 Case 不可手写——Round4 已证）；
   帧 selector 用项名加引号 `selector="&quot;Green&quot;"`。
2. **selector 规范网名 `<Case自身uid>.value`**（本例 `202.value`）；帧内 `Select` 的
   `f:` 也直读这个网，保证未到时时保持当前态。
3. **帧内可直读循环级 SR 网**（`234.tick` / `237.cycles`），只有回写走 Out 隧道——
   NI 官方状态机同形态。
4. **每帧给全部 4 个 Out 隧道显式赋值**（空 `inputs="value:"` 会报"隧道未赋值"）。
5. **停止走 `cond="true"` 隧道 + Condition 直读**（`inputs="425.value"`）；Condition 读
   SR Right 输出网会误报成环，故读 Case 隧道输出网。
6. **终值必须经 SR**：Indicator 读 SR 的 Right 输出网（`290.final_state` 等），不能读
   Case 隧道（隧道值是每次迭代的线，末帧是 Stop，直读得 0）。
7. **History 经 While 级 `mode="index"` Out 隧道**收集每次迭代的状态网（`202.value`），
   自动按迭代追加成数组。
8. **uid 一律 ≥100**，帧基址从 `1000+i*10`（避开循环级 200-303）。

---

## 3. 重大发现：单帧 Case 是 composer 盲区【实测】

最初用同一套生成器生成 **n=1（单状态机）** 时，`convert` 出的 VI `execState 0`（损坏）。
回导（`export-heartbeat*.xml`）揭示：composer 把每帧的跨边界读取各自建成 Case 级输入隧道
（In1..In13），却只接到"属主"帧，另一帧留下 `value:` 全空的隧道桩——导致断头连线。

尝试补一个显式 `selector="&quot;Default&quot;"` 帧（Round4 证实方言支持）**无效**：反而制造
更多断头（另一帧仍空桩）。

**根因**：composer 对"只有 1 个可选项枚举 selector"的 Case Structure 处理有缺陷，必产出坏 VI
（n≥2 的 3 态/4 态机器全部正常）。

**规避（已落进生成器）**：`gen()` 检测到 `len(states)==1` 时**根本不生成 Case Structure**，
改为 `gen_single()`——单态机本无状态转移，把"计时 + 计数 + cond 停止"的直线逻辑放 While
循环内即可（状态值恒为初始态常量，Final State 指示灯直接读常量，History 经 In 隧道把常量
送进循环再被 index 隧道收集）。重构后**多态机字节级回归通过**，单态机直线变体运行全中。

> 这是比 Round4 "字符串 Case 不可手写" 更隐蔽的第二个 Case 陷阱，记入方法论：
> **能避免就避免单选项枚举 selector 的 Case**；若业务确实需要，改用直线逻辑或显式
> 两个枚举项。

---

## 4. 全链路验证（3 个领域，全部通过）【实测】

| 状态机 | 状态（duration） | max_cycles | 预期迭代 | 实测 History | Cycles | Final State | Final Tick |
|---|---|---|---|---|---|---|---|
| Traffic Light | Green3 / Yellow1 / Red2 | 3 | 18 | `[0,0,0,1,2,2]×3`（18 项） | 3 | 0 (Green) | 0 |
| Washing Machine | Soak2 / Wash3 / Rinse3 / Spin4 | 2 | 22 | `[0,0,1,1,1,2,2,3,3,3,3]×2`（22 项） | 2 | 0 (Soak) | 0 |
| Heartbeat（单态） | Only6 | 3 | 6 | `[0,0,0,0,0,0]`（6 项） | 3 | 0 (Only) | 0 |

- **Traffic Light / Washing Machine**：经 `validate(0) → convert → run(pylabview)` 全部命中
  上表预期，证明生成器对**不同状态数（3 / 4）**与**不同领域**通用。
- **Heartbeat**：触发 n=1 直线变体，运行全中，证明单态机边界已被生成器正确处理。

---

## 5. 复用结论（写进状态机方法论）

1. 状态机可**参数化生成**：状态表（状态名 + 时长 + 循环数）→ AIXML，无需手写。
2. 生成器已封装全部 Round4 易错点（内联枚举、SR 直读、全 Out 隧道、cond 隧道 + Condition
   直读、终值经 SR、History index 隧道、uid 基址避让）。
3. **新增铁律**：单选项枚举 selector 的 Case 必坏，单态机改用直线逻辑（`gen_single`）。
4. 工作流不变：`validate → convert → run(backend="pylabview")` 三步全链路。

---

## 6. 产物索引

`research/artifacts/round6/state-machine/`：

| 文件 | 说明 |
|---|---|
| `gen_statemachine.py` | 状态表 → AIXML 生成器（含 n=1 直线变体） |
| `traffic-light-table.json` / `.aixml.xml` / `Traffic Light.vi` | 3 态交通灯，18 迭代 |
| `washing-machine-table.json` / `.aixml.xml` / `Washing Machine.vi` | 4 态洗衣机，22 迭代 |
| `heartbeat-table.json` / `.aixml.xml` / `Heartbeat.vi` | 单态心跳（直线变体） |

复现：`python gen_statemachine.py traffic-light-table.json traffic-light.aixml.xml` →
`lvai_convert_aixml_to_vi` → `lvai_run_vi_and_read_values(backend="pylabview")`。
