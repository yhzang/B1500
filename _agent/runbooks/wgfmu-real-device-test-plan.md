# WGFMU 真机测试计划 (yhzang 上器件前的代码验证流水线)

- 创建：2026-05-20 04:35 CST
- 测试人：yhzang (本人)
- 目的：在 yhzang 把真实 FeFET 器件接上去之前，先用 4 个分级 notebook 验证 WGFMU 代码路径全通、参数装配正确、波形形状符合预期、dll 调用安全。

## 0. 分级原则

| 级别 | notebook | 连机 | 接器件 | 风险 | 目的 |
|------|----------|------|--------|------|------|
| L0 干跑 | 20_wgfmu_iv_sweep_dryrun.ipynb | 否 | 否 | 0 | 验证波形构建/参数装配/plan.json |
| L0 干跑 | 22_wgfmu_wakeup_dryrun.ipynb | 否 | 否 | 0 | 同上,wake-up |
| L1 空连 | 21_wgfmu_iv_sweep_realdevice.ipynb | 是 | 否(开路) | 低 | 验证 dll+VISA+数据回流 |
| L1 空连 | 23_wgfmu_wakeup_realdevice.ipynb | 是 | 否 | 低 | 同上 |
| L2 真测 | 24_wgfmu_iv_sweep_device.ipynb | 是 | 是 | 中 | yhzang 接器件,正式测 |
| L2 真测 | 25_wgfmu_wakeup_device.ipynb | 是 | 是 | 中 | 同上 |

严格门禁:L0 不过不进 L1,L1 不过不进 L2。

## 1. 参数清晰化

### 1.1 WgfmuIVSweepConfig (IV sweep)

| 字段 | 量纲 | 典型值 (FeFET p 沟道) | 边界 | 说明 |
|------|------|---------------------|------|------|
| label | str | "R1A_dryrun_001" | - | 落盘目录名 |
| chan_id | int | 101/102 | 须在 get_channel_ids() 里 | WGFMU 模块号 |
| v_init | V | 0.0 | ±10V | pattern 启动前静态电压 |
| v_base | V | 0.0 | ±10V | 脉冲间 hold 电压 |
| operation_mode | str | "FASTIV" | - | 或 "PG" |
| force_voltage_range | str | "AUTO" | - | 或 "3V"/"5V"/"10V" |
| measure_mode | str | "CURRENT" | - | 或 "VOLTAGE" |
| measure_current_range | str | "1MA" | 量程小=灵敏但易过载 | 1UA/10UA/100UA/1MA/10MA |
| treat_warning_as_error | bool | False(验证)/True(正式) | - | True 时 warning 即 raise |
| timeout_s | s | 60.0 | pattern 时长 ×5 | dll 等待超时 |
| sequence_count | int | 1 | - | pattern 重复次数 |

### 1.2 PulseSegment / linear_voltage_segments (波形)

| 字段 | 量纲 | 典型值 | 边界 | 说明 |
|------|------|--------|------|------|
| v_pulse | V | -3~+3 (读) / -5~+5 (写) | ±10V | 脉冲高电平 |
| t_rise_s / t_fall_s | s | 1e-6 | ≥10 ns | 上升/下降 |
| t_high_s | s | 2e-6 ~ 100e-6 | ≥ rise+fall | 平顶宽度 |
| t_base_s | s | 2e-6 ~ 1e-3 | - | 脉冲间隔 |
| measure_points | int | 20 | ≤ 平顶可容纳 | 每脉冲采样数 |
| measure_average_s | s | 100e-9 | < interval | 单点积分 |

关键约束 (pulse_builder 已处理):
- 测量窗 = t_high - 2*guard, guard = min(t_rise, t_fall, t_high*0.1)
- interval = meas_window / measure_points
- average_s = min(配置值, interval*0.9)

### 1.3 WakeupStage / WakeupReadout

| 字段 | 量纲 | 典型值 (FeFET) | 说明 |
|------|------|--------------|------|
| n_cycles | int | 100/1000/10k | 一 stage 内循环数 |
| v_pgm | V | -3~-5 | PGM 幅值 (p 沟道用负) |
| v_ers | V | +3~+5 | ERS 幅值 |
| t_pgm_s | s | 30e-6 ~ 100e-6 | PGM 宽度 |
| t_ers_s | s | 30e-6 ~ 100e-6 | ERS 宽度 |
| rise_fall_s | s | 1e-6 | rise/fall |
| inter_pulse_s | s | 2e-6 | PGM-ERS 间隔 |
| v_read | V | -0.5~-1.0 | 低扰读出电压 |
| t_read_s | s | 5e-6 | 读出脉冲宽度 |
| measure_points | int | 10 | 每次读出采样数 |

## 2. 四个 notebook 内容设计

### L0 - 20_wgfmu_iv_sweep_dryrun.ipynb
目的:不连机,纯验证 PulseTrainBuilder + WgfmuIVSweepConfig 装配。
Cell:
1. import + 路径
2. linear_voltage_segments(0, -2, 11, ...) 构造 11 个递减脉冲
3. PulseTrainBuilder().build(segments) 拿 plan
4. 打印 plan.total_duration_s / len(plan.vectors/segments/measure_events)
5. plan.waveform_samples() 画时间-电压波形 (11 阶梯)
6. 同图标 measure event 窗 (vlines)
7. assertion: len(segments)==11, len(measure_events)==11, 每个 event t_start+(N-1)*interval ≤ t_high_end
8. dump plan.json 到 notebooks/_dryrun_out/iv_sweep_plan.json
验证:11 个等高度递减脉冲,measure 窗在平顶里,plan.json 字段齐。

### L0 - 22_wgfmu_wakeup_dryrun.ipynb
目的:验证 wake-up segments 构造。
Cell:
1. import
2. 2 个 WakeupStage: stage0 ±3V/30us x50, stage1 ±5V/30us x50
3. WakeupReadout(v_read=-0.5, t_read_s=5e-6, points=10)
4. _build_wakeup_segments(stages, readout) 拿 segments + cycle_meta
5. PulseTrainBuilder().build(segments) 拿 plan
6. assertion: len(segments)==300 (100 cycle x 3), len(cycle_meta)==100, 只有 readout 段有 measure_event
7. 画前 5 cycle 波形 (pgm↓ ers↑ read↓ 交替)
8. dump plan.json

### L1 - 21_wgfmu_iv_sweep_realdevice.ipynb
目的:连真机不接器件,验证 dll+VISA+数据回流。
前置 (markdown checkbox):
- Keysight IO Libraries 装好
- wgfmu.dll 在 PATH
- VISA GPIB0::17::INSTR 测通
- WGFMU 模块在 SMU2/SMU3 slot
- 探针抬起,无 DUT 在 101

Cell:
1. import + 红色安全提示
2. RealWgfmuBackend().load() 单独验证 dll
3. open_session + get_channel_ids 打印
4. 最小参数: v_start=0, v_stop=-1, n_points=5, t_high=2e-6, range="1UA"
5. WgfmuIVSweepRunner.run(...)
6. 检 complete==total
7. 打印 iv_df / qc_df / meta.error_summary
8. 画 samples_df 时间-电流 (开路应近 0)
9. 落盘路径打印

通过标准:无 dll 错,complete==total,qc.status=="ok",|I|<量程 1%。

### L1 - 23_wgfmu_wakeup_realdevice.ipynb
极小参数:1 stage 5 cycles v_pgm=-1 v_ers=+1,run,画 cycles_df.i_read_mean vs cycle_idx。

## 3. yhzang 上器件前清单

1. 真机 Windows:cd 项目3 -> git pull -> pip install -e .
2. 依次跑 20 -> 22 -> 21 -> 23,每跑完发输出/路径给我
3. 任何 assertion fail/异常/warning 停下来
4. 全过后我再写 24/25 真器件 notebook,那时你才接器件

## 4. 本轮不做的事 (防膨胀)

- 不动 iv_sweep.py / wakeup.py / pulse_builder.py (除非 dryrun 揭 bug)
- 不加新测量协议 (trigger out / raw mode)
- 不改 DC 链路
- 不重画能带图 (并行轨道)

## 5. 落盘路径

dryrun -> notebooks/_dryrun_out/ (gitignore)
L1 -> data/L1_aircheck/<label>/ (G 盘,不进 git)
L2 -> 项目4 实测数据/TR-*/
