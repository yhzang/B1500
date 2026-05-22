# 2026-05-22 · 下一轮 WGFMU 上机 stop-gated 流程

> 目的：先排除夹具/接触/漏电，再复跑真正 E1 QUICK300ms，最后只做最小 E2 判别。不要直接扩大矩阵。

## 0. 本轮固定事实

- 测试机：`DESKTOP-BPJ59BJ` / `100.108.189.9`
- 工作目录：`D:\test\B1500`
- Python：`D:\test\B1500\.venv\Scripts\python.exe`
- 执行脚本：`D:\test\B1500\scripts\wgfmu_next_round_minimal.py`
- WGFMU 接线硬编码：**Gate=CH202, Drain=CH201**
- 不用 `autodetect_wgfmu_chan()` 判断 Gate/Drain；302 悬空，不进入本轮测试。
- live 模式每次只允许跑一个 stage，必须带 `--confirm <STAGE>`。

## 1. 先做无硬件输出 dry-run（Hermes/远程 smoke 用）

```powershell
cd D:\test\B1500
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage PLAN
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage ALL_DRY --s0-reps 1 --s1-reps 1 --e1-reps 1 --e2-reps 1
```

预期回报码：

- `PLAN_ONLY_NO_HARDWARE`
- `DRY_RUN_BACKEND: no VISA, no DLL, no hardware output`
- `DRY_RUN_AUDIT: ... max_vectors_seen<=2048`

这一步不打开 VISA、不加载 DLL、不触发硬件输出。

## 2. S0：空夹具/抬针低压 smoke（无 ±5V 写脉冲）

使用场景：探针抬起或空夹具，确认 open/session/低压 read-only 链路没有异常漏电。

```powershell
cd D:\test\B1500
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage S0 --live --confirm S0 --device-id L40W10_01 --geometry L40W10
```

动作：

- 无 ±5V write pulse
- 只做 `Vg_read=[-0.2, 0, +0.2] V`、`Vd=+0.05 V` 的低扰读
- 默认 5 轮

通过回报码：

- `S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE`

Stop gate：

- `S0_STOP_NO_SAMPLES`：没有读到样本，停。
- `S0_STOP_IG_GT_5UA`：空夹具/抬针 |Ig| 超 5 µA，停；不要接器件继续。
- 任意 `SETUP_STOP_*`：通道/确认/会话问题，停。

回报给 Hermes：回报码 + `OUTPUT_CSV` 路径 + `max_abs_Id_A/max_abs_Ig_A`。

## 3. S1：器件只读 baseline（仍无 ±5V 写脉冲）

使用场景：探针已接触器件，先看只读状态下接触/漏电是否健康。

```powershell
cd D:\test\B1500
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage S1 --live --confirm S1 --device-id L40W10_01 --geometry L40W10
```

动作：

- 无 ±5V write pulse
- 只做 `Vg_read=[-0.2, 0, +0.2] V`、`Vd=+0.05 V` 的低扰读
- 默认 20 轮

通过回报码：

- `S1_DONE_PROCEED_TO_E1`

Stop gate：

- `S1_STOP_NO_SAMPLES`：没有读到样本，停。
- `S1_STOP_IG_GT_5UA`：只读 baseline |Ig| 超 5 µA，停；优先查接触/漏电/器件状态。

回报给 Hermes：回报码 + `OUTPUT_CSV` 路径 + `max_abs_Id_A/max_abs_Ig_A`。

## 4. E1：真正 RAWD QUICK300ms v2

```powershell
cd D:\test\B1500
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage E1 --live --confirm E1 --device-id L40W10_01 --geometry L40W10
```

动作：

- ERS/PGM：`+5 V / -5 V, 100 µs`（王渊标称）
- delay：`1 µs, 10 µs, 100 µs, 1 ms, 10 ms, 30 ms, 100 ms, 300 ms`
- 每个 delay 下 ERS/PGM 各跑，默认 3 reps
- 每个 shot 读 `Vg_read=[-0.2, 0, +0.2] V`，`Vd=+0.05 V`
- 预期行数：`8 delays × 3 reps × 2 states × 3 Vg = 144 rows`

通过回报码：

- `E1_DONE_PROCEED_TO_E2_MINIMAL_IF_TREND_HEALTHY`

Stop gate：

- `E1_STOP_NO_SAMPLES`：没有读到样本，停。
- `E1_STOP_IG_GT_20UA`：写后读出 |Ig| 超 20 µA，停；先分析 leakage/contact，不进入 E2。

回报给 Hermes：回报码 + `OUTPUT_CSV` 路径 + `max_abs_Id_A/max_abs_Ig_A`。

## 5. E2：最小 read-disturb 判别（不跑 C100）

只有 E1 结果健康时再跑。

```powershell
cd D:\test\B1500
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage E2 --live --confirm E2 --device-id L40W10_01 --geometry L40W10
```

动作：

- combos：`A1, A100, C1, C10` × ERS/PGM
- 默认 2 reps
- 跳过 C100，避免一上来把 read-disturb 剂量打太重。
- E2 内部保留 split-dose 逻辑，单 pattern vector 预算守住 2048 上限。

通过回报码：

- `E2_MINIMAL_DONE`

Stop gate：

- `E2_STOP_NO_SAMPLES`：没有读到样本，停。
- `E2_STOP_IG_GT_20UA`：E2 中 |Ig| 超 20 µA，停；不要继续扩矩阵。

## 6. 总原则

1. 任何 `*_STOP_*` 都不要继续下一 stage。
2. 不要一次性 live 跑 S0→S1→E1→E2；脚本故意禁止 live `ALL_DRY`。
3. 每个 stage 完成后，把 `REPORT_CODE`、`OUTPUT_CSV`、`max_abs_Id_A`、`max_abs_Ig_A` 发回。
4. 若 Jupyter 还开着旧 notebook，本轮不用它；直接跑 CLI 脚本，避免 stale cell。
5. 若 `WGFMU_openSession status=-6`，优先按现有 helper 逻辑清 GPIB：`inst.clear() → ERRX? drain → *IDN? → ERRX? drain → rm.close() → sleep(2)`；**不要发 `*CLS`**，也不要默认 `*RST`。
