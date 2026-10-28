# HMI HTML-Port — 四个纯前面板 VI（Round 18）

将 4 个 HTML 主界面（Win 经典 3D 风格的测控软件 HMI）移植为 LabVIEW **前面板**：
不要程序逻辑，只要外观像。移植与深度换肤方法论见
`../research/27-html-frontpanel-port-and-restyle.md`。

| 文件 | 对应 HTML 源 | 说明 |
|---|---|---|
| `登录.vi` | 登录页 | 用户名/密码输入 + 登录按钮，生成版原状 |
| `报警.vi` | 报警列表页 | 报警表格 + 过滤控件，生成版原状 |
| `产品侧.vi` | 产品信息页 | 产品参数面板，生成版原状 |
| `波形图.vi` | 多链路实时波形页 | **深度换肤完成版**：27 控件编号剥离、12pt 字体、行内标签、白底数值框、LED 竖排、白底浅灰网格绘图区 |

## 注意

- VI 由 **LabVIEW 2026（中文版）** 的 pylabview 合成器写出，低版本打开可能提示版本警告。
- `波形图.vi` 的白底绘图区是运行时写入的 VI Server 属性（`Plot Area:Colors:BG Color`），
  已随 VI 保存；若重建 VI 需用 `../research/artifacts/round18/helper_graph_style.vi` 重打。
- 曲线颜色当前为白色（占位），真连数据时用同一助手改 `Plot Color`。
- Win95 风格凹凸边框受 LabVIEW 窗格零件绘制表限制，XML 注入不可行（实验钉死，
  见研究文档 §3），需在编辑器中手动加 Decorations。
