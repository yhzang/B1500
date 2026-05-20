# 当前状态

- 更新时间：2026-05-20 21:30 CST
- 当前目标：**L0+L1 全过, 等 yhzang 接器件 → 写 L2 真器件 notebook**

## 2026-05-20 真机联调成果 (yhzang 本人在新电脑 D:\test\B1500)

✅ **20/22/21/23 全过** — 代码 + 真机链路 100% 验证完毕

### 今天解决的 20 个真机适配问题 (已修 push)
1. tests/conftest.py 加 sys.path (scripts/ 顶层包能导入)
2. `requirements/base.txt` 加 matplotlib + jupyter
3. `real_backend.py` 全部 WGFMU enum 改成 WGFMU.cs 真值
   - OPERATION_MODE 2000-2003
   - FORCE_VOLTAGE_RANGE 3000-3004
   - MEASURE_MODE 4000-4001
   - MEASURE_VOLTAGE_RANGE 5001-5002
   - MEASURE_CURRENT_RANGE 6001-6005
   - MEASURE_ENABLED 7000-7001 (新加 map)
   - MEASURE_EVENT_DATA 12000-12001
   - WARNING_LEVEL 1000-1003
4. `_default_dll_search_paths()` 加 `C:\Windows\System32\wgfmu.dll` (现代 64-bit Library 装在这里)
5. `open_session()` 容错: 检测到 status=-3 (session 已开) 自动 closeSession + retry
6. 新加 `setup_helpers.py`: ensure_wgfmu_dll_path / autodetect_visa_addr / autodetect_wgfmu_chan
7. notebook 21/23 重写: 用 setup_helpers 自动探测一切, 不再硬编码 GPIB0 / CHAN_ID 101
8. L1 默认量程 1MA (之前 1UA 会被 RSU baseline 饱和)
9. L1 通过阈值 10µA (之前 1µA 太严, RSU+电缆 baseline 就是 ~1µA)

### 真机拓扑 (yhzang 本机)
```
B1500 主机 (GPIB1::17::INSTR, S/N MY55231213, FW A.06.02.2023.0401)
├── slot 5: B1517A SMU
├── slot 4: B1517A SMU
├── slot 3: B1525A WGFMU (channels 301, 302)  ← 302 没接 RSU
├── slot 2: B1525A WGFMU (channels 201, 202)
└── slot 1: B1530A HV-SPGU
+ 3 个 RSU 把 WGFMU 201/202/301 切到 SMU 测试夹具
+ 3m HRSU 电缆
```

### 重要 baseline (RSU+电缆开路, 探针抬起)
- WGFMU 201 / 探针抬起 / 1MA 量程 / -0.5V 阶梯脉冲: **|I| ≈ 1.14 µA**
- WGFMU 201 / 探针抬起 / 1MA 量程 / ±1V wake-up: **|i_read| ≈ 1.14 µA**
- 物理来源: HRSU 电缆寄生电容 (3m ~150pF) 充放电 + RSU 内部开关漏电
- **yhzang 接器件后 DUT 电流要扣除这个 baseline**
- 物理验证方法: 把 t_rise/t_fall 从 1µs 改 10µs, 如果电流降到 ~110nA 就是电缆电容主导

### 已知坑 (写在 notebook 前置确认里, 但 KB 加固)
- WGFMU CH 302 没接 RSU → 不能 FASTIV (B1500 报 `RSU is not connected; CHANNEL302`)
- 新电脑要装 NI-488.2 GPIB driver (Keysight VISA 不够) + Keysight B1530A Instrument Library 64-bit
- GPIB-USB 适配器偶发 hang, 拔插一次 USB 即恢复
- pyvisa session 残留导致 VI_ERROR_ALLOC: backend.open_session 现在自动 close+retry

## yhzang 下次操作
1. `git pull origin main` (拿到今天的 20 个修复)
2. `pip install -r requirements/dev.txt` (会装 jupyter + matplotlib)
3. 跑 `pytest tests/ -q` 看 11+ passed
4. 跑 21/23 notebook 重验 (现在 cell 完全自动, 改 0 行)
5. 接器件 → 让 Hermes 写 L2 (24 IV 真器件 / 25 wake-up 真器件)

## 上游对接 (项目4 总台)
- 项目3 = 项目4 总台调用的**采集器**
- 当前服务的总台 Round: **R1-A** (WGFMU 扫 IV) / **R1-B** (wake-up 力度阶梯)
- 数据回流: `项目4_FEFET测试/实测数据/TR-*/`
- 测试执行人: **yhzang** (本人, 不是别人)

## 风险 / 未决项
- 真机 baseline 物理验证 (t_rise/t_fall 10x test) 还没做, 强证据但非铁证
- L2 真器件 notebook 还没写, 等 yhzang 给器件参数 (沟道电流量级 / 安全电压范围)
- KB 第 19 条 "新机器 setup runbook" 还没单独成文, 当前散在 `setup_helpers.py` + notebook 前置确认里

## 关键文件 (今天动过)
- `src/fefetlab/measurements/wgfmu/real_backend.py` — 8 个 enum + open_session 容错 + dll 路径
- `src/fefetlab/measurements/wgfmu/setup_helpers.py` (新) — 3 个自动探测 helper
- `src/fefetlab/measurements/wgfmu/__init__.py` — export helpers
- `tests/conftest.py` (新) — sys.path
- `requirements/base.txt` — +matplotlib, +jupyter
- `notebooks/21_wgfmu_iv_sweep_realdevice.ipynb` — 重写
- `notebooks/23_wgfmu_wakeup_realdevice.ipynb` — 重写
- `_agent/05_Handoff_session_followups.md` — 今天遗留清单完整版

(以下为 2026-05-16 之前的旧状态, 已被 2026-05-20 真机联调成果取代)

---

## 历史状态 (2026-05-16 WGFMU 编码完成)


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
