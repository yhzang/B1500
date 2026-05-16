# 当前状态

- 更新时间：2026-05-16 05:30 CST
- 当前目标：WGFMU 模块完成「驱动层 + 波形构建 + 测量协议」三层落地，与已有 DC 链路对称。等真机回归验证 dll 调用路径。

## 上游对接
- 项目3 = 项目4 总台调用的**采集器**。当前服务的总台 Round 是 **R1-A (WGFMU 扫 IV，验证 H2 直流干扰)** 与 **R1-B (wake-up 力度阶梯)**。
- 总台权威进度页：`项目4_FEFET测试/_agent/01_State.md`
- 数据回流目标：`项目4_FEFET测试/实测数据/TR-*/`
- 测试执行人：臧沂豪 (yhzang@mail.ustc.edu.cn)

## 本轮结论 (WGFMU 编码完成)
对照 DC 链路（visa_session → b1500/driver → measurements/dc/{config,measure,sweep,export}）的对称结构，WGFMU 这一侧补齐了缺失的层：

- **驱动层**：`RealWgfmuBackend` (ctypes 绑 `wgfmu.dll`，覆盖 27 / 95 个 WGFMU2 C API)
  - Linux 可静态导入；DLL 在 `.load()` / `.open_session()` 才解析
  - 失败时给清晰 OSError（含搜索路径列表），不 segfault
- **波形构建层**：`PulseSegment` / `PulseTrainBuilder` / `PulseTrainPlan` / `linear_voltage_segments`
  - 把多脉冲扫描从"手写 add_vector 链"重构为声明式 segment 列表
  - 与 backend 解耦，纯数据结构 + 时间轴推算
- **测量协议层**：
  - `WgfmuIVSweepRunner` + `WgfmuIVSweepConfig` + `WgfmuIVSweepResult`：脉冲扫 IV (R1-A)
  - `WgfmuWakeupRunner` + `WakeupStage` + `WakeupReadout` + `WgfmuWakeupConfig`：多阶段 wake-up + 低扰读出 (R1-B)
  - 单脉冲 smoke (`WgfmuSmokeRunner`) 保留，作为最小回归
- **导出层**：复用 `WgfmuDataExporter`，每个 run 落盘 parsed.csv + qc.csv + meta.json + plan.json + setup_ascii.json + iv_curve.csv (or cycles.csv)

## 本地已验证结果
- `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ -q`
  - 期望: **33 passed in 7.74s** (基线 25 → 加 8 个新用例覆盖 IV sweep / wake-up / pulse builder / RealBackend lazy load / feature map)
- import 链路完整: `python -c "from fefetlab.measurements.wgfmu import RealWgfmuBackend, WgfmuIVSweepRunner, WgfmuWakeupRunner, PulseTrainBuilder, linear_voltage_segments"`
- DC 主链路保持稳定，未触动

## 当前风险 / 未决项
- 真机 dll 调用路径**只能在真机那台 Windows 上验证** —— 本机已验证 import 安全 + load() 失败信息清晰，但 27 个 C API 的 argtypes 是按 B1530A User Guide 写的，真机若签名有出入需要按错误现象调整
- `WGFMU_setMeasureEvent` raw_data_mode 当前默认 averaged；切 raw 时 QC 阈值需要调
- `integration_time_*` 仍只是 DC config 预留位 (与 WGFMU 无关，沿袭记录)

## 推荐下一步
1. 真机那台 git pull 后，写 4-5 行调用代码连 B1500 (用一样的 VISA 资源 `GPIB0::17::INSTR`)，跑通最小 IV sweep
2. 跑通后，项目4 总台出第一份正式 TR 测试单（建议 R1-B），按 `项目4_FEFET测试/_agent/runbooks/测试任务发起规约.md` 走
3. 真机数据回流到项目4 `实测数据/TR-*/` 后，在项目4 `_agent/03_Log.md` 写一行收口

## 关键文件 (新增 / 改动)
- `src/fefetlab/measurements/wgfmu/real_backend.py` ← 驱动层 (ctypes binding，Windows-only at runtime)
- `src/fefetlab/measurements/wgfmu/pulse_builder.py` ← 波形构建层
- `src/fefetlab/measurements/wgfmu/iv_sweep.py` ← 脉冲扫 IV
- `src/fefetlab/measurements/wgfmu/wakeup.py` ← 多阶段 wake-up
- `src/fefetlab/measurements/wgfmu/__init__.py` ← 重写导出 + feature map
- `tests/test_wgfmu_iv_and_wakeup.py` ← 6 个新用例
- 历史保留: `src/fefetlab/measurements/wgfmu/{backend,config,smoke,export}.py` 未触动 (与 DC 那侧对称)
- 历史保留: `src/fefetlab/measurements/dc/*` / `tests/test_dc_measurement.py` / `_agent/runbooks/*` 未触动
