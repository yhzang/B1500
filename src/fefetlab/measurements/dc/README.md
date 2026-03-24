# DC扫描API文档

本模块提供了简洁、可复用的DC扫描测量API，用于B1500参数分析仪。

## 主要特性

✅ **简化的接口**：从~100行代码减少到~20行
✅ **自动化处理**：自动配置仪器、错误处理、数据导出
✅ **统一格式**：一致的数据输出（CSV/JSON/QC）
✅ **模块化设计**：可复用的组件，易于扩展

## 快速开始

### 基本用法

```python
from fefetlab.instruments.visa_session import VisaConfig, VisaSession
from fefetlab.measurements.dc import DCSweepAPI

# 配置仪器
visa_cfg = VisaConfig(
    resource="GPIB0::17::INSTR",
    timeout_ms=30000,
    write_termination="\r\n",
    read_termination="\r\n",
    send_end=True,
)

# 执行Id-Vg扫描
with VisaSession(visa_cfg) as session:
    dc_api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6)

    result = dc_api.run_idvg_sweep(
        vg_points=[0.0, -0.2, -0.4, -0.6, -0.8, -1.0],
        vd_fixed=0.1,
        vs_fixed=0.0
    )

    df = result['df']  # pandas DataFrame
    print(f"数据保存到: {result['run_dir']}")
```

## API参考

### DCSweepAPI

主要的高级API类，提供简洁的扫描接口。

#### 初始化

```python
DCSweepAPI(
    session: VisaSession,
    ch_g: int,
    ch_d: int,
    ch_s: int,
    config: Optional[DCSweepConfig] = None,
    export_dir: Path = Path("runs")
)
```

**参数：**
- `session`: 活跃的VISA会话
- `ch_g/ch_d/ch_s`: 栅极/漏极/源极通道号
- `config`: 可选的自定义配置（默认使用notebook标准设置）
- `export_dir`: 结果保存目录（默认`./runs`）

#### 方法

##### `run_idvg_sweep()`

执行Id-Vg扫描（转移特性）- 固定Vd/Vs，扫描Vg。

```python
result = dc_api.run_idvg_sweep(
    vg_points=[0.0, -0.2, -0.4],
    vd_fixed=0.1,
    vs_fixed=0.0,
    auto_export=True,  # 自动保存CSV/JSON/QC
    verbose=True       # 打印进度
)
```

**返回：**
```python
{
    'df': DataFrame,          # 测量数据
    'run_dir': Path,          # 保存目录
    'data_paths': {           # 数据文件路径
        'csv': Path,
        'json': Path
    },
    'qc_df': DataFrame        # QC报告
}
```

##### `run_idvd_sweep()`

执行Id-Vd扫描（输出特性）- 固定Vs，扫描Vg×Vd。

```python
result = dc_api.run_idvd_sweep(
    vg_points=[0.0, -0.4, -0.8],
    vd_points=[0.0, 0.05, 0.10],
    vs_fixed=0.0,
    auto_export=True,
    verbose=True
)
```

##### `run_custom_sweep()`

执行自定义扫描模式。

```python
sweep_points = [
    (vg1, vd1, vs1),
    (vg2, vd2, vs2),
    ...
]

result = dc_api.run_custom_sweep(
    sweep_points=sweep_points,
    sweep_name="my_custom_sweep",
    auto_export=True
)
```

## 数据格式

### 测量数据 (DataFrame)

| 列名 | 类型 | 说明 |
|------|------|------|
| `vg_set` | float | 设置的栅极电压 (V) |
| `vd_set` | float | 设置的漏极电压 (V) |
| `vs_set` | float | 设置的源极电压 (V) |
| `ig_A` | float | 测得的栅极电流 (A) |
| `id_A` | float | 测得的漏极电流 (A) |
| `is_A` | float | 测得的源极电流 (A) |
| `err` | str | 仪器错误信息 |
| `status` | str | 测量状态 ('ok' 或 'invalid') |
| `timestamp` | float | Unix时间戳 |

### QC报告 (DataFrame)

| 列名 | 类型 | 说明 |
|------|------|------|
| `vg_set` | float | 栅极电压 |
| `vd_set` | float | 漏极电压 |
| `vs_set` | float | 源极电压 |
| `status` | str | QC状态 ('ok' 或 'suspect') |
| `issues` | str | 问题列表（';'分隔） |
| `timestamp` | float | 时间戳 |

**可能的issues：**
- `instrument_error`: 仪器报错
- `missing_id/ig/is`: 电流数据缺失
- `measurement_failed`: 测量失败

## 高级用法

### 自定义配置

```python
from fefetlab.dc import DCSweepConfig, DCChannelConfig

# 创建自定义配置
custom_config = DCSweepConfig(
    channels={
        'G': DCChannelConfig(channel=4, vrange=0, i_comp=1e-3),
        'D': DCChannelConfig(channel=5, vrange=0, i_comp=5e-3),
        'S': DCChannelConfig(channel=6, vrange=0, i_comp=5e-3),
    },
    delay_s=0.5,      # 增加延迟
    fmt_mode=5,
    av_count=20,      # 增加平均次数
)

# 使用自定义配置
dc_api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6, config=custom_config)
```

### 低级API使用

如果需要更细粒度的控制：

```python
from fefetlab.dc import DCSweepRunner, DCDataExporter

# 使用sweep runner
runner = DCSweepRunner(b1500, config)
df = runner.sweep_vg(vg_points, vd_fixed, vs_fixed)

# 手动导出
exporter = DCDataExporter()
export_result = exporter.export_sweep(df, "my_sweep")
```

## 示例Notebooks

- `11_dc_api_idvg_example.ipynb`: Id-Vg扫描完整示例
- `12_dc_api_idvd_example.ipynb`: Id-Vd扫描完整示例

## 架构

```
fefetlab/dc/
├── __init__.py         # 包导出
├── config.py           # 配置数据类
├── measure.py          # 单点测量
├── sweep.py            # 扫描引擎
├── export.py           # 数据导出和QC
└── dc_sweep_api.py     # 高级API封装
```

## 对比旧方法

| 特性 | 旧方法 (08/09 notebooks) | 新API |
|------|-------------------------|--------|
| 代码行数 | ~100行 | ~20行 |
| 配置方式 | 手动设置每个参数 | 默认配置或一次性配置对象 |
| 错误处理 | 手动try/except | 自动处理 |
| 数据导出 | 手动保存CSV/JSON | 自动导出CSV/JSON/QC |
| 进度显示 | 手动打印 | 内置progress callback |
| 代码复用 | 复制粘贴 | 直接调用API |

## 迁移指南

### 从08 notebook迁移到新API

**旧代码（08 notebook风格）：**
```python
# 大量的初始化代码...
session = VisaSession(cfg)
b = B1500(session)
b.fmt(1)
b.av(10, 1)
# ...

# 手动循环测量
rows = []
for vg in vg_points:
    r = measure_id_vg_point(vg, vd_fixed, vs_fixed)
    rows.append(r)

# 手动保存
df = pd.DataFrame(rows)
df.to_csv(...)
df.to_json(...)
```

**新代码：**
```python
with VisaSession(visa_cfg) as session:
    dc_api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6)
    result = dc_api.run_idvg_sweep(vg_points, vd_fixed, vs_fixed)
    df = result['df']
```

## 常见问题

**Q: 如何修改电流合规值？**

```python
config = DCSweepConfig.from_notebooks_default(4, 5, 6)
config.channels['D'].i_comp = 5e-3  # 修改漏极合规为5mA
dc_api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6, config=config)
```

**Q: 如何禁用自动导出？**

```python
result = dc_api.run_idvg_sweep(..., auto_export=False)
# 只有df，没有文件保存
```

**Q: 如何自定义导出目录？**

```python
dc_api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6, export_dir=Path("my_data"))
```

**Q: QC报告中的'suspect'状态如何处理？**

检查`issues`列，根据具体问题处理：
- `instrument_error`: 检查仪器状态和连接
- `missing_data`: 可能合规限制或测量失败
- 手动审查可疑数据点

## 未来扩展

- [ ] 支持更多扫描模式（双向扫描、对数扫描）
- [ ] 内置绘图功能
- [ ] 实时数据可视化
- [ ] 更智能的QC分析
- [ ] 支持其他SMU通道配置
