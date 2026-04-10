# B1500自动化测试系统 - 项目开发指南

## 🚀 首次安装（新电脑必读）

> **一键初始化虚拟环境和所有依赖**

```bash
# Unix/Linux/Mac/Git Bash
bash setup.sh

# Windows (PowerShell / CMD)
setup.bat
```

脚本会自动：
1. ✅ 检查Python版本 (需要 ≥ 3.10)
2. ✅ 创建虚拟环境 `.venv`
3. ✅ 安装所有依赖包 (PyVISA, NumPy, Pandas等)
4. ✅ 安装项目包
5. ✅ 验证安装完成

**手动初始化**（如果脚本失败）：
```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements/dev.txt

# 4. 安装项目包
pip install -e .
```

> ⚡ **快速验证**: 想验证DC功能是否正常?
> - **3分钟快速验证**: `PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py`
> - **详细验证说明**: 查看 [TESTING.md](TESTING.md)

## 整体项目架构

```
B1500/
├── notebooks/                    # Jupyter Notebooks - 探索、调试、bring-up
│   │
│   ├─ 基础层 (01-03: Communication & Driver Tests)
│   ├── 01_check_termination.ipynb                 # 串口终止符验证
│   ├── 02_session_smoke.ipynb                     # VISA会话冒烟测试
│   ├── 03_driver_smoke.ipynb                      # B1500驱动冒烟测试
│   │
│   ├─ DC基础 (04-09: DC Measurements)
│   ├── 04_dc_single_channel.ipynb                 # 单通道DC测试
│   ├── 05_dc_multiport_sanity.ipynb               # 多通道健全性测试
│   ├── 06_probe_ti_channels.ipynb                 # 通道探测
│   ├── 07_dc_3terminal_sanity.ipynb               # 三端器件测试
│   ├── 08_dc_idvg_oldversion.ipynb                # [参考] 旧版Id-Vg扫描
│   ├── 09_dc_idvd_oldversion.ipynb                # [参考] 旧版Id-Vd扫描
│   │
│   ├─ DC API (10-11: New API Examples)
│   ├── 10_dc_api_idvg_example.ipynb               # [新API] Id-Vg扫描示例
│   ├── 11_dc_api_idvd_example.ipynb               # [新API] Id-Vd扫描示例
│   │
│   ├─ WGFMU (12-14: Pulse Measurements)
│   ├── 12_wgfmu_smoke.ipynb                       # WGFMU冒烟测试
│   ├── 13_wgfmu_step_pulse_observe.ipynb          # WGFMU阶跃脉冲观测
│   ├── 14_wgfmu_sampling_smoke.ipynb              # WGFMU取样冒烟测试
│   │
│   └─ 工具 (15+: Utilities)
│       └── 15_channel_probe_test.ipynb            # 通道探测工具
│
├── scripts/                      # 可执行脚本 - 一键运行固定流程
│   ├── verify_dc_sweep.py                     # DC功能验证脚本
│   └── batch_sweep.py                         # 批量扫描脚本
│
├── protocols/                    # 测量协议 - 组合基础功能成完整实验
│   └── device_characterization.py             # 器件完整表征协议
│
├── configs/                      # 配置文件
│   ├── instruments.yaml                       # 仪器配置（资源地址、超时等）
│   └── channel_map.yaml                       # 通道映射（G/D/S→4/5/6）
│
├── src/fefetlab/                # Python核心库
│   │
│   ├── instruments/              # 层1：通用仪器接口（LOWEST LEVEL）
│   │   ├── __init__.py
│   │   └── visa_session.py                    # VISA会话管理
│   │
│   ├── b1500/                    # 层2：B1500硬件驱动（INSTRUMENT DRIVER）
│   │   ├── __init__.py
│   │   └── driver.py                          # 底层命令API (dv, ti, dz, cl等)
│   │
│   ├── measurements/             # 层3：测量功能API（HIGH-LEVEL API）
│   │   ├── __init__.py
│   │   │
│   │   ├── dc/                                # DC测量模块 ✅ 已完成
│   │   │   ├── __init__.py
│   │   │   ├── config.py                      # 配置数据类
│   │   │   ├── measure.py                     # 单点测量逻辑
│   │   │   ├── sweep.py                       # 扫描引擎
│   │   │   ├── export.py                      # 数据导出和QC生成
│   │   │   ├── dc_sweep_api.py                # 高级API (DCSweepAPI)
│   │   │   ├── README.md                      # 模块文档
│   │   │   └── tests/                         # 测试/验证
│   │   │       ├── test_dc_sweep.py           # 单元测试
│   │   │       └── demo_dc_sweep.py           # 交互式验证脚本
│   │   │
│   │   ├── ac/                                # AC测量模块 (待开发)
│   │   │   └── [结构同dc/]
│   │   │
│   │   ├── wgfmu/                             # WGFMU脉冲测量模块 (待开发)
│   │   │   └── [结构同dc/]
│   │   │
│   │   └── capacitance/                       # 电容测量模块 (待开发)
│   │       └── [结构同dc/]
│   │
│   └── __init__.py
│
├── runs/                         # 测量结果输出目录（由脚本生成）
│   └── YYYYMMDD_HHMMSS_*_sweep/
│       ├── data.csv              # 原始数据
│       ├── data.json             # JSON格式数据
│       └── qc.csv                # QC质量控制报告
│
├── requirements.txt              # Python依赖
├── README.md                      # 本文件 - 项目开发指南
└── .gitignore


```

## 📓 Notebook 编号规则

为了保持项目的清晰性，所有notebooks按照功能分类编号：

| 范围 | 分类 | 说明 | 状态 |
|------|------|------|------|
| **01-03** | 基础层 | 通信和驱动验证 | ✅ 稳定 |
| **04-07** | DC基础 | 单通道、多通道、三端器件 | ✅ 稳定 |
| **08-09** | DC参考 | 旧版扫描实现（供参考） | 📚 存档 |
| **10-11** | DC API | 新API使用示例（推荐） | ✅ 新建 |
| **12-14** | WGFMU | 脉冲测量实验 | ⏳ 开发中 |
| **15+** | 工具 | 辅助工具和测试 | - |

**命名约定**:
- 格式: `NN_[feature]_[description].ipynb`
- 示例: `10_dc_api_idvg_example.ipynb`
- 所有功能描述使用小写字母和下划线

### 为什么保留旧版（08, 09）?

- 📖 文档参考价值：展示早期手工实现方式
- 🔍 对比学习：对比新旧API的设计差异
- 🛡️ 回归测试：如需验证其他驱动程序，可参考

**建议**: 新开发仅使用 10-11 的API示例。

## 开发流程和规范

### 1️⃣ 每个测量功能的标准结构

所有测量模块（dc, ac, wgfmu等）应遵循统一的架构模式：

| 文件 | 功能 | 职责 |
|-----|------|------|
| `config.py` | 配置数据类 | 定义配置数据结构 (dataclass) |
| `measure.py` | 单点测量 | 执行一个测量点（施压→延迟→测量→归零） |
| `sweep.py` | 扫描引擎 | 通用扫描执行器（支持多种扫描模式） |
| `export.py` | 数据处理 | 数据导出(CSV/JSON)和QC生成 |
| `[type]_api.py` | 高级API | 特定功能的高级封装(e.g. `dc_sweep_api.py`) |
| `README.md` | 模块文档 | API文档、示例、常见问题 |
| `tests/` | 测试 | 单元测试和功能验证脚本 |

### 2️⃣ 开发新功能的步骤

以开发AC测量为例：

```
1. 在 src/fefetlab/measurements/ac/ 创建新模块
2. 按照标准结构创建：
   - config.py       (from acdc扫描特性定义)
   - measure.py      (单点AC测量逻辑)
   - sweep.py        (AC扫描引擎)
   - export.py       (数据导出)
   - ac_sweep_api.py (高级API)
3. 编写 README.md，说明API用法
4. 创建 tests/demo_ac_sweep.py 验证脚本
5. 在 notebooks/[NN]_ac_api_*.ipynb 创建demo notebook
6. 更新本README的"开发历史"记录
```

### 3️⃣ 代码规范

**模块化设计：**
- 底层(measure.py): 原始操作，错误处理
- 中层(sweep.py): 扫描逻辑，灵活但可复用
- 高层(api.py): 简洁易用，隐藏复杂性

**数据流向：**
```
高级API(api.py)
    ↓ (调用)
扫描引擎(sweep.py)
    ↓ (调用)
单点测量(measure.py)
    ↓ (调用)
底层驱动(b1500/driver.py)
    ↓ (调用)
通用接口(instruments/visa_session.py)
```

**文档要求：**
- 每个模块必须有docstring说明用途
- 公共API必须有详细的参数说明
- 提供至少一个完整使用示例

### 4️⃣ 测试验证

每个功能开发完成后：

```bash
# 1. 运行单元测试
python -m pytest src/fefetlab/measurements/[module]/tests/test_*.py

# 2. 运行交互式演示
python src/fefetlab/measurements/[module]/tests/demo_*.py

# 3. 在notebook中验证
# 运行 notebooks/[N]_[module]_api_*.ipynb
```

---

## 开发历史

### ✅ 2026-03-24 - DC扫描API封装完成

**完成内容：**
- [x] DC测量模块架构设计（config, measure, sweep, export, api）
- [x] DCSweepAPI高级接口（run_idvg_sweep, run_idvd_sweep）
- [x] 自动数据导出(CSV/JSON/QC)
- [x] 完整API文档(README.md)
- [x] Demo notebooks (10, 11)
- [x] 功能验证脚本

**模块位置：** `src/fefetlab/measurements/dc/`

**主要类：**
- `DCSweepConfig`: 配置管理
- `DCMeasurePoint`: 单点测量
- `DCSweepRunner`: 扫描引擎
- `DCDataExporter`: 数据导出
- `DCSweepAPI`: 高级API (user-friendly)

**使用示例：**
```python
from fefetlab.measurements.dc import DCSweepAPI

with VisaSession(visa_cfg) as session:
    dc_api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6)
    result = dc_api.run_idvg_sweep(
        vg_points=[0.0, -0.2, -0.4],
        vd_fixed=0.1,
        vs_fixed=0.0
    )
    df = result['df']  # pandas DataFrame
```

**验证方式：**
- 运行 `scripts/verify_dc_sweep.py`
- 运行 notebooks/10 和 11

---

### ⏳ 待开发功能

- [ ] **AC扫描** (measurements/ac/) - LCR电容测量
- [ ] **WGFMU** (measurements/wgfmu/) - 脉冲/动态应力测量
- [ ] **Capacitance** (measurements/capacitance/) - 电容-电压特性
- [ ] **Leakage** (measurements/leakage/) - 漏电流自动筛选
- [ ] **Protocol Layer** - 完整的器件表征协议

---

## 📖 快速开始

### 验证DC功能

```bash
# 方式1: 运行验证脚本（推荐新手）
python scripts/verify_dc_sweep.py

# 方式2: 在notebook中运行示例
# 打开 notebooks/10_dc_api_idvg_example.ipynb 或 11_dc_api_idvd_example.ipynb
# 修改通道号，连接仪器，Run All

# 方式3: 在Python代码中使用
python -c "
from fefetlab.measurements.dc import DCSweepAPI
from fefetlab.instruments.visa_session import VisaConfig, VisaSession

visa_cfg = VisaConfig(resource='GPIB0::17::INSTR', ...)
with VisaSession(visa_cfg) as session:
    api = DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6)
    result = api.run_idvg_sweep([0.0, -0.2, -0.4], 0.1, 0.0)
    print(result['run_dir'])
"
```

### 开发新功能

1. 选择功能名称（如`ac`, `wgfmu`）
2. 在 `src/fefetlab/measurements/[name]/` 创建目录
3. 复制 `dc/` 的结构作为模板
4. 修改配置和测量逻辑
5. 更新本README的开发历史

---

## 配置说明

### instruments.yaml

```yaml
b1500:
  resource: "GPIB0::17::INSTR"    # 仪器GPIB地址
  timeout_ms: 30000                # 超时(毫秒)
  write_termination: "\r\n"        # 写终止符
  read_termination: "\r\n"         # 读终止符
  send_end: true                   # 发送EOI信号
```

### channel_map.yaml

```yaml
current_device:
  role_map:
    G: 4      # 栅极 → CH4
    D: 5      # 漏极 → CH5
    S: 6      # 源极 → CH6
    X: 7      # 备用 → CH7
```

---

## 常见问题

**Q: 运行验证脚本报连接错误？**

A: 检查：
1. 仪器是否打开
2. GPIB地址是否正确（18是控制卡地址，17是仪器地址）
3. 通道号是否正确映射

**Q: 可以同时开发两个功能模块吗？**

A: 是的，完全独立。新功能应在`measurements/[name]/`下创建独立目录。

**Q: 如何扩展DC测量功能？**

A: 在`measurements/dc/`下添加新的sweep模式，或在`dc_sweep_api.py`添加新方法。

**Q: 数据保存到哪里？**

A: `runs/YYYYMMDD_HHMMSS_[sweep_type]/`目录下，包含：
- `data.csv` - 原始数据
- `data.json` - JSON格式
- `qc.csv` - QC报告

---

## 相关文件

- 底层驱动: `src/fefetlab/b1500/driver.py`
- 仪器接口: `src/fefetlab/instruments/visa_session.py`
- DC模块: `src/fefetlab/measurements/dc/README.md`
- Demo notebooks: `notebooks/11_dc_api_idvg_example.ipynb`

---

**最后更新**: 2026-03-24
