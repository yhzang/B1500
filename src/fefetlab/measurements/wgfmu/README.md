# WGFMU 模块状态与入口

这个目录现在不是空脚手架；它已经是项目3 B1500 的 WGFMU 正式代码层。原则是：**在现有模块上增量整理，不重新开一套并行实现**。

## 已具备的功能

- 后端抽象：`WgfmuBackend`
- 占位后端：`DummyWgfmuBackend`，用于 WSL / CI / dry-run 的 workflow shape 测试
- 真实后端：`RealWgfmuBackend`
  - ctypes 绑定 Keysight `wgfmu.dll`
  - DLL lazy load，Linux/WSL import 安全
  - WGFMU enum 已按 `WGFMU.cs` offset 真值修正
- setup helpers：`setup_helpers.py`
  - `ensure_wgfmu_dll_path()`
  - `autodetect_visa_addr("B1500")`
  - `clear_b1500_status_for_wgfmu_open()`
  - `autodetect_wgfmu_chan()`
- 波形构建：`PulseSegment` / `PulseTrainBuilder` / `linear_voltage_segments`
- 测量协议：
  - `WgfmuIVSweepRunner`
  - `WgfmuWakeupRunner`
  - `experiments.py` 中 E1 单点 helper
- 导出能力：parsed / qc / meta / plan / samples / iv / cycles 等 CSV/JSON。

## 当前真机口径

- yhzang B1500 测试机：`D:\test\B1500`
- 真机资源串实测：`GPIB1::17::INSTR`
- WGFMU 通道：`[201, 202, 301, 302]`
- FeFET 接线铁律：Gate=`202`，Drain=`201`
- `302` 悬空/无 RSU，不作为 FASTIV 通道
- WGFMU open 前必须走：

```python
from fefetlab.measurements.wgfmu import clear_b1500_status_for_wgfmu_open

idn = clear_b1500_status_for_wgfmu_open("GPIB1::17::INSTR")
print("B1500 preflight ERRX drain OK:", idn)
```

不要发 `*CLS`，不要默认 `*RST`。这台 B1500A 实测 `*CLS` 会入队 `+100,Undefined GPIB command`，导致 `WGFMU_openSession status=-6`。

## 推荐入口

### 本地 / WSL 验证

```bash
PYTHONPATH=src python -m pytest \
  tests/test_wgfmu_scaffold.py \
  tests/test_wgfmu_iv_and_wakeup.py -q
```

WSL 本地只验证 import / dummy backend / dry-run 逻辑；不要把 WSL 缺 DLL 当真机失败。

### 真机验证

```powershell
cd D:\test\B1500
.venv\Scripts\python.exe -m pytest tests\test_wgfmu_iv_and_wakeup.py tests\test_wgfmu_scaffold.py -q
```

### stop-gated 上机

```powershell
cd D:\test\B1500
.venv\Scripts\python.exe scripts\wgfmu_next_round_minimal.py --stage S1 --live --confirm S1 --device-id <DEVICE_ID> --geometry <GEOMETRY>
```

live 模式必须一段一段跑；任何 `*_STOP_*` 都停。

## 代码整理边界

- ✅ 可以改：测试契约、文档过时口径、preflight 日志、明确的 bug。
- ✅ 可以在 `scripts/wgfmu_next_round_minimal.py` 增量加实验阶段。
- ❌ 不要新增物理风味 fake backend、mock 数据出图、deliverables/demo 脚本。
- ❌ 不要再硬编码 `CHAN_ID=101` 到真机路径。
- ❌ 不要新增另一套 WGFMU runner 与现有 `WgfmuIVSweepRunner` / `WgfmuWakeupRunner` 并行竞争。
