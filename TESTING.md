# DC Sweep API - 功能验证指南

本文档说明如何验证DC扫描API的正常工作。

## 快速验证 (3种方式)

### 方式1️⃣ : 模拟验证 (推荐-最快)

**场景**: 快速检查API代码逻辑是否正确，无需硬件

```bash
cd B1500/
PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py
```

**预期输出**:
```
[Step 1] 创建配置...
✓ Config created:
  G=CH4, D=CH5, S=CH6

[Step 2] 创建模拟仪器...
✓ Mock B1500 created

[Step 3] 执行 Id-Vg 扫描...
✓ Sweep completed: 5 points

[Step 4] 导出数据和QC...
✓ Data exported to: runs\20260324_XXXXXX_verify_dc_api_demo

[Step 5] 测量结果预览:
 vg_set  vd_set     id_A status
    0.0     0.1 0.000001     ok
   -0.2     0.1 0.000001     ok
   -0.4     0.1 0.000001     ok

[Step 6] QC报告:
 vg_set status issues
    0.0     ok
   -0.2     ok
   -0.4     ok

[Step 7] 清理测试数据...
✓ Test directory cleaned

======================================================================
✅ 模拟验证成功！API工作正常
======================================================================
```

**验证内容**:
- ✅ Config创建和解析
- ✅ 单点测量逻辑
- ✅ 数据导出(CSV/JSON)
- ✅ QC报告生成
- ✅ 高级API结构

---

### 方式2️⃣ : 单元测试套件

**场景**: 详细的功能单元测试，有5个独立的测试

```bash
cd B1500/
PYTHONIOENCODING=utf-8 python src/fefetlab/measurements/dc/tests/demo_dc_sweep.py
```

**包含的测试**:
1. **TEST 1**: Configuration Creation
   - 验证配置对象创建和参数

2. **TEST 2**: Single Point Measurement
   - 验证单个测量点的执行和结果正确性

3. **TEST 3**: Sweep Execution
   - 验证多点Id-Vg扫描逻辑

4. **TEST 4**: Data Export and QC
   - 验证CSV/JSON导出
   - 验证QC报告生成

5. **TEST 5**: High-Level API
   - 验证DCSweepAPI的公共接口

**预期输出**: 最后显示 `✅ ALL TESTS PASSED`

**验证内容**:
- ✅ 配置系统
- ✅ 测量逻辑
- ✅ 扫描引擎
- ✅ 数据导出
- ✅ API接口

---

### 方式3️⃣ : 真实硬件验证 (需要仪器)

**场景**: 连接实际的B1500仪器，执行完整的扫描

```bash
cd B1500/
PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py --real
```

**前置条件**:
- B1500仪器已连接并打开
- `configs/instruments.yaml` 配置正确
- `configs/channel_map.yaml` 通道映射正确

**预期输出**:
```
[Step 1] 加载仪器配置...
✓ Config loaded:
  Resource: GPIB0::17::INSTR
  Channels: G=4, D=5, S=6

[Step 2] 连接仪器...
✓ 连接成功!
  IDN: Agilent Technologies,B1500A,...

[Step 3] 执行小范围 Id-Vg 扫描...
Progress: 3/3

✓ 扫描完成！数据保存到: runs\20260324_XXXXXX_verify_dc_api_real

测量结果:
 vg_set  vd_set     id_A status
    0.0     0.1 {...}     ok
   -0.2     0.1 {...}     ok
   -0.4     0.1 {...}     ok

✅ 真实硬件验证成功！
```

**验证内容**:
- ✅ B1500通信正常
- ✅ 通道配置正确
- ✅ 完整扫描流程
- ✅ 数据采集正确

---

## Jupyter Notebook 验证

### Notebook 10: Id-Vg 扫描示例

打开 `notebooks/10_dc_api_idvg_example.ipynb`

**步骤**:
1. 配置仪器连接参数（resource, channels）
2. Run All 或按单元逐步运行
3. 查看测量数据和绘图
4. 验证运行输出中有 "数据已保存到: ..."

**验证点**:
- ✅ Id-Vg特性曲线正确（|Id|随|Vg|增加）
- ✅ Ig远小于Id（栅漏比>1000）
- ✅ 数据文件已保存

### Notebook 11: Id-Vd 扫描示例

打开 `notebooks/11_dc_api_idvd_example.ipynb`

**步骤**:
1. 配置仪器和通道
2. Run All
3. 查看输出特性曲线

**验证点**:
- ✅ Id-Vd曲线形状合理（不同Vg曲线分离）
- ✅ 数据导出成功

---

## 验证检查清单

### 代码层面 (✅ 已通过)

- [x] Config数据类定义正确
- [x] DCMeasurePoint单点测量逻辑正确
- [x] DCSweepRunner扫描引擎正确
- [x] DCDataExporter数据导出正确
- [x] DCSweepAPI高级接口完整
- [x] 导入路径正确（measurements下的相对导入）
- [x] 错误处理完善
- [x] 文档完整

### 功能层面 (✅ 模拟验证已通过)

- [x] 配置创建和应用
- [x] 单点测量执行
- [x] 多点扫描
- [x] 数据导出(CSV)
- [x] JSON序列化
- [x] QC报告生成
- [ ] *真实硬件完整流程*(需硬件)

### 集成层面 (✅ 已通过)

- [x] 模块导入正确
- [x] API调用链正确
- [x] 数据流向正确
- [x] 错误传递正确

---

## 常见问题排查

### 运行脚本报 ModuleNotFoundError

**问题**:
```
ModuleNotFoundError: No module named 'fefetlab'
```

**解决**:
1. 确保在 `B1500/` 根目录运行脚本
2. 或设置PYTHONPATH:
   ```bash
   export PYTHONPATH=B1500/src:$PYTHONPATH
   python scripts/verify_dc_sweep.py
   ```

### 运行脚本报 UnicodeEncodeError

**问题** (Windows):
```
UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'
```

**解决**:
```bash
PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py
```

### 真实硬件验证失败

**问题**: `仪器连接失败: ...`

**检查项**:
1. B1500是否开电源
   ```bash
   # 试试这个命令
   python -c "from fefetlab.instruments.visa_session import VisaSession, VisaConfig; \
   cfg = VisaConfig(resource='GPIB0::17::INSTR', timeout_ms=5000); \
   session = VisaSession(cfg); \
   session.open(); \
   print(session.query('*IDN?')); \
   session.close()"
   ```

2. VISA后端是否安装 (NI-VISA)

3. GPIB地址是否正确
   - 控制卡: 18
   - 仪器: 17
   - 正确资源字符串: `GPIB0::17::INSTR`

4. 通道映射是否正确 (见 `configs/channel_map.yaml`)

---

## 测试结果记录

### 2026-03-24

| 测试项 | 模拟验证 | 单元测试 | 硬件验证 | 备注 |
|--------|---------|---------|---------|------|
| Config创建 | ✅ | ✅ | - | 成功 |
| 单点测量 | ✅ | ✅ | - | 成功 |
| 扫描执行 | ✅ | ✅ | - | 成功 |
| 数据导出 | ✅ | ✅ | - | 成功 |
| QC生成 | ✅ | ✅ | - | 成功 |
| 高级API | ✅ | ✅ | - | 成功 |
| **总体** | **✅ PASS** | **✅ PASS** | **待测** | API就绪 |

---

## 进一步的测试

如果需要更深入的测试，可以:

1. **边界值测试**: 修改demo脚本，添加极端值测试
2. **性能测试**: 测量大量数据点的扫描时间
3. **错误恢复**: 测试错误场景下的恢复能力
4. **数据准确性**: 与之前的notebook结果对比

---

**更新时间**: 2026-03-24
