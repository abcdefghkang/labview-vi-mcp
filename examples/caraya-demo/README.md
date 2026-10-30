# Caraya Demo — AI 写测试、AI 跑测试、AI 判对错

Round 22 产物：Caraya 单元测试框架手工安装后的**测试层全链**样例。
被测对象是 [nested-multi-vi-demo](../nested-multi-vi-demo/) 的孙 VI `Double It.vi`
（`x [int32] → Doubled [int32]`，纯乘法）。

## 文件

| 文件 | 来源 | 说明 |
|---|---|---|
| `Test Double It.vi` | `lvai_generate_test` 生成（placeholder 路线） | 3 用例：`doubles 3`（3→6）、`doubles -4`（-4→-8）、`doubles 0`（0→0）；期望常量自动标签 `expected 1/2/3` |
| `run-tests.vi` | `lvai_generate_caraya_test_runner` 生成 | 把同目录测试 VI 的相对路径收进数组，喂 `Caraya.lvlib\3ARun Tests.vi`（`Interactive=FALSE`，报告路径 `.xml`） |
| `TestReport.xml` | Caraya 2.0.0.151 运行写出 | JUnit 格式；当前是恢复后的全绿状态（tests=3 failures=0） |

## 实测判据（全程 `backend:"pylabview"`，证据在 `research/artifacts/round22/`）

| 阶段 | tests | failures | errors | ok | failing |
|---|---|---|---|---|---|
| 正对照（planA） | 3 | 0 | 0 | true | — |
| 负对照：`lvai_set_constant` 把 `expected 2` 6→99 后重跑（planB 步 2） | 3 | **1** | 0 | false | `case:"doubles -4"`（正是被改的用例） |
| 恢复 `-8` 后复跑（planB 步 4） | 3 | 0 | 0 | true | — |

判据读磁盘上的 JUnit 报告，不看工具自述；`kind:"failure"`（断言没过）与
`kind:"error"`（VI 跑不起来）被工具区分——**Broken ≠ Failed**。

## 复现

```bash
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" batch \
  --plan research/artifacts/round22/planA-positive.json \
  --out  research/artifacts/round22/transcriptA-positive.json
python scripts/mcp_call.py --server "C:\path\LabVIEWMCP.exe" batch \
  --plan research/artifacts/round22/planB-negative.json \
  --out  research/artifacts/round22/transcriptB-negative.json
```

前提：LabVIEW.exe 在跑（gRPC/Nigel 不需要）；`vi.lib\addons\_JKI Toolkits\Caraya\`
已安装（手工装 .vip 配方见 `research/31-caraya-testing-layer.md` §1）。

约束备忘：测试 VI 与 runner 必须同目录（runner 按自身位置转相对路径）；
浮点断言是精确相等，用例值选 IEEE754 精确可表的；`casesJson` 的键是被测 VI
端子名（`lvai_vi_terminals` 现查现用，不猜）。
