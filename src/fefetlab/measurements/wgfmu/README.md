# WGFMU 模块脚手架

这个目录当前不是“已接好官方库的完整 WGFMU 实现”，而是一个正式落库的脚手架。

当前已经具备的功能：
- 配置模型：脉冲参数、测量事件参数、smoke 运行参数
- 后端抽象：`WgfmuBackend`
- 占位后端：`DummyWgfmuBackend`
- smoke 主流程：discovery → offline setup → online setup → execute → result → qc → export → cleanup
- 导出能力：
  - `parsed.csv`
  - `qc.csv`
  - `meta.json`
  - `setup_ascii.json`

当前还不具备的功能：
- 真实官方 Instrument Library 绑定
- ctypes / cffi / pybind11 封装
- 真实硬件验证
- 更复杂的 pulse sequence / 多通道时序编排

## 推荐入口

```python
from fefetlab.measurements.wgfmu import (
    DummyWgfmuBackend,
    MeasureEventParams,
    PulsePatternParams,
    WgfmuSmokeConfig,
    WgfmuSmokeRunner,
)

pulse_cfg = PulsePatternParams(
    chan_id=101,
    pattern_name="smoke_pulse",
    v_init=0.0,
    v_pulse=-1.0,
    t_rise_s=1e-6,
    t_high_s=2e-6,
    t_fall_s=1e-6,
    t_base_s=2e-6,
)
meas_cfg = MeasureEventParams(
    event_name="smoke_event",
    start_time_s=0.0,
    points=20,
    interval_s=2e-7,
    average_s=2e-7,
)
run_cfg = WgfmuSmokeConfig(label="wgfmu_smoke")

runner = WgfmuSmokeRunner(DummyWgfmuBackend())
result = runner.run(
    resource="DUMMY::INSTR",
    pulse_cfg=pulse_cfg,
    meas_cfg=meas_cfg,
    run_cfg=run_cfg,
)

print(result.qc_df)
print(result.paths)
```

## 下一步建议
- 接真实 backend 前，先确认官方库调用方式和异常模型
- 如果开始接真实库，优先新增 `RealWgfmuBackend`
- 真机联调前，先保留 dummy backend 测试不回退
