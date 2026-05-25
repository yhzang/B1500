# 当前状态

- 更新时间：2026-05-26 01:33 CST
- 当前目标：**B1500 stop-gated CLI 已补 `B1500_VISA_ADDR` override；真实测试机已通过 pytest / PLAN / ALL_DRY / S0 live override smoke，准备提交并同步真机 pull。**

## 2026-05-26 B1500_VISA_ADDR override 已验证

- `scripts/wgfmu_next_round_minimal.py` live backend 初始化逻辑：优先读取 `B1500_VISA_ADDR`；非空则直接使用并打印 `B1500_VISA_ADDR_OVERRIDE`，否则回退自动探测。
- 真机验证位置：`ssh Administrator@100.108.189.9` → `D:\test\B1500`。
- 真机测试结果：
  - `pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q` → **13 passed in 5.73s**。
  - `--stage PLAN` → `REPORT_CODE: PLAN_ONLY_NO_HARDWARE`。
  - `--stage ALL_DRY ... --cycle-count 1` → `DRY_RUN_AUDIT: execute_count=96 max_vectors_seen=640`。
  - `set B1500_VISA_ADDR=GPIB1::17::INSTR && ... --stage S0 --live --confirm S0 --device-id ENV_OVERRIDE_TEST --geometry OPEN --s0-reps 1` → `B1500_VISA_ADDR_OVERRIDE: GPIB1::17::INSTR`、`WGFMU_CHANNELS: [201, 202, 301, 302]`、`REPORT_CODE: S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE`。
- 真机覆盖前备份：`D:\test\B1500\_agent\remote_backup_before_hermes_test_20260526_012839\`。
- 下一步：本地 commit/push 后，真机 `git pull origin main` 同步。


## 2026-05-22 下一轮 stop-gated WGFMU 上机流程已落地

- 新增最小 CLI：`D:\test\B1500\scripts\wgfmu_next_round_minimal.py`，已同步到真机 `D:\test\B1500`。
- 新增上机 runbook：`项目3_B1500自动化/B1500/_agent/runbooks/20260522_next_round_stop_gated_wgfmu.md`；真机同路径见 `D:\test\B1500\_agent\runbooks\20260522_next_round_stop_gated_wgfmu.md`。
- 顺序：S0 空夹具/抬针低压 smoke → S1 器件只读 baseline → E1 RAWD QUICK300ms v2 → E2 minimal (`A1/A100/C1/C10`, 不跑 C100)。
- live 模式必须一段一段跑：`--stage S0 --live --confirm S0`；脚本禁止 live 一次性全跑。
- stop gate：S0/S1 |Ig|>5 µA 停；E1/E2 |Ig|>20 µA 停；任何 `*_STOP_*` 不进入下一段。
- 远程 smoke：`py_compile`、`--stage PLAN`、`--stage ALL_DRY --s0-reps 1 --s1-reps 1 --e1-reps 1 --e2-reps 1` 均通过；dry-run 明确不打开 VISA、不加载 DLL、不触发硬件输出，`max_vectors_seen=640<2048`。
- 2026-05-22 17:46 CST 已远程执行 **S0 空夹具 live 低扰版**：`--stage S0 --live --confirm S0 --device-id OPEN_FIXTURE --geometry OPEN --s0-reps 1`；返回 `S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE`，3 rows，`max_abs_Id_A=1.445244e-07`，`max_abs_Ig_A=3.057571e-07`，CSV: `D:\test\B1500\runs\20260522_174642_S0_open_fixture_smoke_OPEN_FIXTURE\s0_open_fixture_smoke.csv`。下一步：只有确认探针已落到器件后才跑 S1。
- 2026-05-22 18:30 CST 已远程执行 **S1 器件只读 baseline**：`--stage S1 --live --confirm S1 --device-id L40W10_02 --geometry L40W10 --s1-reps 1`；返回 `S1_DONE_PROCEED_TO_E1`，3 rows，`max_abs_Id_A=2.168700e-07`，`max_abs_Ig_A=1.552721e-06`，CSV: `D:\test\B1500\runs\20260522_183051_S1_device_read_only_baseline_L40W10_02\s1_device_read_only_baseline.csv`。
- 2026-05-22 18:50 CST 新增并远程执行 `scripts\wgfmu_voltage_echo_check.py`：低压 read-only VOLTAGE 模式自测（Gate=-0.2/0/+0.2 V，Drain=0.05 V，无写脉冲），返回 `VOLTAGE_ECHO_DONE_LOW_VOLTAGE_ONLY`，最大电压误差 `1.81 mV`，CSV: `D:\test\B1500\runs\20260522_185045_VOLTAGE_ECHO_L40W10_02\voltage_echo_low_v_read_only.csv`。限制：不是示波器，不证明探针端 `±5V/100us` 写脉冲；作为无示波器条件下的低压门禁。
- 2026-05-22 18:53 CST 已远程执行 **E1 RAWD QUICK300ms v2**：`--stage E1 --live --confirm E1 --device-id L40W10_02 --geometry L40W10 --e1-reps 1`；返回 `E1_DONE_PROCEED_TO_E2_MINIMAL_IF_TREND_HEALTHY`，48 rows，`max_abs_Id_A=1.719605e-06`，`max_abs_Ig_A=5.274616e-06`，CSV: `D:\test\B1500\runs\20260522_185326_E1_RAWD_QUICK300ms_v2_L40W10_02\e1_rawd_quick300ms_v2.csv`。
- 2026-05-22 18:57 CST 已远程执行 **E2 minimal A1/A100/C1/C10**：`--stage E2 --live --confirm E2 --device-id L40W10_02 --geometry L40W10 --e2-reps 1`；返回 `E2_MINIMAL_DONE`，24 rows，`max_abs_Id_A=5.188955e-07`，`max_abs_Ig_A=5.897400e-06`，CSV: `D:\test\B1500\runs\20260522_185718_E2_minimal_A1_A100_C1_C10_L40W10_02\e2_minimal_A1_A100_C1_C10.csv`。

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

### 真机拓扑 (yhzang 本机；2026-05-22 `UNT?` 复核)
```
B1500 主机 (GPIB1::17::INSTR, S/N MY55231213, FW A.06.02.2023.0401)
├── slot 1: B1525A
├── slot 2: B1530A WGFMU (channels 201, 202)
├── slot 3: B1530A WGFMU (channels 301, 302; CH302 没接 RSU)
├── slot 4: B1517A SMU
├── slot 5: B1517A SMU
├── slot 6: B1517A SMU
├── slot 7: B1511B (disabled)
└── slot 8: B1520A
+ 3 个 RSU 把 WGFMU 201/202/301 切到 SMU 测试夹具；302 悬空/无 RSU
+ 3m HRSU 电缆
```
**FeFET 双通道接线铁律**：Gate=CH202，Drain=CH201。`autodetect_wgfmu_chan(... prefer=201)` 只能发现通道存在，不能知道实际接线，会把 gate/drain 反过来。

### 重要 baseline (RSU+电缆开路, 探针抬起)
- WGFMU 201 / 探针抬起 / 1MA 量程 / -0.5V 阶梯脉冲: **|I| ≈ 1.14 µA**
- WGFMU 201 / 探针抬起 / 1MA 量程 / ±1V wake-up: **|i_read| ≈ 1.14 µA**
- 物理来源: HRSU 电缆寄生电容 (3m ~150pF) 充放电 + RSU 内部开关漏电
- **yhzang 接器件后 DUT 电流要扣除这个 baseline**
- 物理验证方法: 把 t_rise/t_fall 从 1µs 改 10µs, 如果电流降到 ~110nA 就是电缆电容主导

### 2026-05-22 openSession=-6 事故结论（17:45 CST 二次复核）
- 现象：WGFMU `open_session()` 报 `status=-6`，伴随 B1500 error queue 里的 `+100,Undefined GPIB command`。
- 二次诊断结论：raw `WGFMU_openSession("GPIB1::17::INSTR")` 本身可成功；**`*CLS` preflight 会在 yhzang 这台 B1500A 上入队 `+100,Undefined GPIB command`，随后 WGFMU DLL `openSession` 读到该错误并返回 -6**。
- 标准 preflight：每次 `backend.open_session(VISA_ADDR)` 前先走 `clear_b1500_status_for_wgfmu_open(VISA_ADDR)`：pyvisa `inst.clear()` → drain `ERRX?` 到 0 → `*IDN?` → 再 drain `ERRX?` → `inst.close()` → `rm.close()` → `sleep(2)`；**不要发 `*CLS`，也不要默认 `*RST`**。
- 已落地：helper 在 `src/fefetlab/measurements/wgfmu/setup_helpers.py`；`scripts/wgfmu_next_round_minimal.py` 已改为输出 `B1500 preflight ERRX drain OK`；新增回归测试 `test_wgfmu_open_preflight_drains_errx_without_cls`；真机只开会话验证通过，通道 `[201, 202, 301, 302]`。

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
- 数据回流: 正式 TR 用 `项目4_FEFET测试/实测数据/TR-*/`；当前 R1 WGFMU 调试数据按实验类型回流到项目4 `实测数据/E1_rawd/`, `E2_read_disturb/`, `S0_open_fixture_smoke/`；索引见项目4 `_agent/data_inventory_20260522_wgfmu.md`
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
