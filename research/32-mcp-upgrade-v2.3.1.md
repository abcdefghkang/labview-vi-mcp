# Round 32（Round 23）：升级 labview-mcp v2.0.1 → v2.3.1——补丁重打与无迁移升级

> 日期：2026-10-30　在线：是　MCP：LabVIEWMCP.exe **v2.3.1**（`5c9afb35`，2026-10-28 构建，**114 工具**）
> 上一轮：[31-caraya-testing-layer.md](31-caraya-testing-layer.md)（Caraya 装包 + 测试层打通）
> 本轮关闭看板 **P3** 的升级主体；`dump_schema` 逐条 diff 与新工具首测留给 Round 24。

---

## 0. 一句话结论

**升级零迁移完成**：release zip 与旧安装布局同构（`.mcp.json` / `VERSION.txt` /
`agents` / `bin` / `hooks`），停进程 → 旧目录改名备份 → 解压 → 重打 `resolve.py`
补丁 → 114 工具面确认 → Caraya 套件重放全绿。**上游 v2.3.1 仍带着 R14 发现的
`labview_root()` first-hit bug**（208→657 行的大改都没修它）——补丁第三次落点，
本仓库留下 `.diff` 存档。

---

## 1. 升级过程（真实形态，两处网络坑）

### 1.1 找包与下载

- 上游 repo：`Zuehlke/labview-mcp`（旧安装 `VERSION.txt` 里的 actions run 链接暴露的）。
- **API 限流**：匿名 REST API（代理出口 IP 共享额度）`rate limit exceeded`；
  改抓 `releases/expanded_assets/v2.3.1` HTML 页拿资产链接——API 死了页面还活着。
- 资产四个：`labview-mcp-v2.3.1.zip`（8.4 MB）、`labview-mcp.zip`（**104.6 MB，完整包**）、
  两个 .sha256。**注意**：`.sha256` 文件写的是 `labview-mcp.zip` 的哈希——小体积的
  版本化 zip 对不上它，别误判为被篡改。
- 下载两次失败形态：一次截断在 47.7 MB（curl exit 56），`-C -` 续传 + `--retry 3`
  后 SHA256 匹配。

### 1.2 升级步骤（全程可回滚）

| 步 | 动作 | 说明 |
|---|---|---|
| 1 | 备份 `bin\scripts\aixml-pylabview\resolve.py` + `resolve.py.orig-round14` | 到 `%TEMP%\r23\patch-backup\` |
| 2 | 停 `LabVIEWMCP.exe`（PID 20108）；`LabVIEW.exe` 保留 | exe 被进程锁，必须先停 |
| 3 | `labview-mcp` → `labview-mcp.v2.0.1-bak` | 整目录改名即备份，可整体回滚 |
| 4 | 解压 5426 文件 → `C:\Users\heiyashi\labview-mcp` | zip 顶层与本地布局同构 |
| 5 | 重打 `resolve.py` 补丁（见 §2） | 上游仍带 bug，手工重应用 |
| 6 | 验证：编译 + 行为 + 工具面 + 回归 | §3 |

**配置零迁移**：`.mcp.json`、hooks、agents 全部随包更新，本机没有附加配置需要搬。

---

## 2. resolve.py 补丁重打（R14 修复的第三次落点）

**补丁实质**：`labview_root()` 从"沿 x86 base 先走、返回首个命中"改为"两个
Program Files base 里取**版本号最高**的安装"。不做它，2018(32-bit)+2026(64-bit)
双装机上 pylabview 认 2018，AddClass/AddInterface/Message Maker 全部读成
"安装里没有"（R14 实测）。

**v2.3.1 上游把 resolve.py 从 208 行改到 657 行**（LVAddons 锚点、xctl 类型等新逻辑），
但 `labview_root()` 顶部的 first-hit 遍历**原样还在**——旧补丁不能直接盖，
在新函数体上重新应用同一逻辑（`glob` 两 base → 提版本数字 → 取最大），注释改为
"ROUND-14 FIX (re-applied on v2.3.1)"。

验证：`py_compile` 过；`labview_root()` → `...\LabVIEW 2026`。
补丁 diff 存档：`artifacts/round23/resolve-patch-r14.diff`。
**这条该报给上游**（P9 扩容：v2.3.1 仍拒修 first-hit 版本选择）。

---

## 3. 升级后验证（三层）

| 层 | 判据 | 结果 |
|---|---|---|
| 工具面 | `list` 工具数 | **114**（109 `lvai_*` + 5 `pylv_*`），R20 网络调研的数字吻合；`lvai_layout_diagram` / `lvai_layout_diagrams` / `lvai_error_list` / `lvai_dump_schema` 全部在位 |
| bundle | `pylv_status` | ok，93 ms，Python 3.12 bundle 随新包携带 |
| 闭环回归 | R22 Caraya 套件重放 | `tests=3 failures=0 ok=true reportFresh=true`（6.5 s）——**R22 的手工装包与整条 pylabview 链在 v2.3.1 下原样工作** |

工具面存档：`artifacts/round23/tool-surface-v231-114.json`（475 KB 完整 schema）。

---

## 4. 新配方

1. **升级配方**（可复用）：备份补丁 → 停 MCP 进程（LabVIEW.exe 可留）→ 旧目录改名
   备份 → 解压 release zip → 重打补丁 → 三层验证。release zip 即安装布局，
   无安装器、无注册表、无配置迁移。
2. **API 限流绕行**：GitHub REST 限流时，`releases/expanded_assets/<tag>` HTML 页
   照样给出资产链接（不走 API 配额）。
3. **sha256 对哪个文件要看内容**：这个项目的 `.sha256` 是滚动命名 zip 的校验，
   版本化命名的 zip 对不上不算异常。

---

## 5. 遗留与下一轮

- **P3 收尾**：`lvai_dump_schema` 逐条 diff（114 工具 / 23 RPC 权威面）——
  R11 的 99 工具面到 114 的名字级变化清单。
- **P4**：`lvai_layout_diagram` 首测（v2.2.x 起内置写入流程，本机终于有工具）。
- **P5**：`lvai_error_list` 回诊 R6/R8 的 `execState 0` 档案。
- **P9 扩容**：向上游报 `labview_root()` first-hit bug（v2.3.1 仍在）。
- 回滚路径：`labview-mcp.v2.0.1-bak/` 整目录在，改名回来即回 v2.0.1。
