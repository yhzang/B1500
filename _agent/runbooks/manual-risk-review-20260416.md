# 基于官方手册的代码风险复核（2026-04-16）

## 本轮范围
本轮不做测试、不改业务代码，只基于项目代码与工作区内的官方/半官方资料做风险复核。

复核代码：
- `src/fefetlab/instruments/visa_session.py`
- `src/fefetlab/b1500/driver.py`
- `src/fefetlab/measurements/dc/measure.py`
- `src/fefetlab/measurements/dc/sweep.py`
- `src/fefetlab/measurements/dc/dc_sweep_api.py`
- `scripts/verify_dc_sweep.py`

## 参考资料
### 1. `B1500手册/B1500-90000.pdf`
提取到的关键信息：
- `SMU integration time setting: 1 PLC (1 nA to 1 A range, voltage range) / 20 PLC (100 pA range) / 50 PLC (1 pA to 10 pA range)`
- `SMU filter: ON for HPSMU, MPSMU, and HRSMU`
- `SMU measurement terminal connection: Kelvin connection`

### 2. `B1500手册/B1500操作手册.pdf`
提取到的关键信息：
- `Wait for a while until the measurement starts. It will take about 30 seconds settling time in the case of the 1 pA range.`
- 示例里明确把低电流量测的 settling time 视为量程相关问题。

### 3. `B1500手册/9018-01993 EasyEXPERT Software.pdf`
提取到的关键信息：
- `The filter is mounted on each SMU. It assures clean source output with no spikes or overshooting. However, using a filter may increase the SMU settling time. If measurement speed is top priority, set the SMU Filter OFF.`
- `In the power on state, the Classic Test sets the SMU Filter to ON.`
- `Standby function sets any SMUs ... to specific output values and compliances before starting or after stopping measurement.`
- `Bias Hold after Measurement: Bias hold function ON or OFF. Output Value after Measurement: START / STOP / SOURCE / BASE`
- 示例 FLEX 命令中出现 `FMT 13,1 ... ReadDataBuffer`

### 4. `B1500手册/keysight-b1530a-series-user-guide.pdf`
提取到的关键信息：
- 官方例程直接使用 `ERRX?` 读取错误文本
- 官方 DC 流程为：`open -> initialize -> set mode/range -> connect -> force -> measure -> disconnect -> close`

说明：
- 第 4 份资料针对 WGFMU/B1530，不是当前 SMU SCPI 驱动本身；这里只把它作为“官方 DC 生命周期管理思路”的辅助参考，不把它当成对 `CN/CL/DV/TI` 语义的唯一证据。

## 当前代码中基本合理的点
1. `VisaSession` 现在把 `pyvisa` 的硬依赖延迟到 `open()`，这适合本地 Mock 路径。
2. `B1500._parse_errx_code()` 假设 `ERRX?` 返回 `+code,"message"` 形式，目前和官方例程“ERRX? 返回文本后再解析”的思路一致，方向上合理。
3. `dv()` / `ti()` / `fmt()` / `av()` / `fl()` 的封装方向是对的：把命令、基础参数校验和少量解析放在 driver 层。
4. `DCSweepConfig` 暴露 `compliance` / `export_dir` 这类更清晰的公开命名，是朝统一契约走的。

## 风险点
### 高风险
1. `DCSweepRunner._configure_instrument()` 只在初始化时 `CN` 一次，但 `DCMeasurePoint.measure()` 每个点结束都会 `DZ` + `CL`。
- 结果：第一点之后通道被 clear，下一点没有显式重新 `CN`。
- MockB1500 不会暴露这个问题，但真机很可能会。
- 这是当前最值得优先收口的真实链路风险。

2. `DCMeasurePoint.measure()` 只用固定 `time.sleep(self.config.delay_s)` 处理稳定时间，默认 `delay_s=0.2 s`，没有按量程/模块/积分时间区分。
- 官方资料明确说明：低电流量测的 settling time 是量程相关的；1 pA 量程示例甚至达到约 30 秒。
- 如果后续 FEFET 测试进入低电流/亚阈值/ASU 场景，当前固定 0.2 s 的策略风险很高。

### 中风险
3. 当前默认 `fl_mode=0`，即默认把 SMU filter 关掉。
- 官方资料说明 filter 的作用是减少 spike / overshoot；Classic Test 缺省为 ON。
- 当前默认值更偏“速度优先”，对器件保护和稳定性不一定合适。
- 这不一定马上错，但至少不应作为无注释默认值长期存在。

4. 当前 DC 链路没有把 `PLC / integration time` 作为一等配置暴露出来。
- 官方资料给出了不同电流量程对应的积分时间设置。
- 现在只有 `AV` 和 `delay_s`，对于更严肃的低电流测量不够细。

5. `measure()` 中三个 `TI` 查询后只在最后额外读一次 `ERRX?`。
- 如果多个步骤累计了多个错误，目前结果对象里只保留最后一次 `ERRX?` 读出的文本。
- 再加上 `_write()` 自己也会读 `ERRX?`，错误上下文容易被提前消费或压缩。
- 这个问题在 Mock 路径里不明显，在真机调试时可能会降低可诊断性。

6. 当前 driver 的解析明显是“只够当前简单 DC 路径用”。
- 官方资料中的 EasyEXPERT 例子会用 `FMT 13,1` 和 `ReadDataBuffer`。
- 当前 `_parse_scalar_response()` 针对简单 ASCII 标量还行，但如果未来切到更复杂输出格式，现有解析会很脆弱。

### 低风险 / 可观察项
7. 当前每个点结束都 `DZ + CL`，安全性上偏保守，但速度会比较慢，也不符合官方资料里强调的 Standby / Bias Hold / After Measurement 管理方式。
- 如果后续要做更长 sweep 或更复杂偏置序列，可以考虑把“点间保偏”做成明确策略，而不是一律断开。

8. 资料提到 Kelvin connection 是官方推荐测量连接方式；当前代码层没有办法检查接线是否符合这个前提。
- 这不是代码 bug，但真机联调文档里最好写清楚，否则数据质量可能被误归因到代码。

## 可优化项（建议顺序）
### P1
1. 把 `CN` 的时机收口好。
- 最直接：每个 `measure()` 开始前先确保通道已 connect。
- 或者：不要在每个点后 `CL`，而是在 sweep 结束后统一 clear。
- 两种方案都比“只在 runner 初始化时 CN 一次、但每点后 CL”更合理。

2. 把 settling 策略从固定 `delay_s` 改成“至少可按场景配置”。
- 最小改法：在 config 中把 `delay_s` 改成更明确的 measurement settle 参数，并写清适用范围。
- 更进一步：按模块/量程/低电流模式提供不同推荐值。

### P2
3. 重新考虑 `fl_mode` 默认值。
- 如果项目目标偏稳妥，可把默认从 OFF 改成 ON。
- 如果保留 OFF，至少要在 config / README / TESTING 中写清这是“速度优先”选择。

4. 给 DC config 补一层更贴近手册的时间参数。
- 例如 integration/plc、或更明确的 low-current preset。

### P3
5. 让错误记录更完整。
- 可以考虑每个点测完后 drain 一次错误队列，或者把命令级错误上下文附加到 `DCMeasureResult`。

6. 明确限制当前支持的输出格式。
- 在 driver 或 README 里写清：当前只支持某类简单 ASCII 标量读取。
- 未来如果要接更复杂格式，再单独扩 parser，而不是继续靠启发式字符串解析。

## 本轮结论
- 当前代码不是“不能用”，但如果按官方资料口径看，已经有两处非常值得优先处理的真实链路风险：
  1. `CN/CL` 生命周期不一致
  2. settling / filter / integration 策略过于简化
- 如果下一轮继续 coding，建议先做“可行性分析 + 计划”后再落地这两项，而不是直接扩 WGFMU 或继续堆更高层功能。
