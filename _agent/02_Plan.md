# 当前计划

## Goal
**已完成**：与 DC 链路对称，给 WGFMU 这一侧补齐三层结构——驱动层（ctypes 绑 wgfmu.dll）+ 波形构建层（PulseTrainBuilder）+ 测量协议层（IV sweep / wake-up runner）+ 复用导出层。这样可以像 DC 通过 SMU 那样，用 Python 代码经 GPIB/VISA 控制 B1500 跑 WGFMU。

**下一轮**：等真机回归。真机那台 git pull 后，写 4-5 行调用代码用 `RealWgfmuBackend` 直接连 B1500，跑通最小 IV sweep；项目4 总台出第一份正式 TR 测试单（建议 R1-B）。

## Feasibility Analysis (本轮已完成)

### 已有基础 (2026-05-16 开工前)
- DC 主链路 28 passed，收口包 A+B 已完成
- WGFMU 已有最小脚手架（config / backend / smoke / export / dummy backend / 3 tests）
- notebook 12 提供原型，notebook 13/14 是空文件
- 项目4 总台 R1-A (★★★) 与 R1-B (★★) 等着这边 WGFMU 走通
- 工作区里有 B1530A User Guide PDF，能提 95 个 WGFMU2 C 函数名

### 本轮做的扩展（与 DC 对称）
1. **驱动层**：抽 B1530A User Guide → 95 个 WGFMU2 C 函数名，挑覆盖 R1-A/R1-B 的 27 个写 ctypes binding
2. **波形构建层**：`PulseTrainBuilder` 把多脉冲扫描从 notebook 那种"手写 add_vector 链"重构为声明式 `PulseSegment` 列表
3. **测量协议层**：`WgfmuIVSweepRunner`（脉冲扫 IV）+ `WgfmuWakeupRunner`（多阶段 wake-up + 低扰读出）
4. **导出层**：复用已有 `WgfmuDataExporter`

### 本轮不做（留给真机/下一轮）
- 真机 wgfmu.dll 实际调用验证（必须在 Windows + 真机执行）
- raw 数据模式（averaged 模式够 R1-A/R1-B）
- DC bias hold 在 wake-up 之间（`WGFMU_dcforceVoltage`）
- 多通道时序编排（G/D 分别 WGFMU 控制）
- notebook 13/14 真正写满（等真机数据来再做）

### 本轮中途的弯路（已纠正）
椰椰起床前，曾误加了 `physics_dummy.py`（假 PFeFET 物理模型）+ `visualize.py`（matplotlib 画图函数）+ `scripts/generate_wgfmu_deliverables.py`（用假 backend 伪造 3 组测试数据 + 画 5 张 PNG 的脚本）+ `WGFMU_DELIVERABLES.md`（围绕"3 张汇报图"的文档）。椰椰指出"只要编码 + 测试通过证明，不要画图/不要 mock 数据/不要 demo"，已全部移除（未进 git 历史）。

## Validation Commands
- `cd '项目路径' && PYTHONPATH=src python -m pytest -p no:cacheprovider tests/ -q` → **33 passed**
- `python -c "from fefetlab.measurements.wgfmu import RealWgfmuBackend, WgfmuIVSweepRunner, WgfmuWakeupRunner, PulseTrainBuilder, linear_voltage_segments"` → 无报错

## Success Criteria (本轮)
- ✅ `RealWgfmuBackend` 在 Linux 上可静态导入，load() 失败信息清晰
- ✅ `WgfmuIVSweepRunner` mock 路径端到端跑通，输出 per-pulse IV table
- ✅ `WgfmuWakeupRunner` mock 路径端到端跑通，输出 per-cycle 演化 table
- ✅ 测试基线 25 → 33，无回归
- ✅ 真机切换是 1 行代码：`backend = RealWgfmuBackend(); backend.open_session("GPIB0::17::INSTR")`

## Next Round Plan (真机回归)

### Task 1 (真机那台执行)
- 装 Keysight IO Libraries + B1500 软件 (内含 WGFMU 驱动)
- 验证 `wgfmu.dll` 在标准路径 / 或设 `WGFMU_DLL_PATH`
- `python -c "from fefetlab.measurements.wgfmu import RealWgfmuBackend; b=RealWgfmuBackend(); b.load(); b.open_session('GPIB0::17::INSTR'); print(b.get_channel_ids())"`

### Task 2 (真机那台执行)
- 写 4-5 行调用代码：用 `linear_voltage_segments()` 造 segment 列表 → `WgfmuIVSweepRunner(RealWgfmuBackend()).run(...)` → 拿真器件第一组 IV 数据

### Task 3 (本机/Hermes)
- 真机数据回流到项目4 `实测数据/TR-YYYYMMDD-NN/`
- 项目4 `03_Log.md` 写一行收口

## Risks
- 真机 dll 接口若与 User Guide 文档存在签名不一致（如 `addSequence` 第三参数是 int 而非 double），`real_backend.py` 的 ctypes argtypes 需要按真机错误现象调整。这是真机回归阶段的预期工作。
- `WGFMU_setMeasureEvent` 的 `mode` 参数（0=averaged, 1=raw）若改成 raw，返回数据点数会显著变多，QC 阈值要调。
