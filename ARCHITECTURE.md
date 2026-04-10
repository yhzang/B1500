# B1500 项目架构设计指南

本文档定义了B1500自动化测试系统的统一架构模式，所有新功能开发都应遵循此模式。

## 分层架构

```
Application Layer (notebooks, scripts, protocols)
    ↓
High-Level API Layer (measurements/[type]/[type]_api.py)
    ↓
Generic Sweep Engine Layer (measurements/[type]/sweep.py)
    ↓
Single-Point Measurement Layer (measurements/[type]/measure.py)
    ↓
Instrument Driver Layer (b1500/driver.py)
    ↓
Communication Layer (instruments/visa_session.py)
```

每一层的职责和设计原则：

### 层1: 通信层 [LOWEST LEVEL]

**文件**: `src/fefetlab/instruments/visa_session.py`

**职责**:

- 统一的VISA命令收发接口
- 自动处理终止符和编码
- 异常处理和超时管理

**设计原则**:

- ✅ 不关心仪器类型
- ✅ 只处理底层VISA操作
- ✅ 提供同步query/write方法
- ❌ 不做业务逻辑

**示例**:

```python
session = VisaSession(config)
session.open()
result = session.query("*IDN?")  # 获取设备ID
session.close()
```

---

### 层2: 仪器驱动层 [INSTRUMENT DRIVER]

**文件**: `src/fefetlab/b1500/driver.py`

**职责**:

- 封装B1500特定的命令
- 提供统一的命令接口 (dv, ti, dz, cl, fmt, av等)
- 底层错误处理和命令解析

**设计原则**:

- ✅ B1500特定的命令集
- ✅ 简单的函数式接口 (dv, ti, etc.)
- ✅ 自动缓冲区管理
- ✅ 返回解析后的数据 (float, not string)
- ❌ 不做测量逻辑
- ❌ 不做数据处理

**示例**:

```python
b1500 = B1500(session)
b1500.dv(ch=4, vrange=0, voltage=0.5, compliance=1e-3)  # 设置电压
i = b1500.ti(ch=4, irange=0)  # 测量电流
b1500.dz([4, 5, 6])  # 归零通道
```

---

### 层3: 测量功能API层 [HIGH-LEVEL MEASUREMENTS]

这是项目最灵活的部分。每个测量功能（DC、AC、WGFMU等）都有一套标准的内部结构：

#### 子层3a: 配置管理

**文件**: `measurements/[type]/config.py`

**职责**:

- 定义配置数据结构 (dataclass)
- 提供配置工厂方法 (from_defaults, from_yaml等)

**设计原则**:

- ✅ Pure data classes (no logic)
- ✅ Type hints
- ✅ 工厂方法用于常见配置
- ✅ 易于序列化(YAML/JSON)

**示例**:

```python
@dataclass
class DCSweepConfig:
    channels: dict[str, DCChannelConfig]
    delay_s: float = 0.2

    @classmethod
    def from_notebooks_default(cls, ch_g, ch_d, ch_s):
        return cls(channels={...})
```

#### 子层3b: 单点测量

**文件**: `measurements/[type]/measure.py`

**职责**:

- 执行单个测量点（e.g., 设置一组电压→延迟→读电流）
- 返回结果对象 (dataclass)
- 原始的错误处理

**设计原则**:

- ✅ 单一职责：执行一个test point
- ✅ 完整的生命周期管理（setup → measure → cleanup）
- ✅ 异常处理和状态记录
- ✅ 返回结果对象(易于序列化)
- ❌ 不做循环/扫描逻辑

**示例**:

```python
class DCMeasurePoint:
    def measure(self, vg: float, vd: float, vs: float) -> DCMeasureResult:
        # 1. Setup
        # 2. Measure
        # 3. Cleanup (finally block)
        pass
```

#### 子层3c: 扫描引擎

**文件**: `measurements/[type]/sweep.py`

**职责**:

- 执行多点扫描（various sweep patterns）
- 返回pandas DataFrame
- 通用的progress callback支持

**设计原则**:

- ✅ 多种扫描模式 (sweep_vg, sweep_vd, sweep_custom)
- ✅ 柔性的进度报告
- ✅ 配置自动应用
- ✅ 返回DataFrame而不是列表

**示例**:

```python
class DCSweepRunner:
    def sweep_vg(self, vg_points, vd_fixed, vs_fixed, progress_callback=None) -> pd.DataFrame:
        pass

    def sweep_vd(self, vg_points, vd_points, vs_fixed) -> pd.DataFrame:
        pass

    def sweep_custom(self, sweep_points) -> pd.DataFrame:
        pass
```

#### 子层3d: 数据导出

**文件**: `measurements/[type]/export.py`

**职责**:

- 数据保存 (CSV, JSON)
- QC报告生成
- 目录/文件管理

**设计原则**:

- ✅ 统一的导出接口
- ✅ 时间戳目录管理
- ✅ QC逻辑集中
- ✅ 返回路径信息

**示例**:

```python
class DCDataExporter:
    def export_sweep(self, df, sweep_type) -> dict:
        # 返回 {'run_dir': Path, 'data_paths': {...}, 'qc_df': DataFrame}
        pass
```

#### 子层3e: 高级API

**文件**: `measurements/[type]/[type]_api.py`

**职责**:

- 用户友好的单一接口
- 组合上述各层逻辑
- 进度显示和日志

**设计原则**:

- ✅ 最简单的接口（用户只需关注参数）
- ✅ 自动化所有非功能细节
- ✅ 返回易用的结果结构
- ✅ verbose模式用于调试

**示例**:

```python
class DCSweepAPI:
    def run_idvg_sweep(self, vg_points, vd_fixed, vs_fixed) -> dict:
        # 用户只需这一行就能完成整个流程
        pass
```

---

## 模块化设计的优势

```
高级API (简洁)
  ├─ 底层swap复杂性，让用户关注参数
  └─ 实现fast path，无需关心细节

扫描引擎 (灵活)
  ├─ 可独立使用（使用者能自己定制progress）
  ├─ 支持多种扫描模式
  └─ DataFrame输出易于后处理

单点测量 (可靠)
  ├─ 完整的生命周期管理
  ├─ 每次测量独立
  └─ 易于单元测试

配置 (可扩展)
  ├─ 数据驱动
  └─ 支持多种配置源(代码/YAML/预设)
```

---

## 新功能开发模板

当需要开发新的测量功能（如AC扫描）时：

### Step 1: 创建目录结构

```bash
mkdir -p src/fefetlab/measurements/ac/tests
touch src/fefetlab/measurements/ac/__init__.py
```

### Step 2: 步骤运实现各层（从底到上）

#### ac/config.py

```python
@dataclass
class ACSweepConfig:
    channels: dict  # G, D, S
    frequency: float = 1e6  # 1 MHz
    # ... AC特定参数

    @classmethod
    def from_defaults(cls, ch_g, ch_d, ch_s):
        return cls(...)
```

#### ac/measure.py

```python
@dataclass
class ACMeasureResult:
    freq_hz: float
    cg_pF: float
    tand: float
    # ...

class ACMeasurePoint:
    def measure(self, vg: float, vd: float, vs: float) -> ACMeasureResult:
        # Setup → Measure Impedance → Return Result
        pass
```

#### ac/sweep.py

```python
class ACSweepRunner:
    def sweep_vg(self, vg_points, vd_fixed, vs_fixed) -> pd.DataFrame:
        pass
```

#### ac/export.py

```python
class ACDataExporter:
    def export_sweep(self, df, sweep_type) -> dict:
        pass
```

#### ac/ac_sweep_api.py

```python
class ACSweepAPI:
    def run_cgvg_sweep(self, vg_points, vd_fixed, vs_fixed) -> dict:
        # 简洁用户接口
        pass
```

### Step 3: 编写测试

#### ac/tests/demo_ac_sweep.py

- 复制DC的测试结构
- 调整为AC特定逻辑
- 验证5个测试都通过

### Step 4: 编写文档

#### ac/README.md

- API参考
- 使用示例
- 常见问题

### Step 5: 创建example notebook

#### notebooks/13_ac_api_example.ipynb

- 加载AC API
- 执行一个小扫描
- 可视化结果

### Step 6: 注册到top-level API

编辑 `src/fefetlab/measurements/__init__.py`:

```python
from .ac import ACSweepAPI, ACSweepConfig
__all__ = [..., "ACSweepAPI", "ACSweepConfig"]
```

### Step 7: 更新项目文档

编辑主README:

- 在开发历史添加记录
- 更新架构图

---

## 设计检查清单

开发新功能时，用这个清单验证设计质量：

### 代码分层

- [ ]  config.py: 纯数据结构
- [ ]  measure.py: 单点执行，完整生命周期
- [ ]  sweep.py: 多点扫描，支持progress callback
- [ ]  export.py: 数据处理和保存
- [ ]  api.py: 用户友好的高层接口

### 导入

- [ ]  上下层导入方向正确（从高向低）
- [ ]  相对导入使用三层结构 (`from ...b1500`)
- [ ]  避免循环导入

### 文档

- [ ]  每个类有docstring
- [ ]  公共方法有参数说明
- [ ]  提供至少一个完整使用示例
- [ ]  有README.md

### 测试

- [ ]  配置测试
- [ ]  单点测量测试
- [ ]  扫描执行测试
- [ ]  数据导出测试
- [ ]  API接口测试

### 数据

- [ ]  结果使用dataclass
- [ ]  支持to_dict()转换
- [ ]  支持DataFrame转换
- [ ]  支持JSON序列化

---

## 常见设计陷阱

❌ **避免**:

1. 在config中写业务逻辑
2. 在measure中做扫描
3. 在sweep中做数据处理
4. 混淆数据流向（应该向下，不要向上）
5. 硬编码仪器参数（应该在config中）
6. 大对象复制（应该用引用或路径）

✅ **推荐**:

1. 每层单一职责
2. 清晰的数据流向 (high → low)
3. 配置驱动
4. 通用接口 (progress callback, DataFrame output)
5. 完整的文档和测试
6. 易于扩展（新配置/新扫描模式）

---

**更新时间**: 2026-03-24
