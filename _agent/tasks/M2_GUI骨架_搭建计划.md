# M2 GUI 骨架 · 详细搭建计划（待椰椰过目后动手）

> 版本 v1.0 / 2026-06-16 / claude
> 上位计划：`_agent/references/B1500_GUI架构设计_PySide6.md`（v1.0，已定型）
> 决策前提（2026-06-16 椰椰拍板）：
> 1. 本次**只出计划，不写代码**；过目后再动手。
> 2. 扩展策略=**FeFET 优先，但把"共性壳/功能键"与"按存储器单独适配"的缝先划清**。
>    将来加新存储器（RRAM/相变…）时，界面和功能键一致，只补"适配层"，`gui/` 不重写。

---

## 0. 一句话目标

把已落地的引擎核心（`src/fefetlab/engine/`）装上一张可点的 PySide6 壳，做出 **M2 竖切片**：
**选协议 → 自动生成参数表单 → dry-run 跑 → 看编程波形 → 看结果出图 → 落盘 `runs/dry/`**。
全程 **dry-run（`AuditBackend`，不开 VISA / 不载 DLL / 不碰真机）**，所以可在 G 盘开发机上
直接写、直接测，**不依赖那台 B1500**。

---

## 1. 现状校正（计划必须贴真代码，不贴草稿）

读完真代码，有 4 处和设计文档 v1.0 的措辞**不一致**，计划按真代码走：

| 设计文档说 | 真实代码 | 对 M2 的影响 |
|---|---|---|
| `engine.run(..., mode, callbacks)` 内部 `with BackendManager(mode) as bm` 自建后端 | `run(protocol_id, params, *, backend, callbacks=None, confirm="")` —— **backend 由调用方注入**，`BackendManager` 未建，`live` 从 `params["live"]` 读 | **利好**：GUI worker 自己调 `make_backend(False)` 造 `AuditBackend` 再注入即可，M2 不必先建 BackendManager |
| `ParamView(spec, params, ...)` 多参构造 | `ParamView(params)` 单参，包一个 dict | GUI 把 `{**默认, **表单值}` 传进去即可 |
| `validate_params`（范围/LOCKED 越权校验）在 `run` 入口 | **尚未接入** | M2 先做**表单端**校验（QSpinBox setRange / 红框）；引擎端 `validate_params` 留作后续补，不阻塞 M2 |
| `on_shot` / `on_progress` 已接进 runner | **未接**（`on_stage_done`/`on_stop_gate`/`on_error` 才可靠发） | M2 实时逐炮绘图**不做**（那是 M3）；M2 出图=跑完读 CSV，波形=读 `AuditBackend._patterns` |

已就绪、M2 直接可用的引擎件：
- `make_backend(live)`：`live=False` → 返回 `(AuditBackend, "DUMMY::WGFMU")`，已 `open_session`、已 `_validate_channels`。
- `ProtocolEngine().run(id, params, backend=bk, callbacks=cb, confirm=...)`：唯一执行门，内部已做
  `configure_channel_map` + `validate_live_request` + 调 `run_stage_*` + 发 `on_stage_done/on_stop_gate`。
- `REGISTRY`：12 段（S0/S1/E1/E2/E3W/E3A/E4/E5/E6R/E6D/CYCLE/MLC）已带逐参数 `ParamSpec`，按 `family="WGFMU"` 分组。
- `AuditBackend._patterns`：`{"gp": {"init_v", "vectors":[(dt,v)...]}, "dp": {...}}` —— **编程波形预览的唯一真值源**（§6.1 接缝铁律：用元组解包，**不要用 `DummyWgfmuBackend`**）。

---

## 2. 共性壳 vs 适配层 —— 椰椰要的那条缝（本计划的核心）

把整套上位机切成两层。**共性壳建一次，加任何新存储器都不动；适配层=纯引擎侧数据 + 极少量注册钩子。**

### 2.1 共性壳（`gui/`，与存储器类型无关，永不为新存储器改）

下面每个文件都**不写任何 FeFET 专有字眼**，只认 `REGISTRY` / `ParamSpec` / `csv_schema` / `EngineCallbacks` 这些抽象：

- 主窗口、三栏布局、dock 系统
- 协议树：**按 `ProtocolSpec.family` 泛化分组**（现在只有 WGFMU，将来自动多出 RRAM tab）
- 参数表单：**100% 按 `ParamSpec` 自动生成**（kind→控件、unit→SI 缩放、visibility→三档显隐），早已与协议无关
- 运行控制：dry/live 开关、设备身份、预检清单、进度、安全指标、运行/停止/恢复 —— **功能键对所有存储器一致**
- 日志面板：`on_log(level,code,msg)` 泛化，分级过滤/着色
- 结果浏览：扫 `runs/`、读 manifest
- 线程层：EngineController / EngineWorker（实现 `GuiCallbacks`）/ DeviceSessionManager
- 对话框：live 二次确认、设备连接、首次配置向导

### 2.2 适配层（每种存储器一份，加新类型时只动这里）

| 适配点 | 是什么 | FeFET 现状 | 加 RRAM 时要补 |
|---|---|---|---|
| ① **runners** | 真正打波形/测量的函数 | `run_stage_*` 已有 11+1 | 写 RRAM 的 set/reset/retention/endurance runner |
| ② **ProtocolSpec 注册** | 有哪些协议、各自 `ParamSpec`、`family`、`csv_schema`、`requires` 链 | `registry.py` 已注册 | 在 registry 加 `family="RRAM"` 的若干 ProtocolSpec |
| ③ **绘图分派** | 把某 `csv_schema` 的 CSV 画成有意义的图 | `fefet_fixedcols` → MW vs delay/cycle | 注册 `"rram_iv"` → R vs cycle / I-V 回滞 |
| ④ **stop-gate 度量列** | 安全停门看哪一列 | `Ig_mean_A`（栅漏） | RRAM 可能看 compliance / `I_reset` 列 |
| ⑤ **family_defaults** | 子类型默认（读网格方向等） | pFeFET / nFeFET | RRAM 的双极/单极默认 |
| ⑥ **workflow 链** | report_code 推进顺序 | S0→S1→E1→… | RRAM 的 forming→set/reset→endurance |

**契约一句话：加一种新存储器 = 写 runners + 注册 ProtocolSpec + 为新 `csv_schema` 注册 1 个绘图函数。`gui/` 一行不改，功能键和界面自动一致。**

### 2.3 为把这条缝从第一天就坐实，M2 必须交付的"接缝件"

否则缝是嘴上的、代码里仍是 FeFET 硬编码：

1. **绘图分派注册表**（不要把 FeFET 画法写死在 `PlotPanel` 里）：
   ```python
   # gui/plot_dispatch.py  —— 壳只认 schema 字符串，画法按 schema 查表
   PLOT_DISPATCH: dict[str, Callable[[pd.DataFrame, PlotWidget], None]] = {}
   def register_plot(schema): ...        # 装饰器
   @register_plot("fefet_fixedcols")     # ← FeFET 适配，住在 gui/adapters/fefet_plots.py
   def _plot_fefet_mw(df, plot): ...
   ```
   壳里 `PlotPanel` 永远只 `PLOT_DISPATCH[spec.csv_schema](df, widget)`；新存储器=新增一个 `@register_plot("rram_iv")`，壳不动。
2. **协议树按 family 泛化**：节点来源 = `group_by(REGISTRY.values(), key=lambda s: s.family)`，**不写死** "S0/S1/E1…"。
3. **运行控制不出现协议名硬编码**：dry/live、run/stop/recover、预检、安全指标全走 `EngineCallbacks` 抽象。

> 落点建议：把 ③④⑤⑥ 这类"FeFET 专有但属于 UI/分析侧"的东西收进 `gui/adapters/fefet_*.py`，
> 与壳物理隔离；引擎侧的 ①② 仍在 `src/fefetlab/`。将来 `gui/adapters/rram_*.py` 即第二份适配。

---

## 3. 文件清单（M2 要新建的）

> 估行数仅为规模参考。`gui/` 依赖 PySide6 + pyqtgraph + engine；**绝不 import 仪器层**。

### 3.1 依赖与工程
| 文件 | 动作 | 内容 |
|---|---|---|
| `requirements/gui.txt` | 新建 | `PySide6>=6.6`、`pyqtgraph>=0.13`（base.txt 现**无** GUI 依赖，必须补） |
| `pyproject.toml` / `setup.cfg` | 改（若有） | 加 `gui` 可选依赖组；`gui` 包纳入打包 |

### 3.2 共性壳 `gui/`
| 文件 | 类 | 线程 | 职责 | 估行 |
|---|---|---|---|---|
| `gui/__init__.py` | — | — | 包标记 | 5 |
| `gui/app.py` | `main()` | — | `QApplication` 入口、异常钩子、`python -m gui` | 40 |
| `gui/main_window.py` | `MainWindow` | GUI | 组装三栏 + dock、菜单、`QSettings` 布局持久化 | 180 |
| `gui/protocol_panel.py` | `ProtocolPanel` | GUI | **按 family 泛化**的协议树 + 托管 ParamForm；发 `protocolSelected(id)` | 140 |
| `gui/param_form.py` | `ParamForm` | GUI | 按 `ParamSpec` 自动渲染控件、即时校验、`collect()→dict`（SI 还原） | 220 |
| `gui/run_control_panel.py` | `RunControlPanel` | GUI | dry/live、设备身份、预检清单、进度、安全指标、运行/停止/恢复 | 200 |
| `gui/plot_panel.py` | `PlotPanel` | GUI | pyqtgraph；`show_waveform(patterns)` + `show_result(df, schema)`（**只查分派表**） | 160 |
| `gui/plot_dispatch.py` | `register_plot` / `PLOT_DISPATCH` | — | 绘图分派注册表（接缝件①） | 40 |
| `gui/log_panel.py` | `LogPanel` | GUI | 结构化日志、分级过滤、STOP/ERROR 着色 | 110 |
| `gui/run_browser_panel.py` | `RunBrowserPanel` | GUI | 扫 `runs/{dry,live}`、读 manifest 摘要、选 run → 出图 | 170 |
| `gui/engine_controller.py` | `EngineController(QObject)` | GUI | 唯一协调者：收 `RunRequest` → 起 worker → 转接信号到各 panel | 130 |
| `gui/engine_worker.py` | `EngineWorker(QObject)` + `GuiCallbacks` | **worker** | 子线程：`make_backend(False)` → `ProtocolEngine().run(...)`；`GuiCallbacks` 把事件 emit 成 Qt 信号；**不碰 widget** | 150 |
| `gui/device_session_manager.py` | `DeviceSessionManager(QObject)` | GUI | 持 backend 句柄 + resource + 连接状态/IDN（M2 仅 dry 占位，live 留接口） | 90 |
| `gui/widgets/list_edit.py` | `ListEditWidget` | GUI | 逗号列表编辑（= `_parse_float_list_csv`），解析失败红框 | 70 |
| `gui/widgets/channel_combo.py` | `ChannelComboBox` | GUI | `ALLOWED − FORBIDDEN` 通道下拉（LOCKED 只读展示） | 50 |
| `gui/widgets/preflight_view.py` | `PreflightView` | GUI | 预检三行点亮（M2 dry 显示"模拟全绿"） | 60 |
| `gui/models.py` | `RunRequest`(frozen dataclass) | — | 跨线程传值：`stage/params/live/confirm/device_id/geometry/device_family` | 30 |

### 3.3 FeFET 适配层 `gui/adapters/`（M2 先放 FeFET 一份）
| 文件 | 职责 |
|---|---|
| `gui/adapters/__init__.py` | import 各适配模块以触发 `@register_plot` 注册 |
| `gui/adapters/fefet_plots.py` | `@register_plot("fefet_fixedcols")`：复刻 notebook 40 cell4 的 MW vs delay/cycle（ERS−PGM 双线、按 `state_target` 分色） |

### 3.4 测试 `tests/`
| 文件 | 内容 |
|---|---|
| `tests/test_param_form_render.py` | 给定 `REGISTRY["E1"].params`，断言生成的控件数/类型/范围正确；`collect()` 往返一致（offscreen，`QT_QPA_PLATFORM=offscreen`） |
| `tests/test_engine_worker_dry.py` | 不起 Qt 事件循环，直接调 worker 的 run 逻辑：`make_backend(False)`+`engine.run("S0", dry params)` → 收到 `on_stage_done` + `runs/dry/` 落盘 + `AuditBackend._patterns` 非空 |
| `tests/test_plot_dispatch.py` | `PLOT_DISPATCH["fefet_fixedcols"]` 已注册；喂一份小 CSV 不抛 |

---

## 4. M2 竖切片数据流（dry-run，开发机可跑）

```
用户在 ProtocolPanel 选 "E1"
  └─ ProtocolPanel 读 REGISTRY["E1"].params → ParamForm 自动建表单
用户填表单（或留默认）→ ParamForm.collect() → dict（µs→秒等 SI 还原）
用户点 "Dry Run"
  └─ RunControlPanel 组 RunRequest(stage="E1", params={**默认,**表单, live:False}, live:False)
     └─ EngineController.start_run(req) → EngineWorker.moveToThread(QThread) → started→worker.run
        └─ [worker 线程] backend,_ = make_backend(False)            # AuditBackend，无硬件
           cb = GuiCallbacks(self)                                  # 实现 EngineCallbacks
           ProtocolEngine().run("E1", req.params, backend=backend, callbacks=cb, confirm="")
             ├─ configure_channel_map(view)  validate_live_request("E1", False, "")  # dry 直接过
             ├─ run_stage_e1(backend, view)  → 跑完一段 dry，落盘 runs/dry/<ts>_E1_<dev>/
             └─ cb.on_stage_done(summary, run_dir) → emit stageDone(summary, run_dir)
           # 跑完后 worker 读 backend._patterns → emit planReady(gp_xy, dp_xy)
  └─ [主线程] stageDone 槽：读 run_dir/*.csv → PlotPanel.show_result(df, "fefet_fixedcols")
            planReady 槽：PlotPanel.show_waveform(patterns) 画 Vg(t)/Vd(t)
            on_log 槽：LogPanel 追加 REPORT_CODE / STAGE_SUMMARY
RunBrowserPanel 刷新 → 新 run 出现，可重新载入出图
```

要点：
- **波形预览**：M2 用"跑完读 `backend._patterns`（最后一炮）"得到 Vg/Vd 波形 —— 不需要 `on_shot`。逐炮实时刷新留 M3。
- **结果出图**：`on_stage_done` 给 `run_dir` → 读 CSV → `PLOT_DISPATCH[spec.csv_schema]`。
- **取消**：M2 dry 单段很快，Stop 仅置 `_cancel` 标志（协作式占位），真正断点续跑留 M4/CYCLE。

---

## 5. 分步实施顺序（每步独立可验收，出问题易回退）

| 步 | 内容 | 验收（开发机，无硬件） |
|---|---|---|
| **M2.0** | 加 `requirements/gui.txt`，装 PySide6+pyqtgraph；建 `gui/` 包骨架 + `app.py` 空窗口 | `python -m gui` 弹出空主窗口不报错 |
| **M2.1** | `models.py` + `ParamForm`：按 `REGISTRY["E1"].params` 渲染表单 + `collect()` | `test_param_form_render` 绿；手点能看到 E1 全参数控件、高级折叠、LOCKED 灰显 |
| **M2.2** | `ProtocolPanel` 按 family 泛化树 + 选中联动 ParamForm | 点不同协议，表单随之重建 |
| **M2.3** | `EngineWorker`+`GuiCallbacks`+`EngineController`+QThread；`RunControlPanel` 的 Dry Run 按钮 | `test_engine_worker_dry` 绿；点 Dry Run 不卡主线程，`runs/dry/` 出目录 |
| **M2.4** | `plot_dispatch.py` + `adapters/fefet_plots.py` + `PlotPanel.show_result` | 跑完 E1/CYCLE dry，结果图（MW vs delay/cycle）出来 |
| **M2.5** | `PlotPanel.show_waveform`（读 `_patterns`，元组解包）+ `LogPanel` | 编程波形 Vg/Vd 双轴出来；日志按级过滤 |
| **M2.6** | `RunBrowserPanel` 扫 `runs/` + 读 manifest + 离线出图；`QSettings` 布局持久化 | 选历史 run 重新出图；关掉重开布局还原 |

完成 M2.0–M2.6 = 设计文档 M2 验收："不连硬件、不装 VISA 即可全程点完：选协议→填表单→dry 跑→编程波形预览→结果出图→落盘 `runs/dry/`"。

---

## 6. M2 明确**不做**（避免范围蔓延，留给后续里程碑）

- 逐炮实时绘图 / 进度条随 shot 增长 → **M3**（需先把 `on_shot`/`on_progress` 接进 runner，属 M1 余项）
- live 真机 / LiveConfirmDialog 真生效 / 预检三步真点亮 / 会话恢复 → **M4**
- 自定义协议序列编辑器 → **M5**
- PyInstaller 打包 / DLL 冻结路径 / 配置向导 / 回流项目4 → **M6**
- DC 卡片（需 mock VisaSession + DC 落盘统一 + `Ig_mean_A` 列映射）→ 随 M2 之后单独并入（设计 §7.4/C6）
- 引擎端 `validate_params` / BackendManager / wakeup 单通道改造 → M1 余项，按需补

---

## 7. 与 M1 余项的关系（哪些必须先补、哪些可并行）

- **M2 竖切片不被 M1 余项卡**：dry-run 路径用 `make_backend(False)` + 现有 `engine.run`，已够。
- **建议在 M3 前补的 M1 余项**（不阻塞 M2，但 M3 要用）：`on_shot`/`on_progress` 接进 `run_stage_*` 的 shot 循环（设计 D1，唯一会碰 runner 函数体的改动，只加回调不动物理，字节一致回归仍守）。
- **可延后**：`build_argparser`（CLI 薄壳化，与 GUI 无关）、`validate_params`（M2 先表单端校验）、DC 注册（随 DC 卡片）、BackendManager（live 时再封装；M2 dry 不需要）。

---

## 8. 风险与取舍

1. **波形预览取"最后一炮"**：M2 不接 `on_shot`，`_patterns` 是 dry 跑完时缓存的最后一个 shot 的向量。对"看波形长什么样"够用；要看"每炮波形"得等 M3。已在 §4 标注。
2. **绘图分派若偷懒写死在 PlotPanel**：会让"共性/适配"缝形同虚设，将来加存储器又得改壳。**M2.4 必须落 `plot_dispatch` 注册表**（接缝件①），这是不可省的。
3. **PySide6 体积/打包**：M2 只管开发态能跑；onedir 打包与 DLL 冻结是 M6 的事，现在不碰。
4. **测试需 offscreen**：CI/开发机无显示时用 `QT_QPA_PLATFORM=offscreen` 跑 GUI 测试；纯逻辑测试（worker dry / 分派表）不依赖显示。
5. **G 盘 ↔ 测试机同步**：`gui/` 是新增包目录，按记忆铁律 [test-machine-sync-discipline] —— 同步到测试机时要带上整个 `gui/` 目录 + `requirements/gui.txt`，scp 覆盖不 pull。

---

## 9. 整体验收标准（M2 收口判据）

1. 开发机 `pip install -r requirements/gui.txt` 后 `python -m gui` 起得来。
2. 全程不连硬件、不装 VISA：选 E1 → 填表单 → Dry Run → 编程波形出 → MW 结果图出 → `runs/dry/` 落盘 → RunBrowser 可重载。
3. `--stage ALL_DRY` 字节级回归不变（GUI 不碰 runner，护栏仍守）。
4. `pytest tests/ -q` 全绿（含 3 个新 GUI 测试，offscreen）。
5. **共性/适配缝成立**：`gui/` 壳内无 FeFET 协议名硬编码；FeFET 画法只在 `gui/adapters/fefet_plots.py`；协议树按 family 泛化。模拟"加一个假 family 的 ProtocolSpec + 一个 `@register_plot`"，壳能自动多出 tab 并出图（可写成一个 smoke 测试坐实缝）。
