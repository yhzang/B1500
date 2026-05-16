# 项目3 / B1500 自动化

## 项目定位
- 项目别名：项目3 / B1500
- 根路径：`/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500`
- 当前工作副本说明：这是阿耶工作区内的项目副本；当前目录不是 git 工作树。
- Python 包名：`fefetlab`
- 项目目标：围绕 B1500 自动化测量建立可复用的通信层、驱动层、DC/WGFMU 等测量 API、验证脚本和后续扩展结构。

## 当前目标
1. 保持 DC 主链路的代码、测试、脚本、文档一致
2. 给用户另一台电脑上的真机验证准备清晰入口和记录口径
3. 让 WGFMU 从 notebook 原型迈向正式模块，目前已先落地最小脚手架

## 从哪里继续
- 当前状态：`_agent/01_State.md`
- 当前计划：`_agent/02_Plan.md`
- 工作日志：`_agent/03_Log.md`
- 参考索引：`_agent/04_ReferenceMap.md`
- 环境/验证 runbook：`_agent/runbooks/setup-and-verify.md`
- 本轮测试收口：`_agent/runbooks/batch-a-test-closure.md`

## 关键路径
- `README.md`
- `TESTING.md`
- `ARCHITECTURE.md`
- `COMPLETION_SUMMARY.md`
- `scripts/verify_dc_sweep.py`
- `tests/test_verify_dc_sweep_script.py`
- `tests/tests_imports.py`
- `tests/test_dc_measurement.py`
- `tests/test_wgfmu_scaffold.py`
- `src/fefetlab/__init__.py`
- `src/fefetlab/instruments/visa_session.py`
- `src/fefetlab/measurements/dc/`
- `src/fefetlab/measurements/wgfmu/`
- `notebooks/12_wgfmu_smoke.ipynb`

## 当前已知关键事实
- 2026-05-16 已完成 **WGFMU 模块编码**（驱动层 + 波形构建 + 测量协议，与 DC 链路对称）：
  - 新增 `RealWgfmuBackend` (ctypes 绑 wgfmu.dll，覆盖 27 个 WGFMU2 C API)
  - 新增 `PulseTrainBuilder` + `PulseSegment` + `linear_voltage_segments`
  - 新增 `WgfmuIVSweepRunner` (脉冲扫 IV)
  - 新增 `WgfmuWakeupRunner` + `WakeupStage` (多阶段 wake-up)
  - 测试基线 **33 passed in 7.74s** (新增 8 个，原 25 个无回归)
- 2026-04-16 已完成"收口包 A"：
  - `VisaSession.query()` 已有返回值，并补了测试锁定行为。
  - `src/fefetlab/__init__.py` 已改成 lazy export，纯 Mock 路径不再因包入口 eager import 卡在 `pyvisa`。
  - `DCChannelConfig` 现以 `compliance` 为公开名，同时保留 `i_comp` 兼容。
  - `DCDataExporter` 现以 `export_dir` 为公开名，同时保留 `base_dir` 兼容。
  - `scripts/verify_dc_sweep.py` 模拟路径已重新跑通。
  - `README.md` / `TESTING.md` / `COMPLETION_SUMMARY.md` 已收口到真实仓库状态。
- 2026-04-16~17 已完成“收口包 B”：
  - `CN/CL` 生命周期已修复。
  - `fl_mode` 默认转为 `1`，并在验证脚本中显式打印。
  - `integration_time_mode` / `integration_time_factor` 已作为预留配置位落到 config。
- 2026-04-17 已完成 WGFMU 脚手架：
  - `src/fefetlab/measurements/wgfmu/` 已正式落库
  - 已有 `config.py` / `backend.py` / `export.py` / `smoke.py` / `README.md`
  - 已有 `DummyWgfmuBackend` 与 `WgfmuSmokeRunner`
  - 已有 `tests/test_wgfmu_scaffold.py`
- 当前本地已验证通过的入口：
  - `PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_verify_dc_sweep_script.py tests/tests_imports.py tests/test_dc_measurement.py tests/test_wgfmu_scaffold.py -q`
  - `PYTHONPATH=src python scripts/verify_dc_sweep.py`
- 当前未完成：
  - 真实硬件验证仍需用户在另一台电脑执行
  - WGFMU 仍未接真实官方库，仅完成正式脚手架
