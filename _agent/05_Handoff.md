# 项目3 压缩恢复点 (05_Handoff)

> 当一次会话即将结束、要切换设备/换模型/隔一段时间再回来时，在这里写一段"接力棒"。
> 格式：倒序追加，最新在最上面。每次开场新会话先读 `01_State.md` + 本文件最顶 1-2 条即可。

---

## 2026-06-23 (2) → 需求vs现状深审 + 可视化/参数/预设大改 + 全绿 150(⭐新会话从这接)

**椰椰反馈**:GUI 还简陋;重分析项目4 测量需求 vs 现状(参数/导出/log/bug/真实下发),并参考本机 EasyEXPERT。

**本轮做了(全部 scp 测试机 + pytest 绿,150 passed)**:
- **深度分析**:项目4 **R1–R14** 测量需求清单(E1S retention/rich-read Id-Vg/E6S/E6M/DC/Toff 扫描/50µs 读窗/前置脉冲极性/PGM 读扰/温度×3/S1 基线)+ GUI 可视化/参数/live 三路审计(本会话 workflow 输出)。
- **参考 EasyEXPERT**:本机 `C:\Program Files (x86)\Agilent\B1500`(桌面授权超时,改读安装结构+知识)。吸收:每轴 log/线性一等控件、导出、Graph+List 双视图、命名预设、Append 叠加。
- **可视化(plot_panel)**:加 保存图片(PNG/SVG)+导出CSV;**按 schema 智能默认 log 轴**(fefet delay→logX,DC |Id|→logY);新增**数据表 List 视图**。
- **参数 bug 修(param_form)**:① FLOAT 小数位/步长按量级自适应(修极小 s 值被 6 位小数静默清零);② **电压参数夹到 ±10V** + nullable 电压>10V 判非法(防误填烧器件);③ INT_LIST(检查点)拒空/拒非正;④ collect 遇非法字段直接抛。
- **命名预设(presets.py)**:类 EasyEXPERT Favorite Setup,存/取命名参数集到 `configs/presets/*.json`(UTF-8 无 BOM);ParamForm.apply_values/select_protocol/set_identity;app 预设工具条。
- **RunBrowser**:导出图 + **回流项目4**(复制 CSV/manifest,读 utf-8-sig 吃 BOM、写 utf-8 无 BOM)。
- **DC live 友好守卫**:选 DC+live 弹"未接真机后端,仅 dry"(不抛栈)。

**真实下发诚实结论**:**WGFMU live 真能下发**(RealWgfmuBackend 真 ctypes 调 wgfmu.dll execute,代码就绪待真机环境:DLL/VISA/接线 201/202);**DC/SMU live = NotImplementedError 仅 dry**;安全门 confirm==stage 真拦。

**测试**:本轮 +15(viz4+param6+preset3+rbexport2);`pytest tests/` **150 passed**;金标准 169/640 不破。commit 到 `6b2c694`(未 push)。

**⚠️ 仓库在被并行开发**:co-dev 提了 `d23dee0`(friendly names + group by"测什么")+ `1d00615`(no-code DSL Project5 M2);`ProtocolSpec.group` 已存在,我的代码/测试已兼容。**改 engine 共享文件(registry/wgfmu_fefet)前先 re-read 防冲突;本轮我只动 gui/。**

**R9 自动定时序列已做**(`gui/scheduler.py` DelaySchedule 纯逻辑 + SchedulePanel + app.py「自动定时序列」dock):写后秒-分钟级 delay 自动倒计时 + 到点触发当前协议,记 requested vs actual,免手动掐表(153 passed)。**剩余建议(未做)**:① randomize_delays 提升为可见 ADVANCED 开关(需动 registry+wgfmu_fefet,与 co-dev 协调);② DC live 真机后端(需接 SMU);③ 主结果图多 run 叠加(目前仅 RunBrowser)。

**椰椰待办**:测试机桌面双击 `run_gui.bat` 看界面;`git push`。

---

## 2026-06-23 → GUI 上位机"完整化"收口 + 全绿 131 + 可回退安全网(⭐新会话从这接)

**椰椰目标**:把测试机代码备份成可回退,然后把在建 GUI 改成"完整可用上位机,参考 EasyEXPERT,专属 FeFET,保留其他存储器预留位",测试确保功能全部正常再停。

**接力状态(全部 scp 到测试机 + 真机 pytest 绿)**:
- **可回退安全网**:G 盘 git checkpoint `6703392` + tag **`pre-gui-rebuild-20260623`**(回退 = `git reset --hard pre-gui-rebuild-20260623`)+ 全历史 bundle `C:\Users\Administrator\.claude\tmp\B1500_pre_gui_rebuild_20260623.bundle`;测试机物理备份 `D:\test\B1500_backup_pre_gui_20260623`。
- **现状澄清**:GUI 非从零——M1 引擎 + `gui/` 16 文件早落地、`python -m gui` 本就能起。本轮=**完整化打磨 + 测试坐实**,非重写。MainWindow 在 `gui/app.py`(无独立 main_window.py)。
- **本轮新增/改(均已 scp + 测试机绿)**:
  ① `tests/conftest.py`:offscreen 兜底——**自动 strip 掉 cmd `set VAR=offscreen &&` 的尾随空格**(根治 06-17 坑①,曾让首个建窗测试 exit 9 假"段错误")+ setdefault offscreen + 会话级 `qapp` fixture(不依赖 pytest-qt)。
  ② `gui/app.py`:菜单栏(文件/视图/设备/帮助)+ 状态栏接线指示(Gate=202/Drain=201/CH302禁用)+ QSettings 布局持久化 + 接线/关于对话框 + `--selftest` 无人值守冒烟 + on_shot→max|Ig| 安全指标。
  ③ `gui/run_control_panel.py`:"预检/安全"组(接线状态行 + 本轮 max|Ig| 着色)+ reset_safety/update_safety。
  ④ 扩展缝坐实:`tests/test_extensibility_seam.py`(假 RRAM family 自动出 tab + 新 csv_schema 分派 + 壳层无 FeFET 协议码硬编码)+ 指南 `_agent/references/扩展_新增存储器类型指南.md`。
  ⑤ worker 集成测试 `tests/test_engine_worker.py`(WGFMU E1 + DC_IDVG 两 family dry 真跑通——壳里唯一"按运行"路径,此前零覆盖)。
  ⑥ `gui/__init__.py` 文档串改 raw(去 `\B` SyntaxWarning)。
- **验证**:测试机 `pytest tests/` = **131 passed**(120→+11);`python -m gui --selftest`(offscreen)**exit 0**(真起主窗口+事件循环+干净退出);金标准 ALL_DRY **169/640 不破**。
- **"完整可用"边界(诚实)**:dry-run 全链路 + DC 卡片 + 扩展缝 = **已测可用**;**live 真机 / 会话恢复(M4)= UI/安全门已接但未在真机验证**(需接 B1500 + 器件,有烧器件风险,留椰椰本地确认);M5 自定义配方 DSL / M6 PyInstaller 打包 = **预留未做**(椰椰说"以后可加")。

**椰椰待办**:① 测试机**桌面**双击 `run_gui.bat` 亲眼看界面(SSH 起的窗口不在它显示器上);② git push(本轮 commit 未推,需代理);③ 决定要不要继续 live 真机联调(M4)/ 自定义配方(M5)/ 打包(M6)。

**坑沿用**:远程 `pytest tests/`(限定目录,别 bare,会收集旧用例/开真机 VISA);`set "QT_QPA_PLATFORM=offscreen"`(加引号——现 conftest 已兜底但 shell 仍建议加)。

---

## 2026-06-22 → SSH 闭环打通 + M1 Step1(on_shot)/Step2(B7) done＋真机验证

**椰椰问"你是可以 ssh 连接的吧"→ 是,且已闭环。** 分析机本身在 Tailscale 网内,`ssh administrator@100.108.189.9` 免密 + `scp` + 远程 `pytest` 全通(DERP 中继)。上一会话连不上是网络隔离的 Cowork 沙箱(另一套环境),与本机无关;UU远程鼠标/剪贴板绕路作废。**以后一改一验证我自己闭环:G 盘改 → scp 推 → 远程 pytest → 读结果。**

**本会话产出(均已 scp 到测试机 ＋ 真机 pytest 绿):**
- **Step1 on_shot**:4 文件(`protocols/wgfmu_fefet.py`、`engine/engine.py`、`engine/callbacks.py`、`tests/test_engine_run.py`)。→ **同时解锁 06-17 handoff 里说的 M3 逐炮实时绘图**(GUI 现可接 on_shot)。
- **Step2 B7 常量提升**:`wgfmu_fefet.py` + `engine/registry.py`;9 个新 flag＋ParamSpec(E3W/E3A/E4/E5);新增顺序保留解析 `_parse_float_list_ordered`(踩 `E4_PREBIAS_V=[0,+2,-2]` 非升序 → 原 `sorted()` 会破金标准 的坑)。
- 测试机 `tests/` **89 passed in 25s**;ALL_DRY 仍 `execute_count=169 / max_vectors_seen=640`。备份 `.bak_20260622`(Step1 四文件)、`.bak_20260622_preB7`(B7 两文件)。

**同步真相(纠正上一会话的"岔开"恐慌):** G 盘 vs 测试机 65 个 .py **内容完全一致**(差异仅 CRLF/LF);G 盘 git 含测试机 HEAD `7389f01` 且领先 11 commit = 规范源。别再被 Google Drive 按需枚举的"空文件夹/缺 gui"假象骗;比对一律用内容哈希 `C:\Users\Administrator\.claude\tmp\hashpy_norm.ps1`。

**下一步(M1 余项剩 5):** ① `validate_params` → ② `build_argparser`(依赖 B7,现可做)→ ③ DC 注册进 REGISTRY → ④ BackendManager → ⑤ 去模块全局 `GATE_CH/DRAIN_CH/...`(线程安全,压轴)。另:GUI v1(06-17)已在测试机可跑(桌面双击 `run_gui.bat`),on_shot 就位后 M3 live 绘图可接。

**坑备忘:** 远程测试跑 `pytest tests/`(限定目录),**勿** bare `pytest`——会收集 `_agent/remote_backup_*/` 旧用例 ＋ `src/scripts/connect_test.py`(开真机 VISA)而炸。

---

## 2026-06-17 (2) → 上位机已同步测试机 + 离屏验证 17 passed(可上桌面看界面了)

- **同步**:本机 Tailscale 重启后连通(SSH 一度超时其实是本机 Tailscale 没起,起来即通)。SHA256 核验:测试机 `engine`/`protocols` 与本机一致(`audit_backend.py` 仅 CRLF/LF 差异、功能同),故**只推新增**:`gui/`(14)+`requirements/gui.txt`+`run_gui.bat`+`tests/test_gui_smoke.py`,17 文件逐字节核对一致,**零覆盖现有代码**。
- **装依赖**:测试机 venv(Python 3.13.5)装 PySide6 6.11.1 + pyqtgraph 0.14.0(清华镜像)。
- **验证(offscreen 离屏)**:`pytest tests/test_gui_smoke.py tests/test_engine_run.py` → **17 passed**(ParamForm 覆盖全部 12 协议 + MainWindow 构造 + 12 段 dry 逐字节对齐金标准)。GUI 组件构造无误。
- **远程操作三个坑(记下别再踩)**:① 本机别在 shell 里 `set QT_QPA_PLATFORM=offscreen & ...`——cmd 把 `&` 前空格并进变量值,Qt 报 plugin `"offscreen "`(带空格)直接 abort;让测试自己 `os.environ.setdefault` 即可。② ssh→远端 cmd 下 `python -c "..."` 的双引号会被吞,改用无引号命令或 scp 脚本文件再跑。③ pytest 里 QApplication 必须放模块全局,否则测试结束 GC 析构顺序错乱段错误(已修 `tests/test_gui_smoke.py` 的 `_APP`)。
- **待椰椰**:在测试机**桌面**双击 `run_gui.bat`(或先建桌面快捷方式)看界面——SSH 启的 GUI 窗口不会出现在它的显示器上,必须在测试机本地/RDP 启。`QFontDatabase` 字体警告 offscreen 才有,真桌面无碍。

---

## 2026-06-17 → 上位机初版界面已写 + 对抗式自查 + 修复(本机未跑,待测试机验)

**椰椰拍板**:不只出计划了,直接做初版界面,"我们再改"。

**已落地**:新增 `gui/` 包(14 文件)+ `requirements/gui.txt`(PySide6+pyqtgraph)+ `tests/test_gui_smoke.py`(离屏,无 PySide6 自动 skip)。架构=共性壳 + FeFET 适配层:
- 壳(与存储器无关):`app/main_window`、`protocol_panel`(按 `family` 泛化分组)、`param_form`(按 `ParamSpec` 自动生成)、`run_control_panel`(身份+dry/live+运行/停止)、`engine_worker`+`engine_controller`(QThread,worker 只 emit 不碰 widget)、`plot_panel`/`log_panel`/`plot_dispatch`(按 csv_schema 查表)。
- 适配层:`gui/adapters/fefet_plots.py` `@register_plot("fefet_fixedcols")`。
- 只走引擎门:worker `params=vars(parse_args([])) ∪ 非None表单/身份`,`make_backend(live)`,`ProtocolEngine().run(stage,params,backend=,callbacks=,confirm=)`。dry 结果图标"DRY 占位电流·非器件数据"(守 02_Plan 弯路铁律)。

**本机不跑**(分析机),用对抗式 review 代替运行:两轮工作流(plot/pandas + 引擎接口/PySide6/逻辑健壮性,后三个首轮 API socket 挂掉已重跑),共 20 条发现、**0 high**。已修:①清空数值框→None 覆盖默认致 `range(None)`/`float(None)` 崩(表单回退默认 + worker 丢 None 键双保险);②`make_backend` 早于 `configure_channel_map` 致用错/陈旧通道全局(worker 里先 configure 再 make_backend,镜像 CLI);③进度条空转(接 `set_progress`);④两处 legend 累积泄漏;⑤`_pattern_xy` 容忍 dict 向量;⑥波形标"最后一炮"、`protocolSelected` 接状态栏、运行中禁用协议树。**留作后续(v1 可接受)**:逐炮实时绘图(M3,待 runner 接 on_shot)、request_stop 直接置 bool(GIL 安全,设计如此)。

**下一步**:① 按同步铁律把整个 `gui/` + `requirements/gui.txt` scp 到测试机(覆盖不 pull),`pip install -r requirements/gui.txt`,`python -m gui` 实跑(注意:测试机 venv 须已 `pip install -e .`,否则 smoke 测试 import fefetlab 会 ERROR 而非 skip);② 椰椰看界面提改法迭代。**另:**《代码规范》文档(规范抽取工作流已出 133 条+核验)尚未成文,GUI 这轮后补。

---

## 2026-06-16 → 上位机 M2 详细搭建计划已出（只出计划，未动工；等椰椰过目）

**椰椰决策**：(1) 本次只出详细搭建计划，过目后再写代码；(2) 扩展策略=**FeFET 优先，但先把"共性壳/功能键"与"按存储器单独适配"的缝划清**，将来加新存储器（RRAM/相变…）界面功能键一致、只补适配层、`gui/` 不重写。暂无具体第二种存储器目标，留好位即可。

**计划落点**：`_agent/tasks/M2_GUI骨架_搭建计划.md`（含现状校正/共性-适配契约/文件清单/数据流/分步验收/风险）。

**关键结论（读真代码核出，供动手时贴齐）**：
- M2 竖切片**不卡硬件、不卡 M1 余项**：dry-run 走 `make_backend(False)`→`AuditBackend`→现有 `engine.run(id, params, backend=bk, callbacks=cb)`，可在 G 盘开发机直接写+测。
- 真代码 4 处与设计文档措辞不一致（计划按真代码）：`engine.run` 是**注入式 backend**（BackendManager 未建）、`ParamView(params)` 单参、`validate_params` 未接、`on_shot/on_progress` 未接进 runner。
- `REGISTRY` 已带逐参数 ParamSpec（12 段，含 MLC），按 `family` 分组；波形预览唯一真值源=`AuditBackend._patterns`（元组解包，勿用 `DummyWgfmuBackend`）。
- **依赖缺口**：base.txt 无 GUI 依赖，M2.0 须加 `requirements/gui.txt`（PySide6+pyqtgraph）。
- **接缝铁律**：M2.4 必须落 `gui/plot_dispatch.py` 注册表 + 协议树按 family 泛化，否则"共性/适配"缝形同虚设。

**下一步**：椰椰过目计划 → 确认后从 M2.0 起逐步实施（每步独立验收）。同步到测试机要带上整个 `gui/` + `requirements/gui.txt`（scp 覆盖不 pull）。

---

## 2026-06-11 (2) → 🐛 hotfix：single_shot M1 搬家漏改 `_HERE`（import 即崩）已修，git 未提交

**问题**：06-10 M1 搬家把 `_HERE` 更名 `_SRC`，但 `scripts/wgfmu_single_shot_disturb.py` 行 1066 `REST_ANCHOR_PATH = _HERE.parent/...` 漏改 → import 即 NameError，**现行版完全不可运行**（项目4 开题摘要审计工作流顺带发现）。

**修复（2026-06-11，Claude·开题会话代办）**：改为 `_SRC.parent / "runs" / "rest_anchor.txt"`（`_SRC.parent` 与旧 `_HERE.parent` 同为仓库根，rest_anchor 落点不变），带注释。py_compile 通过、`_HERE` 运行时引用清零。**未跑完整测试套件、未 commit——下次会话顺手 pytest + 提交**。测试机上现部署的是 06-09 旧版（哈希 a1f514d0，不受影响），但**修复 commit 前禁止 scp 部署现行版**。

---

## 2026-06-11 → 上位机重构 M1：engine 键石已落地 + 命名(serial/die)收口；M1 余项派 codex

**大背景**：项目3 从散脚本走向**测试机本地 PySide6 上位机**（远程只为开发，装好即独立运行）。设计文档 `_agent/references/B1500_GUI架构设计_PySide6.md` + `_agent/references/B1500_自定义测试配方与接线档案_设计.md`。

**已落地（commit/push/测试机验证，79 passed）**：
- **搬家**：1378 行 WGFMU CLI → `src/fefetlab/protocols/wgfmu_fefet.py`（原 `scripts/wgfmu_next_round_minimal.py` 退役）。`ALL_DRY` 审计 = **execute_count=169 / max_vectors_seen=640**（E6R/E6D 加入后；旧 96 作废）。
- **M1 引擎键石**：`src/fefetlab/engine/`（specs/param_view/callbacks/registry/engine）。`ProtocolEngine.run(protocol_id, params, *, backend, callbacks)` = GUI/CLI **唯一执行门**，经 `ParamView` 驱动现有 11 段 `run_stage_*`，**逐字节对齐金标准**（零行为改变）。
- **数据存储两级归集**：`runs/<device>/<die>/{live,dry}/<ts>_<stage>/`。device=`--device-id`（批次/自命名，可中文，如 `微所pfefet2026`）；die=`--geometry`+`--serial`（如 `L10W40_41`）。新增 **`--serial`**（修复序号此前并入自由文字 device-id 后丢失的回归），manifest 加 `serial`。**下游（项目4/2）读 manifest 的 device_id/geometry/serial，勿按路径深度解析**（历史有扁平/器件一级/两级三种布局并存）。

**进行中**：M1 余项派 **codex**（本机 codex 在 `C:\Users\Administrator\.codex\.sandbox-bin\codex.exe`，不在 PATH）——先做**安全机械核心**：ParamSpec 逐参数枚举（registry.py 填 `params=(...)`）+ B7 常量提升（E3/E4/E5 硬编码→argparse 可设，默认值不变 → 金标准逐字节不动）+ `build_argparser`。**硬约束：79 测试全绿、ALL_DRY 169/640 不变、不碰 serial/die 代码。** 较险的 `on_shot` 接入 / DC 注册 / 去模块全局留作复核第二轮。

**下一步**：椰椰给新器件需求（几何/类型/安全电压/测什么/接线）→ 翻译成 stage+参数 → S0→S1→实验链。现有 CLI 已够测，M1 余项只挡 GUI 表单自动生成，不挡测试。

---

## 2026-06-10 → 新方向：用后面板 Digital I/O 口自制板控制（已建档，未动工）

**起因**：椰椰看后面板红框那个 D-Sub 口，想自制一块板挂上去做控制。已查官方手册核实并建档。

**核实结论**（出处 `b1500 program guide/9018-01851.pdf` ch.2-71~2-87 + 命令参考）：
- 是 **D-Sub 25 针母座**，内含 **16 路 TTL（DIO 1~16）**；官方文档完整覆盖、**可编程**（走现有 VISA/GPIB，文本命令 ERMOD/ERM/ERC/ERS?/TGP）。
- **自制板控制成立**（官方 16440A 选择器就是经 16445A 适配器挂这个口、B1500 翻 DIO 位切 SMU↔SPGU）。
- **纠正一个说法**：这 16 根线**不能配置/驱动 SMU/WGFMU 的测量功能**（那是总线软件的活）；它干的是 ①输出 16 位 TTL 驱动你的板子（继电器/选择器）②读外部状态做联锁 ③硬件触发同步。
- **线**：自制板**不必买原厂线**，一根 DB-25 公头转端子的现成线即可（B1500 侧是母座，你要公头）；要原厂/BNC 才看 16493G、N1253A-100、N1253A-200。

**完整档案**（引脚表/电气/命令/设计步骤/待核实项）：`_agent/references/digital_io_port_自制板控制_档案.md`。
**测试计划 HTML**（给椰椰看的单文件，kami 视觉语言，含接线/命令/测试代码/板子架构）：`_agent/references/digital_io_测试计划.html`。

**⏸ 当前挂起（等硬件）**：椰椰要先买 **DB25 公头转接线端子板**（标准两排 13+12、**公头**，因 B1500 那口是母座；淘宝搜「DB25 公头 转接线端子」）。到手插上后跑 16 线 smoke 验证：`ERMOD 0` → `ERC 2,1`（只拉低 DIO1，量哪个端子掉到~0.8V 即确认 DIO1=针15，GND=针13/25）→ 逐位翻 + `ERS?` 读回。**纯量 TTL、不接器件、零风险。** 我已提议写 `scripts/digital_io_smoke.py`（逐根翻+读回+引脚对照+preflight），等椰椰买到插头说一声就写/上机。

**之后（板子方向）**：等椰椰定板子目标（路由切换 / 安全联锁 / 触发同步，可叠加）→ 画 DIO bit→功能映射表 → 在 `src/fefetlab/b1500/driver.py` 加 ERMOD/ERM/ERC/ERS?/TGP 薄封装（Mock 先行）。架构=自制版 16440A/RSU，难点只在信号完整性(SMU 保 guard/低漏、WGFMU 保快沿)。WGFMU 是否能经本口触发需另查 B1530A 手册。

---

## 2026-05-26 01:33 CST → B1500_VISA_ADDR override 真机验证已过，待 commit/pull 同步

**改动**：`scripts/wgfmu_next_round_minimal.py` live backend 初始化时优先读 `B1500_VISA_ADDR`；有值则直接使用并打印 `B1500_VISA_ADDR_OVERRIDE`，无值才 `autodetect_visa_addr("B1500")`。

**真机验证**（`D:\test\B1500`）：
1. 覆盖前远端备份：`D:\test\B1500\_agent\remote_backup_before_hermes_test_20260526_012839\`。
2. `pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q` → **13 passed in 5.73s**。
3. `--stage PLAN` → `REPORT_CODE: PLAN_ONLY_NO_HARDWARE`。
4. `--stage ALL_DRY --s0-reps 1 --s1-reps 1 --e1-reps 1 --e2-reps 1 --e3-reps 1 --e4-reps 1 --e5-reps 1 --cycle-count 1` → `DRY_RUN_AUDIT: execute_count=96 max_vectors_seen=640`。
5. live override smoke：`set B1500_VISA_ADDR=GPIB1::17::INSTR && ... --stage S0 --live --confirm S0 --device-id ENV_OVERRIDE_TEST --geometry OPEN --s0-reps 1` → `B1500_VISA_ADDR_OVERRIDE: GPIB1::17::INSTR`，`WGFMU_CHANNELS: [201, 202, 301, 302]`，`REPORT_CODE: S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE`，CSV `D:\test\B1500\runs\20260526_012948_S0_open_fixture_smoke_ENV_OVERRIDE_TEST\s0_open_fixture_smoke.csv`。

**下一步**：本地 commit + push，然后真机 `git pull origin main`，确认 clean/同 SHA。

---

---

## 2026-05-22 18:58 CST → L40W10_02 stop-gated WGFMU 已跑完 S1/E1/E2 minimal

**已执行**：
1. S1 device read-only baseline：`D:\test\B1500\runs\20260522_183051_S1_device_read_only_baseline_L40W10_02\s1_device_read_only_baseline.csv`，`max_abs_Ig_A=1.552721e-06`。
2. 低压 `VOLTAGE_ECHO`：`D:\test\B1500\runs\20260522_185045_VOLTAGE_ECHO_L40W10_02\voltage_echo_low_v_read_only.csv`，最大电压误差约 `1.81 mV`；不是示波器，不证明写脉冲探针端波形。
3. E1 QUICK300ms v2：`D:\test\B1500\runs\20260522_185326_E1_RAWD_QUICK300ms_v2_L40W10_02\e1_rawd_quick300ms_v2.csv`，48 rows，`max_abs_Ig_A=5.274616e-06`。
4. E2 minimal：`D:\test\B1500\runs\20260522_185718_E2_minimal_A1_A100_C1_C10_L40W10_02\e2_minimal_A1_A100_C1_C10.csv`，24 rows，`max_abs_Ig_A=5.897400e-06`。

**云端归档**：项目4 `实测数据/S1_device_read_only_baseline/20260522_L40W10_02/`、`实测数据/voltage_echo_low_v_read_only/20260522_L40W10_02/`、`实测数据/E1_rawd/20260522_L40W10_02_QUICK300ms_v2/`、`实测数据/E2_read_disturb/20260522_L40W10_02_minimal_A1_A100_C1_C10/`。

**下一步**：先判读，不要直接继续 E3；若继续上机，优先在“重复 E1 e1-reps=3”和“E5 read-window grid”之间二选一。

---

---
## 2026-05-22 17:47 CST → WGFMU openSession=-6 真根因修正 + S0 空夹具 live 已过

**已完成**：远程只做无输出 openSession 诊断 → 最小修复 → dry-run/只开会话验证 → S0 空夹具 live 低扰执行。

**关键结论**：`GPIB1::17::INSTR` 是可用资源串，raw `WGFMU_openSession` 本身能成功。真正触发 `status=-6` 的是旧 preflight 里的 `*CLS`：yhzang 这台 B1500A 会把 `*CLS` 入队为 `+100,Undefined GPIB command`，随后 WGFMU DLL openSession 读到该错误而失败。

**当前标准 preflight**：只用 `clear_b1500_status_for_wgfmu_open(VISA_ADDR)`：pyvisa `inst.clear()` → drain `ERRX?` 到 0 → `*IDN?` → 再 drain `ERRX?` → close `inst/rm` → `sleep(2)` → `backend.open_session()`。不要发 `*CLS`，不要默认 `*RST`。

**已落地/同步**：
- `src/fefetlab/measurements/wgfmu/setup_helpers.py`：helper 改为 ERRX drain，不发 `*CLS`。
- `scripts/wgfmu_next_round_minimal.py`：日志改为 `B1500 preflight ERRX drain OK`。
- `tests/test_wgfmu_iv_and_wakeup.py`：新增 `test_wgfmu_open_preflight_drains_errx_without_cls` 回归测试。
- 已同步到真机 `D:\test\B1500`。

**验证**：
- 真机 `py_compile` 通过。
- 真机 regression：`test_wgfmu_open_preflight_drains_errx_without_cls` → 1 passed。
- `--stage PLAN` / `ALL_DRY --s0-reps 1 --s1-reps 1 --e1-reps 1 --e2-reps 1` 通过；dry-run 无 VISA/DLL/硬件输出。
- 真机只开会话验证通过：`WGFMU_CHANNELS: [201, 202, 301, 302]`，close status 0。
- S0 空夹具 live 低扰版已跑：`--stage S0 --live --confirm S0 --device-id OPEN_FIXTURE --geometry OPEN --s0-reps 1` → `S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE`；3 rows；`max_abs_Id_A=1.445244e-07`，`max_abs_Ig_A=3.057571e-07`；CSV `D:\test\B1500\runs\20260522_174642_S0_open_fixture_smoke_OPEN_FIXTURE\s0_open_fixture_smoke.csv`。

**下一步**：不要自动进入 S1。只有 yhzang 确认探针已经落到器件后，再跑 S1 device read-only baseline；S1 仍按 `|Ig|>5µA` stop gate。

---

## 2026-05-22 → 下一轮 WGFMU stop-gated 上机从这里开始

**已准备好**：真机 `D:\test\B1500` 上已有 `D:\test\B1500\scripts\wgfmu_next_round_minimal.py` 和 `D:\test\B1500\_agent\runbooks\20260522_next_round_stop_gated_wgfmu.md`。

**怎么跑**（PowerShell）：
```powershell
cd D:\test\B1500
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage S0 --live --confirm S0 --device-id L40W10_01 --geometry L40W10
```
S0 通过后才跑 S1；S1 通过后才跑 E1；E1 健康后才跑 E2。任何 `*_STOP_*` 都停，把 `REPORT_CODE`、`OUTPUT_CSV`、`max_abs_Id_A/max_abs_Ig_A` 发回。

**顺序/阈值**：S0 空夹具/抬针 read-only smoke (`|Ig|>5µA` 停) → S1 器件 read-only baseline (`|Ig|>5µA` 停) → E1 RAWD QUICK300ms v2 (`|Ig|>20µA` 停) → E2 minimal A1/A100/C1/C10 (`|Ig|>20µA` 停，先不跑 C100)。

**验证**：远程 `py_compile` / `PLAN` / `ALL_DRY` 已过；dry-run 不打开 VISA、不加载 DLL、不触发硬件输出；`max_vectors_seen=640<2048`。

---

## 2026-05-22 · G盘 ↔ 真机 D:\test\B1500 双端代码统一

- 背景：yhzang 有时改 G 盘工作区，有时改真机 `D:\test\B1500`，两端 raw hash 差异较多。
- 对比方式：先做 raw manifest，再做语义 manifest；文本统一换行，notebook 去掉输出/metadata 后比较。
- 结论：源码/测试语义已经一致；真实活跃差异只在 `_agent` 文档与 `notebooks/30-34`。大量 raw diff 只是 CRLF/LF。
- 统一策略：
  - `_agent/01_State.md`, `_agent/03_Log.md`, `_agent/05_Handoff.md`：以 G 盘最新版为准同步到真机。
  - `notebooks/31-34`：以 G 盘最新版为准同步到真机，保留 `clear_b1500_status_for_wgfmu_open()` preflight 与 Gate=202/Drain=201。
  - `notebooks/30_E1_rawd.ipynb`：以 G 盘最新版为代码底座，但保留真机端用户参数 `DEVICE_ID="L40W10_01"`, `GEOMETRY="L40W10"`。
  - `notebooks/30_E1_rawd_QUICK300ms.ipynb`：真机端独有，已复制回 G 盘，并升级为同样的 preflight/helper 写法。
  - 真机端旧 `.bak` 与 `_agent/remote_backup_before_hermes_test_*` 只作备份，不参与代码统一。
- 备份位置：
  - G 盘：`_agent/sync_backup_before_unify_20260522_041927/`
  - 真机：`D:\test\B1500\_agent\sync_backup_before_unify_20260522_041936\`
- 验证：
  - 双端语义 manifest 复查：活跃文件 0 diff；剩余差异全部为备份目录/`.bak`。
  - 真机：`D:\test\B1500\.venv\Scripts\python.exe -m pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q` → **12 passed in 0.71s**。
- 后续口径：短期以 G 盘工作区为规范源；真机端可跑实验/临时改 notebook，但跑前跑后要回同步，尤其不要让 `DEVICE_ID/GEOMETRY` 与 preflight 修复互相覆盖。


## 2026-05-22 → WGFMU openSession=-6 事故收口 · 通道/拓扑口径修正

**这次干了什么**: 针对 E1 QUICK300ms / E1-E5 真机 notebook 的 `WGFMU_openSession status=-6` 事故做根因收口，并扫描旧通道硬编码。结论已经落到代码、notebook 和 `_agent`。

**硬事实 (真机复核)**:
- `*IDN?`：`Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401`
- `UNT?`：`B1525A,0;B1530A,0;B1530A,0;B1517A,0;B1517A,0;B1517A,0;B1511B,1;B1520A,0;0,0;0,0`
- 口径：slot1=B1525A；slot2/3=B1530A；slot4/5/6=B1517A；slot7=B1511B disabled；slot8=B1520A。
- FeFET 接线铁律：**Gate=CH202, Drain=CH201**。不要再用 `autodetect_wgfmu_chan(... prefer=201)` 推断 gate。

**openSession=-6 根因/修法**:
- 不是 DLL 位数，也不是通道不存在；是 B1500 GPIB error queue / VISA resource 残留导致 WGFMU DLL `openSession` 读到旧错误队列。
- 标准 preflight：`inst.clear()` → drain `ERRX?` 到 0 → `*IDN?` → 再 drain `ERRX?` → `inst.close()` → `rm.close()` → `sleep(2)` → 再 `backend.open_session(VISA_ADDR)`。**不要发 `*CLS`**（本机实测会入队 `+100` 并导致 -6）。
- 已做成 helper：`clear_b1500_status_for_wgfmu_open(VISA_ADDR)`，位置 `src/fefetlab/measurements/wgfmu/setup_helpers.py`。

**本轮最小修正**:
- `notebooks/30_E1_rawd.ipynb`, `32_E3_pulse_matrix.ipynb`, `33_E4_imprint.ipynb`, `34_E5_visibility.ipynb`：旧 `Gate=autodetect/prefer201, Drain=202` 已改为 `Gate=202, Drain=201`。
- `notebooks/30-34`：所有 `backend.open_session(VISA_ADDR)` 前已插入 `clear_b1500_status_for_wgfmu_open(VISA_ADDR)`。
- `src/fefetlab/measurements/wgfmu/experiments.py`：修复 `run_e1_single_point()` 对 backend result 契约的旧用法（size 是 `(complete,total)`；values 是 DataFrame，不是 `(times, values)` tuple）。
- `tests/test_wgfmu_iv_and_wakeup.py`：新增 E1 单点回归测试；缺 DLL 测试改为 mock `ctypes.WinDLL`，避免真机系统级 `wgfmu.dll` 让“缺 DLL”用例误通过。

**验证**:
- 已通过 SSH 在真机测试机跑：`Administrator@100.108.189.9` → `D:\test\B1500` → `.venv\Scripts\python.exe -m pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q` → **12 passed in 0.71s**。
- 关键纠正：项目3 WGFMU 测试默认应在 B1500 真机测试机跑，不要在本机 WSL 里用缺依赖环境假跑。

**下一次真机操作提示**:
1. 真机 `D:\test\B1500` 拉最新代码后，Jupyter 里不要只 Restart Kernel；如果浏览器 tab 还开着旧 notebook，要 Refresh/Reopen 文件，避免执行 stale in-memory cell。
2. 从 E1/E2/E3/E4/E5 的 setup cell 重新跑，看到 `B1500 preflight ERRX drain OK: ...` 后再进入实验循环。
3. 若再报 `openSession=-6`，优先查是否有另一个 notebook/kernel 占用 WGFMU session，再查 GPIB-USB hang（必要时拔插）。

---

## 2026-05-20 → L0+L1 全过 · 真机适配完成 · 等接器件做 RAWD

**这次干了什么**: yhzang 在新电脑 `D:\test\B1500` 把 WGFMU 链路从代码到真机全验通。`20_dryrun + 22_dryrun + 21_realdevice + 23_realdevice` 四个 notebook 全 PASS, 期间发现并修了 20 个真机适配 bug, 全部 push 到 GitHub。

**关键技术决策 (跟之前不一样)**:
- 真机 baseline 不是 0, 是 RSU+3m HRSU 电缆 + 探针卡的 **440kΩ 漏电路径**, 在 -0.5V 下表现为 ~1.14 µA, 跟电压成线性关系 (实测验证: 0V→11nA, -0.5V→1.14µA, t_rise 改 10x 无影响排除电容主导)
- 旧口径已更正：FeFET 实测接线为 **Gate=CH202, Drain=CH201**；不要再按 CH201=Gate 执行
- 项目 4 总台 R1 真正要做的是 **E1 RAWD** (write-after-delay 单点读), 不是传统 IDVG sweep — 必须用 **WGFMU 双通道** (CH202 Vg 脉冲 + CH201 Vd 测 Id 瞬态；旧 CH201=Vg 口径已废弃), SMU 跟不上 µs 级 read pulse

**新机器怎么准备**:
```powershell
# 1) 装 Keysight IO Libraries Suite (VISA)
# 2) 装 NI-488.2 GPIB driver (Keysight VISA 不够)
# 3) 装 Keysight B1530A Instrument Library 64-bit (dll 落到 C:\Windows\System32\wgfmu.dll)
# 4) 拉代码
cd <work_dir>
git clone https://github.com/yhzang/B1500.git
cd B1500
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
# 5) 跑测试
pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q  # 期望 11 passed
# 6) 跑 notebook 20→22→21→23
jupyter notebook notebooks/
```

**地雷 / 已知坑** (今天踩过的, 都修了或文档化了):
- PowerShell `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` 要先放行才能激活 venv
- pip 装包: 必须加 `--trusted-host` 或用清华镜像, 不然 SSL 证书错
- B1500 GPIB-USB 偶发 hang, 拔插一次 USB 即恢复
- 双 GPIB 卡时 list_resources 返回 GPIB0 + GPIB1, 真 B1500 可能在 GPIB1 (用 `autodetect_visa_addr("B1500")` 自动找)
- WGFMU CH 没接 RSU 不能 FASTIV: 报 `RSU is not connected; CHANNELxxx` (yhzang 本机 302 没接 RSU)
- WGFMU.cs 真值: enum 全是 offset+小数字 (2000+, 3000+, 4000+, 5001+, 6001+, 7000+, 12000+, 1000+), 不是 0/1/2
- 第一版 real_backend.py 所有 enum 全错 (已修)
- WSL G 盘是 Google Drive 挂载, 不支持 symlink, venv 必须建在本地盘

**下次开场要确认**:
- yhzang 准备好器件 (L10W10, 接 WGFMU 双通道 + RSU + 探针) 了吗
- 明天目标: 写 `24_wgfmu_rawd_device.ipynb` (E1 RAWD 简版 5 个 t_delay 点) → 真器件跑通

**E1 RAWD 设计参数** (要 yhzang 明天确认的):
- Vg 通道: CH202 (Gate；2026-05-22 已复核)
- Vd 通道: CH201 (Drain；2026-05-22 已复核)
- ERS pulse: +5V / 100µs (王渊标称)
- PGM pulse: -5V / 100µs (王渊标称)
- read pulse: Vg = -0.5V / 5µs, Vd = -50 mV 恒定
- t_delay 简版: 1µs / 10µs / 100µs / 1ms / 10ms (5 点验 setup)
- t_delay 完整: 17 点 (1µs → 100s, 半 decade)

**测试人**: **yhzang (本人)**, 不是别人

---

## 2026-05-16 → WGFMU 编码完成 · 等真机 (已合入历史, 由 2026-05-20 取代)

(详见上)
