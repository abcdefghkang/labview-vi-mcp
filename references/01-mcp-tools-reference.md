# 01 · MCP 工具参考（实机验证版）

## 1. 环境与路径

| 项目 | 值 / 说明 |
|---|---|
| LabVIEW 2018（32 位中文） | MCP 服务器 **`labview-native-2018`**（COM / VI Server 脚本，23 个工具）——前面板编辑主通道 |
| LabVIEW 2026 | MCP 服务器 **`labview`**（Zuehlke LVAI，98+ 个 `lvai_*` 工具）——生成/描述/测试辅助 |
| MCP 注册文件 | `C:\Users\<you>\.config\opencode\opencode.json` —— **两个服务器都要保留**，缺一个少一半能力 |
| 调用方式（OpenCode） | 在 Code Mode `execute` 里用 `tools["labview-native-2018"].工具名({...})` / `tools.labview.lvai_xxx({...})` |
| 超时兜底 CLI | `C:\LV_MCP\bin\LabVIEWMCP.exe`（例：`--pylv-extract <vi> --out <目录>` 全量导出 XML，绕过 MCP 45 秒超时） |
| 内嵌 Python | `C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\runtime\python.exe`（3.12 + Pillow；跑脚本前设 `PYTHONIOENCODING=utf-8`） |
| 渲染输出根 | `C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\work\mcp_render\<VI名>\export_*\`，PNG 取 **mtime 最新** |
| 属性/类 ID 对照表 | `C:\Users\<you>\AppData\Local\LabVIEWNativeMCP\tools\native_locale_18.json`（查成员名与 ID） |
| 试错草稿 VI | `C:\LV_AUTOTEST\gen\scratch_probe.vi`（能力探针专用） |
| 前置条件 | 目标 LabVIEW 实例必须**正在运行**；建议两个实例常驻 |

> 注意：本文件中的绝对路径是本机实测环境。把经验库分享给别人时，路径需要按对方机器调整（插件安装位置、user 目录名）。

## 2. labview-native-2018 —— 23 个工具逐个说明

### 2.1 文件 / 生命周期

| 工具 | 语义 |
|---|---|
| `new_vi(path)` | 新建空 VI；**路径已存在会拒绝**（永不覆盖用户文件） |
| `open_vi(path[, reload])` | 打开 VI；`reload=True` 强制读盘刷新（改完保存后用） |
| `save_vi(path)` | 保存当前编辑到同一路径 |
| `version_info()` | 报告 COM 目标版本 / 架构 / 安装位置 / 隔离缓存 |

### 2.2 对象编辑（核心）

| 工具 | 语义 |
|---|---|
| `add_object({owner, style, location:[x,y]})` | 新建对象 → 返回 `{result: N}`（N 即引用号）。`location` 是**左上角**；`bounds` 参数被忽略。`owner` 传面板引用 |
| `delete_objects({references:[N,...]})` | 删除对象（装饰/控件/文本都行）。删除前确认不是别人图层 |
| `set_property({object_class, member, reference, value})` | 写属性。**`value` 必须是字符串**；`object_class` 用类名（`Decoration`/`Text`/`Boolean`/`Digital` 等） |
| `get_property({object_class, member, reference})` | 读属性 → `{value: ...}` |
| `inspect_vi(path)` | **一次性dump全对象**（reference/uid/class/owner/label/position…）。批量改完必须重新 inspect 拿最新引用 |
| `find_objects` / `search_styles` / `invoke` | 查对象 / 查样式名 / 调方法 |

### 2.3 程序框图侧（编辑器场景用）

`inspect_node`（节点端子：**重配节点后端子会变，必须重查**）、`wire`（连线）、`clean_up_diagram`（框图整理）、`add_shift_register`、`connector`（连接器窗格）、`configure_express_parameters`、`select_polymorphic`。

### 2.4 批量 / 执行 / 渲染

| 工具 | 语义 |
|---|---|
| `edit_batch({steps:[{id,tool,args}]})` | 一次 STA 派发批量执行；**第一个失败即停止、不回滚、不自动保存**。适合小批次高把握操作 |
| `run_vi(path)` | **真实执行**（可能触发硬件/网络 IO）。仅做前面板还原时不要用它 |
| `render_vi({path, surface:"panel"})` | 前面板渲染 PNG：写入新的 `export_*` 目录并附图像返回；**返回 null 属正常**，以“出现新 export_* / PNG mtime 更新”判断完成 |
| `call_stats()` | 各工具耗时统计 |

## 3. Zuehlke `labview` —— 98+ 个 `lvai_*` 工具按能力分组

### 3.1 环境 / 诊断
`lvai_status` · `lvai_list_labview_installations` · `lvai_ensure_labview` · `lvai_error_list` · `lvai_exec_state` · `lvai_get_application_configuration` · `lvai_vi_server_reference` · `lvai_dump_schema` · `lvai_log_usage_data`

### 3.2 文件 / 项目 / 库
`lvai_open_file` · `lvai_close_vi` · `lvai_close_active_project` · `lvai_describe_project` · `lvai_build_from_build_specification` · `lvai_lvproj_reference` · `lvai_lvlib_reference` · `lvai_add_to_library` · `lvai_add_vis_to_project`

### 3.3 描述 / 理解（读代码）
`lvai_describe_vi` · `lvai_describe_ctl` · `lvai_describe_class` · `lvai_discuss_file` · `lvai_monitor_discuss_vi` · `lvai_vi_terminals` · `lvai_connector_pane`

### 3.4 AIXML 文本往返（重量级备用通道）
`lvai_convert_vis_to_aixml` · `lvai_convert_vi_to_aixml` · `lvai_convert_aixml_to_vi` · `lvai_check_aixml` · `lvai_validate_aixml` · `lvai_apply_aixml_to_vi` · `lvai_aixml_reference` · `pylv_apply` · `pylv_rebuild`
> 把 VI 变成文本 XML，批量文本编辑后回写。native 脚本搞不动的大改造可走这条路。

### 3.5 生成 / 脚手架
`lvai_generate_vi` · `lvai_generate_vis` · `lvai_generate_vi_with_events` · `lvai_placeholder_subvi` · `lvai_make_malleable` · `lvai_set_vi_icon` · `lvai_set_constant` · `lvai_graft_diagram` · `lvai_layout_diagram` · `lvai_swap_subvis` · `lvai_wire_dynamic_events` · `lvai_set_event_data_fields` · `lvai_coercion_dots`

### 3.6 类 / 接口 / typedef
`lvai_create_class` · `lvai_create_interface` · `lvai_create_typedef` · `lvai_create_accessors` · `lvai_create_message_class` · `lvai_add_class_field` · `lvai_add_class_method` · `lvai_bind_class_fields` · `lvai_bind_control_references` · `lvai_bind_pane_typedef` · `lvai_bind_typedef_constants` · `lvai_flatten_typedefs` · `lvai_resave_ctl`

### 3.7 测试
`lvai_generate_test` · `lvai_generate_method_test` · `lvai_generate_class_test` · `lvai_generate_mock_class` · `lvai_generate_caraya_test_runner` · `lvai_run_lunit_tests` · `lvai_run_caraya_tests` · `lvai_lunit_add_test_method` · `lvai_lunit_scaffold_class_tests` · `lvai_run_vi_and_read_values` · `lvai_run_vi_as_top_level`

### 3.8 DQMH 框架
`lvai_dqmh_reference` · `lvai_dqmh_new_module` · `lvai_dqmh_new_event` · `lvai_dqmh_convert_event` · `lvai_dqmh_place_handler` · `lvai_dqmh_remove_event` · `lvai_dqmh_rename_event` · `lvai_dqmh_rename_module` · `lvai_dqmh_validate_module` · `lvai_dqmh_create_module_template` · `lvai_dqmh_create_rt_tester` · `lvai_dqmh_new_unit_test` · `lvai_dqmh_remove_do_something`

### 3.9 面板 / 调色板 / 示例
`lvai_drop_palette_item` · `lvai_find_palette_item`（**注意：会真改 IDE 状态——高亮调色板**） · `lvai_palette_index` · `lvai_example_index` · `lvai_filter_example_search_candidates` · `lvai_filter_palette_search_candidates` · `lvai_monitor_front_panel_cleanup`

### 3.10 缓存 / 监控
`lvai_search_info_cache` · `lvai_lookup_info_cache_items` · `lvai_monitor_code_completion` · `lvai_monitor_example_searches` · `lvai_monitor_palette_searches` · `lvai_monitor_project_changes`

## 4. 选择原则

- **前面板像素级布局 / 批量属性修改 / 渲染核验** → `labview-native-2018`（本经验库主体）
- **生成新代码、类/typedef、测试、理解现成 VI、AIXML 文本改造** → Zuehlke `labview`
- 两者可混合：native 摆面板 + Zuehlke 生成框图逻辑；或 Zuehlke 生成骨架 + native 修外观。
