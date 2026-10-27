# Round 17 — Complex-Demo Showcase：闭环不依赖 gRPC，循环方言正式落地

> 本轮在线（2026 工位），但 **gRPC / Nigel AI 服务本会话未启动**（LabVIEW.exe 在跑，但
> `lvai_status` 报 "Could not find a port serving lvai.LVAI"）。无人值守无法手动开 Nigel，
> 于是把整条 **AI→AIXML→编译→运行** 链路切到 **pylabview 后端**跑通，并由此把"循环方言"这块
> 长期只有离线稿、从未真正编译过的空白补上了。一句话：**闭环不再依赖 gRPC**；**LV020 循环边界规则**落成。

---

## 1. 环境：gRPC 掉了，但闭环照样走

| 读数 | 值 | 含义 |
|---|---|---|
| `lvai_status` | `errorKind: InvalidOperationException`，50 个候选端口全 `Unavailable`/`DeadlineExceeded` | **gRPC / Nigel 未启动**（IDE 在，但 AI 服务没起） |
| `tasklist` | `LabVIEW.exe` + 2× `LabVIEWMCP.exe` 都在 | LabVIEW 进程存活、可响应 ActiveX |
| pylabview 路线 | `pylv_status` 健康（resolve.py 补丁取最高版本 = 2026） | 纯 Python  composer + ActiveX 运行，全程不需要 gRPC |

**关键结论（新）**：`lvai_convert_aixml_to_vi(backend:"pylabview")` 用 pylabview 自带的
composer 把 AIXML 写成 `.vi`（**不需要 NI 的 gRPC ConvertAIXMLToVI RPC**）；
`lvai_run_vi_and_read_values(backend:"pylabview")` 经 LabVIEW 的 ActiveX 服务器实跑。
只要 `LabVIEW.exe` 在跑，整条链路就通——**gRPC / Nigel 关掉不再是 blockers**。

> 顺带：pylabview 的 `versionWarning` 仍写着 "LabVIEW 2018 is in use"，但本机是 2026、
> 写出的 `.vi` 带 2026 戳且实跑正确。这是 pylabview 版本探测的** cosmetic bug**（被
> Round14 的 resolve.py 补丁与自身探测逻辑搞混），不是真问题，忽略即可。

---

## 2. 核心产物：一个真正"复杂"的 VI

`examples/complex-demo/Accumulator.vi` —— While Loop + **四个 shift register**，
迭代 `N` 次（第 k 次元素 = k+1），累计 **Sum / SumSq / Product**，并用 `Condition` 节点
在 `iter1 >= N` 时退出循环，输出 `Done=true`。这不是叶子节点堆砌，而是带**循环、寄存器、
算术、条件终止**的真算法。

**实测（pylabview 后端，两次不同输入，证明循环真的在迭代而非返回常量）**：

| N | Sum | SumSq | Product | Done | 手工核对 |
|---|---|---|---|---|---|
| 3 | 6  | 14 | 6   | true | 1+2+3=6；1+4+9=14；1·2·3=6 ✓ |
| 5 | 15 | 55 | 120 | true | 1+…+5=15；1+…+25=55；1·…·5=120 ✓ |

读盘（`.vi` 落盘 6707 B）+ 实跑（数值逐位吻合）= 真成功，不看任何 `ok` 自述。

**配套**：`research/artifacts/round17/loop-probe.aixml.xml`（单 shift register 计数探针，
用来隔离验证循环方言的最小样本，Count=N 实测通过）。

---

## 3. LV020 落成：循环方言的边界规则（本轮最大收获）

`research/artifacts/round16` 里的 `traffic-light.aixml.xml` 是**离线轮写的、从未真正编译过**
的循环样本，它把 `Zero`/`One` 常量放在 **root**，又在循环内被 `Add` 等节点直接消费——
这恰好踩中 pylabview composer 的硬规则。本轮用了三个来回才把方言钉死：

1. **第一版**（常量在 root，被循环内节点消费）→ 拒：`net '4203.one' crosses a diagram
   boundary without a tunnel`。根因：root 常量进循环内节点必须走 Tunnel。
2. **第二版**（把 `Zero`/`One` 挪进循环内）→ 拒：`net '4202.zero' crosses a diagram
   boundary without a tunnel`。根因：shift register 的 `Left` 端子**在循环边界上**，循环内
   常量喂它等于"从内穿到边界"，照样算越界。
3. **第三版（正解）**：`Zero`/`One` **留在 root**（喂 shift register `Left`，外→外合法），
   同时 `One` 额外经 `Tunnel In2` 送进循环内给 `Add` 用。全部 `errorCode 0`、`execState 1`。

> **LV020 — 线不能隐式穿循环边界，除非走 Tunnel（对 LV012 的实例化）**：
> - 喂**循环内节点**的常量 → 必须经 `<Tunnel>` 进循环。
> - 喂 **shift register `Left`/`Right` 端子**（它们贴在循环边界上）的常量 → 必须留在
>   **root 图**，直连 `Left`；**不能**放进循环内。
> - shift register 的 `Right`（循环出口）喂 root 级 indicator 是**豁免**的越界，允许。
> - 推论：`traffic-light.aixml.xml` 旧稿里"root 常量 → 循环内节点"的写法在真机上会拒；
>   它之所以一直没爆，是因为 Round6 是离线轮、从没编译过。

这条规则的价值：之前"AI 能不能写带循环的 LabVIEW"只有**离线样本**、没有**真机证据**；
现在有了 `loop-probe` + `Accumulator` 两份真机跑通的循环样本，循环方言从"猜的"变成"验过的"。

---

## 4. 闭环配方（pylabview-only，写入 00-status §8 第 6 段）

```bash
# 编译：pylabview 自带 composer，不需要 gRPC / Nigel
lvai_convert_aixml_to_vi(
    backend: "pylabview",
    aiXmlFilePath: "<repo>/examples/complex-demo/Accumulator.aixml.xml",
    viPath:        "<repo>/examples/complex-demo/Accumulator.vi")   # 路径反斜杠（Windows）

# 运行：经 LabVIEW ActiveX（LabVIEW.exe 必须在跑）
lvai_run_vi_and_read_values(
    backend:   "pylabview",
    viPath:    "<repo>/examples/complex-demo/Accumulator.vi",
    inputsJson: '{"N":"5"}')                                        # → Sum=15,SumSq=55,Product=120,Done=true
```

判据：读盘 + 实跑数值，不看 `ok`。`Accumulator.vi` 已提交，可直接跑。

---

## 5. 对看板与最佳实践的影响

- **环境假象第六例**：gRPC / Nigel 没起，表现像"工具全挂"。但 pylabview 后端让闭环照样通——
  这是本项目的"逃生舱"，比"等有人开 Nigel"稳得多。
- **能力地图新增**：AI 写"带循环+多 shift register+条件终止"的算法 VI，端到端跑通（pylabview 后端）。
- **铁律新增 LV020**（见 §3），并据此把 `traffic-light.aixml.xml` 降级标注为"离线稿，未编译"。
- **优先级推进**：原 P4（`layout_diagram`）、P5（`error_list`）确认在 v2.0.1 工具面里
  **不存在**（ToolSearch 只命中 6 个 `lvai_*`：status/dump_schema/convert_vi_to_aixml/
  run_vi_and_read_values/ensure_labview/graft_diagram），这两条继续挂起；本轮用
  "编译+运行真机验证"替代了它们的部分意图（循环样本已验）。

---

## 6. 一句话带走

> **闭环不再被 gRPC 绑死**：gRPC / Nigel 没起时，整条 AI→AIXML→编译(pylabview)→运行(pylabview)
> 链路照样跑，只要 `LabVIEW.exe` 在。**LV020 把循环方言钉死**——常量喂循环内节点走 Tunnel、
> 喂 shift register 端子留 root，否则 composer 拒；据此一个带四寄存器的真算法 VI
> （Sum/SumSq/Product）在 N=3/5 两次输入下数值逐位吻合，成为项目首个真机跑通的"复杂程序"旗舰样例。

---

## 7. 下一步

1. **P1（仍在）**：IDE 手搭"父类型窗格端子"调用方——重定界规则下 AI 生成调用方的唯一对照实验；
   等有人开 Nigel 或升级到 gRPC 在线时再做。
2. **P2**：装 Caraya（VIPM，需联网）→ `generate_test(pylabview)`，把测试层最后一级打通。
3. **P3**：升级 ≥ v2.2.0 → `dump_schema` diff；升级会覆盖 `resolve.py` 补丁须重打。
4. **P4 / P5**：确认 `layout_diagram` / `error_list` 在更高版本是否存在；本机 v2.0.1 工具面无此二者。
5. 把 `Accumulator` 扩成**多 VI 版**（顶层 VI Call 一个子 VI 做迭代、另一个汇总），补上"复杂程序=多 VI 协作"那一块。
