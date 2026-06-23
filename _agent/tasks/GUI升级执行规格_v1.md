# B1500 FeFET 上位机 · GUI 升级执行规格 v1

> 来源:2026-06-22 多智能体研究(挖 EasyEXPERT + B1530A 手册 + 审计现有 GUI/ParamSpec)。
> 分支:`gui-upgrade-20260622`(基线 commit `e6dbdee`)。本机不跑 GUI/硬件,只跑纯 Python 单测;真机验证走 scp→测试机 pytest / `python -m gui`。
> **目录契约以代码为准**:现行两级 `runs/<device>/<die>/{live,dry}/<ts>_<stage>`(orchestration/export.py:28-35);设计文档 §6.4/§6.5/§10.4 的旧 `runs/{dry,live}/<ts>_<STAGE>_<dev>` 已过时。

## 增量顺序(按价值/风险)
1. ✅ **on_shot 实时增量绘图(完成 commit b337910)** — plot_panel `begin_live_plot/append_shot_rows`(环形缓冲、33ms QTimer 限频、>4000 点降采样、ERS/PGM 配色);app `_wire` 接 `c.shot`、`_on_run` 提交后 `begin_live_plot`。真机 `tests/` 绿。
2. ✅ **ParamForm typed 控件 + 单位 + 校验(完成 commit 4b9c394)** — 按 kind/widget 渲染 QSpinBox/QDoubleSpinBox(时间单位 µs/ns/ms 做 SI 缩放,µA 不缩放)/QComboBox/只读 LOCKED/CSV 校验红框+is_valid;None 默认留可空。真机 `tests/` 102 passed。
   — 附带:ISPP 闭环协议(项目5 杀手锏)已注册进 REGISTRY,GUI 协议树自动出现、typed 表单 + 实时图都对它生效。
3. ✅ **输出根目录 + run_log.txt + 无 BOM CSV(完成 commit a1cdb95)** — run_control_panel 输出根目录选择器(默认空=repo ROOT,椰椰定)→RunRequest.out_root→worker→`_stage_dir(root=getattr(args,'out_root','') or ROOT)`;`_on_stage_done` 写 `run_dir/run_log.txt`(UTF-8 无 BOM);**全部 8 处 CSV 写入 `utf-8-sig`→`utf-8`**(dc/wgfmu export、iv_sweep、wakeup;FIELDNAMES 走 orchestration/export.py 本就无 BOM,golden 169/640 不动)。真机 `tests/` 106 passed。
4. ✅(部分) **提升硬编码旋钮(完成 commit eb0f787)** — 经 configure_channel_map 一次性注入运行时全局(波形构建零改动、golden 169/640 不动):**read_irange_gate/drain(CHOICE 下拉)、n_pts、raw_data_mode(CHOICE)** 已提升进 COMMON,所有协议共有、GUI 自动出下拉/spinbox。真机 107 passed,gatekeeper 逐字节守门。
   - **遗留(增量4b)**:t_rf/t_read/t_neutral/t_reset —— 这 4 个时间常量散作字面量/参数默认遍布 ~40 处波形构建点,深度串改、golden 风险高、日常少改,单列后做。
5. ✅ **可视化进阶(完成 commit 883b70c)** — 结果图工具条:log X/Y 轴、自动缩放、InfiniteLine 十字游标读坐标、Id/Ig 通道显隐、Id_std 误差棒;数据级开关经 plotter options 传适配器,轴级由壳施加;结果 df 缓存改开关即重画。真机 110 passed。(MW 派生线 + 手动范围 spinbox 暂略,够用即可。)
6. ✅(6a+6b) **RunBrowser + DC 协议族(完成 commit 53972b8 / 40ef27b)** — **6a**:新「历史浏览」tab,`scan_runs` 扫两级布局、按 device/die 分组、选中离线重画(按 manifest stage 查 schema)、多选叠加对比。**6b**:DC_IDVG/IDVD 接进引擎+GUI(family=SMU、csv_schema=dc,dry 经 MockB1500 跑通、落两级目录+manifest、RunBrowser 可见、`@register_plot("dc")` 出 Id-Vg/Id-Vd 半对数图);引擎 family 分流(WGFMU 才 configure_channel_map,SMU 旁路)是唯一触 WGFMU 的改动且逐字节不变;DC live 门照常生效。真机 **120 passed**,golden 169/640 不动。**遗留(待器件)**:SMU live 真机后端、CLI 开放 DC stage、回流项目4。

## 要提升的硬编码旋钮(增量4;提升三步:runner 加 flag → registry `_p` 加 ParamSpec → test_registry_params 守门 default 逐字节)
| 旋钮 | 现位置 | kind/widget | 默认 |
|---|---|---|---|
| read_irange_gate | wgfmu_fefet.py:72 | CHOICE/COMBO (1UA,10UA,100UA,1MA,10MA) | "1MA" |
| read_irange_drain | wgfmu_fefet.py:73 | CHOICE/COMBO | "100UA" |
| n_pts | wgfmu_fefet.py:66 | INT/SPINBOX min=1 | 5 |
| raw_data_mode | 写死 :493 | CHOICE/COMBO (averaged,raw) | "averaged" |
| t_rf | :61 | FLOAT/DOUBLE_SPINBOX unit=ns(10ns 栅格) | 100e-9 |
| t_read | :64 | FLOAT unit=µs | 5e-6 |
| t_neutral | :65 | FLOAT unit=µs ADVANCED | 100e-6 |
| t_reset | :62 | FLOAT unit=ms ADVANCED | 1e-3 |
| average_s | :460 | 只读派生显示,不入参 | — |
| DC 整族 | 缺失 | 见增量6 | §4.5 |

物理校验借鉴(写进 GUI 校验):10ns 时间栅格(singleStep=10ns 并对齐提示);WGFMU 无真限流(靠选小电流量程,UI 注明);MEASURE_MODE_CURRENT 强制 5V 电压量程联动;±10V 量程 PG 模式不可用。

## 可视化值得抄的 EasyEXPERT 范式
三联显示(X-Y 图 + List 表 + Parameters 标量);Auto Analysis(用户可编辑公式自动提 Vth/MW/SS + 自动画线);Data Status 状态码(C=compliance/V=overflow/X=oscillation 区分脏数据);Setup Summary 一行编码源设定印图底;append/overlay 多达 50 层 + Hold 层。

## 保存路径
输出根目录选择器(默认 ROOT,透传 ExperimentContext.root);run_log.txt(UTF-8 无 BOM);DC BOM `utf-8-sig`→`utf-8`(dc/export.py:81,143);WGFMU 主路径已无 BOM(export.py:38-46 正确);回流项目4(增量6,统一 UTF-8 无 BOM)。EasyEXPERT 蓝本:Workspace→Test Record 两级 + 导出粒度选择 + Preset 导入导出 + Backup/Restore。

## 开放问题决议(2026-06-22,椰椰确认 + claude 默认)
- Q1 单位缩放:**只对 µs/ns/ms/µA/nA 做 spinbox 工程量缩放**,s/V 不缩放(默认)。
- Q2 BOM:**全改 UTF-8 无 BOM**,改前 grep 确认无下游依赖 BOM(默认)。
- Q3 DC 目录:RunBrowser **同时扫两套**,不动 DC 落盘(默认,留增量6)。
- Q4 raw_data_mode:**ADVANCED + "仅限短采样"校验提示**(默认)。
- Q5 measure/operation mode:**本轮锁死 "Fast IV + CURRENT"**,不暴露联动副作用大的旋钮(默认)。
- Q6 实时图:**已实现**——实时 append,跑完用 CSV 重画一遍权威终图。
- Q7 输出根目录默认:**保持 repo 根(现状)**,GUI 加选择器随时可改(椰椰确认 2026-06-22)。
- 节奏:增量1 完成后**椰椰先在测试机看效果再继续**(椰椰确认 2026-06-22)。

## (原始开放问题清单)需要椰椰拍板的开放问题
1. **SI 单位缩放范围**:只对 µs/ns/ms/µA/nA 做 spinbox 工程量缩放(s/V 不缩放)?还是全部走工程记数法(像 EasyEXPERT `1.2345 mA`,更一致但改动大)?
2. **其余 BOM 是否一并修**:增量3 只改 DC 两处;wgfmu/export.py:40-41、iv_sweep.py:238-239、wakeup.py:314-315 也带 BOM——是否一并改成 UTF-8 无 BOM(需确认无下游依赖 BOM)?
3. **DC 目录契约**:DC 现扁平,WGFMU 两级。RunBrowser(增量6)要 DC 改两级同构,还是同时扫两套?
4. **raw_data_mode 暴露层级**:raw 长 retention 会爆 4M 缓存——BASIC 还是 ADVANCED+短采样校验提示?
5. **measure mode/operation mode 是否暴露**:Fast IV vs PG、CURRENT vs VOLTAGE 物理重大但有联动副作用——本轮暴露,还是先锁死"Fast IV + CURRENT"(FeFET 读 Id 标准组合)?
6. **实时图 vs 跑完图**:实时 append 跑完后,用一次性 show_result(从 CSV 重读)覆盖刷一遍(以落盘为准)?建议是。
7. **输出根目录默认值**:默认 = repo 根 ROOT,还是指向某数据盘 / G 盘项目4 路径?数据默认想落哪?

> 完整 file:line 版见本次工作流输出(已并入 05_Handoff)。
