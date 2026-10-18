# 14 — Round6（三）：数组 / 簇操作节点覆盖面试探

> 标注惯例：【实测】= 本机一手测量数据；【经验】= 通用工程结论。
> 环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1；生成走 grpc AIXML 通道
> （validate → convert），运行走 pylabview（ActiveX）。
> 产物：`research/artifacts/round6/node-probe/`（7 个 AIXML + 5 个 VI）。

前几轮的状态机只用到基础节点（Add / GreaterOrEqual / Select / ShiftReg / Case）。要让 AI 写
**真实算法 VI**，必须覆盖数组与簇这两大类"数据结构"节点。本轮用探针逐一验证 AIXML 能否
表达常用数组/簇节点，并固化正确的终端名与接线范式。

---

## 1. 数组常量字面量语法（先奠基）【实测】

```xml
<Constant _name="Arr A" outputs="value:110.arrA" type="array{int32}" uid="110" uid_parent="root" value="[10,20]"/>
```

- 类型写 `array{<elemType>}`（如 `array{int32}`、`array{double}`）。
- 字面量写方括号 `[a,b,c]`，字符串元素加引号 `"x"`。
- 数组 Indicator 同写法：`type="array{int32}" value="[]"`。

---

## 2. 数组节点覆盖结果（12 个，全部通过）【实测】

探针 `array-ops.aixml.xml` + `array-extra.aixml.xml`，对照 `lvai_aixml_reference` 的终端名，
全部 `validate(0) → convert → run(pylabview)` 命中预期值：

| 节点 | 关键终端名（inputs → outputs） | 验证（输入 → 输出） |
|---|---|---|
| `Build Array`（组元素） | `element:`×N → `appended array:` | `[1],[2],[3]` → `[1,2,3]` |
| `Build Array`（`concat="true"` 拼接） | `array:`×N → `appended array:` | `[10,20]+[30]` → `[10,20,30]` |
| `Index Array` | `array,index` → `element`（两个 `index:` 扩成两个 `element`） | `[10,20,30]` idx1 → `20` |
| `Array Size` | `array` → `size(s):` | `[10,20,30]` → `3` |
| `Array Subset` | `array,index,length` → `subarray:` | `[10,20,30,40]` idx1 len2 → `[20,30]` |
| `Insert Into Array` | `array,index,new element/subarray` → `output array:` | `[10,20,30]` idx0 插99 → `[99,10,20,30]` |
| `Delete From Array` | `array,length,index` → `array w/ subset deleted:,deleted portion:` | 同上 idx1 len2 → `[10]` / `[20,30]` |
| `Initialize Array` | `element,dimension size` → `initialized array:` | `7`×3 → `[7,7,7]` |
| `Search 1D Array` | `1D array,element,start index (0)` → `index of element:` | `[10,20,30]` 找30 → `2` |
| `Replace Array Subset` | `array,index,new element/subarray` → `output array:` | `[10,5,8,3,20]` idx2 换99 → `[10,5,99,3,20]` |
| `Array Max & Min` | `array` → `max value,max index (indices),min value,min index (indices)` | `[10,5,8,3,20]` → 20@4 / 3@3 |
| `Reverse 1D Array` | `array` → `reversed array:` | `[10,5,8,3,20]` → `[20,3,8,5,10]` |

### 2.1 二维索引范式（重要补充）【实测 / 参考】

`Index Array` 与 `Replace Array Subset` 支持 `dimensions="2"`，**被禁用的维度其终端名加
`disabled ` 前缀**——禁用哪个维度就取"整行"或"整列"，这是把"取一个元素"变成"取整行/整列"
的唯一机制（不是形式，是语义）：

```xml
<!-- 取一整列（禁用行）：行在前、列在后，终端顺序必须遵守 -->
<Node _name="Index Array" dimensions="2"
      inputs="array:40.all,disabled index (row):,index (col):23.value"
      outputs="element:41.element" uid="41" uid_parent="root"/>
<!-- 取一个元素：两个索引都接线 -->
<Node _name="Replace Array Subset" dimensions="2"
      inputs="array:705.value,index (row):1367.value,index (col):1413.value,new element/subarray:1259.value" .../>
```

---

## 3. 簇节点 / 范式（5 个，全部通过）【实测】

### 3.1 簇字面量常量（最稳）【实测】

```xml
<Constant _name="Named Cluster" outputs="value:130.clu"
          type="cluster{int32.Field A,string.Field B,double.Field C}"
          uid="130" uid_parent="root" value="[1,&quot;two&quot;,3.5]"/>
```

- 类型 `cluster{<type>.<name>,...}`；字面量 `[v0,"v1",v2]`。实测回读字段名与值全对。

### 3.2 Bundle 是**纯追加**语义——这是本轮最关键发现【实测】

**错误写法（必错）**：只写 `element:` 输入、不提供 `cluster:` 基：

```xml
<Node _name="Bundle" inputs="element:101.value,element:120.two,element:121.d35"
      outputs="output cluster:150.clu" .../>
```

composer 会把**第一个 `element:` 提升为 `cluster:` 追加基**，结果产出 2 元素簇（与 3 元素
指示器冲突报错），或直接损坏。

**错误写法（必错）**：用 `cluster{}`（未定型空簇）作基——报"常量包含未定义类型 / 已连接两个
包含不同内容的簇"。

**正确范式（已验证产出 `[1,two,3.5]`）**：提供一个**已定型但为空的簇常量**作 `cluster:` 基，
再追加 `element:` ：

```xml
<Constant _name="Empty Base" outputs="value:140.base"
          type="cluster{int32,string,double}" uid="140" uid_parent="root" value=""/>
<Node _name="Bundle" inputs="element:101.value,element:120.two,element:121.d35,cluster:140.base"
      outputs="output cluster:150.clu" uid="150" uid_parent="root"/>
```

> **经验铁律**：在 AIXML 里"从独立线新建一个簇"必须用 `value=""` 的**类型化空簇常量**作
> 追加基；`cluster{}` 不行，`element:` 裸写也不行。Append 语义下没法用无基方式构建。

### 3.3 Unbundle / Bundle By Name / Unbundle By Name【实测】

```xml
<Node _name="Unbundle"   inputs="cluster:150.clu" outputs="element:151.a,element:152.b,element:153.c" .../>
<Node _name="Bundle By Name" fields="Field B"
      inputs="Field B:122.repl,input cluster:130.clu" outputs="output cluster:154.clu2" .../>
<Node _name="Unbundle By Name" fields="Field A,Field C"
      inputs="input cluster:154.clu2" outputs="Field A:155.a,Field C:156.c" .../>
```

- `Bundle By Name` 的输入顺序：**字段在前、`input cluster` 压尾**（参考 §8 实测）。
- 验证：`Bundle Out=[1,two,3.5]`；`Unbundled A/B/C=1/two/3.5`；
  `BundleByName Out=[1,TWO-REPLACED,3.5]`；`ByName A/C=1/3.5`。

---

## 4. 覆盖盲区（必须记录）【实测】

| 节点 | 状态 | 说明 |
|---|---|---|
| `Split Array` | **不被支持** | composer 报 `Unrecognized node type: Split Array`。参考文档亦无条目。 |
| | | 需要"拆分数组"时，用 `Array Subset` + `Delete From Array`（或 Index 循环）绕开； |
| | | 若确需，需从已有 VI 导出该节点反推终端名（参考 §8 的未覆盖节点发现流程）。 |

---

## 5. 复用结论（写进节点覆盖方法论）

1. **数组 12 个常用节点全部可表达**，终端名以 `lvai_aixml_reference` 为准（**终端名须查，不
   可猜**——如 `new element/subarray`、`array w/ subset deleted:` 含空格与标点）。
2. **簇字面量常量**是最稳的建簇方式；**Bundle 必须走"类型化空簇基 + 追加"范式**，否则必错。
3. **二维索引用 `dimensions="2"` + `disabled index (行/列):`**，禁用维度 = 取整行/整列。
4. **`Split Array` 当前不可用**，用 `Array Subset` / `Delete From Array` 组合替代。
5. 探针套路：`validate → convert → run(backend="pylabview")` 读回字面量核对，比只看
   execState 更可靠（pylabview 把 `[]` 具体化为单元素等运行路线细节需对照）。

---

## 6. 产物索引

`research/artifacts/round6/node-probe/`：

| 文件 | 说明 |
|---|---|
| `array-ops.aixml.xml` / `Array Ops Probe.vi` | 数组 8 节点（Build/Index/Size/Subset/Insert/Delete/Init/Search） |
| `array-extra.aixml.xml` / `Array Extra Probe.vi` | 数组 4 节点（Replace/Max&Min/Reverse；Split Array 已证不支持并移除） |
| `cluster-ops.aixml.xml` / `Cluster Ops Probe.vi` | 簇 4 节点（Bundle/Unbundle/BundleByName/UnbundleByName，正确追加范式） |
| `cluster-literal.aixml.xml` / `Cluster Literal Probe.vi` | 簇字面量常量 |
| `bundle-only.aixml.xml` | 反例：裸 `element:` 被提升为基 → 错簇（证据） |
| `bundle-empty.aixml.xml` | 反例：`cluster{}` 未定型 → 校验拒绝（证据） |
| `bundle-typed-base.aixml.xml` / `Bundle Typed Base Probe.vi` | 正例：类型化空簇基 + 追加 → `[1,two,3.5]` |

> `bundle-only` / `bundle-empty` 是"踩坑证据"，保留以警示 Bundle 追加范式，不单独运行。
