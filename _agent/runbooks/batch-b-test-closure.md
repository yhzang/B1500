# 收口包 B：高风险修复测试说明

## 1. 本轮目标
按“可行性分析 → 计划 → 落地”的流程，先修两类优先问题：
1. `CN/CL` 生命周期不一致
2. `settling / filter / integration time` 策略过于简化

本轮不做真实硬件验证，只做本地代码、测试和说明收口。

## 2. 本轮实际改动
### 2.1 连接生命周期修复
修改文件：
- `src/fefetlab/measurements/dc/measure.py`
- `src/fefetlab/measurements/dc/sweep.py`

改动内容：
- `DCSweepRunner._configure_instrument()` 不再在初始化时只做一次 `CN`
- `DCMeasurePoint.measure()` 改为每个单点开始前显式 `CN([G, D, S])`
- 单点结束后仍保留 `DZ + CL`

结果：
- connect / source / measure / zero / clear 生命周期重新闭合到单点测量层
- 避免“第一点后 CL 断开，下一点却不重新 CN”的真机风险

### 2.2 稳定优先默认值
修改文件：
- `src/fefetlab/measurements/dc/config.py`

改动内容：
- `fl_mode` 默认值从 `0` 改为 `1`
- `from_notebooks_default()` 同步改为 `fl_mode=1`

设计口径：
- 默认策略改为 stability-first
- 若用户明确要速度优先，仍可显式传 `fl_mode=0`

### 2.3 integration time 预留配置位
修改文件：
- `src/fefetlab/measurements/dc/config.py`

新增字段：
- `integration_time_mode: Optional[str] = None`
- `integration_time_factor: Optional[float] = None`

说明：
- 本轮只把能力保留到 config 层
- 尚未在 driver 层下发仪器命令
- 这样后续拿到更明确的 programming guide 命令后，可以直接接线

### 2.4 文档口径同步
修改文件：
- `src/fefetlab/measurements/dc/README.md`
- `README.md`
- `TESTING.md`
- `COMPLETION_SUMMARY.md`

收口内容：
- 修正导入路径为 `fefetlab.measurements.dc`
- 示例中统一使用 `compliance`
- 写清 `fl_mode=1` 的稳定优先默认值
- 补上 integration time 预留配置位说明
- 修正 notebook 编号与模块路径
- 把 `tests/test_verify_dc_sweep_script.py` 纳入正式测试入口说明

## 3. TDD 过程说明
### Red：先补 failing tests
本轮先在 `tests/test_dc_measurement.py` 增加/调整了以下测试：

1. `test_config_creation`
- 新增断言：
  - `fl_mode == 1`
  - `integration_time_mode is None`
  - `integration_time_factor is None`

2. `test_config_supports_reserved_integration_time_fields`
- 验证 config 已具备 integration time 预留配置位

3. `test_sweep_reconnects_channels_for_each_point`
- 新增 `ConnectionSensitiveMockB1500`
- 要求：未 `CN` 的通道不能 `DV/TI`
- 验证多点 sweep 时每个点都会重新 connect

### 失败验证命令
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_dc_measurement.py::test_config_creation tests/test_dc_measurement.py::test_config_supports_reserved_integration_time_fields tests/test_dc_measurement.py::test_sweep_reconnects_channels_for_each_point -q -vv
```

失败点：
- `fl_mode` 仍为 0
- `integration_time_*` 字段不存在
- 第二个 sweep 点在连接敏感 mock 下变成 `invalid`

## 4. Green：实现后通过的验证
### 命令 1：目标测试
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_dc_measurement.py::test_config_creation tests/test_dc_measurement.py::test_config_supports_reserved_integration_time_fields tests/test_dc_measurement.py::test_sweep_reconnects_channels_for_each_point -q -vv
```
结果：
- `3 passed`

### 命令 2：DC 全量本地 pytest
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_dc_measurement.py -q
```
结果：
- `20 passed in 8.24s`

### 命令 3：整合回归
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/test_verify_dc_sweep_script.py tests/tests_imports.py tests/test_dc_measurement.py -q
```
结果：
- `25 passed in 8.07s`

### 命令 4：本地模拟验证脚本
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500' && PYTHONPATH=src python scripts/verify_dc_sweep.py
```
结果：
- Mock / 模拟验证完整跑通
- 启动时会显式打印当前配置：`Delay`、`FMT`、`AV`、`Filter: ON (fl_mode=1)`、`Integration time: unset (reserved config only)`

## 5. 当前结论
### 已解决
- `CN/CL` 生命周期不一致
- filter 默认值过于偏速度优先
- integration time 没有配置落点
- DC README 中一批与当前实现不一致的说明

### 仍未解决
1. integration time 仍未真正下发到仪器
- 原因：本轮没有足够明确的 programming guide 命令依据
- 当前只把能力保留在 config 层

2. 真实硬件验证仍未做
- 仍需用户在另一台电脑执行

## 6. 下一轮建议
如果继续 coding，建议下一轮再按同样流程推进：
1. 先做可行性分析
2. 再写计划
3. 再落地

最优先候选是：
- 真机回归后，如果确认需要，再把 integration time 真正接到 driver 命令层
- 或者继续进入 WGFMU 正式模块骨架设计
