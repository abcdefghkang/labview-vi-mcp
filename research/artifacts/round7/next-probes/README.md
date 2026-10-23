# next-probes — Round8 待跑探针（2026-10-22 预制，未经本机运行）

预制于 LabVIEW 离线会话（MCP disabled、LabVIEW 未启动）。**LabVIEW 在线且升级到
≥ v2.2.0 后按序运行**，结果回填本文档与 `research/16-upstream-tracking-and-event-structures.md`。

## 探针清单

| 探针 | 文件 | 来源 | 测什么 | 预期 |
|---|---|---|---|---|
| P1 | `p1-user-event-two-loops.aixml.xml` | **上游 skeleton 字节级副本**（Zuehlke/labview-mcp v2.0.1 `bin/scripts/aixml-skeletons/`，上游 2026-10-10 实测可跑） | For 源 + While handler + Tick 用户事件 + Stop 静态帧；placeholder payload 形态 | `Ticks Received = 5`，`Error Out.status = false` |
| P2 | `p2-payload-direct-form.aixml.xml` | 按 P1 改写 | payload 直接点名（`fields="Source,Tick,Time"`，Tick 直入 Or），无 placeholder | 同 P1 |
| P3 | `p3-cluster-payload.aixml.xml` | 按上游 t120 形态改写 | 簇 payload `{Last,N}`：Bundle 拍平（typed-empty base + element: 追加，Round6 惯用法）、帧内 `fields="Source,Last,N,Time"` 双元素读出、仅 Last 可停 | `Ticks Received = 3`，`Last N = 2`（Ticks To Send=3） |
| P4 | `p4-two-events-one-registration.aixml.xml` | 按上游 t121 形态改写 | 一个注册两个用户事件（`event source:` 重复输入）、SR 存 Last Count、Tick 停 | `Last Count = 2`（Ticks To Send=3） |
| P5 | `p5-valuechange-timeout-frames.aixml.xml` | 按上游 t88 形态改写 | 静态事件：` "Go": Value Change ` + ` Timeout `（500ms 走结构隧道）+ latched Stop 停；SR 双计数器 | execState 1；置 Go=true、Stop=true 后 `Go Presses ≥ 1` |

## 运行方式（LabVIEW 在线后）

```text
1. 升级 LabVIEWMCP 到 ≥ v2.2.0（XControls / Network Streams 是 v2.0.1 没有的能力），
   重启 LabVIEW，确认 lvai gRPC 服务在（pylabview 路线不依赖它，但运行侧要 ActiveX）。
2. lvai_convert_aixml_to_vi(aixmlPath=<probe 路径>, backend="pylabview", openVI=true)
   —— 注意 backend 必须显式给 "pylabview"：grpc 路线对本机 helper 类文档有
   helperAixmlInvalid 风险，且用户事件在 grpc 路线需三调用（generate → wire_dynamic_events
   → set_event_data_fields）。
3. lvai_run_vi_and_read_values(viPath=<probe .vi>, backend="pylabview",
                               controls={"Ticks To Send": 5})
4. 判据铁律：pylv_extract 回读文件核验（不要信内存/工具自报 success，Round7 竞态教训）。
```

P1 跑通后再跑 P2-P5；任一失败先查 `%TEMP%\LabVIEW_32_*_cur.txt`（~100 DWarn 后日志停写，
需重启 LabVIEW）。

## 已知不确定点（按概率排序）

1. **P5 的 Timeout 隧道接线**：`eventTimeOut` 终端如何喂值（本文档用结构隧道 + 根常量
   500ms）是猜测写法，其余部分均沿用已验证惯用法。失败时先读堆确认该终端接法。
2. **P3 簇字面量常量** `cluster{bool.Last,int32.N}` 作 Create User Event 的 datatype：
   Round6 验证过簇字面量常量与 Bundle 惯用法，但未验证过"簇 datatype 喂 Create User
   Event"这一格。
3. **P4 的 Count payload 直喂** `event data cluster:<循环 i>`：标量直喂在 P1/P2 已验证
   （Greater Or Equal 结果直喂），循环迭代终端直喂未验证。
4. P1 的 Stop 控件在帧内 `<Control uid_parent=<帧>>` 形态沿用上游 skeleton（其
   `Panel Close?`/静态帧同款），本机未复跑过该文档。
