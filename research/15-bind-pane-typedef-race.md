# 15 — Round7：`lvai_bind_pane_typedef` 竞态根因与"一条边"修复

> 标注惯例：【实测】= 本机一手测量数据；【经验】= 通用工程结论。
> 环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1。
> 本轮全部实验走 **pylabview（ActiveX）路线**（原因见 §7：grpc 路线在本机被阻断）。
> 产物：`research/artifacts/round7/`（5 个实验 JSON + 仪器化 helper v1/v2 + 4 套 fixture + 3 套文件级证据）。

Round5 留下了".ctl 绑定的最后一公里"：AIXML 生成的 VI 面板上是**普通控件**，要让它绑定
到 `.ctl` 类型定义（typedef），必须靠 `lvai_bind_pane_typedef` 工具（ActiveX 路线）做事后
替换。本轮把这最后一公里打透，过程如下：

1. 发现该工具的**保存链与绑定循环之间存在数据流竞态**——工具报告完全成功
   （`terminalsBound=2`、所有 error cluster 全 0），而**保存下来的文件里一个 typedef 都没有**；
2. 用"五点读回"仪器化 helper 复现竞态、定位根因；
3. 用**一条数据流边**修复并双重验证（修好坏档 + 冷启干净首跑）；
4. 附带确认 grpc 路线在本机对该工具不可用（`helperAixmlInvalid` 清单再添一项）。

---

## 1. 背景：什么是 bind pane typedef，为什么重要

`lvai_bind_pane_typedef(viPath, lvclassPath, projectPath, bindings[], backend)`：
对一个类成员的 VI 面板，把指定终端（如 `Setpoint`、`Unit`）的普通控件**替换（Replace）**
为 `.ctl` 类型定义控件，使 VI 保存后携带 typedef 引用。

这是 AI 生成工业级 LabVIEW 代码的关键一步——真实项目里控件几乎全部走严格 typedef
（改一处类型、全工程联动）。AIXML 生成通道目前**不能**在面板控件上直接声明 typedef
绑定，因此事后绑定是必经之路。

工具自带验证：绑定后会**脱离 LabVIEW**（pylabview 路线直接读文件）检查保存文件里是否
真的有这些 typedef——`verified` 字段。这个独立文件级校验是后来抓住竞态的关键。

---

## 2. 实验矩阵（2026-10-19 ~ 10-20，全部 pylabview 路线）【实测】

| # | 对象 | helper | 结果 |
|---|---|---|---|
| A | `Monitor.aixml.vi`（冷，从未加载） | **原版**（bundled） | **竞态赢了**：verified=true，2 个 .ctl 都在文件里 |
| B | `Race1.aixml.vi`（当天新建，从未加载） | **仪器化 v1**（原版结构+五点读回） | **竞态输了**：工具报全成功，文件里 0 个 typedef |
| C | 同一个 Race1（被 B 弄成"内存已绑定/文件未绑定"） | **仪器化 v2**（+一条边） | **修复生效**：verified=true，文件里 2 个 .ctl |
| D | `Monitor.aixml.vi` | 原版，backend 省略（→grpc） | **路线被拒**：`helperAixmlInvalid`，validate 即失败 |
| E | `Race2.aixml.vi`（冷，从未加载） | 仪器化 v2 | **干净首跑**：五点读回全程自洽，文件级校验通过 |

---

## 3. 根因：保存链与绑定循环之间没有数据流边【实测】

原版 helper 的 BD 图数据流：

```
Controls[] 读取 ─┬─> 绑定循环（For Loop：Search 1D Array 找终端 → Control.Replace）
                 └─> 保存链（LVClass.Open → VI.Save.Instrument → 重开 → 类 Save）
```

两条支路在同一个 `Controls[]` 读取后就**同时就绪**，彼此之间**没有任何数据流边**。
LabVIEW 的调度因此完全自由：`Save.Instrument` 完全可能在绑定循环的 `Replace` 落盘之前
就把文件写完了。此时：

- 内存里：`Replace` 随后生效 → 任何"重开 VI"读到的都是**已绑定**状态（LabVIEW 内存缓存）；
- 文件里：保存先发生 → **一个 typedef 都没有**；
- 工具 indicators：`terminalsBound=2`、每个 error cluster 全 0 → **报告完全成功**。

实验 B 完整拍到了这个分裂态。而且竞态是**概率性**的（实验 A 原版 helper 在冷
Monitor 上就赢了）——这解释了 10-19 的观测：第一次绑定 `bindcheck/` 文件里没有 .ctl，
第二次绑定 `bindcheck2/` 文件里就有了（第二次跑时内存里的 VI 已带 Replace，即使保存
再次抢先，写出去的也是已绑定控件）。工具文档自己也记过同类失败模式
（"a run reported 1 for a file that ended up with none"）。

> 【经验】凡是"改内存 → 保存"两段式 helper，**必须用数据流边把保存链 gate 在改动链之后**；
> 仅靠 error cluster 全零不能证明落盘。文件级校验（脱离 LabVIEW 读文件）是唯一可信判据。

---

## 4. 仪器化方法：五点读回 + Replace 活性探针【实测】

为定位竞态，把 helper 复制为仪器化版本（`lvai_bind_pane_typedef_instr.xml`，v1），
保留全部原 indicators（工具解析不变），新增：

**(a) 五点读回**——在五个时刻读面板全部控件的 `Is Typedef?` / `Typedef:Path`：

| 点 | 时机 | 看到什么 |
|---|---|---|
| 1 | 绑定前 | 真实初始态（冷 VI：obj in/out 是类私有数据类型，Setpoint/Unit 普通） |
| 2 | Replace 后（内存） | **v1 的坑**：该读回挂在第一个 Controls[] 读的 error 链上，会抢跑在绑定循环之前 |
| 3 | `Save.Instrument` 后重开 | LabVIEW 缓存态——**即使文件没绑定，这里也显示已绑定** |
| 4 | 类 `Save` 后再重开 | 同上（缓存） |
| 5 | （工具自带）脱离 LabVIEW 读文件 | **文件真值**——唯一可信判据 |

**(b) Replace 活性探针**——在 Case 的 True 帧里，从 `Replace` 的 error out 串一个
Property Node 去读刚被消费的 refnum：**error 1055 = refnum 已失效 = Replace 真的执行了**；
error 0 = 没替换。实验 B/C/E 全部 1055，证明确实替换了——问题从来不在 Replace 本身，
而在保存时序。

---

## 5. 修复：一条边（v2）【实测】

v2 与 v1 的 diff **只有三处新增**（见 `artifacts/round7/bind-helper-instr-v2.aixml.xml`）：

```xml
<!-- 1. 常量 -->
<Constant _name="zero" type="int32" uid="4160" uid_parent="root" value="0" outputs="value:4160.value"/>
<!-- 2. 对绑定循环的 replace-errors 数组输出取第 0 个元素 -->
<Node _name="Index Array" inputs="array:4259.errs,index:4160.value" outputs="element:4161.cluster" uid="4161" uid_parent="root"/>
```

然后把 `4161.cluster`（replace-errors 数组首个元素）接到两处原来"悬空"的 `error in`：

| 接收方 | 原接线 | 新接线 |
|---|---|---|
| Replace 后 `Controls[]` 读回（uid 4410） | `4245.err`（第一个 Controls[] 读的 error） | `4161.cluster` |
| `LVClass.Open`（保存链入口） | `4410.err` | `4161.cluster` |

效果：**整个保存链（LVClass.Open → Save.Instrument → 重开 → 类 Save）被 gate 在绑定循环
的 replace-errors 数组之后**——循环没跑完，保存不可能开始。同时第二个读回点也真正落到了
循环之后，五点读回全程自洽。

验证（同 fixture、同绑定、同路线，唯一差别就是这条边）：

- **实验 C**（修复坏档）：Race1 被 B 弄成"内存已绑定/文件未绑定"，v2 一跑，
  `verified=true`，文件里两个 .ctl 都在（`extract-race1-after-v2/` 的 FPHb 里
  `Setpoint.ctl`×3、`Unit.ctl`×3）；
- **实验 E**（冷启干净首跑）：Race2 从未加载，五点读回
  `[T,F,F,T] → [T,T,T,T] → [T,T,T,T] → [T,T,T,T]`（普通 → Replace 后绑定 → 保存后绑定 →
  类保存后绑定），工具文件级校验通过。

对照实验 B 的文件级证据 `extract-race1-after-v1/`：FPHb 里 **0 个** .ctl，只有类私有
数据簇（`Profile Gen.ctl`，obj in/out 自带）。

---

## 6. 对 AI 开发 LabVIEW 的意义【经验】

1. **".ctl 绑定"路线打通**：AIXML 生成面板（普通控件）→ `lvai_bind_pane_typedef`
   （pylabview 路线）→ 保存文件携带 typedef。类方法 + typedef 控件 + 多 VI 调用这条
   工业主流形态，现在全链路可用。
2. **修好的 helper 是生成物**：v1/v2 两个仪器化 helper 本身就是 AIXML 写的 VI
   （`lvai_add_class_method` + composer），修复 LabVIEW 工具链缺陷的手段还是 AIXML——
   本轮是"用 AIXML 修 AIXML 工具链"的又一例。
3. **判据升级**：凡 helper 报 success，都要以"脱离 LabVIEW 的文件读回"为准
   （pylv_extract 或工具自带 verified 字段）；内存读回（重开 VI）会被 LabVIEW 缓存欺骗。

---

## 7. 路线事实：grpc 路线对本机该工具不可用【实测】

实验 D：`lvai_bind_pane_typedef` 不带 backend（默认 grpc）→ `helperAixmlInvalid`：
NI ValidateAIXML 拒绝 bundled helper AIXML，中文报错包括"关闭引用: 包含未连线或错误的
接线端 / 调用节点: 无效方法 / 已连接两个不同类型的接线端 / For循环: N未连接"等
（详见 `artifacts/round7/results/exp-d-grpc-route-rejected.json`）。

即：已知的环境问题（`helperAixmlInvalid`，此前只影响面板整理/连接器面板 helper）
**同样影响 bind helper**，且发生在任何实际工作之前。**本轮所有实验因此走 pylabview
路线**——该路线下 helper 由我们自己的 composer 生成（不经 NI 校验），经 ActiveX 运行。

---

## 8. 复现步骤

```text
1. 准备 fixture（AIXML 生成，pylabview 或 grpc 路线均可）：
   - Profile Gen.lvclass + Profile Gen.lvproj（含 Typedefs 文件夹：Setpoint.ctl、Unit.ctl）
   - 类成员 VI：obj in/obj out（path 占位，lvai_add_class_method 重定型为类）
     + Setpoint(double) + Unit(string)，见 artifacts/round7/fixtures/*.aixml.xml
2. 复现竞态（v1）：
   lvai_bind_pane_typedef(viPath=Race1, lvclassPath, projectPath,
     bindings=[{Setpoint→Setpoint.ctl},{Unit→Unit.ctl}], backend="pylabview",
     helperAixmlPath=bind-helper-instr-v1.aixml.xml)
   → 工具可能报 verified=true 或 false；用 pylv_extract 读文件 FPHb 数 .ctl 引用
3. 验证修复（v2）：同 2 换 helperAixmlPath=bind-helper-instr-v2.aixml.xml
   → verified=true，FPHb 出现 Setpoint.ctl/Unit.ctl
4. 文件级判据（无 LabVIEW）：pylv_extract 后 grep FPHb 中的 .ctl 名
```

## 9. 本轮铁律（入 best-practices）

1. **改内存→保存型 helper 必须加数据流边**把保存链 gate 在改动链后；error cluster 全零
   ≠ 落盘。
2. **文件级校验是唯一可信判据**：pylv_extract（无 LabVIEW）或工具 verified 字段；
   LabVIEW 内存缓存会让"重开 VI"读回显示已生效。
3. **bind_pane_typedef 只用 pylabview 路线**（grpc 路线本机 helperAixmlInvalid）。
4. Replace 活性用 error 1055 探针判定（refnum 已消费 = 真的替换了）。
5. 竞态是概率性的：一次成功不代表修复；要在"冷启首跑"和"坏档修复"两种 fixture 上都验证。
