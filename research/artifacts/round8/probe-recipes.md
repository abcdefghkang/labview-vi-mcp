# Round8 探针配方（离线准备，LabVIEW 在线后按序执行）

> 状态：**【待验证】** 全部未在本机运行。每条给出前置条件、工具调用序列、判据与失败判读。
> 依据：`research/17-complex-program-playbook.md` §1.1/1.2/1.3/1.4/6。
> 下轮第一件事：升级到 ≥ v2.2.0 并 `lvai_dump_schema` 核对 RPC；下列工具名若变化以 schema 为准。

---

## 通用前置

```text
1. 备份 fixture 到 experiments/ 下新目录（不在被 LabVIEW 加载的路径上改）
2. lvai_ensure_labview          # 冷启动正常；starting 再调一次
3. lvai_dump_schema > schema-v2.2.0.json
4. 每个探针用独立 LabVIEW 会话（重启清 1562 / 烧名 / Caraya 陈旧 refnum）
```

---

## P6 — 类方法调用自己的访问器（Round6 遗留问题，上游 2026-09-25 首测路线）

**目标**：验证 `path` 替身 + `lvai_generate_vi` + `lvai_add_class_method(已存在 vi)` 这条
"无 stub"路线在**我们自己的类**上成立；观察 `failedAtStep: execState` 是否仍写出文件；
观察 56002 是否复现（旧版工具）。

**Fixture**：复用 `artifacts/round6/` 的类（含 2 字段 + 访问器），或新建
`Probe.lvclass{double.Gain, double.Current}` + `Read Gain.vi` / `Read Current.vi`。

```text
1. lvai_create_class(path=Probe.lvclass, fields=double.Gain=1|double.Current=2)
2. lvai_create_accessors(class=Probe.lvclass, fields=Gain,Current)
3. lvai_open_file(project=Probe.lvproj, vi=Read Current.vi)      # 只开一个成员
4. 写 AIXML：Read Scaled.vi —— 两个 path 替身端子 + 直接 Call
   <Call target="Probe.lvclass\3ARead Gain.vi" .../>
   <Call target="Probe.lvclass\3ARead Current.vi" .../>
   Multiply → 指示器
5. lvai_generate_vi(aixmlPath=..., viPath=<类目录>\Read Scaled.vi)
   预期：validate 报 Unsupported SubVI（预期）；convert 成功；failedAtStep: execState（预期）；文件写出
6. lvai_exec_state(Read Scaled.vi)     # 此时应为 0
7. lvai_add_class_method(class=Probe.lvclass, vi=Read Scaled.vi,
                         classTerminals=[Probe in, Probe out], dispatch=true)
   预期：ok:true, terminalsRetyped:2
   若 56002 → 关项目、删 .lvproj 中该 VI 的 <Item> 行、重试
8. lvai_exec_state(Read Scaled.vi)     # 判据：1
9. pylv_extract → grep FPHb：class="udClassDDO" 计数 = 2（obj in/out），stdPath 残留 = 0
10. lvai_run_vi_and_read_values(Read Scaled.vi, controls={Gain:2,Current:3}) → 期望 6
```

**判据**：步骤 8 = 1；步骤 9 `udClassDDO`=2 且无 `stdPath`；步骤 10 = 6。
**失败判读**：
- 步骤 5 直接 `Error 53` → 项目上下文不匹配（目标没 through project 打开）
- 步骤 5 `Error 1051` → 该名已被前一次失败烧掉，换新名并重启
- 步骤 7 56002 → loose 项目项，手删 `<Item>`
- 步骤 8 仍 0 → 类没加载/成员归属没写成，查双保存顺序

---

## P7 — 接口 override 保存顺序 A/B（上游 §1.3 定律的本机复现）

**目标**：验证"先 `AddItemFromMemory` 后 `Save.Instrument`"与反序的可执行性差异。

```text
A（错序，对照组）：
 1. lvai_create_interface(ICanScale.lvclass, method=Scale.vi, terminals=[ICanScale in/out, double factor])
 2. lvai_create_class(Scaler.lvclass, fields=double.Gain, parentInterfaces=ICanScale.lvclass)
 3. 脚本化 override（按其文档 §3 的手工顺序，VI 先 Save.Instrument 再 AddItemFromMemory）
 4. 探针 VI：类常量 + 调 Scale → 期望 Error 1003（VI not executable）
 5. {LV.SubVI} Replace 该 override → 期望 Error 1154
B（正序）：
 3'. AddItemFromMemory("Scale.vi") → Save.Instrument → {LV.LVClassLibrary} Save
 4'. 同探针 → 期望 execState 1 且运行正确
```

**判据**：A 复现 1003/1154；B 全绿。若 A 不复现，记录并放弃该对照组（不硬凑结论）。
**成本提示**：这条要手写 AIXML helper，约 4–6 轮；若时间紧可先跑 B 与 P6，P7 延后。

---

## P8 — Caraya 最小套件（测试层首次落地）

```text
1. 被测对象：一个纯计算叶子 VI（复用 P6 的 Multiply 或 Round2 的温度转换）
2. lvai_generate_test(subject=<VI>, cases=[
     {label:"boiling", inputs:{celsius:"100"}, expect:{fahrenheit:"212"}},
     {label:"freeze",  inputs:{celsius:"0"},   expect:{fahrenheit:"32"}},
     {label:"negative-control", inputs:{celsius:"100"}, expect:{fahrenheit:"999"}}])
   预期：route: direct（项目能列出 subject 时），三例断言生成
3. lvai_generate_caraya_test_runner(tests=[<test.vi>], reportPath=<...>.xml)
   注意：报告必须 .xml；Interactive=FALSE
4. 跑 runner → 第一次可能 Error 1 且无报告（重建后假失败）→ 立刻再跑一次
5. 判据：JUnit XML 里 tests="3" failures="1"，失败项正是 negative-control
6. 额外：把测试 VI 移到与 subject 不同的目录再跑一次（验证跨目录直接 Call 成立）
```

**失败判读**：
- `failedAtStep: cases` + `refusal.notOnPane` → 用例里写了 pane 外的名字
- 报告文件不存在 → 扩展名不是 `.xml`
- 两次都 `Error 1` → 不是假失败，查 Caraya 安装与 target 拼写

---

## P9 — 冷启动复核（G5 的最后一步）

```text
1. 产物清单：P6 的 Read Scaled.vi、P8 的 test VI + runner
2. 完全退出 LabVIEW（Stop-Process 后 lvai_ensure_labview）
3. 新会话里直接：lvai_exec_state(<每个产物>)  → 全 1
4. lvai_run_vi_and_read_values(Read Scaled.vi, {Gain:2,Current:3}) → 6
5. pylv_extract 产物，grep 链接路径：相对路径（..\SubVIs\...）为正常，
   绝对路径指向另一个构建目录 = 上游记录的"同名旧构建捕获"缺陷
```

**判据**：全部 `execState 1` 且数值正确；链接记录里没有跨构建的绝对路径。
