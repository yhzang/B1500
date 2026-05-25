# DC Sweep API - 功能验证指南

本文档只说明当前仓库内可用的验证入口和验证边界。

- 仓库内当前以本地 Mock / 模拟验证为主。
- 真实硬件验证需要在连接 B1500 的另一台电脑上执行。
- 当前文档不再把仓库状态表述为“全部通过”或“READY”。

## 快速验证（3种方式）

### 方式1️⃣：本地 Mock / 模拟验证

适用场景：快速检查 DC API 的本地逻辑，不需要真实硬件。

```bash
cd B1500/
PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py
```

当前用途：
- 走 MockB1500 路径，检查无硬件场景下的调用链。
- 作为仓库内最直接的本地验证入口。
- 重点覆盖配置、扫描、导出、API 封装等逻辑。

说明：
- 请以命令实际输出为准，本文档不再预写“必然成功”的整段输出。
- 如果命令失败，通常表示导入路径、依赖或测试样例与当前代码仍有漂移，需要继续收口。

---

### 方式2️⃣：pytest 本地用例

适用场景：使用当前仓库里实际存在的 pytest 文件做本地验证。

```bash
cd B1500/
PYTHONPATH=src python -m pytest tests/test_verify_dc_sweep_script.py tests/tests_imports.py tests/test_dc_measurement.py tests/test_wgfmu_scaffold.py -q
```

当前覆盖范围：
- 验证脚本输出中的关键配置可见性（含 filter / integration 占位）
- 包入口导入边界
- pyvisa 缺失时的 Mock 路径导入
- DC 配置对象与测量链路
- WGFMU 脚手架导入、dummy smoke workflow、导出结果与列重命名

说明：
- 当前 pytest 入口包括 `tests/test_verify_dc_sweep_script.py`、`tests/tests_imports.py`、`tests/test_dc_measurement.py` 和 `tests/test_wgfmu_scaffold.py`。
- 仓库中并不存在 `src/fefetlab/measurements/dc/tests/demo_dc_sweep.py` 这一正式验证入口。
- WGFMU 当前是“正式脚手架 + dummy backend 可测”，不是“真实官方库已接好”。
- 本文档不再预写 `ALL TESTS PASSED` 一类固定结论。

---

### 方式3️⃣：真实硬件验证（需要仪器）

适用场景：在连接 B1500 的电脑上做真实测量流程验证。

```bash
cd B1500/
PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py --real
```

前置条件：
- B1500 仪器已连接并上电。
- `configs/instruments.yaml` 配置正确。
- `configs/channel_map.yaml` 通道映射正确。
- 在具备 VISA / GPIB 环境的电脑上执行。

边界说明：
- 当前仓库不做真实硬件验收记录。
- 真机结果由用户另一台电脑执行并确认。
- 因此，仓库文档只声明“提供真机验证入口”，不声明“真机已通过”。

---

## Jupyter Notebook 验证

### Notebook 10 / 11：DC 示例

文件：
- `notebooks/10_dc_api_idvg_example.ipynb`
- `notebooks/11_dc_api_idvd_example.ipynb`

用途：
- 演示正式落库的 DC API 用法。
- 适合作为 bring-up / 交互式检查入口。

说明：
- 若只是本地开发，可先看调用路径和参数，不必把 notebook 运行结果表述为正式验收。
- 若要做真机验证，请在连接 B1500 的电脑上运行。

### Notebook 12-34：WGFMU 原型、真实上机与交互式实验

文件：
- `notebooks/12_wgfmu_smoke.ipynb`（历史原型 / bring-up 参考）
- `notebooks/20-23_*`（L0/L1 dry-run / realdevice 验证）
- `notebooks/30-34_*`（E1/E2/E3/E4/E5 交互式实验入口）

当前口径：
- `src/fefetlab/measurements/wgfmu/` 已包含正式模块：dummy backend、`RealWgfmuBackend`、pulse builder、IV/wake-up runner、E1 helper 与 setup helpers。
- 当前真机主入口优先用 CLI：`scripts/wgfmu_next_round_minimal.py`，避免 Jupyter stale cell。
- 真机测试必须在 yhzang B1500 测试机 `D:\test\B1500` 执行；WSL 本地只做 dummy/dry-run/import 验证。
- WGFMU open 前不发 `*CLS`；统一走 `clear_b1500_status_for_wgfmu_open()`。

---

## 验证检查清单

### 当前仓库已具备的验证入口

- [x] `scripts/verify_dc_sweep.py`（本地 Mock / `--real` 双入口）
- [x] `tests/test_verify_dc_sweep_script.py`（验证脚本输出与关键配置可见性）
- [x] `tests/test_dc_measurement.py`（DC pytest 本地验证文件）
- [x] `tests/test_wgfmu_scaffold.py`（WGFMU smoke / dummy backend pytest）
- [x] `tests/test_wgfmu_iv_and_wakeup.py`（WGFMU pulse builder / IV / wake-up / real backend / preflight 回归）
- [x] `notebooks/10_dc_api_idvg_example.ipynb`
- [x] `notebooks/11_dc_api_idvd_example.ipynb`
- [x] `notebooks/12_wgfmu_smoke.ipynb` 等 WGFMU 原型 notebook

### 当前不应再写成“已完成”的事项

- [ ] 仓库内替代真机记录的口头验收（真机结果必须有远程命令/CSV/日志）
- [ ] “全部通过” / “READY” 这类无边界总括
- [ ] 未经 stop gate 的一次性 live 全跑
- [ ] `scripts/batch_sweep.py`
- [ ] `protocols/device_characterization.py`

---

## 常见问题排查

### 运行脚本报 ModuleNotFoundError

问题示例：
```text
ModuleNotFoundError: No module named 'fefetlab'
```

解决：
1. 确保在 `B1500/` 根目录运行。
2. 或显式设置 `PYTHONPATH`：
   ```bash
   export PYTHONPATH=src:$PYTHONPATH
   python scripts/verify_dc_sweep.py
   ```

### 运行脚本报 UnicodeEncodeError

问题示例（Windows）：
```text
UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'
```

解决：
```bash
PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py
```

### 真实硬件验证失败

常见检查项：
1. B1500 是否开机并连通。
2. VISA / GPIB 环境是否安装完整。
3. `configs/instruments.yaml` 中的资源字符串是否正确。
4. `configs/channel_map.yaml` 中的通道映射是否正确。
5. 是否在连接真实仪器的那台电脑上执行。

---

## 当前状态记录

### 2026-04-16

| 类别 | 当前仓库口径 | 备注 |
|------|--------------|------|
| DC 本地验证 | 可做本地 Mock / 模拟验证 | 以实际命令结果为准 |
| pytest | 存在实际用例文件 | 包括 `tests/test_verify_dc_sweep_script.py`、`tests/test_dc_measurement.py`、`tests/test_wgfmu_scaffold.py` |
| 真机验证 | 在 yhzang 测试机执行并回流 CSV/日志 | 项目3记录命令/结果，项目4归档实测数据 |
| WGFMU | 正式模块 + stop-gated 真机流程 | 有 `RealWgfmuBackend`、`scripts/wgfmu_next_round_minimal.py`、`tests/test_wgfmu_iv_and_wakeup.py` |
| 整体状态 | 可继续增量整理 / 上机 / 数据回流 | 不用无边界 READY 表述 |

---

## 进一步的测试建议

1. 在连接 B1500 的另一台电脑上执行 `scripts/verify_dc_sweep.py --real`，把真机结果与本仓库文档分开记录。
2. 如果 WGFMU 要继续扩展，沿现有 `src/fefetlab/measurements/wgfmu/` 和 `scripts/wgfmu_next_round_minimal.py` 增量加阶段；不要重新起一套并行结构。
3. 只有当 `scripts/batch_sweep.py`、协议层代码真实落库后，再把它们写回 README / 完成总结。

---

**更新时间**: 2026-04-16
