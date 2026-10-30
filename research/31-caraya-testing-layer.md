# Round 31（Round 22）：Caraya 装上了——测试层最后一级打通

> 日期：2026-10-30　在线：是　MCP：LabVIEWMCP.exe v2.0.1（99 工具）
> 上一轮：[30-nested-multi-vi-chain.md](30-nested-multi-vi-chain.md)（三层嵌套链 + batch 直驱）
> 本轮回答看板方向 **D（测试）** 的最后一条开放项：Caraya 缺件。

---

## 0. 一句话结论

**Caraya 单元测试框架手工安装成功，AI 经 MCP 的完整测试闭环自此打通**：
`lvai_generate_test` 生成测试 VI → `lvai_generate_caraya_test_runner` 生成 runner →
`lvai_run_caraya_tests` 跑出 JUnit 判据，全程 `backend:"pylabview"`；
正对照 `tests=3 failures=0 ok=true`，负对照（`lvai_set_constant` 改错一个期望值）
`failures=1` 且报告**指名道姓**点出被改的用例，恢复后复绿。判据自始至终来自磁盘上的
JUnit 报告，不看工具自述。

**R13 的"Caraya 缺件"判断被修正**：缺的从来不是 MCP 侧工具——本地 v2.0.1 的 99 个工具
里 `lvai_generate_test`、`lvai_generate_caraya_test_runner`、`lvai_run_caraya_tests`
一应俱全——缺的只是 Caraya 运行时本身（vi.lib 里的 Caraya.lvlib）。装上它，三个工具
原样就能用。

---

## 1. 安装过程（真实形态，含一次返工）

### 1.1 找包

- `github.com/JKI/Caraya` 的 releases API **404**——框架已迁到 **`vipm-io/caraya`**。
  按 repo 名猜地址是死路，`/search/repositories?q=caraya` 一把命中。
- 最新 release **2.0.0**（2025-06-19），资产 `jki_lib_caraya-2.0.0.151.vip`，6,433,804 B。
- 下载走代理（`curl --socks5-hostname 127.0.0.1:10808`），直连 GitHub 依然 000。
- spec 关键行：`Exclusive_LabVIEW_Version="LabVIEW>=20.0"`（2026 满足）；
  无 Pre/Post Install 脚本（纯文件铺设，手工安装合法）；依赖
  `jki_rsc_toolkits_palette>=1.1` 只影响调色板图标，跑测试不需要。

### 1.2 铺文件（.vip 就是 zip）

| 包内组 | 数量 | 目标 |
|---|---|---|
| File Group 0 | 713 | `<LabVIEW 2026 根>`（help/、project/、resource/、`vi.lib/addons/_JKI Toolkits/Caraya/`） |
| File Group 1 | 15 | `vi.lib/addons/_JKI Toolkits/dynamic_palette/`（函数选板 .mnu） |

本机未装 VIPM，用内置 Python 的 `zipfile` 按 spec 解包（写 Program Files 需管理员，
本机 shell 有）。

**一次返工，记下形态**：第一遍把 File Group 0 的 `vi.lib/...` 相对路径拼到了
`vi.lib\addons\_JKI Toolkits\Caraya` 里面，结果整个包在 Caraya 目录下又嵌套了一层
（`Caraya\vi.lib\addons\_JKI Toolkits\Caraya\...`）。spec 里 `Target Dir="<application>"`
的意思是**相对 LabVIEW 安装根**，不是相对包内同名目录。发现手段：按文档路径找
`Caraya.lvlib` 不存在 → 列目录见嵌套 → 清掉重铺。判据永远是"文档说的路径上有没有
那个文件"，不是"解压报没报错"。

### 1.3 安装验证（编辑期证据）

- `Caraya.lvlib` 21,956 B；`Run Tests.vi` 17,961 B——即 runner 生成器的调用目标
  `Caraya.lvlib\3ARun Tests.vi`（`3A` 是 lvlib 命名空间对 `:` 的转义，磁盘名就是
  `Run Tests.vi`）。
- 唯一零字节文件 `batch-tester\nonVI member for ...` 是原包测试样例，非损伤。
- **库真的能被解析**（最有力的编辑期证据）：后面生成的测试 VI 回读
  `callTargets` 含 `Caraya.lvlib:Test.lvclass:Define Test.vi` 与
  `Caraya.lvlib:Assert.lvclass:Assert Equal Value_Variant.vi`——LabVIEW 在打开测试 VI
  时把刚装的库解析成功了。

---

## 2. 实验闭环（batch 直驱，两份计划四份证据）

被测对象：R21 的孙 VI `examples/nested-multi-vi-demo/Double It.vi`
（`x [int32] → Doubled [int32]`，纯乘法，端子经 `lvai_vi_terminals` 现查现用）。
产出到新目录 `examples/caraya-demo/`。

### 2.1 计划 A：正对照（`planA-positive.json` → `transcriptA-positive.json`）

| 步 | 工具 | 耗时 | 要点 |
|---|---|---|---|
| 1 | `lvai_generate_test` | 108.5 s | 3 用例（3→6、-4→-8、0→0）；**placeholder 路线**（Double It.vi 无 .lvproj，工具自动降级并说明原因）；期望常量自动标签 `expected 1/2/3` 并在 `expectedConstants` 里逐条列出 |
| 2 | `lvai_generate_caraya_test_runner` | 19.0 s | runner 写到同目录 `run-tests.vi`，测试路径按 runner 自身位置转相对（工具的设计约束：测试 VI 必须在 runner 目录之下） |
| 3 | `lvai_run_caraya_tests` | 6.6 s | 判据：`tests=3 failures=0 errors=0 ok=true reportFresh=true` |

判据三重验收：
1. 工具答 JSON（如上）；
2. **磁盘 JUnit 报告** `examples/caraya-demo/TestReport.xml`（438 B，`reportFresh:true`
   即本次运行所写），快照存 `artifacts/round22/testreport-positive-snapshot.xml`，
   框架署名 `framework-version="2.0.0.151"`，三个 `<testcase name="doubles 3/-4/0"/>`
   无 failure 子节点；
3. 测试 VI 回读 `callTargets` 证明它静态链接了 Caraya 断言与被测 VI。

### 2.2 计划 B：负对照 + 恢复（`planB-negative.json` → `transcriptB-negative.json`）

| 步 | 工具 | 耗时 | 结果 |
|---|---|---|---|
| 1 | `lvai_set_constant`：`expected 2` → `99` | 6.3 s | 按 `expectedConstants` 给的标签定位，改后回读导出确认 |
| 2 | `lvai_run_caraya_tests` | 6.5 s | **`tests=3 failures=1 errors=0 ok=false`**；`failing` 数组指名：`case:"doubles -4", kind:"failure", body:"\"FAIL\""`——正是被改错的那个用例 |
| 3 | `lvai_set_constant`：`expected 2` → `-8` 恢复 | 5.1 s | |
| 4 | `lvai_run_caraya_tests` | 6.3 s | `tests=3 failures=0 ok=true`——现场复原，suite 幂等可重跑 |

三条判读：

- **Broken ≠ Failed 成立且被区分**：负对照产生的是 `kind:"failure"`（合法的测试失败，
  用例跑了、断言没过），不是 `kind:"error"`（测试 VI 本身跑不起来）。改期望值不破坏
  测试 VI——这正是"断言错误"与"产品缺陷/VI 损坏"三类信号里前两类的分界。
- **报告指名道姓**：`failing[].case` 直接给出用例 label，不用人肉翻报告——工具描述里
  "A Caraya failure body is the literal string \"FAIL\", so the case LABEL is what
  identifies it" 落到了实处。
- **改常数成本 5-6 s**：R13 时代改一个期望值要整版重新生成测试（两次 ~56 s 的再生成），
  `lvai_set_constant` 按标签原位改、存盘、回读验证，一个数量级的差距。

### 2.3 全程参数（可复放）

```
python scripts/mcp_call.py --server <exe> batch --plan planA-positive.json --out transcriptA-positive.json
python scripts/mcp_call.py --server <exe> batch --plan planB-negative.json --out transcriptB-negative.json
```

四步/四步全幂等：复跑只是把 TestReport.xml 的时间戳刷新一遍。R21 定型的
"一轮 = 一份 JSON 计划 + 一次运行"在测试层原样成立。

---

## 3. 新配方（本轮沉淀）

1. **测试层全自动路线**（Board D 关闭"有条件"，升级为 A 列可交付）：
   `lvai_vi_terminals` 查端子 → `lvai_generate_test`（casesJson 按端子名键控，
   浮点断言是精确相等，用例值选 IEEE754 精确可表的）→
   `lvai_generate_caraya_test_runner`（测试 VI 与 runner 同目录）→
   `lvai_run_caraya_tests` 读 JUnit。全程 `backend:"pylabview"`，只需 LabVIEW.exe 在跑。
2. **负对照配方**：`generate_test` 返回的 `expectedConstants` 是 set_constant 的标签表；
   改错 → 跑 → 核对 `failing[].case` 指对 → 改回 → 复跑归零。一个"测试层活性证明"
   从此是 4 步 batch、约 25 s。
3. **手工装 VIP 包配方**：.vip 即 zip，读包内 `spec` 段拿 `Exclusive_LabVIEW_Version`
   与各 File Group 的 `Target Dir`；`<application>` = LabVIEW 安装根，`<vi.lib>` =
   vi.lib 目录；铺完以"文档路径上找得到关键 .lvlib/.vi"为验收，再以"生成物 callTargets
   解析出新库"为活性证明。不需要 VIPM。
4. **repo 迁移坑**：JKI 系工具的 GitHub home 可能已迁到 `vipm-io/*`，老 org 的
   releases API 是 404 不是空。

---

## 4. 证据清单（`artifacts/round22/`）

| 文件 | 内容 |
|---|---|
| `planA-positive.json` / `transcriptA-positive.json` | 正对照 batch 计划与逐字 transcript（32.9 KB） |
| `planB-negative.json` / `transcriptB-negative.json` | 负对照+恢复 batch 计划与逐字 transcript |
| `testreport-positive-snapshot.xml` | 正对照时点磁盘 JUnit 报告快照（438 B） |
| `install-notes.json` | 安装来源、spec 关键行、返工记录、验证清单、耗时 |

运行产物（`examples/caraya-demo/`）：`Test Double It.vi`（9.7 KB，工具生成）、
`run-tests.vi`（7.9 KB，工具生成）、`TestReport.xml`（恢复后的全绿报告）。

---

## 5. 边界与遗留

- **`lvai_typedef_tree` fpsane.cpp(1140) 崩溃**（P2 备注项）：本轮未调用 typedef 树，
  未复现未排除，保持开放。
- **DIRECT 路线未测**：被测 VI 无 .lvproj 走了 placeholder 路线；被工程列管的 VI
  （`projectPath` 给出时）走 direct 路线，本轮未覆盖，下轮带 .lvproj 的样例补。
- **setup / error-in 链**：casesJson 的 `setup` 键（用例前调其他 VI）未测。
- **Caraya 自带测试套件**（vi.lib\addons\_JKI Toolkits\Caraya\tests\）未跑——若要
  深度验证安装完整性，用它当负载。
- 断言只有 `Assert Equal Value_Variant`（精确相等）；Caraya 的
  `Assert Almost Equal` 等未接线，浮点用例仍需自选精确值。
