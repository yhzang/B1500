# 工作日志

## 2026-05-16 05:30 WGFMU 模块编码完成（驱动层 + 波形构建 + 测量协议）
- Goal：椰椰要求把 WGFMU 部分写好，能像 SMU/DC 链路那样通过代码控制 B1500 跑 WGFMU 功能。**只要编码 + 测试通过证明**，不要画图、不要 mock 数据、不要 demo。
- What changed：
  - 新增 `src/fefetlab/measurements/wgfmu/real_backend.py` (461 行)：基于 ctypes 的 `RealWgfmuBackend`，绑定 27 / 95 个 WGFMU2 C API (从 B1530A User Guide 提取)。Linux 可静态导入，调用 `.load()` 才解析 DLL，失败给清晰 OSError。
  - 新增 `src/fefetlab/measurements/wgfmu/pulse_builder.py` (206 行)：`PulseSegment` / `PulseTrainBuilder` / `PulseTrainPlan` / `linear_voltage_segments`，把多脉冲扫描的 (vector, measure_event) 时间线声明式构建出来，跟 backend 解耦。
  - 新增 `src/fefetlab/measurements/wgfmu/iv_sweep.py` (277 行)：`WgfmuIVSweepRunner` + `WgfmuIVSweepConfig` + `WgfmuIVSweepResult`，输入 segments 列表，输出 (samples_df, iv_df per-pulse summary, qc_df, meta, plan)。
  - 新增 `src/fefetlab/measurements/wgfmu/wakeup.py` (359 行)：`WgfmuWakeupRunner` + `WakeupStage` + `WakeupReadout`，多阶段 PGM/ERS 交替 + 低扰读出，per-cycle 汇总。
  - 重写 `src/fefetlab/measurements/wgfmu/__init__.py`：导出新接口、`list_wgfmu_scaffold_features()` feature map 扩展。
  - 新增 `tests/test_wgfmu_iv_and_wakeup.py`：6 个契约测试 (pulse builder 时间线、IV runner 工作流、wake-up runner 工作流、RealBackend 无 DLL 静态可导入 + load() 失败信息清晰、feature map 完整性)。
  - 历史保留：`backend.py` / `config.py` / `smoke.py` / `export.py` / `README.md` 未触动。`DummyWgfmuBackend` 沿用作为本地测试 backend。
- Evidence：
  - `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ -q` → **33 passed in 7.74s** (基线 25 → 加 8)
  - `python -c "from fefetlab.measurements.wgfmu import RealWgfmuBackend, WgfmuIVSweepRunner, WgfmuWakeupRunner, PulseTrainBuilder, linear_voltage_segments, WakeupStage, WakeupReadout"` → 无报错
- Current state：WGFMU 模块在 mock 路径上完成"端到端走一遍 + 测试覆盖"。真机绑定层 (`RealWgfmuBackend`) 在 Linux 上验证了"无 DLL 静态可导入 + load() 失败信息清晰"两个契约。**真机 DLL 调用路径只能等真机那台执行**。
- Reverted (本轮中途的弯路)：曾经误加了 `physics_dummy.py` (假 PFeFET 物理模型) + `visualize.py` (matplotlib 画图) + `generate_wgfmu_deliverables.py` (demo 脚本) + `WGFMU_DELIVERABLES.md` (汇报文档)。椰椰指出"只要编码 + 测试通过"，已全部移除，不进 git 历史 (用 reset --soft 拆掉污染 commit 重做)。
- Next step：(1) 真机那台 git pull 后写 4-5 行调用代码连 B1500，跑通最小 IV sweep；(2) 项目4 总台出第一份 TR 测试单 (建议 R1-B)；(3) 真机数据回流到项目4 `实测数据/TR-*/` 后在项目4 `03_Log.md` 写一行收口。

## 2026-04-17 01:xx WGFMU 正式脚手架落地
- Goal：按用户要求先把 WGFMU 的正式模块架子搭起来，看清楚它当前准备承载哪些功能
- What changed：
  - 先基于 `notebooks/12_wgfmu_smoke.ipynb` 和现有 `dc/` 架构做了可行性分析，并把计划写入 `_agent/02_Plan.md`
  - 在 `_agent/archive/20260417_wgfmu_scaffold_preedit/` 做了修改前 checkpoint
  - 按 TDD 先新建 `tests/test_wgfmu_scaffold.py`，让 `fefetlab.measurements.wgfmu` 缺失导致收集失败
  - 然后正式落库 `src/fefetlab/measurements/wgfmu/`：
    - `config.py`
    - `backend.py`
    - `export.py`
    - `smoke.py`
    - `__init__.py`
    - `README.md`
  - 在 `src/fefetlab/measurements/__init__.py` 增加 WGFMU 导出
  - 新增 `list_wgfmu_scaffold_features()`，让当前脚手架支持的功能可以直接列出来
  - 同步更新 `README.md`、`TESTING.md`、`COMPLETION_SUMMARY.md` 到“WGFMU 脚手架已落库”的新状态
  - 新增测试说明：`_agent/runbooks/wgfmu-scaffold-test-closure.md`
- Evidence：
  - `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_wgfmu_scaffold.py -q -vv`
    - 结果：`3 passed`
  - `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_verify_dc_sweep_script.py tests/tests_imports.py tests/test_dc_measurement.py tests/test_wgfmu_scaffold.py -q`
    - 结果：`28 passed in 8.67s`
  - `list_wgfmu_scaffold_features()` 当前输出包含四组：config / backend / workflow / export
- Current state：WGFMU 已不再只是 notebook 原型，而是有了正式模块脚手架；但真实官方库绑定与真机联调仍未开始
- Next step：如果继续做 WGFMU，优先在当前脚手架上设计 `RealWgfmuBackend`，不要另起并行结构

## 2026-04-17 00:34:52 CST
- Goal：把 `fl_mode=1` 和 integration time 预留位做成“运行时可见”，便于用户一步一步执行脚本时直接核对输出
- What changed：
  - 新增 `tests/test_verify_dc_sweep_script.py`，先用 TDD 约束验证脚本必须显示关键配置
  - `scripts/verify_dc_sweep.py` 新增 `build_dc_config_display_lines()`
  - 模拟验证与真机验证入口现在都会打印：Channels / Delay / FMT / AV / Filter / Integration time
  - `README.md`、`TESTING.md`、`COMPLETION_SUMMARY.md`、`_agent/runbooks/batch-b-test-closure.md` 同步更新，把这个可见性测试纳入正式测试入口
- Evidence：
  - `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_verify_dc_sweep_script.py tests/tests_imports.py tests/test_dc_measurement.py -q`
    - 结果：`25 passed in 8.07s`
  - `cd '项目路径' && PYTHONPATH=src python scripts/verify_dc_sweep.py`
    - 输出中已显式出现 `Filter: ON (fl_mode=1)` 与 `Integration time: unset (reserved config only)`
- Current state：特殊默认值已经不仅“记案”，而且“脚本运行时可见”
- Next step：若用户接下来手动联调，可优先用脚本而不是 notebook，逐步核对这些输出项

## 2026-04-16 23:59:30 CST
- Goal：按用户要求，把上一轮手册复核里指出的高风险点按“可行性分析→计划→落地”流程真正收口
- What changed：
  - 先在 `_agent/02_Plan.md` 写了收口包 B 的可行性分析和实现计划
  - 在 `_agent/archive/20260416_batch_b_preedit/` 做了修改前 checkpoint 备份
  - 按 TDD 先修改 `tests/test_dc_measurement.py`，补出三个失败点：
    1. `fl_mode` 默认值应为稳定优先
    2. config 需要 integration time 预留位
    3. 多点 sweep 需要每点重新 connect 通道
  - 然后修改实现：
    - `src/fefetlab/measurements/dc/measure.py`：每个单点开始前显式 `CN`
    - `src/fefetlab/measurements/dc/sweep.py`：runner 初始化不再做一次性 `CN`
    - `src/fefetlab/measurements/dc/config.py`：`fl_mode` 默认设为 `1`，新增 `integration_time_mode` / `integration_time_factor`
    - `src/fefetlab/measurements/dc/README.md`：同步更新导入路径、参数命名和新配置口径
  - 新增本轮测试说明：`_agent/runbooks/batch-b-test-closure.md`
- Evidence：
  - failing test 命令：
    - `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_dc_measurement.py::test_config_creation tests/test_dc_measurement.py::test_config_supports_reserved_integration_time_fields tests/test_dc_measurement.py::test_sweep_reconnects_channels_for_each_point -q -vv`
  - 通过后的验证命令：
    - `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_dc_measurement.py -q`
      - 结果：`20 passed in 8.24s`
    - `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/tests_imports.py tests/test_dc_measurement.py -q`
      - 结果：`23 passed in 8.47s`
    - `cd '项目路径' && PYTHONPATH=src python scripts/verify_dc_sweep.py`
      - 结果：Mock / 模拟验证完整跑通
- Current state：高风险里的 `CN/CL` 生命周期问题已经收掉；filter 默认值已统一到更稳妥口径；integration time 先完成 config 预留位，但还没有真正接到仪器命令层
- Next step：若继续走仪器参数一致性路线，下一步该先确认 integration time 的正式编程命令，再决定是否接到 driver

## 2026-04-16 22:xx 手册复核（本轮未跑测试）
- Goal：按用户要求先不测，直接基于工作区内 B1500 官方文档再检查一遍代码风险和优化空间
- What changed：
  - 发现并读取了工作区内 `B1500手册/` 目录下多份官方/官方随附资料
  - 基于 `B1500-90000.pdf`、`B1500操作手册.pdf`、`9018-01993 EasyEXPERT Software.pdf`、`keysight-b1530a-series-user-guide.pdf` 重新复核了 `visa_session.py`、`driver.py`、`measure.py`、`sweep.py`、`dc_sweep_api.py`、`verify_dc_sweep.py`
  - 形成了新的手册对照结论并写入 `_agent/runbooks/manual-risk-review-20260416.md`
- Key findings：
  1. `CN/CL` 生命周期不一致，是当前最值得优先处理的真机风险
  2. `delay_s=0.2` + `fl_mode=0` 默认值与官方资料强调的 settling / filter / integration time 约束相比过于简化
  3. 当前解析与脚本仍适合简单 DC 路径，但对更复杂 FMT / buffer 读法的扩展性偏弱
- Evidence：
  - `B1500手册/B1500-90000.pdf`
  - `B1500手册/B1500操作手册.pdf`
  - `B1500手册/9018-01993 EasyEXPERT Software.pdf`
  - `B1500手册/keysight-b1530a-series-user-guide.pdf`
  - `_agent/runbooks/manual-risk-review-20260416.md`
- Current state：项目3现阶段最合理的下一步，不是继续扩功能，而是先做这轮手册复核里指出的高风险收口
- Next step：若用户确认继续 coding，先做“可行性分析→计划→落地”，优先修 `CN/CL` 生命周期和 settling/filter 策略
