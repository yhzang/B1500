# B1500 FeFET 上位机(PySide6)架构设计

> 版本 v1.0 / 2026-06-09 / 作者 yhzang
> 落点:`项目3_B1500自动化\B1500\_agent\references\`
> 适用读者:器件物理背景、会 Python、非专业前端。本文给推荐与定论,不罗列开放选项。

---

## 0. 摘要与设计原则

这是**"把已有引擎收口 + 装一张脸"**,不是重写。`scripts/wgfmu_next_round_minimal.py`(1378 行)里真正值钱的是波形/测量原子(`run_e1_shot`/`run_disturb_delay_shot`/`_build_read_phase`/`_configure_and_run_phase`/`_summarize_windows`)、11 个 `STAGE_REGISTRY` 阶段、以及一整套已被真机验证的安全模型(ERRX-drain 预检、`initialize` 每会话一次、`StopGatePolicy`、`validate_live_request`、向量预算护栏)。它们之所以 GUI 调不动,**唯一原因**是签名 `runner(backend, args)` 里的 `args` 是 argparse 产物,把"参数定义/解析/读取"焊死在了 CLI 进程里。

因此本设计的核心动作只有四类,**全程不碰协议物理逻辑**:(1) 把散在四处的参数收口成一个唯一的 `ParamSpec`/`ProtocolSpec` 注册表;(2) 用一层只读视图 `ParamView` 把 `args` 依赖替换掉,让同一个 `run_*` 函数既吃 CLI 的 argparse、也吃 GUI 的 dict;(3) 把会话生命周期与调度从脚本 `main()` 抽进 headless 的 `ProtocolEngine`;(4) 在引擎之上装一个 PySide6 桌面壳。

铁律(贯穿全文):**独立桌面 / 单机单用户 / dry-run 默认**。引擎层零 Qt 依赖、可被 pytest 与 CLI 直接调;硬件调用只在 worker 线程;dry-run 不开 VISA、不加载 DLL;live 一段一确认;所有写 G 盘(回流项目4)的数据一律 UTF-8 无 BOM。本文档同时吸收了评审清单的全部补漏与矛盾修正——凡草稿与真实代码冲突处,**以真实代码为准**(已逐条核验,见各节"代码核验"标注)。

---

## 1. 现状诊断与目标

**为何"乱":参数散在四处,GUI 无从消费。**
1. **模块级全局常量**:`VG_READS`/`VD_READ`/`V_ERS`/`V_PGM`/`T_WRITE`/`DELAYS_QUICK300`/`E2_MINIMAL_COMBOS`/`VG_E5`/`DISTURB_*_DEFAULT`/`CYCLE_CHECKPOINTS_DEFAULT`/`MEAS_IRANGE_GATE`/`MEAS_IRANGE_DRAIN`(脚本第 49–105 行)。
2. **argparse**:`parse_args` 里 60 多个 `--xxx`,混着默认值、help、类型、CSV 解析。
3. **`_resolve_*` 裁决函数**:`_resolve_write_v`/`_resolve_t_write`/`_resolve_vd_read`/`_resolve_s1_vg`,承载"None→论文标称默认"的语义。
4. **stop-gate 阈值**:九个 `--*-ig-stop-uA`,又在 `_build_manifest` 里被手抄一遍。

GUI 没法消费其中任何一处。**收口策略一句话:把"每个协议的参数面"声明成数据(单一事实源 `ProtocolSpec`),让 GUI 表单、CLI argparse、参数校验、manifest 落盘四件事都从它派生;协议物理函数只"搬家 + 换 args 替身",函数体零改动。**

目标产物:一个独立的 PySide6 桌面 exe,yhzang 不写代码就能选协议、填参数、dry-run 预览波形、live 受控测真机、看实时曲线、浏览历史 run、拼自定义脉冲序列,且全程被同一套安全门禁保护。

---

## 2. 总体架构

### 2.1 四层分层

```
┌──────────────────────────────────────────────────────────────────┐
│ GUI 层 (gui/, 依赖 PySide6 + engine)                                │
│   MainWindow / ProtocolPanel / ParamForm / RunControlPanel /        │
│   PlotPanel / LogPanel / RunBrowserPanel / DeviceDialog /           │
│   EngineController(协调) + EngineWorker(子线程, 桥事件→Qt 信号)      │
├──────────────────────────────────────────────────────────────────┤
│ 引擎核心层 (engine/, headless, 零 Qt)                                │
│   specs.py(ParamSpec/ProtocolSpec) / registry*.py(REGISTRY) /       │
│   engine.py(ProtocolEngine.run) / param_view.py(ParamView) /        │
│   backend_manager.py(会话生命周期) / callbacks.py(EngineCallbacks)  │
├──────────────────────────────────────────────────────────────────┤
│ 现有测量层 (protocols/ + measurements/, 物理逻辑零改动)              │
│   protocols/wgfmu_fefet.py(由脚本整体搬入: run_*_shot/run_stage_*/  │
│     _build_read_phase/_summarize_windows/FIELDNAMES/STAGE_REGISTRY) │
│   measurements/dc/(DCSweepAPI) · measurements/wgfmu/(wakeup/iv_sweep)│
│   orchestration/(core.py/export.py: StopGatePolicy/StageSummary 等) │
├──────────────────────────────────────────────────────────────────┤
│ 驱动通信层 (measurements/wgfmu/{audit,real}_backend, dc/visa)       │
│   AuditBackend(dry, 无硬件) ‖ RealWgfmuBackend(live, wgfmu.dll)      │
│   VisaSession(DC) · ensure_wgfmu_dll_path · clear_b1500_status_*    │
└──────────────────────────────────────────────────────────────────┘
```

**关键约束**:`engine/`、`protocols/`、`orchestration/`、`measurements/` 一律不 `import PySide6`。GUI 与引擎之间只通过 `EngineCallbacks` 协议通信。`orchestration/core.py`(`StopGate`/`StopGatePolicy`/`StageSummary`/`StageSpec`/`validate_live_request`)与 `export.py`(落盘契约)**一行不改**,被引擎包装继承。

### 2.2 线程模型: Qt 主线程 ↔ EngineWorker

- **主线程(GUI)**:绝不碰 VISA/DLL,只更新 widget、画图、收发信号。
- **worker 线程(QThread + moveToThread)**:跑 `ProtocolEngine.run(...)`,所有阻塞硬件调用(`execute()`/`wait_until_completed()`/秒级 delay sweep)都在这里。引擎事件通过 `EngineCallbacks` 实现 → 在 worker 线程 `emit` Qt 信号 → Qt 自动 `QueuedConnection` 跨线程投递到主线程槽 → 槽更新 widget。
- **取消 = 协作式,绝不 `QThread.terminate()`**。硬杀线程会让 WGFMU 会话/DLL 处于半开状态,正是引发 `status=-6` 的祸根。Stop 按钮只置标志,引擎在每个 shot / CYCLE chunk 边界查询 `is_cancelled()`,干净收尾(`close_session`)后抛 `StopGate("USER_CANCELLED", ...)`,语义与现有 `KeyboardInterrupt→USER_ABORTED` 一致。

> **代码核验**:`make_backend(live)` 真实返回 `(backend, visa_addr)` 元组,脚本 `main()` 里 `backend, _resource = make_backend(args.live); args._backend_resource = _resource`(第 1349–1350 行)。`runner` 真实调用契约是位置参数二元 `STAGE_REGISTRY[stage].runner(backend, args)`(第 1354 行)。`GATE_CH`/`DRAIN_CH` 是**模块全局**,由 `configure_channel_map(args)` 在 backend 构造前改写,**不是** `AuditBackend(gate_ch=...)` 的构造路径以外的注入。本设计据此把 resource 一并收进 `BackendManager`,并在收口后保留"全局改写"这一条路径(不引入构造注入的第二条路,避免两者并存)。

---

## 3. 引擎核心 (headless)

### 3.1 唯一权威 ParamSpec / ProtocolSpec(收敛五份草稿定义)

> **吸收评审 A1/A2**:五个草稿各写了一份不兼容的 `ParamSpec`(字段名 `name` vs `key`、`min/max` vs `minimum/maximum`、`kind` 枚举 vs 字符串、锁定语义 `editable` vs `visibility` vs `U/A/L`)和两个落点(`engine/registry.py` vs `orchestration/catalog.py`)。**本节定为唯一权威,其余维度一律消费它。** 落点定为 `engine/specs.py`(纯数据,零仪器/零 Qt)。

```python
# src/fefetlab/engine/specs.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

class ParamKind(Enum):
    FLOAT="float"; INT="int"; BOOL="bool"
    FLOAT_LIST="float_list"   # 对应 _parse_float_list_csv
    INT_LIST="int_list"       # 对应 cycle checkpoints
    CHOICE="choice"

class Visibility(Enum):
    BASIC="basic"             # U: 用户日常可设,主面板直接显示
    ADVANCED="advanced"       # A: 高级默认,藏在"显示高级"折叠里
    LOCKED="locked"           # L: 锁定-安全,只读灰显或需二次确认

class Widget(Enum):
    DOUBLE_SPINBOX="double_spinbox"; SPINBOX="spinbox"
    CHECKBOX="checkbox"; CSV_LINE="csv_line"; COMBO="combo"; CHANNEL="channel"

@dataclass(frozen=True)
class ParamSpec:
    name: str                       # 唯一权威键名(蛇形): "vd_read"/"e1_ig_stop_uA"。== 引擎接收键 == argparse dest
    label: str                      # 中文显示名:"读出 Vd"
    kind: ParamKind
    default: Any
    unit: str = ""                  # "V"/"s"/"µA";GUI 按 unit 做 SI 缩放(µs↔1e-6)
    visibility: Visibility = Visibility.BASIC   # 三档,取代草稿的 editable 布尔与 U/A/L 字符串
    minimum: float | None = None    # 统一用 minimum/maximum(非 min/max)
    maximum: float | None = None
    choices: tuple[Any, ...] | None = None
    widget: Widget = Widget.DOUBLE_SPINBOX
    cli_flag: str | None = None     # "--vd-read";None=不暴露给 CLI
    device_overridable: bool = False  # pFeFET/nFeFET 是否分别给默认(并入维度4)
    depends_on: str | None = None
    help: str = ""

    @property
    def editable(self) -> bool:     # 兼容读法:LOCKED 即不可编辑
        return self.visibility is not Visibility.LOCKED

@dataclass(frozen=True)
class PlotHint:
    schema: str        # "fefet_fixedcols" | "iv_sweep" | "dc" | "wakeup_cycles"
    kind: str          # "mw_vs_delay" | "mw_vs_cycle" | "id_vg" | "ref_vs_disturb" ...
    x: str; y: str     # CSV 列名:x="delay_s", y="Id_mean_A"
    group_by: str = "" # "state_target"

@dataclass(frozen=True)
class ProtocolSpec:
    id: str                         # 阶段码 "E1"/"E6D"/"DC_IDVG"/"WAKEUP"/"CUSTOM"
    title: str                      # "RAWD 写后延迟读"
    family: str                     # "WGFMU" | "SMU" | "WGFMU_WAKEUP"
    physics: str                    # "retention" | "read-disturb" | "imprint" | ...
    description: str
    params: tuple[ParamSpec, ...]
    stop_gate: "StopGatePolicy | None"      # 直接复用 orchestration.core.StopGatePolicy
    csv_schema: str                 # "fefet_fixedcols"(FIELDNAMES)/"dc"/"iv_sweep"/"wakeup_cycles"
    requires: tuple[str, ...] = ()  # 门禁链:期望已完成的上游 report_code(并入维度4)
    family_defaults: dict = field(default_factory=dict)  # {"pFeFET":{...},"nFeFET":{...}} 仅差异项
    plot_hints: tuple[PlotHint, ...] = ()
    note: str = ""                  # 如 "pFeFET 建议先唤醒"
    runner: Callable[..., "StageSummary"] = None   # 适配后的 run_stage_*
```

**字段对照(旧来源 → ParamSpec)**:argparse 的 `type`/`default`/`help` → `kind`/`default`/`help`;`_resolve_*` 的"None 回退全局"裁决 → `default` 直接写成论文标称值,runner 内 `_resolve_*` 原样保留(`ParamView` 把 dict 转回它期望的形态);九个 `--*-ig-stop-uA` → 每协议一个 `ParamSpec` + `stop_gate` 两者保持一致,且 manifest 不再手抄,改为遍历 spec.params 生成。

`ProtocolSpec` 是旧 `StageSpec`(四元组 `name/output_label/description/runner`)的**超集**,迁移期提供 `as_stage_spec()` 兼容属性给仍引用 `StageSpec` 的旧代码,逐步退役。

### 3.2 注册表一次驱动四件事

```python
# src/fefetlab/engine/registry.py
REGISTRY: dict[str, ProtocolSpec] = {p.id: p for p in (
    S0, S1, E1, E2, E3W, E3A, E4, E5, E6R, E6D, CYCLE,   # WGFMU(11 阶段)
    RET, WAKEUP, PHYS,                                   # WGFMU 补全(§7)
    DC_IDVG, DC_IDVD, DC_CUSTOM,                         # SMU
    CUSTOM,                                              # 自定义协议(§8)
)}
```

- **GUI 表单**:遍历 `REGISTRY[id].params`,按 `kind`/`widget`/`minimum`/`maximum`/`unit`/`visibility` 生成控件。
- **CLI argparse**:`build_argparser(REGISTRY)` 遍历所有有 `cli_flag` 的 param 自动 `add_argument`,取代手写 60 行。
- **校验**:`validate_params(spec, params)` 按 `minimum/maximum/choices/kind` 检查,越界抛 `StopGate("SETUP_STOP_PARAM_OUT_OF_RANGE_...")`。**并入评审 D3**:`validate_params` 同时强制"`LOCKED` 字段不得来自外部 params(GUI/Profile/CLI 越权传入即拒)",这样 CLI 薄壳 `vars(args)` 喂 `run` 时也绕不过——过滤下沉到引擎层,GUI/CLI 共用。
- **manifest**:`manifest["params"] = {p.name: params[p.name] for p in spec.params}`,自动覆盖旧 `wgfmu_effective`/`stop_gates_uA`,不再手抄。

### 3.3 统一 run 接口

```python
# src/fefetlab/engine/engine.py  —— 纯 Python,零 Qt
class RunMode(Enum):
    DRY="dry"; LIVE="live"

class ProtocolEngine:
    def run(self, protocol_id: str, params: dict, mode: RunMode,
            callbacks: "EngineCallbacks", confirm: str = "") -> StageSummary:
        spec = REGISTRY[protocol_id]
        validate_params(spec, params)                          # 含 LOCKED 越权拒绝
        validate_live_request(protocol_id, mode is RunMode.LIVE, confirm)  # 原样复用 core.py
        with BackendManager(mode, callbacks) as bm:            # 会话生命周期(§3.5)
            view = ParamView(spec, params, backend_resource=bm.resource, live=mode is RunMode.LIVE)
            try:
                summary = spec.runner(bm.backend, view, callbacks=callbacks)
                callbacks.on_stage_done(summary, run_dir=summary.out_csv.parent)
                return summary
            except StopGate as e:
                callbacks.on_stop_gate(e.code, str(e), recoverable=_is_recoverable(e))
                raise
```

GUI 和 CLI 都只调这一个 `run`。它等于把脚本 `main()`(第 1324–1371 行)拆出来,把"验证→建会话→跑→收尾"收口在一处,**任何调用方都绕不过** `validate_params` 和 `validate_live_request`。

### 3.4 ParamView:让 run_stage_* 脱离 args 而函数体零改动

`run_stage_e1` 内部到处是 `args.e1_reps`/`args.device_id`/`args.seed`/`_resolve_write_v(state, args)`。最低风险做法不是改函数体,而是造一个 dict 后端的只读命名空间替身,让 `getattr(args, "e1_reps")` 照常命中。

> **吸收评审 C3**:草稿的 `__getattr__` 直接 `return self._d[k]` 会在 `_d` 未就绪时递归。**修正**:`_d` 用 `object.__setattr__` 写入,`__getattr__` 用 `object.__getattribute__` 取 `_d`,并对 `_d` 自身短路。

```python
# src/fefetlab/engine/param_view.py
class ParamView:
    """只读视图:让 run_stage_*(backend, args) 里所有 args.xxx 命中 dict。
    既不改协议逻辑,也不改 _resolve_* / _build_manifest / _stage_dir。"""
    def __init__(self, spec, params, *, backend_resource, live,
                 device_id="", geometry="", seed=20260522):
        merged = {p.name: params.get(p.name, p.default) for p in spec.params}
        merged.update(device_id=device_id or params.get("device_id", ""),
                      geometry=geometry or params.get("geometry", ""),
                      live=live, seed=params.get("seed", seed),
                      gate_ch=GATE_CH, drain_ch=DRAIN_CH,        # 来自模块全局
                      _backend_resource=backend_resource, _argv=[])
        object.__setattr__(self, "_d", merged)
    def __getattr__(self, k):
        if k == "_d":
            raise AttributeError(k)
        d = object.__getattribute__(self, "_d")
        try: return d[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self, k, v):
        object.__getattribute__(self, "_d")[k] = v
```

`run_stage_e1(backend, ParamView(...))` 一行不改地跑通,`_resolve_write_v`/`_build_manifest`/`_stage_dir` 全部继续工作。

### 3.5 backend 与会话生命周期

`make_backend` + `_ensure_wgfmu_initialized` + `_is_wgfmu_session_error` + `_reopen_wgfmu_session` + `_validate_channels` 整体搬进 `engine/backend_manager.py`,对外是上下文管理器,**必须持有并暴露 resource**(评审 A5:草稿都丢了 resource,而它要写 manifest、给 FIX B 恢复用)。

```python
# src/fefetlab/engine/backend_manager.py
class BackendManager:
    def __init__(self, mode: RunMode, cb: EngineCallbacks): ...
    def __enter__(self) -> "BackendManager":
        # = 旧 make_backend:dry→AuditBackend(无 VISA/无 DLL);
        #   live→ensure_wgfmu_dll_path → clear_b1500_status_for_wgfmu_open(ERRX drain,不发 *CLS/*RST)
        #        → open_session → 记 _fefet_visa_addr/_fefet_wgfmu_initialized=False → _validate_channels
        self.backend, self.resource = _make_backend_impl(self.mode, self._cb)   # 返回元组,resource 暴露为属性
        return self
    def __exit__(self, *exc):
        try: self.backend.close_session()
        except Exception: pass
    def ensure_initialized(self, force=False): ...          # = _ensure_wgfmu_initialized
    def recover_session(self):                              # = _reopen_wgfmu_session(self.backend)
        _reopen_wgfmu_session(self.backend)                 # 只收 backend 一个参数,resource 自带在 backend._fefet_visa_addr
```

- **DC 侧对称**:live 时 `BackendManager` 的 DC 分支开 `VisaSession` + 构造 `DCSweepAPI(session, ch_g=4, ch_d=5, ch_s=6)`(SMU 角色铁律)。**吸收评审 C6**:`DCSweepAPI` 构造即 `B1500(session)`,**当前没有 hardware-free 路径**。M2 阶段 DC 的 dry-run 由一个 mock `VisaSession`(返回合法格式的假读数)提供;在该 mock 落地前,文档明确标注 **DC 卡片的 dry-run 预览能力依赖 mock session,M2 必须交付,否则 DC 仅 live**。
- **initialize 每会话一次**铁律由 `BackendManager.ensure_initialized` 守护(沿用 `_fefet_wgfmu_initialized` 标志);GUI 多次跑不同段复用同一已 init 会话,绝不每段 re-init(否则 ~146 次后 `status=-6`)。

> **代码核验**:`_ensure_wgfmu_initialized` 注释已写明 root cause——`WGFMU_initialize` 每会话调一次,旧流程每 phase/chunk 调一次(~146x/1e5 disturb)导致 `status=-6`。`_reopen_wgfmu_session(backend)` 只收 backend,靠 `backend._fefet_visa_addr` 自带 resource(脚本第 358 行)。

### 3.6 事件回调契约(收敛三份签名)

> **吸收评审 A3**:三份草稿的事件契约互斥(维度1 `EngineCallbacks` 对象式 + 维度2 `EngineWorker` 信号多出 4 个无对应回调的 + 维度5 `RunObserver` 注入方式不同)。**本节定为唯一权威**:对象式 `EngineCallbacks`,合并三方方法全集。

```python
# src/fefetlab/engine/callbacks.py
from typing import Protocol, Mapping
class EngineCallbacks(Protocol):
    def on_progress(self, done: int, total: int) -> None: ...
    def on_plan_ready(self, gate_xy, drain_xy, vectors_seen: int) -> None: ...   # dry 编程波形(维度2)
    def on_preflight_step(self, name: str, ok: bool, detail: str) -> None: ...   # ERRX/通道/接线(维度2)
    def on_shot(self, stage: str, seq: int, rows: list[Mapping]) -> None: ...    # 每个 run_*_shot 返回后
    def on_safety_metric(self, max_abs_ig: float, threshold: float) -> None: ... # 实时 |Ig| 预警(维度2)
    def on_log(self, level: str, code: str, msg: str) -> None: ...               # 带 code(维度5)
    def on_stage_done(self, summary: "StageSummary", run_dir) -> None: ...        # 带 run_dir(维度5)
    def on_stop_gate(self, code: str, msg: str, recoverable: bool) -> None: ...   # recoverable 区分可恢复(评审 B5)
    def on_error(self, exc: BaseException, recoverable: bool) -> None: ...
    def is_cancelled(self) -> bool: ...
```

**runner 注入约定(唯一)**:`run_stage_*(backend, view, *, callbacks=None)`——加一个可选 keyword `callbacks=None`,向后兼容(CLI 不传也能跑)。`ParamView` 不再持有回调引用(避免维度1 的 `_callbacks` 持有与维度2/5 的 `observer=` 形参两套并存)。

**兼容现有 print 出口**:`CliCallbacks` 实现里 `on_shot`→`print("SHOT_OK: ...")`、`on_stage_done`→ `summarize_rows` 三行 print、`on_stop_gate`→`print("REPORT_CODE:")+print("STOP_GATE:")`,**老脚本输出文本完全不变**,现有 runbook/解析向后兼容。`GuiCallbacks`(在 gui/ 包)实现里每个方法 `emit` 对应 Qt 信号。

**StopGate 事件化**:`StopGate(code, message)` 原样抛出,`engine.run` 捕获后调 `on_stop_gate` 再 re-raise。`recoverable` 由 `_is_recoverable(exc)` 判定(`status=-6` 类→可恢复,其余→致命),GUI 据此决定弹"可点恢复会话"还是"致命"(评审 B5)。

### 3.7 CLI 收编为薄壳

```python
# scripts/wgfmu_next_round_minimal.py  (收口后约 30 行,保留路径与 CLI 兼容)
from fefetlab.engine import ProtocolEngine, REGISTRY, build_argparser, RunMode
from fefetlab.engine.callbacks import CliCallbacks
from fefetlab.orchestration import StopGate

def main(argv=None) -> int:
    ap = build_argparser(REGISTRY)
    args = ap.parse_args(argv)
    if args.stage == "PLAN":
        print_plan(REGISTRY, vars(args)); print("REPORT_CODE: PLAN_ONLY_NO_HARDWARE"); return 0
    mode = RunMode.LIVE if args.live else RunMode.DRY
    try:
        ProtocolEngine().run(args.stage, vars(args), mode, CliCallbacks(), confirm=args.confirm)
        return 0
    except StopGate:
        return 20   # CliCallbacks 已 print REPORT_CODE/STOP_GATE
```

### 3.8 模块落点

> **吸收评审 A6**:三份草稿对收口文件名不一致(`protocols/wgfmu_fefet.py` vs `protocols/fefet_wgfmu.py` vs `orchestration/custom_protocol.py`)。**唯一权威落点如下:**

```
src/fefetlab/
  engine/                       ← 新增,零 Qt
    specs.py registry.py registry_wgfmu.py registry_dc.py registry_extra.py
    engine.py param_view.py backend_manager.py callbacks.py
  protocols/
    wgfmu_fefet.py              ← 脚本整体搬入(run_*_shot/run_stage_*/_build_read_phase/
                                  _configure_and_run_phase/_summarize_windows/FIELDNAMES/STAGE_REGISTRY)
    custom_protocol.py          ← CustomProtocolSpec/expand_custom_shot/run_stage_custom(§8)
  orchestration/                ← 不动(core.py/export.py/__init__.py)
  measurements/dc, measurements/wgfmu  ← 不动
gui/                            ← 依赖 Qt + engine
scripts/wgfmu_next_round_minimal.py  ← 退化为薄壳
```

第一步搬家后删掉脚本顶部 `sys.path.insert`,模块常量/函数原样保留;`--stage ALL_DRY` 的 `DRY_RUN_AUDIT: execute_count=96 max_vectors_seen=640` 必须与 State 记录一致(字节级回归护栏)。

---

## 4. 参数分类总表

三级口径(对齐 §3.1 `Visibility`):**U=BASIC(用户日常)/ A=ADVANCED(高级默认)/ L=LOCKED(锁定-安全)**。判据:U 改它不破安全不变量且是实验自变量;A 有合理默认、是方法学/复现旋钮;L 是物理/接线/会话铁律,错值会烧器件/打错通道/会话死锁,GUI 只读或需二次确认+审计。

### 4.1 GLOBAL(运行身份)

| 字段 | 来源 | 含义 | 默认 | 范围 | 级 |
|---|---|---|---|---|---|
| device_id | `--device-id` | 器件标识,进 CSV/manifest/目录 | `L40W10_01` | 任意(`_slug` 清洗) | U |
| geometry | `--geometry` | 沟道几何,驱动 `_device_family` | `L40W10` | L10*/L20*/L40* | U |
| device_family | manifest `device_family` | pFeFET/nFeFET,覆盖读 Vg 网格 | pFeFET | {pFeFET,nFeFET} | U |
| stage | `--stage` | 选协议段 | `PLAN` | 见 REGISTRY | U |
| live | `--live` | 是否打真机 | `False` | T/F | **L** |
| confirm | `--confirm` | live 确认串,须 == stage | `""` | == stage | **L** |
| seed | `--seed` | 随机化/复现种子 | `20260522` | int | A |

### 4.2 CHANNEL(接线)— 多为 L

| 字段 | 来源 | 默认 | 范围 | 级 | 锁定理由 |
|---|---|---|---|---|---|
| WGFMU Gate 通道 | `--gate-ch`/`DEFAULT_GATE_CH` | 202 | {201,202,301} | **L** | 接线铁律;改=改物理接线,须二次确认+审计 |
| WGFMU Drain 通道 | `--drain-ch`/`DEFAULT_DRAIN_CH` | 201 | {201,202,301} | **L** | `gate==drain`→`SETUP_STOP_BAD_CHANNEL` |
| 允许通道集 | `--allowed-channels` | {201,202,301} | 子集 | A | 换夹具才动 |
| 禁用通道集 | `--forbidden-channels` | {302} | 含 302 | **L** | CH302 无 RSU;不允许移除 302 |
| SMU 角色 G/D/S/spare | `channel_map.yaml:role_map` | 4/5/6/7 | {4,5,6,7} | **L** | DC 接线铁律 |

GUI 体现:整族放"接线档案"只读卡片,顶部状态灯 `Gate=202 ✓ Drain=201 ✓ CH302 forbidden ✓`;改 Gate/Drain 须点"我已确认重新接线"才解锁;校验复用 `configure_channel_map()` / `_validate_channels`。

### 4.3 WGFMU-COMMON(写脉冲/读窗,跨段共享)

| 字段 | 来源 | 含义 | 单位 | 默认 | 范围 | 级 |
|---|---|---|---|---|---|---|
| write_v | `--write-v`→`_resolve_write_v`(覆盖 V_ERS=+5/V_PGM=-5) | 写幅值,ERS=+/PGM=− | V | ±5.0 | 0–6 软上限 | U |
| t_write_s | `--t-write-s`→`_resolve_t_write`(覆盖 T_WRITE) | 写脉宽平顶 | s | 100e-6 | 1e-6–1e-3 | U |
| vd_read | `--vd-read`→`_resolve_vd_read`(覆盖 VD_READ) | 读相漏压 | V | 0.05 | 0.02–0.2 | U |
| s1_vg | `--s1-vg`→`_resolve_s1_vg`(覆盖 VG_READS) | 只读 Vg 点 | V | [-0.2,0,0.2] | 逗号列表 | U |
| t_rf_s | `T_RF` | 脉冲上升/下降沿(写脉冲&读窗共用;读窗内现写死 T_RF,见 §4.6/B7) | s | 100e-9 | 50e-9–1e-6 | A |
| t_reset_s | `T_RESET` | 写前归零 | s | 1e-3 | — | A |
| t_read_s | `T_READ` | 单次读保持时长(决定读窗采样宽度) | s | 5e-6 | — | A |
| t_neutral_s | `T_NEUTRAL` | 读相前缀 | s | 100e-6 | — | A |
| n_pts | `N_PTS` | 每读窗采样点数(软件取均值→ Id_mean±Id_std,见 §4.6) | 个 | 5 | 1–200(常用≤20) | A |
| raw_data_mode | `set_measure_event` 第7参(现写死) | 读出取点模式 averaged/raw(见 §4.6) | enum | `averaged` | {averaged,raw} | A |
| irange_gate | `MEAS_IRANGE_GATE` | 栅极读电流量程 | enum | `1MA` | 见 §4.6 | A |
| irange_drain | `MEAS_IRANGE_DRAIN` | 漏极读电流量程 | enum | `100UA`(2026-06-04 下调) | 见 §4.6 | A |

### 4.4 WGFMU-STAGE(各段专属)

`*_reps` 与列表参数为 U;`*_ig_stop_uA` 阈值为 A(阈值可调,**门本身不可摘**);`*_wide_vg`/`*_randomize` 为 A。

| 段 | 用户名 | 关键 U 参数 | 默认 | stop |Ig|(A) |
|---|---|---|---|---|
| S0 | 空夹具 smoke | s0_reps=5, s1_vg, vd_read | — | s0_ig_stop_uA=5.0 |
| S1 | 器件 baseline | s1_reps=20 | — | s1_ig_stop_uA=5.0 |
| E1 | RAWD 写后延迟读 | e1_reps=3, e1_full_delays(到10s), e1_wide_vg | delays=DELAYS_QUICK300 | e1_ig_stop_uA=20.0 |
| E2 | 读扰动 minimal | e2_reps=2(combos=E2_MINIMAL_COMBOS,跳C100) | 固定8组 | e2_ig_stop_uA=20.0 |
| E3W | 脉宽扫描 | e3_reps=3, widths(=E3_WIDTHS) | 1µs→300µs | e3_ig_stop_uA=30.0 |
| E3A | 幅值扫描 | e3_reps=3, amps(=E3_AMPS) | 3/4/5V | e3_ig_stop_uA=30.0 |
| E4 | imprint 预偏压 | e4_reps=3, prebias_v(=E4_PREBIAS_V), prebias_s | [0,±2]V × [1ms,100ms,1s] | e4_ig_stop_uA=30.0 |
| E5 | Vg×Vd 窗格 | e5_reps=3, vg(=VG_E5 含-1.0), vd(=VD_E5), delays(=DELAYS_E5) | — | e5_ig_stop_uA=20.0 |
| E6R | 无扰动参考 | e6r_reps=3, e6d_delays, e6d_wide_vg | DISTURB_DELAYS_DEFAULT | e6r_ig_stop_uA=20.0 |
| E6D | 半Vdd反极性扰动 | e6d_reps=3, e6d_amps(=[2.5]), e6d_delays, e6d_width_s | width=100µs | e6d_ig_stop_uA=30.0 |
| CYCLE | 检查点耐久 | cycle_count=1e5, cycle_checkpoints, cycle_wide_vg | checkpoints=[10..1e5] | cycle_ig_stop_uA=30.0 |

E6D 扰动极性 `_opposite_disturb_voltage`(ERS→−/PGM→+)为 **L(只读)**:反极性是实验定义,不让 UI 翻号以免误烧。CYCLE 的 `CYCLE_STRESS_VECTOR_GUARD=128` / `WGFMU_MAX_VECTORS_PER_PATTERN=2048` 为 **L(只读)**:向量预算,内核自动分块。

### 4.5 SMU/DC(来源 `DCSweepConfig` + `DCSweepAPI`)

| 字段 | 来源 | 含义 | 默认 | 级 |
|---|---|---|---|---|
| vg_points | `run_*_sweep(vg_points=)` | 栅压点 | — | U |
| vd_fixed/vd_points | `vd_fixed`/`vd_points` | 漏压 | — | U |
| vs_fixed | `vs_fixed` | 源压 | 0.0 | U |
| i_comp(compliance) | `DCChannelConfig.compliance` | 限流保护 | 1e-3 | U(调高=放宽保护,>1mA 弹提醒;调低永远安全) |
| 通道 G/D/S | `DCChannelConfig.channel` | SMU 物理通道 | 4/5/6 | **L** |
| vrange | `DCChannelConfig.vrange` | 0=自动量程 | 0 | A |
| delay_s | `delay_s` | 设压后测量延时 | 0.2 | A |
| fmt_mode | `fmt_mode` | 1=12位/5=13位 | 5 | A |
| av_mode/av_count | `av_mode`/`av_count` | ADC 平均模式/次数 | 1/10 | A |
| fl_mode | `fl_mode` | 1=滤波 ON | 1 | A |

### 4.6 量程与读窗(高风险 A)

**电流量程**(合法 enum 来自 `real_backend.py:MEASURE_CURRENT_RANGE_MAP`):合法值**只有** `1UA/10UA/100UA/1MA/10MA`(对应 6001–6005),GUI 必用**下拉枚举**,杜绝非法字符串。选小了→过载/饱和;选大了→分辨率丢失。默认 Gate=1MA(保守防过载)、Drain=100µA(µA 级分辨率)。选 `10MA` 时弹"超量程档,确认器件确实有 mA 级电流"提醒。值经 `_configure_and_run_phase` 的 `set_measure_current_range(ch, MEAS_IRANGE_GATE if ch==GATE else MEAS_IRANGE_DRAIN)` 下发。

**读出是两级平均**(对应"一次读是几个点的平均"):`_build_read_phase` 在每个读窗里取 `n_pts` 个点,**软件层** `_summarize_windows` 把它们取均值落 `Id_mean_A`、标准差落 `Id_std_A`(std 即免费的读出噪声指标);而**硬件层**每个点本身是 WGFMU 在 `average_s`(≈200ns 孔径)内的平均(`set_measure_event` 的 `"averaged"` 模式)。即:**一次读 = n_pts 个点的均值,每个点又是 average_s 窗口内的硬件平均**。默认值代入:`t_read=5µs, n_pts=5 → guard=200ns, meas_window=4.8µs, interval=960ns, average_s=200ns`,即 5µs 读保持内取 5 个点、每点平均 200ns。

**暴露 vs 派生(原则:给语义旋钮,锁耦合量)**:
- **暴露(A,用户可调)**:`n_pts`(点数/统计)、`t_read_s`(读保持)、`raw_data_mode`(averaged/raw)、`t_rf_s`(沿)。
- **派生/锁定(只显示计算值)**:`interval=meas_window/n_pts`、`average_s=min(200ns, interval*0.8)`、`guard`、点间 `gap`。**原因**:`set_measure_event` 有硬约束 `average_s < interval_s`(违反即报错),所以 `average_s/interval` **不让裸调**,由 `n_pts`/`t_read` 推出并显示。
- **新决策——`raw_data_mode` 改为可选切换(默认 `averaged`)**:主力实验 E1 **RAWD(写后延迟读)** 关心的是读出电流随时间的弛豫**瞬态**,`raw` 模式吐出 n_pts 个原始点的时间序列(看衰减形状),`averaged` 抹平噪声出稳态点。代价:切 `raw` 时 QC/stop-gate 阈值需重调(历史笔记已记此坑)。默认仍 `averaged`,协议/配方可选 `raw`。

GUI 实时显示"本段估算向量数 / 2048",超预算禁止 live。

> **吸收评审 B7(阻塞前置)**:`MEAS_IRANGE_GATE/DRAIN`(注释承诺 `--read-irange-*` 但**代码未实现**,实测确为模块全局无 argparse)、`E3_WIDTHS/E3_AMPS/E4_PREBIAS_V/S/VG_E5/VD_E5/DELAYS_E5/N_PTS/T_RF/T_READ` 全是硬编码;读窗 `_build_read_phase` 另把沿(`T_RF`)、`average_s`、`raw_data_mode="averaged"` 写死,M1 一并提升:沿/读保持/取点模式(averaged↔raw)做成可设入参,`average_s` 仍由 `n_pts`/`t_read` 派生。E3/E4/E5 卡片与表单全依赖它们可设。**"把模块常量提升为 ParamSpec/入参"是 M1 的阻塞前置任务,不是可选优化**——建议派给 Codex 做批量重构。在它落地前,E3W/E3A/E4/E5 在 GUI 里只能显示不能改。

### 4.7 协议预设 Profile(两级默认)

```
有效值 = run_override(本次填的)  if 非空
        else profile_default(命名预设)
        else module_global(V_ERS/V_PGM/T_WRITE/VD_READ/VG_READS… 论文标称兜底)
```

这正是 `_resolve_write_v` 的语义。Profile 存 `configs/profiles/*.json`(**UTF-8 无 BOM**),结构与 `RunRequest` 同构:`{stage, params, device_id, geometry, device_family}`。**Profile 不得含 L 字段**(gate_ch/drain_ch/forbidden/live/confirm),该过滤下沉到 `validate_params`(评审 D3),GUI 与 CLI 共用。内置预设:「标准RAWD QUICK300」「宽栅pFeFET(含-1.0V,write ±5)」「耐久10万次」「读扰动minimal」。`RunBrowserPanel` 提供"从历史 run 的 manifest 反建预设",闭环 `_build_manifest`。

---

## 5. GUI 设计

### 5.1 窗口布局(线框图)

**结论:单 `QMainWindow` + 中央 `QSplitter` 三栏,左栏内 `QTabWidget` 区分协议套件,绘图/日志/run浏览用 `QDockWidget` 停靠。** 不用纯 tab 顶层(割裂"边跑边看波形/日志"),不用全 dock(单人本机固定布局更稳)。dock 可拉大全屏看曲线、临时收起日志,布局状态用 `QSettings` 持久化。

```
┌───────────────────────────────────────────────────────────────────────────┐
│ 菜单: 文件  设备  视图  预设  帮助        [● 已连接 GPIB1::17 IDN✓] 器件:pFeFET│
├──────────────────────┬────────────────────────────┬─────────────────────────┤
│ ProtocolPanel        │ RunControlPanel            │  (dock) PlotDock        │
│ [WGFMU][DC][自定义]   │ 模式: ( )dry-run ●live      │ [编程波形][实时结果]     │
│  S0 空夹具 smoke      │ device_id: L40W10_01        │  上 Vg(t)/Vd(t) 波形    │
│  S1 只读 baseline     │ geometry : L40W10           │  下 Id/Ig vs delay/cycle│
│  E1 RAWD写后读 ◀选中  │ ── 预检 ──────────────       │                         │
│  E2 read-disturb      │ [✓]ERRX drain               ├─────────────────────────┤
│  E3W/E3A 脉宽/幅值    │ [✓]通道 G=202 D=201          │  (dock) RunBrowserDock  │
│  E4 imprint           │ [!]CH302 无RSU(禁用)         │ runs/dry  runs/live     │
│  E5 Vg×Vd 窗格        │ ──────────────────           │ 20260522_..S0_OPEN ...  │
│  E6R/E6D 扰动参考     │  进度 ▓▓▓▓░░ 23/48           │  └report_code: S0_..    │
│  CYCLE 耐久           │  当前 |Ig|=3.1µA(门5µA)      │  └[打开CSV][载入绘图]   │
│  RET 长保持/WAKEUP    │  ┌────────┐ ┌─────────┐      │  └[反建预设][多run对比] │
│  PHYS 脉冲迟滞        │  │ ▶ 运行  │ │ ■ 停止  │      ├─────────────────────────┤
│ ─────────────────     │  └────────┘ └─────────┘      │  (dock) LogDock         │
│ ParamForm(自动生成):  │  [恢复会话](status=-6 时亮)   │ 17:46 ERRX drain OK     │
│  写电压 ±5.0 V        └────────────────────────────┘ │ 17:46 STOP_GATE ...🔴   │
│  写脉宽 100 µs  [高级▸]                               │ [✓INFO][✓WARN][✓STOP]   │
└──────────────────────┴────────────────────────────┴─────────────────────────┘
```

### 5.2 类划分

| 类 | 线程 | Qt? | 职责 |
|---|---|---|---|
| `MainWindow(QMainWindow)` | GUI | 是 | 组装 panel/dock,菜单,`QSettings` 布局持久化 |
| `ProtocolPanel(QWidget)` | GUI | 是 | 协议树(节点=REGISTRY 条目)+ 托管 ParamForm;发 `protocolSelected(id)` |
| `ParamForm(QWidget)` | GUI | 是 | 按 ParamSpec 自动渲染控件,即时校验,产出 `dict[str,Any]` |
| `RunControlPanel(QWidget)` | GUI | 是 | dry/live 开关、设备身份、预检清单、进度、安全指标、运行/停止/恢复 |
| `PlotPanel(QWidget)` | GUI | 是 | pyqtgraph;`update_waveform(plan)`/`append_result_rows(rows)` |
| `LogPanel(QWidget)` | GUI | 是 | 追加结构化日志,分级过滤,STOP/ERROR 着色 |
| `RunBrowserPanel(QWidget)` | GUI | 是 | 扫 `runs/`,读 manifest/report_code,离线绘图,多 run 对比 |
| `EngineController(QObject)` | GUI | 是 | 唯一协调者:收集 `RunRequest`→启 `EngineWorker`→转接信号到各 panel |
| `EngineWorker(QObject)` | **worker** | 仅 Signal | 子线程跑 `ProtocolEngine.run`;实现 `GuiCallbacks` 把事件 emit 成 Qt 信号;**不碰 widget** |
| `DeviceSessionManager(QObject)` | GUI | 是 | 持有 backend 句柄 + resource + 连接状态/IDN + 会话恢复 |

`RunRequest`(纯数据,跨线程传值):

```python
@dataclass(frozen=True)
class RunRequest:
    stage: str; params: dict; live: bool; confirm: str
    device_id: str; geometry: str; device_family: str
```

### 5.3 信号槽 / 线程

`EngineWorker` 信号集与 §3.6 `EngineCallbacks` 一一对应(`GuiCallbacks.on_xxx → self.sig_xxx.emit(...)`),不再多发无对应回调的信号:

```python
class EngineWorker(QObject):
    progress = Signal(int, int)
    planReady = Signal(object, object, int)     # gate_xy, drain_xy, vectors_seen
    preflightStep = Signal(str, bool, str)
    shot = Signal(str, int, object)
    safetyMetric = Signal(float, float)
    log = Signal(str, str, str)                 # level, code, msg
    stageDone = Signal(object, object)          # StageSummary, run_dir
    stopGate = Signal(str, str, bool)           # code, msg, recoverable
    error = Signal(object, bool)
    finished = Signal()

    def __init__(self, req: RunRequest, session: DeviceSessionManager):
        super().__init__(); self._req = req; self._session = session; self._cancel = False

    @Slot()
    def run(self):
        cb = GuiCallbacks(self)                 # 实现 EngineCallbacks
        cb._is_cancelled = lambda: self._cancel
        try:
            ProtocolEngine().run(self._req.stage, self._req.params,
                                 RunMode.LIVE if self._req.live else RunMode.DRY,
                                 cb, confirm=self._req.confirm)
        except StopGate:
            pass    # cb.on_stop_gate 已 emit
        except Exception as e:
            self.error.emit(e, False)
        finally:
            self.finished.emit()

    @Slot()
    def request_stop(self):
        self._cancel = True    # 仅置标志,引擎在 shot/chunk 边界落停
```

连接(`EngineController.start_run`):`worker.moveToThread(thread)` → `thread.started.connect(worker.run)` → 各信号 `connect` 到对应 panel 槽(`QueuedConnection` 自动跨线程)→ `worker.finished.connect(thread.quit)`。主线程绝不卡。

### 5.4 参数表单自动生成

`ParamForm` 是通用渲染器,按 `ParamSpec.kind` 映射控件,**不为每个协议手写表单**:

| kind | 控件 | 约束 |
|---|---|---|
| FLOAT | QDoubleSpinBox(单位后缀,内部 SI 缩放) | `setRange(min,max)` |
| INT | QSpinBox | reps≥1 |
| CHOICE | QComboBox | choices(如量程枚举) |
| FLOAT_LIST/INT_LIST | ListEditWidget(逗号文本框,等价 `_parse_float_list_csv`) | 解析失败红框,空回落 default |
| CHANNEL | ChannelComboBox(`ALLOWED_CHANNELS` 减 `FORBIDDEN`) | 见 §4.2 |
| BOOL | QCheckBox | — |

三档可见性:BASIC 直接显示;ADVANCED 折叠在"显示高级" QGroupBox;LOCKED 只读灰显+锁图标(把接线铁律做成视觉常驻)。即时校验:范围用 QDoubleSpinBox 硬约束,列表/越界用 QValidator+红框+tooltip,任一非法则 `is_valid()=False` → 禁用"运行"。`collect()` 把 unit 缩放还原成 SI(µs→秒、µA→安培)后输出,键名 == `ParamSpec.name`,直接塞 `RunRequest.params`。

### 5.5 运行控制与安全 UI

- **dry/live 开关**:一对 QRadioButton,默认 dry-run;切 live 时控制栏换淡红底。
- **live 一段一确认**:点运行且 live 时弹 `LiveConfirmDialog(stage)`:(a) 醒目摘要(stage/device_id/写电压脉宽/|Ig|门/Gate=202 Drain=201);(b) 勾选"我已确认探针位置与接线";(c) **手输 stage 码**文本框。两者满足才 enable。**UI 只是双保险,confirm 字符串的唯一语义由引擎 `validate_live_request(stage, live, confirm)` 兜底,要求 `confirm==stage`**(评审 A4:UI 自动填还是手输,最终都必须等于 stage,否则抛 `SETUP_STOP_CONFIRM_REQUIRED_*`)。
- **预检可视化**:`PreflightView` 三行,由 `on_preflight_step` 点亮:① ERRX drain(`clear_b1500_status_for_wgfmu_open`,不发 *CLS/不默认 *RST,失败红✗阻断"会话将 status=-6");② 通道校验 G=202 D=201(`configure_channel_map` 的 `SETUP_STOP_BAD_CHANNEL`);③ 接线提示常驻"Gate→CH202,Drain→CH201;CH302 无 RSU 已禁用"。dry-run 时退化为"无 VISA/无 DLL/无硬件"全绿标注"模拟"。
- **stop-gate 触发**:`on_stop_gate(code,msg,recoverable)` → 安全指标区与进度条变红 + LogPanel 该行红底加粗 + `QMessageBox.critical`(标题=code 如 `E1_STOP_IG_GT_20UA`,正文=`max |Ig|=5.27e-06 > 2.0e-05`);若 `recoverable=True` 同时点亮"恢复会话"按钮。引擎已在抛 StopGate 前于边界安全收尾,GUI 只负责"喊出来"。
- **实时安全指标**:`on_safety_metric(now_max_ig, threshold)` 每 shot 更新 `当前 |Ig|=3.1µA(门5µA)`,>80% 阈值时转橙预警。

### 5.6 设备会话面板(`DeviceDialog` + `DeviceSessionManager`)

`DeviceSessionManager` 是 GUI 侧唯一握 backend 句柄**与 resource** 的地方。字段:VISA 资源(默认读 `configs/instruments.yaml`,可被 `B1500_VISA_ADDR` 覆盖)、通道映射(只读展示 Gate=202/Drain=201/forbidden=302/SMU 4/5/6/7)、device_id/geometry/device_family(与 RunControlPanel 双向同步)、连接状态/IDN。

- **连接按钮** → 后台跑 live 预检链(`ensure_wgfmu_dll_path`→`clear_b1500_status_for_wgfmu_open`→`open_session`),成功点绿灯显示 `*IDN?`,失败显示 DLL 搜索路径列表。
- **恢复会话按钮**(评审 B5):对接 `BackendManager.recover_session()`→`_reopen_wgfmu_session(backend)`(close→ERRX drain→reopen→force `ensure_initialized(force=True)`)。**启用条件**:仅当上一次 `on_stop_gate`/`on_error` 带 `recoverable=True`(即 `status=-6` 类)时亮起;`ensure_initialized(force=True)` 在 worker 线程内执行(GUI 线程不碰 backend)。
- **initialize 每会话一次**由 `DeviceSessionManager` 守护(沿用 `_fefet_wgfmu_initialized`)。

### 5.7 配置持久化

两层:Qt 框架状态用 **QSettings**(窗口几何 `saveGeometry`、dock 布局 `saveState`、上次选中协议、dry/live 默认、上次 device_id/geometry/family;`closeEvent` 存、`__init__` 恢复);业务参数预设用 **JSON Profile**(§4.7,UTF-8 无 BOM,加载时按 ParamSpec 逐字段 set,缺字段回落 default、多余字段忽略,保证协议升级后旧 profile 仍可用)。

---

## 6. 实时数据预览 / 绘图 / 日志 / 显示范围

### 6.1 一个必须先消除的接缝陷阱

`AuditBackend.add_vector` 把向量存成**元组** `(dt, v)`(实测 `audit_backend.py:add_vector` 第 90 行 `append((float(dtime_s), float(voltage)))`),而 `DummyWgfmuBackend.add_vector` 存成字典 `{"dtime_s","voltage"}`。notebook 40 的 `vectors_to_xy` 靠元组解包 `for dt, volt in vectors`。**所以 GUI 编程波形预览一律走 `AuditBackend`,绝不用 `DummyWgfmuBackend`**——这是引擎适配层的硬约定。`_patterns[name]` 形如 `{"init_v": float, "vectors": [(dt,v),...]}`,是预览唯一真值源。

### 6.2 实时绘图(增量 append + 限频 setData + 降采样)

| 视图 | X | Y | 来源 | 刷新 |
|---|---|---|---|---|
| 编程波形 | time | Vg/Vd | dry `AuditBackend._patterns`(§6.1) | 一次性,提交即冻结 |
| MW vs delay/cycle | delay_s(log)/cycle | Id(ERS)−Id(PGM)@主读点 | `on_shot` 增量 | 每 shot 一点 |
| 实测 Id/Ig 序列 | seq/time | Id_mean/Ig_mean | `on_shot` rows | 每 shot 多点 |

`on_shot` 是 WGFMU 天然刷新节拍(一 shot=一组读点),粒度刚好(WGFMU 是 execute→wait→批量取,本就无亚 shot 流)。数据进环形缓冲,30fps 上限 `QTimer`(33ms)批量 flush 到曲线,`setData` 整体重设(**不循环 addItem**);超 4000 点抽稀显示(不丢底层缓冲)。MW=`Id_ERS−Id_PGM` 是派生量,放分析层,**不进 CSV schema**(避免改 `FIELDNAMES` 契约)。颜色口径:ERS `#2659AD` / PGM `#B80000` / READ `#1A801A`。

> **吸收评审 D1(MVP 能力边界,必须钉死)**:逐 shot `on_shot` 实时点图依赖 runner 在 shot 边界调 `callbacks.on_shot(...)`。这要求在收口时给 `run_stage_*` 的 shot 循环里**加上 `on_shot` 调用**——本设计把这一步并入 **M1 收口(而非"远期可选")**,因为 GUI 表单与实时绘图都靠它。在 `on_shot` 未接入前,实时绘图只能靠解析 stdout `SHOT_OK ... seq=` 文本拿粗进度,**这是 M2 之前的临时降级,M3 必须交付真 `on_shot`**。

### 6.3 显示范围 / 缩放

pyqtgraph `ViewBox`/`AxisItem` 直接给齐:X/Y 手动范围(四个 QDoubleSpinBox→`setRange(..., padding=0)`)+ "自动缩放"(`enableAutoRange()`);对数轴(电流跨零,**默认 Y 线性**,提供"Y log(|值|)"开关,delay 轴默认 log-X);游标(`InfiniteLine`+`signalProxy` 监听 `sigMouseMoved`,LabelItem 显示最近点,电流 µA/nA 自适应);通道显隐(Id/Ig/Vg/Vd 各一 `PlotDataItem`,`QCheckBox.toggled→setVisible`,不删数据);按 state 分色(ERS/PGM 独立 item 固定色)。

### 6.4 分级日志落盘

日志来自 `on_log(level, code, msg)`。等级映射:`REPORT_CODE`/`STAGE_SUMMARY`/`SHOT_OK`/`MANIFEST`→INFO;`get_warning_summary` 非空→WARN;`STOP_GATE`→STOP;`make_backend` 异常/status=-6/DLL 缺失→ERROR。GUI 用只读 `QPlainTextEdit`(自动滚底)+ 四等级 QCheckBox 过滤 + 关键字过滤(底层存全量,过滤只改显示);颜色 INFO 灰/WARN 橙/STOP 红粗/ERROR 红底。**落盘**:同时写 `runs/{dry,live}/<ts>_<STAGE>_<dev>/run_log.txt`(**UTF-8 无 BOM**,与 manifest 同目录),格式 `ISO时间 [LEVEL] code: msg`;run_dir 由 `make_stage_dir` 返回,worker 在 `on_stage_done` 拿到后写入。

### 6.5 跑完结果浏览与历史 run 对比

独立"结果"标签页(不依赖正在跑的 run):run 选择器 `QTreeView` 扫 `runs/{dry,live}/`,读 manifest 做摘要(stage/device_id/live/effective);自动出图按 `csv_schema` 分派绘图器——`fefet_fixedcols`(E1/E5/CYCLE/E3)走 MW vs delay/cycle(`pd.read_csv`→按 `Vg_read_V≈主读点(默认-1.0V)`过滤→`groupby(['delay_s','state_target'])['Id_mean_A']`→ERS−PGM,逐字节复刻 notebook 40 cell4),E6R+E6D 走参考 vs 扰动双线,`dc`/`iv_sweep`/`wakeup_cycles` 各走专属绘图器(§7)。多 run 对比:勾选 2~N 个叠加同坐标系(不同 marker/线型,图例 `device_id@ts`)。读 manifest 用 `yaml.safe_load`(只读场景,环境已装 PyYAML);**写仍用项目 `write_manifest_yaml` 保持零依赖契约**。

---

## 7. FeFET 协议目录

### 7.1 设计原则:把"阶段"升级为"协议卡片",内核函数零改写

GUI 不拼 argparse 字符串调 CLI(那是把"乱"复制进 GUI),而在 `ProtocolSpec`(§3.1)之上提供面向用户的卡片元数据。卡片层纯数据,真正干活的仍是现有 `run_*_shot` / `DCSweepAPI.run_*_sweep` / `WgfmuWakeupRunner.run` / `PulseTrainBuilder`+`WgfmuIVSweepRunner`。`ParamSpec.default` 全部 import 自 `protocols/wgfmu_fefet.py` 的模块常量,**不复制数值**。

### 7.2 现有 11 阶段翻译成协议卡片

所有 WGFMU 结果是 `FIELDNAMES` 固定列 CSV(`csv_schema="fefet_fixedcols"`),pyqtgraph 按 `stage` + `state_target`(ERS/PGM) 分组,x 轴在 `delay_s`/`n_read`/`repeat_index`(CYCLE 装 checkpoint)/`dose_mode`(E3 装 `tw=`/`amp=`,E4 装 `pb=`)中选,y 轴 `Id_mean_A`(误差棒 `Id_std_A`),Ig 监控固定 `Ig_mean_A`。MW 统一定义:同 Vg/delay 下 `Id_mean(ERS)−Id_mean(PGM)`,派生量在分析层。

| 段 | 用户名 | 物理量 | 输出图谱 | 先决/门禁 |
|---|---|---|---|---|
| S0 | 空夹具只读自检 | 接线/漏电本底(~1.14µA) | 各 Vg 点 Id/Ig 散点 | 入口;`|Ig|>5µA→S0_STOP_IG_GT_5UA` |
| S1 | 器件只读 baseline | 静态读电流/栅漏 | Id-Vg 只读点 + Ig | 先 S0 OK(`S0_DONE_PROCEED_TO_S1_*`) |
| E1 | RAWD 写后保持 | retention 快版 | Id_mean vs delay_s(ERS/PGM 双线) | 先 S1(`S1_DONE_PROCEED_TO_E1`);`|Ig|>20µA` |
| E2 | 读扰动 | 反复读累积扰动 | Id_mean vs n_read | 先 E1(`E1_DONE_PROCEED_TO_E2_*`);20µA |
| E3W | 脉宽扫描 | programming kinetics | Id_mean/MW vs t_write | 先 E1;30µA |
| E3A | 幅值扫描 | programming kinetics | Id_mean/MW vs V_write | 先 E1;30µA |
| E4 | imprint 预偏压 | imprint | Id vs (prebias_V×prebias_s) | 先 E1;30µA |
| E5 | Vg×Vd 窗格 | 记忆窗口可视化 | Id-Vg 双态 + MW 标注 | 先 E1;20µA |
| E6R | 无扰动参考 | retention 参考线 | Id vs delay(reference) | 与 E6D 成对;20µA |
| E6D | 半Vdd反极性扰动 | 写扰动 disturb | Id vs delay + 叠 E6R reference | 先 E1;30µA |
| CYCLE | 检查点耐久 | endurance | MW vs cycle(log-x) | 放最后,先 E1/E5;30µA |

### 7.3 标准表征补全(全靠复用)

> **吸收评审 C1(硬错误修正)**:`run_e1_shot` 是固定的 reset+write+delay+read 写后读 shot,签名 `(backend, *, state, delay_s, vg_reads, vd_read, n_pts, v_write, t_write)`,**没有脉宽/幅值扫描、disturb、cycle stress 入口**。E6R 实际用 `run_disturb_delay_shot`,CYCLE 用 `_run_cycle_stress_*`,E3 用 `run_stage_e3_width/amp`。**草稿"run_e1_shot 给 E1/RET/E3W/E3A/E5/E6R/CYCLE 共用"是错的**——只有 RET(长延迟版 E1)能真正复用 `run_e1_shot`,其余卡片各引用自己的 runner。

| 卡片 | 物理量 | 复用什么(不重写) | csv_schema | 落点说明 |
|---|---|---|---|---|
| **RET** 长保持 | retention(到 10s/更长) | **直接复用 `run_e1_shot`**,只覆盖 delay 列表(扩 `DELAYS_FULL`);等价 `--stage E1 --e1-full-delays`。report code 仍 E1 家族,落盘契约不变 | fefet_fixedcols | 零新代码 |
| **PHYS** 脉冲 Id-Vg 迟滞 | MW 主力回线 | `pulse_builder.linear_voltage_segments` 拼上行+下行 → `PulseTrainBuilder.build()` → `WgfmuIVSweepRunner`。pFeFET 默认 Vg[-1.0→+0.5],nFeFET[-0.5→+1.0] | iv_sweep | IVSweep 输出列与 FIELDNAMES 不同,**不强塞**,GUI 按 schema 分派绘图器 |
| **DC_IDVG/DC_IDVD** | DC 转移/输出,SS,DC 迟滞/MW | 薄适配器调 `DCSweepAPI.run_idvg_sweep/run_idvd_sweep`(SMU G=4/D=5/S=6) | dc | 见 §7.4 两处胶水 |
| **WAKEUP** | per-cycle i_read vs cycle,MW 形成/翻负 | `WgfmuWakeupRunner.run(stages, readout, cfg)` | wakeup_cycles | 见 §7.5 会话/通道改造 |
| (PUND) | 铁电极化 | **暂不实现**,catalog 留占位 `status="needs_physics_review"` | — | MFIS 上 PUND 是否有意义需 KB 拍板;不为"补全"上物理可能无效的协议 |

speed map(E3W+E3A 合成 MW vs t_write 多幅值族)与 endurance 失效判据(MW 跌破阈值线)归**分析层**,不进采集目录。

### 7.4 DC 纳入目录的两处胶水(必须写,否则倒退)

> **吸收评审 C4 + C5**:
> 1. **`run_idvg_sweep` 没有 `progress_callback` 形参**(实测:内部 `progress` 闭包只在 `verbose` 时 print,真正收 callback 的是底层 `self.runner.sweep_vg(progress_callback=...)`)。所以"零改动接进度条"不成立——**必须给 `DCSweepAPI` 三个 `run_*_sweep` 加 `progress_callback` 形参并透传到 `self.runner.sweep_*`**(一行胶水,但当前不存在)。
> 2. **DC 无 `Ig_mean_A` 列**(DC QC 列名是 `id_A`/`ig_A`/`is_A`),而 `StopGatePolicy.check` 在取不到 metric 列时 `if not values: return` **静默放行**(实测 `core.py` 第 102 行)。所以"DC 也接 StopGatePolicy"在未做列映射前是**永远不触发的假门禁**。**必须在 DC runner 适配器里把 DC 栅电流列映射到 `Ig_mean_A` 再过门禁**;在映射落地前,文档标红 **DC 路径无安全门禁**。

### 7.5 wakeup 的会话/通道改造(评审 B6)

实测 `WgfmuWakeupRunner.run` **自己 `open_session`/`close_session`**,且 `WgfmuWakeupConfig.chan_id` 默认 **101**(单通道),与 11 阶段的 Gate=202/Drain=201 **双通道 `add_sequence`** 模型不同——直接接进统一 `BackendManager`+`_validate_channels`(要求两条同步序列,`abs_tol=2e-12` 时长校验)会触发 `_validate_sequences` 失败。**改造工作量(不是一句"改成接收 backend"能带过)**:(a) WAKEUP runner 改为接收已打开 backend(统一会话生命周期,避免与"每会话一次 init"冲突);(b) 明确 wakeup 是单通道模型,WAKEUP 卡片走**独立校验分支**(不套用双序列 `_validate_sequences`),chan_id 设为 Gate=202 而非默认 101;(c) wakeup 走 `WgfmuDataExporter` 自有 schema,`csv_schema="wakeup_cycles"` 的绘图分派需单独验证。

### 7.6 双器件类型(pFeFET/nFeFET)参数化

GUI 顶部全局"器件类型"选择,所有卡片 `ParamSpec.default` 经 `family_defaults` 覆盖后下发。差异**只在读 Vg 网格方向 + MW 符号**:

```python
FAMILY_DEFAULTS = {
  "pFeFET": {"vg_read_grid": [-1.0,-0.7,-0.4,-0.2,0.0,0.2],   # == VG_E5
             "vg_cycle": [-1.0,-0.7,-0.4],                    # == VG_CYCLE
             "phys_vg_range": (-1.0, 0.5), "wakeup_recommended": True},
  "nFeFET": {"vg_read_grid": [-0.2,0.0,0.2,0.4,0.7,1.0],
             "vg_cycle": [0.4,0.7,1.0],
             "phys_vg_range": (-0.5, 1.0), "wakeup_recommended": False},
}
```

**写死的取舍(避免后来者去改 run_*_shot)**:① 写极性 ERS/PGM **不按器件族翻**(`V_ERS=+5/V_PGM=-5` 是写脉冲电压极性,不是器件类型;`_resolve_write_v` 只控幅值符号;器件族只改读 Vg 网格方向,否则与 `_opposite_disturb_voltage` 打架);② MW 符号 pFeFET/nFeFET 相反,在分析层按 family 取绝对值或带符号显示,不进采集层;③ family 写进 `manifest.yaml`(现有 `_build_manifest` 已落 `device_family`)。

### 7.7 安全推进工作流链

`report_code` 已把推进链编码进字符串,GUI 直接消费,不另发明状态机:

```
S0 ──S0_DONE_PROCEED_TO_S1_IF_PROBES_ON_DEVICE──▶ S1
S1 ──S1_DONE_PROCEED_TO_E1──▶ E1
E1 ──E1_DONE_PROCEED_TO_E2_MINIMAL_IF_TREND_HEALTHY──▶ {E2, E5, RET}
            ├──▶ E3W/E3A ──▶ speed map(分析层)
            ├──▶ E4 (imprint)
            ├──▶ E6R+E6D (扰动,成对)
            └──▶ CYCLE (耐久,放最后)
旁路: PHYS/DC_IDVG/DC_IDVD 在 S1 OK 后任意接;WAKEUP 在 S1 OK 后、E1 之前(pFeFET 需先唤醒)
```

GUI 从每个 run 的 `report_code.json` 判断下一步解锁哪些卡片;`requires=("S0_DONE_*",)` 未满足时**置灰该卡片的 live 按钮(dry-run 始终可点)**。WAKEUP 卡片加 `note="pFeFET 建议先唤醒,否则 MW 可能未形成或为负"`,nFeFET 可跳过。

---

## 8. 自定义协议设计

### 8.1 原则:不发明新执行器,只发明"声明 → 现有 run_* 风格展开器"

自定义协议产出声明式 `CustomProtocolSpec`,由 `expand_custom_shot(backend, spec)` 翻译成**完全相同的 add_vector 序列**,复用 `_build_read_phase` 布读窗、`_configure_and_run_phase` 执行、`_summarize_windows`+`FIELDNAMES` 落盘。这样天然继承 stop-gate / 向量预算 / manifest / dry-run。落点 `protocols/custom_protocol.py`,把 `_build_read_phase`/`_configure_and_run_phase`/`_summarize_windows` 三个纯函数与协议一起留在 `protocols/wgfmu_fefet.py`,custom 从中 import,口径不分叉。

### 8.2 声明式结构(存 YAML/JSON)

积木=段(segment),gate 与 drain 两轴**逐段同步推进**(两轴总时长必须 `isclose`,`abs_tol=2e-12`,实测 `_validate_sequences`)。

```yaml
name: "myproto_ers_then_halfdisturb"
description: "ERS 写入 → 半 Vdd 反向扰动 → 多读点读窗"
vd_read: 0.05
read_irange_gate: "1MA"
read_irange_drain: "100UA"
custom_ig_stop_uA: 20.0
segments:
  - {kind: reset,       t_s: 1.0e-3}
  - {kind: write,       v: 5.0,  t_s: 100.0e-6, t_rf_s: 100.0e-9}
  - {kind: delay,       t_s: 1.0e-5}
  - {kind: disturb,     v: -2.5, t_s: 100.0e-6, t_rf_s: 100.0e-9}
  - {kind: delay,       t_s: 1.0e-3}
  - {kind: read_window, vg_reads: [-1.0,-0.7,-0.4,-0.2,0.0,0.2], n_pts: 5}
```

### 8.3 映射到 add_vector + 自动读窗(修正后的展开器)

> **吸收评审 C2(硬错误修正,原草稿不可行)**:实测 `_build_read_phase` 在 `t_prefix>0` 时往 gp **和** dp 都补 prefix;在 `t_prefix=0` 时**只写 gp 不写 dp 的 prefix 段**,而 read 窗的 dp 轴从 `t_total>t_prefix` 才铺 `vd_read`。原草稿让前序段只往 dp 自己铺、再传 `t_prefix=0`,会导致 read 阶段 dp 轴只铺读窗长度,gp 轴=前序+读窗,**两轴总时长不等**,被 `_validate_sequences` 拒。**正确范式是 `run_e1_shot`:前序段 gp/dp 同步铺,再传 `t_prefix=0` + `event_offset_s=t_prefix`。**

```python
def expand_custom_shot(backend, spec: CustomProtocolSpec) -> list[dict]:
    backend.clear()
    backend.create_pattern("gp", 0.0)
    backend.create_pattern("dp", 0.0)
    t_prefix = 0.0
    windows = None
    for seg in spec.segments:
        if seg.kind in ("reset", "delay"):
            backend.add_vector("gp", seg.t_s, 0.0)
            backend.add_vector("dp", seg.t_s, 0.0)        # ← 关键:dp 同步铺
            t_prefix += seg.t_s
        elif seg.kind in ("write", "disturb", "raw_gate"):
            for dt, vg in [(seg.t_rf_s, seg.v), (seg.t_s, seg.v), (seg.t_rf_s, 0.0)]:
                backend.add_vector("gp", dt, vg)
                backend.add_vector("dp", dt, 0.0)         # ← dp 同步铺持 0
                t_prefix += dt
        elif seg.kind == "read_window":
            windows = _build_read_phase(                  # 前序已 gp/dp 同步,这里 t_prefix=0
                backend, vg_reads=list(seg.vg_reads), vd_read=spec.vd_read,
                t_prefix=0.0, n_pts=seg.n_pts, event_offset_s=t_prefix)
    assert windows is not None, "custom protocol must contain at least one read_window"
    g_df, d_df = _configure_and_run_phase(backend, measure=True, timeout_s=_auto_timeout(t_prefix))
    return _summarize_windows(g_df, d_df, windows)
```

注册进 REGISTRY 后,`run_stage_custom(backend, view)` 拿到 stop-gate(`_check_ig` 默认 20µA)/manifest/CSV;`CustomProtocolSpec` 原样序列化进 manifest `custom_spec`,**可复现可追溯**。

### 8.4 GUI 序列编辑器 + dry-run 波形预览

左侧 `QTableWidget`(列 kind/V/t/t_rf/vg_reads/n_pts,kind 下拉,增删行+上下移),右侧上下两 `pyqtgraph.PlotWidget`(gate/drain,`setXLink` 共享 X 轴),读窗用半透明 `LinearRegionItem` 高亮 + 标 measure_event 点。表格编辑触发**去抖(200ms)预览刷新**:

```python
def refresh_preview(self):
    spec = self.table_to_spec()
    bk = AuditBackend(gate_ch=202, drain_ch=201, channels=[201,202,301,302])
    bk.open_session("DRYRUN")
    try:
        expand_custom_shot(bk, spec)
        bk.execute()    # 当校验器用:触发 _validate_sequences(两轴对齐) + 向量预算
    except (ValueError, RuntimeError) as e:
        self.status.show_error(str(e)); return
    tg, vg = vectors_to_xy(bk._patterns['gp']['init_v'], bk._patterns['gp']['vectors'])
    td, vd = vectors_to_xy(bk._patterns['dp']['init_v'], bk._patterns['dp']['vectors'])
    self.curve_g.setData(tg*1e3, vg); self.curve_d.setData(td*1e3, vd)
    self.budget_bar.setValue(bk.max_vectors_seen)   # /2048
```

把 `execute()` 当校验器:它跑 `_validate_sequences`(两轴时长对齐)和向量预算,把 GUI 想要的合法性检查白送。

### 8.5 护栏(与内置同源)

1. **dry-run 默认 + 预览**:预览只用 `AuditBackend`(不开 VISA/不载 DLL),对硬件零风险。
2. **向量预算 <2048**:`AuditBackend.execute()` 在 `_validate_vector_budget` 抛 `RuntimeError`(>2048)并维护 `max_vectors_seen`;GUI 预览读它显示 `1840/2048`,逼近 1920(=2048−128 guard)变黄、超 2048 禁 live 标红。**MVP 阶段自定义协议不自动分块**(内置 CYCLE/E6D 靠 `_dose_chunk_counts`/`_max_cycle_stress_chunk` 分块跑过 2048,自定义协议无分块=能力落差),超预算提示用户拆段或缩短——**文档明确这个落差**(评审 B2)。
3. **stop-gate**:`run_stage_custom` 走 `_check_ig`/`_check_samples`,阈值 `custom_ig_stop_uA` 默认 20µA。
4. **电压上限**:任一 write/disturb 段 `|v|>5.0V` 弹确认(论文标称 ±5V),live 提交前再走 `validate_live_request("CUSTOM", live, confirm)`(一段一确认)。

---

## 9. 安全模型与物理铁律

| 铁律 | 引擎层如何落实 | UI 层如何落实 |
|---|---|---|
| **dry-run 默认** | `RunMode` 默认 DRY;`make_backend(False)` 不开 VISA/不载 DLL | dry/live 开关默认 dry;dry 预检全绿标"模拟" |
| **live 一段一确认** | `validate_live_request(stage, live, confirm)` 在 `run` 入口,`confirm!=stage` 抛 `SETUP_STOP_CONFIRM_REQUIRED_*`;`ALL_DRY` live 抛 `SETUP_STOP_LIVE_ALL_FORBIDDEN` | `LiveConfirmDialog` 手输 stage 码 + 勾选接线;UI 双保险,confirm 唯一语义由引擎兜底 |
| **stop-gate 不可摘** | `StopGatePolicy(metric="Ig_mean_A", threshold=...)` 在每 shot/段查;阈值可调,门本身不暴露关闭开关 | 安全指标实时显示 + 触发红屏弹窗;DC 路径**必须先做列映射**(§7.4)否则假门禁 |
| **ERRX 预检不发 *CLS** | `clear_b1500_status_for_wgfmu_open(visa_addr)` 只 drain 错误队列,**不发 *CLS/不默认 *RST**(对应 status=-6 事故结论) | 预检第①行点亮;失败红✗阻断"会话将 status=-6" |
| **initialize 每会话一次** | `BackendManager.ensure_initialized`(沿用 `_fefet_wgfmu_initialized`);多段复用同一会话 | 不提供"强制 re-init"危险开关 |
| **接线铁律** | `configure_channel_map`/`_validate_channels`:Gate=202/Drain=201/forbidden=302/`gate==drain`→`SETUP_STOP_BAD_CHANNEL`;SMU G=4/D=5/S=6 | CHANNEL 族 LOCKED 只读卡片;改 Gate/Drain 须"我已确认重新接线" |
| **会话恢复(FIX B)** | `recover_session()`→`_reopen_wgfmu_session(backend)`(close→ERRX drain→reopen→force init);`status=-6` 经 `on_stop_gate(recoverable=True)` 上报 | "恢复会话"按钮仅在 `recoverable=True` 时亮;恢复在 worker 线程执行 |
| **向量预算护栏** | `_validate_vector_budget`(>2048 抛);内置分块自动 | 预览实时显示 `n/2048`,超预算禁 live |
| **取消 = 协作式** | shot/chunk 边界查 `is_cancelled()`,干净 `close_session` 后抛 `USER_CANCELLED` | Stop 按钮只置标志,绝不 `terminate()` |
| **LOCKED 字段不可越权** | `validate_params` 拒绝外部传入 L 字段(GUI/Profile/CLI 共用) | Profile 加载时 + 表单都不暴露 L 字段编辑 |

---

## 10. 打包与部署

> **吸收评审 B3(硬约束点名,五份草稿全漏)。**

### 10.1 PyInstaller:onedir,不 onefile

**结论用 onedir(`--onedir`)**:onefile 每次启动解压到临时目录,DLL 路径解析更脆、启动慢、杀软误报率高;onedir 产出一个文件夹(`dist/B1500GUI/`),`wgfmu.dll` 等可直接放进去、路径稳定。`.spec` 要点:

```python
# B1500GUI.spec 关键项
datas=[('configs/*.yaml', 'configs'), ('configs/profiles/*.json', 'configs/profiles')]
binaries=[('vendor/wgfmu.dll', '.')]   # 若 DLL 可随包分发;否则见 10.2
hiddenimports=['pyvisa', 'pyvisa_py', 'pyqtgraph', 'pandas', 'yaml']
# PySide6 用官方 hook 自动收集 Qt 插件(platforms/styles),勿手删
```

### 10.2 依赖处理(三类,处置不同)

1. **wgfmu.dll(Keysight WGFMU 驱动)**:随机器 Keysight 安装,路径由 `ensure_wgfmu_dll_path()` 搜索。**冻结环境陷阱**:PyInstaller 下 `__file__`/相对路径失效,`sys._MEIPASS` 才是资源根。**必须改 `ensure_wgfmu_dll_path` 支持冻结**:搜索顺序加 (a) `sys._MEIPASS`/exe 同目录;(b) 环境变量 `WGFMU_DLL_PATH`;(c) Keysight 标准安装路径。若 DLL 随包分发要确认许可允许。
2. **VISA runtime(NI-VISA / Keysight IO Libraries)**:**不能打进 exe,必须机器预装**。首次启动检测 `pyvisa.ResourceManager()` 可用性,缺失则弹引导"请安装 Keysight IO Libraries / NI-VISA"。
3. **NI-488.2(GPIB)**:同 VISA,机器级预装(B1500 走 GPIB),首次启动检测。

### 10.3 配置向导(评审 B4)

首次启动若无 `configs/instruments.yaml`/`channel_map.yaml` → 弹配置向导:① VISA 检测(列出 `rm.list_resources()`,选 B1500 或填 `B1500_VISA_ADDR`);② wgfmu.dll 路径确认(检测失败让用户指);③ 通道映射确认(默认 Gate=202/Drain=201/forbidden=302/SMU 4/5/6/7,只读展示让用户核对接线);④ device_id 命名约定提示。向导产出的 yaml 用 **UTF-8 无 BOM** 写。

### 10.4 数据回流项目4(评审 B1,硬约束点名,全空白补上)

> **核验**:WGFMU 走 `make_stage_dir` 写 `runs/{live,dry}/<ts>_<stage>_<dev>/`、CSV 用 `write_rows_csv`(UTF-8 无 BOM);DC 走 `DCDataExporter.create_run_dir` 写**扁平** `runs/<ts>_<sweeptype>/`、CSV 用 `utf-8-sig`(**带 BOM**)。两套目录契约 + 两套编码不一致,且 BOM 版回流会破坏下游解析。

**统一处置(三条)**:
1. **目录统一**:DC 落盘改走 `runs/{dry,live}/<ts>_<stage>_<dev>/`(让 `DCDataExporter` 接受 dry/live 与 device 维度),或在 `RunBrowserPanel` 显式同时扫两套目录契约。推荐前者(M2 改 DC export 一处,长期干净)。
2. **编码统一 UTF-8 无 BOM**:把 DC export 的 `encoding="utf-8-sig"` 改为 `"utf-8"`(两处:`save_data` 与 `generate_qc`),与 WGFMU `write_rows_csv` 一致。
3. **回流到项目4**:GUI"导出/回流"动作——用户在 RunBrowser 选 run → 复制 CSV/manifest 到 G 盘项目4 实测数据目录(路径以项目4 `_agent` 约定为准,命名沿用 `<ts>_<stage>_<dev>`),**一律 UTF-8 无 BOM**;若源 CSV 是 BOM 版则转码后写。回流由用户显式触发(不自动),写盘前校验编码。

---

## 11. 落地路线图

每个里程碑给验收标准;CLI 薄壳与现有 notebook **并存**(notebook 40 的 `vectors_to_xy` 被移植成 `PlotPanel` 工具函数,notebook 本身保留作探索用,不弃用)。

### M1 — 引擎收口 + ParamSpec 注册表
- 第1步搬家(脚本整体进 `protocols/wgfmu_fefet.py`,删 `sys.path.insert`);第2步引入 `ParamView`;第3步为 11 阶段 + DC 写 `ProtocolSpec`;第4步 `build_argparser` 替换手写 argparse;**并入阻塞前置(评审 B7)**:模块常量(`MEAS_IRANGE_*`/`E3_WIDTHS`/`E3_AMPS`/`E4_PREBIAS_*`/`VG_E5`/`VD_E5`/`DELAYS_E5`/`N_PTS`)提升为入参;**并入 `on_shot` 接入**(评审 D1,不推迟到远期)。
- **验收**:`--stage ALL_DRY` 输出 `DRY_RUN_AUDIT: execute_count=96 max_vectors_seen=640` 与 State 一致;同 device/seed 下 dry-run CSV 与收口前**逐字节一致**(项目已用验收手法);pytest 喂假 `EngineCallbacks` 跑通 11 阶段 dry;CLI `SHOT_OK`/`REPORT_CODE` 文本不变。

### M2 — GUI 骨架 + 参数表单 + dry-run 跑通
- MainWindow/三栏/dock;ParamForm 自动生成;EngineController+EngineWorker+QThread;`AuditBackend` 元组路径波形预览(§6.1);结果出图;**DC mock session(评审 C6)**;**DC 落盘统一到 `runs/{dry,live}` + UTF-8 无 BOM(评审 B1)**。
- **验收**:不连硬件、不装 VISA 即可全程点完:选协议→填表单→dry 跑→编程波形预览→结果出图→落盘 `runs/dry/`。

### M3 — 实时绘图 + 日志
- pyqtgraph 增量 `on_shot` 30fps 限频 + 降采样 + 显示范围/对数轴/游标/通道显隐;分级日志落盘 `run_log.txt`(UTF-8);RunBrowser 历史 run 对比。
- **验收**:dry 跑 E1/CYCLE 时实时点图随 shot 增长、限频不卡;日志按级过滤;多 run 叠加对比图可出。

### M4 — live 安全门禁 + 真机联调
- LiveConfirmDialog;PreflightView 三步点亮;stop-gate 红屏;**会话恢复按钮(评审 B5,`recoverable` 区分)**;**长实验进度/中断(评审 B2,CYCLE 进度靠 chunk 边界 `on_progress`;明确是否支持 checkpoint 断点续跑)**。
- **验收**:真机 S0 空夹具 baseline ~1.14µA 复现;live 一段一确认生效;故意触发 stop-gate 红屏并干净收尾;CYCLE 长跑可中途协作式停在 checkpoint 边界。

### M5 — 自定义协议编辑器
- 序列表格 + dry 波形预览(`execute()` 当校验器)+ 向量预算条 + 电压上限确认;`expand_custom_shot`(§8.3 修正版,gp/dp 同步铺)+ `run_stage_custom`。
- **验收**:拼一条 ERS→扰动→读窗,dry 预览波形正确、两轴时长校验通过、向量预算显示;live 走 `validate_live_request("CUSTOM",...)`。

### M6 — 打包交付
- PyInstaller onedir + `.spec`;`ensure_wgfmu_dll_path` 支持 `sys._MEIPASS`/`WGFMU_DLL_PATH`(评审 B3);VISA/NI-488.2 缺失检测;首次安装配置向导(评审 B4);**DC 回流项目4 UTF-8(评审 B1)**。
- **验收**:在干净测试机解压 dist 即可启动;DLL/VISA 缺失给清晰引导;首次向导生成 yaml(UTF-8 无 BOM);回流的 CSV 在项目4 下游可正常解析。

---

## 12. 风险与取舍

1. **`on_shot` 接入是 M1 而非远期(D1)**:若推迟,M3 实时绘图只能解析 stdout 文本,粗且脆。已把它钉进 M1 收口的 shot 循环——这是唯一会改 `run_stage_*` 函数体的地方,但只加一行回调、不动物理逻辑,字节一致回归仍守得住。
2. **DC 安全门禁依赖列映射胶水(C5)**:在 `Ig_mean_A` 列映射落地前,DC 路径是假门禁(静默放行)。文档已标红,M2 必须随 DC 接入一并交付,否则 DC live 无 |Ig| 保护。
3. **自定义协议无自动分块(B2)**:相对内置 CYCLE/E6D 是能力落差;MVP 取舍为"超 2048 禁 live + 提示拆段",不引入与内置不同的执行语义。远期可让 `expand_custom_shot` 复用 `_dose_chunk_counts` 分块。
4. **wakeup 单通道改造(B6)**:接进统一会话需独立校验分支 + chan_id 改 202,工作量不小;若 M 排期紧,WAKEUP 可推到 M5 之后单独迭代,先不阻塞主链。
5. **DC dry-run 依赖 mock session(C6)**:`DCSweepAPI` 构造即要真 `VisaSession`,M2 须交付 mock,否则 DC 卡片的"dry-run 默认"铁律对 DC 不成立(只能 live),与全局铁律冲突。
6. **冻结环境 DLL 路径(B3)**:`ensure_wgfmu_dll_path` 在 PyInstaller 下大概率失效,M6 必须改;这是"能不能在测试机跑起来"的成败点,不可推迟。
7. **PUND 暂不实现**:MFIS 结构上 PUND 物理意义需 KB 拍板,不为"补全"上可能无效的协议,留占位 `needs_physics_review`。
