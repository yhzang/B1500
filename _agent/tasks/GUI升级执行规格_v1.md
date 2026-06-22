# B1500 FeFET 上位机 · GUI 升级执行规格 v1

> 来源:2026-06-22 多智能体研究(挖 EasyEXPERT + B1530A 手册 + 审计现有 GUI/ParamSpec)。
> 分支:`gui-upgrade-20260622`(基线 commit `e6dbdee`)。本机不跑 GUI/硬件,只跑纯 Python 单测;真机验证走 scp→测试机 pytest / `python -m gui`。
> **目录契约以代码为准**:现行两级 `runs/<device>/<die>/{live,dry}/<ts>_<stage>`(orchestration/export.py:28-35);设计文档 §6.4/§6.5/§10.4 的旧 `runs/{dry,live}/<ts>_<STAGE>_<dev>` 已过时。

## 增量顺序(按价值/风险)
1. **on_shot 实时增量绘图** ← 第一个赢。链路已全通到 controller,唯一断点 `app.py:_wire()` 没接 PlotPanel。plot_panel 加 `begin_live_plot(schema)`+`append_shot_rows(stage,seq,rows)`(环形缓冲、33ms QTimer 限频、>4000 点降采样、ERS#2659AD/PGM#B80000);app.py `_wire` 接 `c.shot`、`_on_run` 提交后 `begin_live_plot`。风险低。
2. **ParamForm typed 控件 + 单位 + 校验** — 全重写 param_form.py:103-149,按 `ParamSpec.widget` 分 QSpinBox/QDoubleSpinBox(带 SI 单位后缀,collect 还原 SI)/QComboBox/只读 CHANNEL/CSV 校验;非法红框禁运行。风险中(collect SI 还原口径,要加 GUI 单测)。
3. **输出根目录选择 + run_log.txt 落盘 + DC BOM 修复** — run_control_panel 加输出根目录选择器→RunRequest→`ExperimentContext(root=)`(需 wgfmu_fefet._stage_dir:749-758 允许 root 注入);`_on_stage_done` 写 `run_dir/run_log.txt`(UTF-8 无 BOM);dc/export.py:81,143 `utf-8-sig`→`utf-8`。风险低-中。
4. **提升剩余硬编码旋钮**(见下表) — 先 runner 加 flag、再 registry 加 ParamSpec,`pytest tests/test_registry_params.py` 守门。风险中。
5. **可视化进阶** — log 轴(delay_s log-X、Y log|Id|)、手动范围 spinbox+自动缩放、InfiniteLine 游标、Id/Ig 通道显隐、Id_std 误差棒、MW=Id_ERS−Id_PGM 派生线。风险中。
6. **DC 协议族 ParamSpec + RunBrowserPanel**(历史浏览/多 run 叠加/回流项目4) — 最大块,最后做。风险高。

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

## 需要椰椰拍板的开放问题(answers 待填)
1. **SI 单位缩放范围**:只对 µs/ns/ms/µA/nA 做 spinbox 工程量缩放(s/V 不缩放)?还是全部走工程记数法(像 EasyEXPERT `1.2345 mA`,更一致但改动大)?
2. **其余 BOM 是否一并修**:增量3 只改 DC 两处;wgfmu/export.py:40-41、iv_sweep.py:238-239、wakeup.py:314-315 也带 BOM——是否一并改成 UTF-8 无 BOM(需确认无下游依赖 BOM)?
3. **DC 目录契约**:DC 现扁平,WGFMU 两级。RunBrowser(增量6)要 DC 改两级同构,还是同时扫两套?
4. **raw_data_mode 暴露层级**:raw 长 retention 会爆 4M 缓存——BASIC 还是 ADVANCED+短采样校验提示?
5. **measure mode/operation mode 是否暴露**:Fast IV vs PG、CURRENT vs VOLTAGE 物理重大但有联动副作用——本轮暴露,还是先锁死"Fast IV + CURRENT"(FeFET 读 Id 标准组合)?
6. **实时图 vs 跑完图**:实时 append 跑完后,用一次性 show_result(从 CSV 重读)覆盖刷一遍(以落盘为准)?建议是。
7. **输出根目录默认值**:默认 = repo 根 ROOT,还是指向某数据盘 / G 盘项目4 路径?数据默认想落哪?

> 完整 file:line 版见本次工作流输出(已并入 05_Handoff)。
