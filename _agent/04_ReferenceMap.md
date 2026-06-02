# Reference Map

## 总台 (上游, 跨项目)

- **项目4 FeFET 测试 (总台)** ← 项目3 服务于这个总台
  - 总台入口: `G:/我的云端硬盘/阿耶工作区/项目4_FEFET测试/_agent/01_State.md`
  - 项目3 在总台中的角色: **采集器** — 按总台测试规约跑 B1500, 输出标准化 CSV + meta.yaml
  - 项目4 何时调用项目3:
    - 总台 Round 选定假设 (例 R1-A: WGFMU 扫 IV 验证 H2)
    - 总台出测试单 (TR-YYYYMMDD-NN), 走 `项目4_FEFET测试/_agent/runbooks/测试任务发起规约.md`
  - 数据回流目的地: 正式测试单用 `项目4_FEFET测试/实测数据/TR-*/`；当前 R1 WGFMU 调试/判别数据按实验类型进 `项目4_FEFET测试/实测数据/{E1_rawd,E2_read_disturb,S0_open_fixture_smoke}/`，详见项目4 `_agent/data_inventory_20260522_wgfmu.md`
  - 完成任务后: **必须**回写一行到项目4 `_agent/03_Log.md`
  - 测试执行人: 臧沂豪 (yhzang@mail.ustc.edu.cn), 不是 Hermes 直接跑

- `README.md`
  - Purpose: 项目总入口、目录结构、快速开始、当前真实状态口径
  - Importance: high
  - Check when: 重新进入项目、确认当前目录/模块实际存在什么
  - Keywords: setup, structure, current-state

- `TESTING.md`
  - Purpose: 当前验证入口说明（Mock / pytest / 真机）与验证边界
  - Importance: high
  - Check when: 跑测试、解释验证结果、准备远端联调时
  - Keywords: verify, mock, pytest, real hardware

- `ARCHITECTURE.md`
  - Purpose: 分层架构与模块职责说明
  - Importance: high
  - Check when: 修改 measurements / driver / visa 层边界时
  - Keywords: architecture, layers, API design

- `COMPLETION_SUMMARY.md`
  - Purpose: 历史完成口径的校正版，说明哪些是已落库、哪些还未完成
  - Importance: medium
  - Check when: 判断历史“已完成”表述是否仍可信时
  - Keywords: completion, historical status, calibrated summary

- `tests/tests_imports.py`
  - Purpose: 包入口导入边界、`pyvisa` 缺失时 Mock 路径可导入、`VisaSession.query()` 返回行为
  - Importance: high
  - Check when: 修改 `src/fefetlab/__init__.py` 或 `visa_session.py` 时
  - Keywords: lazy import, pyvisa boundary, query return

- `tests/test_dc_measurement.py`
  - Purpose: DC 配置、MockB1500、measure/sweep/export/API 的本地 pytest 主用例
  - Importance: high
  - Check when: 修改 DC 契约、导出、脚本或测试列结构时
  - Keywords: compliance, export_dir, measurement columns, mock regression

- `scripts/verify_dc_sweep.py`
  - Purpose: 当前最直接的本地 Mock / 真实硬件双入口验证脚本
  - Importance: high
  - Check when: 做最小 smoke test 或给用户远端回归命令时
  - Keywords: verify_dc_sweep, simulated, real

- `src/fefetlab/__init__.py`
  - Purpose: 包根入口；当前已通过 lazy export 避免导入时提前触发 `pyvisa`
  - Importance: high
  - Check when: 再次出现“Mock 路径被真实依赖卡住”时
  - Keywords: package entry, lazy export, import boundary

- `src/fefetlab/instruments/visa_session.py`
  - Purpose: VISA 会话包装；当前支持缺少 `pyvisa` 时保留模块可导入，仅在 `open()` 时要求真实依赖
  - Importance: high
  - Check when: 修改通信层或真实硬件接入逻辑时
  - Keywords: pyvisa, open, query, import safety

- `src/fefetlab/measurements/dc/config.py`
  - Purpose: DC 通道配置；当前公开名为 `compliance`，兼容 `i_comp`
  - Importance: high
  - Check when: notebook / API / tests 的命名不一致时
  - Keywords: compliance, i_comp, backward compatibility

- `src/fefetlab/measurements/dc/export.py`
  - Purpose: DC 导出；当前公开名为 `export_dir`，兼容 `base_dir`
  - Importance: high
  - Check when: API / exporter / tests 的导出目录命名不一致时
  - Keywords: export_dir, base_dir, backward compatibility

- `notebooks/12_wgfmu_smoke.ipynb`
  - Purpose: WGFMU 当前最直接的原型接口来源
  - Importance: high
  - Check when: 准备把 WGFMU 从 notebook 迁到正式模块时
  - Keywords: WgfmuLib, DummyWgfmuLib, dataclass, prototype

- `B1500手册/B1500-90000.pdf`
  - Purpose: B1500 官方 Users Guide，本轮主要用于积分时间、滤波、Kelvin 连接等硬件/测量前提核对
  - Importance: high
  - Check when: 评估 DC 量测参数是否过于简化时
  - Keywords: integration time, filter, Kelvin, users guide

- `B1500手册/B1500操作手册.pdf`
  - Purpose: B1500 官方 Quick Start/操作手册，本轮主要用于低电流量测 settling time 参考
  - Importance: high
  - Check when: 评估 delay / 低电流测量等待时间时
  - Keywords: settling time, 1 pA range, quick start

- `B1500手册/9018-01993 EasyEXPERT Software.pdf`
  - Purpose: 官方软件训练资料，本轮主要用于 filter、standby、bias hold、FMT 示例核对
  - Importance: high
  - Check when: 评估 after-measure / filter / 输出格式策略时
  - Keywords: SMU Filter, Standby, Bias Hold, FMT 13,1

- `B1500手册/keysight-b1530a-series-user-guide.pdf`
  - Purpose: WGFMU 官方 guide，本轮主要作为 ERRX? 例程和 connect/force/measure/disconnect 生命周期辅助参考
  - Importance: medium
  - Check when: 评估错误读取与 channel lifecycle 时
  - Keywords: ERRX?, DC flow, connect, disconnect

- `_agent/runbooks/batch-a-test-closure.md`
  - Purpose: 本轮收口包 A 的测试说明、命令、结果与未决项
  - Importance: high
  - Check when: 下一个对话要快速恢复“这轮到底改了什么、测了什么”时
  - Keywords: batch-a, test closure, handoff

- `_agent/runbooks/manual-risk-review-20260416.md`
  - Purpose: 基于本地官方资料做的代码风险复核结论
  - Importance: high
  - Check when: 决定下一轮先修哪些真实链路风险时
  - Keywords: manual review, risk, optimization, CN/CL, settling

- `_agent/runbooks/batch-b-test-closure.md`
  - Purpose: 收口包 B 的测试说明、TDD 失败点、通过结果与剩余边界
  - Importance: high
  - Check when: 下一个对话要快速恢复“高风险修复这轮到底改了什么、测了什么”时
  - Keywords: batch-b, cn/cl lifecycle, filter default, integration time

- `src/fefetlab/measurements/wgfmu/__init__.py`
  - Purpose: WGFMU 正式脚手架入口与 feature map
  - Importance: high
  - Check when: 想快速看 WGFMU 当前已经准备承载哪些功能时
  - Keywords: wgfmu scaffold, exports, feature map

- `src/fefetlab/measurements/wgfmu/config.py`
  - Purpose: WGFMU pulse / measure event / smoke run 配置模型
  - Importance: high
  - Check when: 调整 smoke 场景的参数结构时
  - Keywords: pulse pattern, measure event, smoke config

- `src/fefetlab/measurements/wgfmu/backend.py`
  - Purpose: WGFMU backend 抽象与 dummy backend
  - Importance: high
  - Check when: 开始设计 RealWgfmuBackend 或绑定官方库时
  - Keywords: backend, dummy backend, interface

- `src/fefetlab/measurements/wgfmu/smoke.py`
  - Purpose: WGFMU smoke workflow 主流程
  - Importance: high
  - Check when: 需要理解当前 WGFMU 架子到底能从 discovery 跑到 export 哪些步骤时
  - Keywords: smoke runner, workflow, qc, export

- `src/fefetlab/measurements/wgfmu/export.py`
  - Purpose: WGFMU 导出器，负责 run_dir / paths / 保存 parsed/qc/meta
  - Importance: medium
  - Check when: 调整 WGFMU 导出结构时
  - Keywords: exporter, paths, parsed, meta, qc

- `tests/test_wgfmu_scaffold.py`
  - Purpose: WGFMU 脚手架 pytest，覆盖导入、dummy smoke、导出与列重命名
  - Importance: high
  - Check when: 改 WGFMU 架子时防回归
  - Keywords: wgfmu tests, scaffold, smoke, dummy backend

- `_agent/runbooks/wgfmu-scaffold-test-closure.md`
  - Purpose: WGFMU 脚手架本轮的 TDD 说明、验证结果与下一步建议
  - Importance: high
  - Check when: 下一个对话要快速恢复"WGFMU 架子现在到哪了"时
  - Keywords: wgfmu closure, scaffold, handoff

## WGFMU 升级层 (2026-05-16 新增)

- `src/fefetlab/measurements/wgfmu/real_backend.py`
  - Purpose: ctypes 绑 `wgfmu.dll` 的 `RealWgfmuBackend`，覆盖 27 个 WGFMU2 C API
  - Importance: high
  - Check when: 真机调用层报错 / 加新的 C API 函数
  - Keywords: ctypes, wgfmu.dll, lazy load, WGFMU_DLL_PATH

- `src/fefetlab/measurements/wgfmu/pulse_builder.py`
  - Purpose: `PulseSegment` / `PulseTrainBuilder` / `linear_voltage_segments`，声明式多脉冲构建
  - Importance: high
  - Check when: 设计新扫描模式 (扫宽度 / 扫电压 / 多通道时序)
  - Keywords: pulse segment, builder, plan, linear sweep

- `src/fefetlab/measurements/wgfmu/iv_sweep.py`
  - Purpose: `WgfmuIVSweepRunner`，脉冲扫 IV (项目4 R1-A 主链路)
  - Importance: high
  - Check when: 改扫 IV 的数据契约 / 解析窗口策略
  - Keywords: iv sweep, per-pulse summary, R1-A

- `src/fefetlab/measurements/wgfmu/wakeup.py`
  - Purpose: `WgfmuWakeupRunner` + `WakeupStage` + `WakeupReadout`，多阶段 wake-up + 低扰读出 (R1-B)
  - Importance: high
  - Check when: 改 wake-up 协议 / 加新的 stage 维度
  - Keywords: wake-up, multi-stage, readout, R1-B

- `tests/test_wgfmu_iv_and_wakeup.py`
  - Purpose: 新模块 pytest 用例 (pulse builder / IV / wake-up / RealBackend)
  - Importance: high
  - Check when: 改新模块时防回归
  - Keywords: wgfmu tests, IV sweep, wake-up, real backend lazy

- `B1500手册/keysight-b1530a-series-user-guide.pdf`
  - (已存在条目，但现在重要性升级)
  - **新用途**: `real_backend.py` 函数列表的权威来源；后续加 C API 时按此 PDF 校对
  - Keywords: WGFMU2 C API, 95 functions, error codes, constants
