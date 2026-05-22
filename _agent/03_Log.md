
---

## 2026-05-22 22:20 CST L10W10_02 fresh 复测 + pause/recovery 完成
- Goal：按 L10W10_01 的最小包复测 L10W10_02 fresh 点：S1 → E1 full-delay wide-Vg 3 reps → 20-cycle → pause recovery。
- Evidence：
  - S1 live：`--stage S1 --live --confirm S1 --device-id L10W10_02 --geometry L10W10 --s1-reps 1` → `S1_DONE_PROCEED_TO_E1`，3 rows，`max_abs_Ig_A=1.004714e-06`，CSV `D:\test\B1500\runs\20260522_215017_S1_device_read_only_baseline_L10W10_02\s1_device_read_only_baseline.csv`。
  - E1 3-rep live 曾在第 2 rep 遇到 `WGFMU_initialize failed status=-6: viReadSTB returned -1073807360`，未保存完整 CSV；复核 S1 `L10W10_02_POSTERR` 通过，`max_abs_Ig_A=1.578818e-06`。
  - E1 改为单 rep 保存：REP1/2/3 均完成，CSV 分别为 `D:\test\B1500\runs\20260522_215417_E1_RAWD_QUICK300ms_v2_L10W10_02_REP1\...`、`20260522_215616...REP2`、`20260522_215717...REP3`；rows 各 132，`max_abs_Ig_A=2.272456e-05/1.768234e-05/1.964097e-05`。
  - 20-cycle live：`D:\test\B1500\runs\20260522_215935_CYCLE_endurance_L10W10_02\cycle_endurance.csv`，120 rows，`max_abs_Ig_A=1.855480e-05`。
  - Pause recovery 5-cycle live：`D:\test\B1500\runs\20260522_221114_CYCLE_endurance_L10W10_02_RECOVERY5\cycle_endurance.csv`，30 rows，`max_abs_Ig_A=1.870009e-05`。
- Cloud archive：项目4 `实测数据/S1_device_read_only_baseline/20260522_L10W10_02*/`、`实测数据/E1_rawd/20260522_L10W10_02_fullDelay_wideVg_rep{1,2,3}/`、`实测数据/cycle_endurance/20260522_L10W10_02_{20cycles,recovery_after_pause_5cycles}/`。
- Current recommendation：L10W10_02 已完成最小复现包。长 E1 以后优先单 rep 保存；这颗点不建议继续大 stress，若补做只做 30–60min 后 5-cycle recovery 或换新点统计。

## 2026-05-22 21:45 CST L10W10_01 pause/recovery + wide-Vg 参数修正
- Goal：继续当前 L10W10_01 点，验证 20-cycle 后 MW 是否可暂停恢复；同时修正 `--e1-wide-vg` 漏掉 `Vg=-1.0V` 的脚本问题。
- What changed：`scripts/wgfmu_next_round_minimal.py` 中 `VG_E5` 已改为 `[-1.0, -0.7, -0.4, -0.2, 0.0, 0.2]`；远端 `D:\test\B1500` 已同步，sha256 `4b9ad542deee74343fa7b25e60d4f3817037ea50872e456393af1b83d067a0c6`；`py_compile` 和 dry-run E1 通过，PLAN 输出包含 `-1.0V`。
- Evidence：
  - Recovery 5-cycle live：`--stage CYCLE --live --confirm CYCLE --device-id L10W10_01 --geometry L10W10 --cycle-count 5 --cycle-ig-stop-uA 30` → `CYCLE_ENDURANCE_DONE`，30 rows，`max_abs_Id_A=2.541764e-06`，`max_abs_Ig_A=1.661098e-05`，CSV `D:\test\B1500\runs\20260522_211102_CYCLE_endurance_L10W10_01\cycle_endurance.csv`。
  - Corrected after-pause E1 live：`--stage E1 --live --confirm E1 --device-id L10W10_01 --geometry L10W10 --e1-reps 1 --e1-wide-vg --e1-full-delays --e1-ig-stop-uA 30` → `E1_DONE...`，132 rows，`max_abs_Id_A=3.656449e-06`，`max_abs_Ig_A=2.842555e-05`，CSV `D:\test\B1500\runs\20260522_213549_E1_RAWD_QUICK300ms_v2_L10W10_01\e1_rawd_quick300ms_v2.csv`。
- Note：中间曾跑过一次旧 `VG_E5=[-0.4..+0.4]` 的 E1（`20260522_211752...`），不含主读点 `-1.0V`，只作低扰健康参考，不用于主判读。
- Cloud archive：项目4 `实测数据/cycle_endurance/20260522_L10W10_01_recovery_after_pause_5cycles/` 与 `实测数据/E1_rawd/20260522_L10W10_01_after_pause_fullDelay_wideVg_fixed_1rep/`。
- Next step：因最后一次 E1 `max |Ig|≈28.4µA` 接近 30µA 诊断门限，不建议继续 stress 当前 L10W10_01；若继续机制统计，换 fresh 点跑最小包。

## 2026-05-22 18:58 CST E1 QUICK300ms v2 + E2 minimal live 完成
- Goal：在 S1 + 低压 VOLTAGE_ECHO 通过后，按 stop gate 继续完成 L40W10_02 的 E1 QUICK300ms v2 与 E2 minimal。
- Evidence：
  - E1 live：`--stage E1 --live --confirm E1 --device-id L40W10_02 --geometry L40W10 --e1-reps 1` → `E1_DONE_PROCEED_TO_E2_MINIMAL_IF_TREND_HEALTHY`，48 rows，`max_abs_Id_A=1.719605e-06`，`max_abs_Ig_A=5.274616e-06`，CSV `D:\test\B1500\runs\20260522_185326_E1_RAWD_QUICK300ms_v2_L40W10_02\e1_rawd_quick300ms_v2.csv`。
  - E2 live：`--stage E2 --live --confirm E2 --device-id L40W10_02 --geometry L40W10 --e2-reps 1` → `E2_MINIMAL_DONE`，24 rows，`max_abs_Id_A=5.188955e-07`，`max_abs_Ig_A=5.897400e-06`，CSV `D:\test\B1500\runs\20260522_185718_E2_minimal_A1_A100_C1_C10_L40W10_02\e2_minimal_A1_A100_C1_C10.csv`。
- Cloud archive：已复制到项目4 `实测数据/E1_rawd/20260522_L40W10_02_QUICK300ms_v2/` 与 `实测数据/E2_read_disturb/20260522_L40W10_02_minimal_A1_A100_C1_C10/`。
- Initial read：E1 Vg=0 的 MW(ERS-PGM) 从 1µs `+1.33 µA` 衰减到 100–300ms 接近零；E2 Vg=0 的 A1/A100/C1/C10 为 `+9.13 nA/-16.15 nA/+35.82 nA/+136.97 nA`，未复现昨晚 C 模式强负 MW。
- Next step：先写判读收口，不直接继续 E3；若继续上机，优先补 E1 repeats 或 E5 read-window grid。

## 2026-05-22 18:51 CST S1 器件只读 + 低压 VOLTAGE_ECHO 通过
- Goal：在无示波器条件下，继续推进到 E1 前先用 WGFMU 自身 VOLTAGE 模式对低压 read 窗做最小自检，同时不对器件施加写脉冲。
- What changed：新增 `scripts/wgfmu_voltage_echo_check.py`，复用 stop-gated 通道/preflight 规则，固定 Gate=202、Drain=201；live 必须 `--confirm VOLTAGE_ECHO`；只发 Gate=-0.2/0/+0.2 V、Drain=0.05 V，并以 VOLTAGE 模式回读。
- Evidence：
  - S1 live：`--stage S1 --live --confirm S1 --device-id L40W10_02 --geometry L40W10 --s1-reps 1` → `S1_DONE_PROCEED_TO_E1`，3 rows，`max_abs_Id_A=2.168700e-07`，`max_abs_Ig_A=1.552721e-06`，CSV `D:\test\B1500\runs\20260522_183051_S1_device_read_only_baseline_L40W10_02\s1_device_read_only_baseline.csv`。
  - VOLTAGE_ECHO dry-run/py_compile on test machine passed；live：`--live --confirm VOLTAGE_ECHO --device-id L40W10_02 --geometry L40W10` → `VOLTAGE_ECHO_DONE_LOW_VOLTAGE_ONLY`，`max_abs_voltage_error_V=1.810184e-03`，CSV `D:\test\B1500\runs\20260522_185045_VOLTAGE_ECHO_L40W10_02\voltage_echo_low_v_read_only.csv`。
- Limitation：这是 WGFMU 低压端子自测，不是示波器；不能证明探针端 `±5V/100us` 写脉冲真实幅值/极性/脉宽。该疑问保留到 E1 数据健康性/未来示波器验证。
- Next step：可进入 E1 QUICK300ms v2，建议先 `--e1-reps 1`；任何 `E1_STOP_*` 立即停止，不进入 E2。

## 2026-05-22 17:47 CST WGFMU -6 真根因修正 + S0 空夹具 live 低扰通过
- Goal：在不产生输出的前提下复核 `WGFMU_openSession status=-6` 真根因，最小修复后完成 dry-run/只开会话验证，并执行 S0 空夹具低扰 live。
- Root cause：`GPIB1::17::INSTR` 可用，raw `WGFMU_openSession` 可成功；旧 helper 的 `*CLS` 会在 yhzang B1500A 入队 `+100,Undefined GPIB command`，随后 WGFMU DLL openSession 读到该错误返回 `-6`。
- What changed：
  - `src/fefetlab/measurements/wgfmu/setup_helpers.py`：preflight 改为 `inst.clear()` + drain `ERRX?` + `*IDN?` + 再 drain `ERRX?` + close `inst/rm` + `sleep(2)`；不再发 `*CLS`。
  - `scripts/wgfmu_next_round_minimal.py`：日志改为 `B1500 preflight ERRX drain OK`。
  - `tests/test_wgfmu_iv_and_wakeup.py`：新增 `test_wgfmu_open_preflight_drains_errx_without_cls`，防止回退到 `*CLS`。
- Evidence：
  - 真机同步到 `D:\test\B1500` 后：`py_compile` 通过；新增回归测试 1 passed；`PLAN`/`ALL_DRY --s0-reps 1 --s1-reps 1 --e1-reps 1 --e2-reps 1` 通过；只开会话验证通过，`WGFMU_CHANNELS=[201,202,301,302]`，close status 0。
  - S0 空夹具 live：`--stage S0 --live --confirm S0 --device-id OPEN_FIXTURE --geometry OPEN --s0-reps 1` → `S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE`，3 rows，`max_abs_Id_A=1.445244e-07`，`max_abs_Ig_A=3.057571e-07`，CSV `D:\test\B1500\runs\20260522_174642_S0_open_fixture_smoke_OPEN_FIXTURE\s0_open_fixture_smoke.csv`。
- Next step：不要自动跑 S1；只有 yhzang 确认探针已落到器件后，再跑 S1 device read-only baseline（仍以 `|Ig|>5µA` 为 stop gate）。

## 2026-05-22 06:45 CST 下一轮 WGFMU stop-gated CLI + 上机文档
- Goal：把项目4 判读后的下一轮上机顺序落实到测试机，避免直接扩大矩阵。
- What changed：新增 `scripts/wgfmu_next_round_minimal.py`，提供 S0 空夹具/抬针 read-only smoke、S1 器件只读 baseline、E1 RAWD QUICK300ms v2、E2 minimal (`A1/A100/C1/C10`, skip C100)。固定 Gate=CH202, Drain=CH201；live 模式必须 `--confirm <STAGE>`，不允许 live 一次性全跑。
- 上机文档：`_agent/runbooks/20260522_next_round_stop_gated_wgfmu.md`，同已同步到真机 `D:\test\B1500\_agent\runbooks\...`。
- Evidence：本机 dry-run 通过；真机 SSH 下 `py_compile`、`--stage PLAN`、`--stage ALL_DRY --s0-reps 1 --s1-reps 1 --e1-reps 1 --e2-reps 1` 均通过；dry-run 输出 `DRY_RUN_BACKEND: no VISA, no DLL, no hardware output`，`max_vectors_seen=640<2048`。
- Next step：yhzang 只需从 PowerShell 跑 S0，看到 `S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE` 后再进入 S1；任何 `*_STOP_*` 都先回报码和 CSV，不继续。

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

# 工作日志

## 2026-05-22 00:55 CST WGFMU openSession=-6 事故收口 + E1-E5 preflight 固化
- Goal：收口 E1 QUICK300ms / E1-E5 真机 notebook 的 `WGFMU_openSession status=-6`，同时清掉旧 Gate/Drain 反接口径和 `*RST` preflight 风险。
- Root cause：异常中断/上一轮 notebook 后，B1500 GPIB error queue 与 VISA/GPIB 资源状态残留；WGFMU DLL `openSession` 在旧状态下返回 -6。不是 DLL 位数、不是通道不存在。
- What changed：
  - 新增 `clear_b1500_status_for_wgfmu_open(VISA_ADDR)`：`inst.clear()` → drain `ERRX?` 到 0 → `*IDN?` → 再 drain `ERRX?` → `inst.close()` → `rm.close()` → `sleep(2)`；不发 `*CLS` / `*RST`。
  - `notebooks/30_E1_rawd.ipynb` 到 `34_E5_visibility.ipynb` 的所有 `backend.open_session(VISA_ADDR)` 前均插入该 preflight。
  - `src/fefetlab/measurements/wgfmu/experiments.py` 修复 `run_e1_single_point()` 读取 backend result 的旧契约：`get_measure_value_size()` 是 `(completed,total)`，`get_measure_values()` 是 DataFrame。
  - `tests/test_wgfmu_iv_and_wakeup.py` 新增 E1 单点回归测试。
  - `_agent/01_State.md` / `_agent/05_Handoff.md` 更新真机拓扑与硬接线：Gate=CH202, Drain=CH201；slot2/3 才是 B1530A WGFMU。
  - `src/scripts/connect_test.py` 旧 `*RST` 改为 `*CLS`，避免把重置当成普通 WGFMU preflight。
- Evidence：
  - 全项目扫描旧口径：没有发现“把 gate 赋给自动探测结果或 CH201”的可执行代码；剩余 Gate=CH202/Drain=CH201 命中均为正确口径或历史更正说明。
  - E1-E5 notebook code cell 语法解析通过；每个 notebook 均 `import clear_b1500_status_for_wgfmu_open` 且 `preflight_count=3`。
  - **真机测试机 SSH 验证**：`Administrator@100.108.189.9`，`D:\test\B1500`，`.venv\Scripts\python.exe -m pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q` → **12 passed in 0.71s**。注意：项目3 WGFMU 测试应在真机测试机跑，不要在本机 WSL 里假跑。
  - 测试补丁：`test_real_backend_load_fails_gracefully_when_dll_missing` 改为 mock `ctypes.WinDLL` 抛 `OSError`，因为真机 Windows 已安装系统级 `C:\Windows\System32\wgfmu.dll`，不能用“传不存在路径”模拟缺 DLL。
- Next step：真机 `D:\test\B1500` 当前已同步关键源码/测试文件并通过 pytest；Jupyter 里不要只 Restart Kernel，如果浏览器 tab 还开着旧 notebook，要 Refresh/Reopen 文件，避免执行 stale in-memory cell。从 setup cell 重新跑，确认出现 `B1500 preflight ERRX drain OK: ...` 再进实验循环。

## 2026-05-21 22:25 CST E2 read-disturb notebook 修复 B1530A pattern vector 上限
- Goal：继续真机 E2 (`notebooks/31_E2_read_disturb.ipynb`) 跑到 `Mode C, n_read=100` 时的失败；现象是单个 WGFMU pattern 被塞进约 6423 个 vector，超过 B1530A 单 pattern 2048 vector 上限。
- What changed：
  - 远程测试机 `D:\test\B1500\notebooks\31_E2_read_disturb.ipynb` 已先备份为 `31_E2_read_disturb.ipynb.bak_20260521_222009`。
  - Cell 2 固定真实接线：`Gate=CH202, Drain=CH201`，不再用 autodetect（防止反接）。
  - Cell 4 改成 split-dose：Reset+Write 执行一次；dose 按安全 vector budget 分块执行；最后 verify read 执行一次。C/n=100 自动分块为 `[30, 30, 30, 10]`，单 gate pattern 最大 1920 vectors。
  - 同步回 G 盘工作区同名 notebook，sha256=`e09271a7fcc23856117bcac56e483995999724d2d0575dfbbb83a780b4b3b3c3`。
- Evidence：
  - 远程 `.venv` 下编译 notebook 全部 code cell 通过。
  - 远程 dummy backend 端到端验证通过：`mode C n=100 -> execute_count=6, max_vectors_seen=1920, rows=3`。
- Current state：E2 notebook 已可重新从 helper cell 开始执行；预期不再触发 2048 vector 上限错误。
- Next step：在真机 notebook 中从 Cell 4/5/6 继续跑 E2；若仍报错，优先看是否是多 execute 分块带来的 session/timeout 问题，而不是 vector 上限。

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
