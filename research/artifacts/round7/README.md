# round7 产物清单（研究第七轮：bind_pane_typedef 竞态根因 + 一条边修复）

对应文档：`../../15-bind-pane-typedef-race.md`。

环境：LabVIEW 2026 26.3.1f1 中文版 + LabVIEWMCP 2.0.1。本轮全部走 **pylabview
（ActiveX）路线**（grpc 路线对 `lvai_bind_pane_typedef` 的 bundled helper 报
helperAixmlInvalid，见 `results/exp-d-grpc-route-rejected.json`）。

## 目录

| 目录 | 内容 |
|---|---|
| `results/` | 5 个实验的完整测量记录（exp-a ~ exp-e，含五点读回原始数组） |
| `bind-helper/` | 仪器化 helper 的 AIXML 源：v1（原版结构 + 五点读回 + Replace 活性探针）、v2（v1 + 一条数据流边） |
| `fixtures/` | 复现用 fixture 源：5 个类成员 VI 的 AIXML + `Profile Gen.lvclass` / `.lvproj` + `Setpoint.ctl` / `Unit.ctl` |
| `file-evidence/` | 文件级真值（pylv_extract 产物，只要文本件）：racy-v1 后 0 个 .ctl；fixed-v2 后各 2 个 .ctl |

## 一句话结论

原版 `lvai_bind_pane_typedef` 的**保存链与绑定循环之间没有数据流边**，`Save.Instrument`
可能在 `Control.Replace` 之前写盘——工具报全成功而文件里 0 个 typedef（竞态，概率性）。
**修复 = 一条边**：把绑定循环 replace-errors 数组的首元素（Index Array）接入
`LVClass.Open` 的 error in 与 Replace 后 `Controls[]` 读回的 error in，保存链即被 gate
在绑定循环之后。实验 C（坏档修复）+ 实验 E（冷启干净首跑）双重验证。

## 关键文件

| 文件 | 说明 |
|---|---|
| `bind-helper/bind-helper-instr-v1.aixml.xml` | 仪器化 v1：五点读回（before / after-Replace / after-Save / after-class-Save）+ True 帧内 Replace 活性探针（error 1055 = 真替换） |
| `bind-helper/bind-helper-instr-v2.aixml.xml` | 仪器化 v2：仅多一个 `zero` 常量 + 一个 `Index Array`（array=绑定循环 `4259.errs`，index=0）+ 两处 error in 重接 |
| `results/exp-b-race1-v1-racy-reproduced.json` | 竞态复现：terminalsBound=2、error 全 0、两探针均 1055，而文件 0 个 typedef |
| `results/exp-c-race1-v2-fixed.json` | 同档修复：一条边之后 verified=true |
| `results/exp-e-race2-v2-cold-first-run.json` | 冷启干净首跑：五点读回 `[T,F,F,T]→[T,T,T,T]→…` |
| `file-evidence/after-v1-racy/Race1.aixml_FPHb.xml` | grep `.ctl` 名 = 0 命中（只有类私有数据簇 Profile Gen.ctl） |
| `file-evidence/after-v2-fixed/Race1.aixml_FPHb.xml` | `Setpoint.ctl`×3、`Unit.ctl`×3 |
| `file-evidence/after-v2-cold/Race2.aixml_FPHb.xml` | 同上 |

## 复现要点

1. fixture 生成：`fixtures/*.aixml.xml` → `lvai_convert_aixml_to_vi`（Race1/Race2 需
   `lvai_add_class_method` 把 obj in/out 从 path 占位重定型为类）。
2. 竞态复现：`lvai_bind_pane_typedef(..., backend="pylabview",
   helperAixmlPath=bind-helper-instr-v1.aixml.xml)`；文件级判据用 pylv_extract 后
   grep FPHb 中的 `.ctl` 名（**不要信内存读回**——LabVIEW 缓存会显示已生效）。
3. 修复验证：同 2 换 `bind-helper-instr-v2.aixml.xml`。
4. 判据铁律：error cluster 全零 ≠ 落盘；文件级校验（无 LabVIEW）是唯一可信判据。
