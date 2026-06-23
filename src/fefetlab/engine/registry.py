"""协议注册表 · GUI / CLI / manifest 的唯一协议来源。

设计文档 §3.2。把现有 `protocols.wgfmu_fefet.STAGE_REGISTRY`(11 段 StageSpec)
升格成 `ProtocolSpec`(超集),`runner` 直接指向现有 `run_stage_*`,**协议逻辑零改写**。

每个 ProtocolSpec 的 `params` 现已枚举该协议的**测量旋钮 + 通道**(供 GUI 表单自动
生成 / 校验 / manifest)。枚举口径:
  * 每个 `ParamSpec` 1:1 对应 `wgfmu_fefet.parse_args` 的一个 `--flag`,`name`==argparse
    dest,`default`==argparse 默认值(一致性由 `tests/test_registry_params.py` 逐条守门)。
  * `cli_flag` 由 `name` 按 `--{name.replace('_','-')}` 派生,保证 name↔flag 不会手抖错配。
  * **器件身份字段(device-id/geometry/serial/device-type/operator)不进 params** —— 它们是
    Setup Profile / 运行头里的自由文本元数据,且 ParamKind/Widget 词汇刻意不含纯文本类型;
    身份由器件选择器处理,不在逐协议测量表单里。`--stage`(协议选择器本身)、`--confirm`
    (live 安全握手令牌)同理不入 params。
  * B7 物理常量已提升为 flag 并枚举:E3W=e3_widths/e3_delay_s、E3A=e3_amps/e3_delay_s、
    E4=e4_prebias_v/e4_prebias_s/e4_post_delay_s、E5=vg_e5/vd_e5/delays_e5(均用顺序保留
    解析,默认值由 runner 常量派生,逐字节对齐金标准)。仍硬编码的低层常量(读量程、T_RF
    等波形时序)不属测量旋钮,继续留在 runner。
"""
from __future__ import annotations

from typing import Any

from ..protocols.wgfmu_fefet import (
    DEFAULT_ALLOWED_CHANNELS,
    DEFAULT_DRAIN_CH,
    DEFAULT_FORBIDDEN_CHANNELS,
    DEFAULT_GATE_CH,
    DEFAULT_MEAS_IRANGE_DRAIN,
    DEFAULT_MEAS_IRANGE_GATE,
    DEFAULT_RAW_DATA_MODE,
    IRANGE_CHOICES,
    RAW_DATA_MODE_CHOICES,
    DELAYS_E5,
    DISTURB_AMPS_DEFAULT,
    DISTURB_DELAYS_DEFAULT,
    DISTURB_WIDTH,
    CYCLE_CHECKPOINTS_DEFAULT,
    E3_AMPS,
    E3_DELAY,
    E3_WIDTHS,
    E4_POST_DELAY,
    E4_PREBIAS_S,
    E4_PREBIAS_V,
    ISPP_ID_TOL_UA,
    ISPP_MAX_STEPS,
    ISPP_READ_DELAY,
    ISPP_READ_VG,
    ISPP_TARGET_ID_UA,
    ISPP_VD_READ,
    ISPP_VG_MAX,
    ISPP_VG_START,
    ISPP_VG_STEP,
    ISPP_V_ERASE,
    ISPP_WIDTH,
    MLC_AMPS_DEFAULT,
    MLC_DELAY,
    MLC_PULSE_WIDTH,
    MLC_READ_VD,
    MLC_READ_VG,
    MLC_V_ERASE,
    DEFAULT_N_PTS,
    STAGE_REGISTRY,
    VD_E5,
    VG_E5,
)
from .specs import ParamKind as K
from .specs import ParamSpec
from .specs import ProtocolSpec
from .specs import Visibility as V
from .specs import Widget as W

# 阶段码 → (人类标题, 物理量语义)。与设计 §7 协议卡片对齐。
_META = {
    "S0": ("空夹具/抬针 smoke", "smoke"),
    "S1": ("器件只读 baseline", "baseline"),
    "E1": ("RAWD 写后延迟读", "retention"),
    "E2": ("读扰动 minimal", "read-disturb"),
    "E3W": ("脉宽扫描", "pulse-width"),
    "E3A": ("幅值扫描", "amplitude"),
    "E4": ("imprint 预偏压", "imprint"),
    "E5": ("Vg×Vd 可视窗格", "visibility"),
    "E6R": ("无扰动参考", "reference"),
    "E6D": ("半Vdd 反极性扰动-延迟", "disturb-delay"),
    "CYCLE": ("检查点耐久", "endurance"),
    "MLC": ("多值编程幅值扫描", "multi-level"),
    "ISPP": ("ISPP 增量步进编程(闭环)", "closed-loop"),
}


def _p(
    name: str,
    kind: K,
    default: Any,
    *,
    label: str,
    unit: str = "",
    vis: V = V.BASIC,
    widget: W = W.DOUBLE_SPINBOX,
    minimum: float | None = None,
    maximum: float | None = None,
    choices: tuple | None = None,
    help: str = "",
) -> ParamSpec:
    """构造 ParamSpec,`cli_flag` 由 `name` 派生(`--{name 蛇形转横杠}`),name==argparse dest。"""
    return ParamSpec(
        name=name,
        label=label,
        kind=kind,
        default=default,
        unit=unit,
        visibility=vis,
        minimum=minimum,
        maximum=maximum,
        choices=choices,
        widget=widget,
        cli_flag="--" + name.replace("_", "-"),
        help=help,
    )


def _reps(name: str, default: int, label: str) -> ParamSpec:
    return _p(name, K.INT, default, label=label, vis=V.BASIC, widget=W.SPINBOX,
              minimum=1, help="重复次数/器件")


def _ig_stop(name: str, default: float) -> ParamSpec:
    return _p(name, K.FLOAT, default, label="|Ig| 停门", unit="µA", vis=V.ADVANCED,
              minimum=0.0, help="栅极漏电安全停门:|Ig| 超过即停,不进下一炮/段")


# ── 公共:接线通道(LOCKED 铁律) + 复现/运行模式,所有协议都有 ───────────────────
COMMON = (
    _p("gate_ch", K.INT, DEFAULT_GATE_CH, label="Gate 通道", vis=V.LOCKED,
       widget=W.CHANNEL, help="接 Gate 的 WGFMU 通道;错值打错电极,须接线档案确认"),
    _p("drain_ch", K.INT, DEFAULT_DRAIN_CH, label="Drain 通道", vis=V.LOCKED,
       widget=W.CHANNEL, help="接 Drain 的 WGFMU 通道;须与 Gate 不同"),
    _p("allowed_channels", K.INT_LIST,
       ",".join(str(x) for x in sorted(DEFAULT_ALLOWED_CHANNELS)),
       label="允许通道集", vis=V.LOCKED, widget=W.CSV_LINE,
       help="本夹具允许使用的 WGFMU 通道"),
    _p("forbidden_channels", K.INT_LIST,
       ",".join(str(x) for x in sorted(DEFAULT_FORBIDDEN_CHANNELS)),
       label="禁用通道集", vis=V.LOCKED, widget=W.CSV_LINE,
       help="绝不可选的通道(如未接 RSU 的 302)"),
    _p("vd_read", K.FLOAT, None, label="读出 Vd", unit="V", vis=V.BASIC,
       help="读取时 Drain 电压;None=协议标称 0.05 V"),
    _p("seed", K.INT, 20260522, label="随机种子", vis=V.ADVANCED, widget=W.SPINBOX,
       help="延迟随机化种子,复现用"),
    _p("live", K.BOOL, False, label="联机(真机)", vis=V.ADVANCED, widget=W.CHECKBOX,
       help="True=驱动真机(须一段一确认);False=dry 审计"),
    # 读窗参数(增量4):提升为可调,所有协议共有(configure_channel_map 注入运行时全局)
    _p("n_pts", K.INT, DEFAULT_N_PTS, label="读窗平均点数", vis=V.ADVANCED, widget=W.SPINBOX,
       minimum=1, help="每个读窗的硬件平均采样点数(默认 5)"),
    _p("read_irange_gate", K.CHOICE, DEFAULT_MEAS_IRANGE_GATE, label="Gate 读量程", vis=V.ADVANCED,
       widget=W.COMBO, choices=IRANGE_CHOICES, help="Gate 读电流量程;on/off 跨数量级时选小量程提分辨"),
    _p("read_irange_drain", K.CHOICE, DEFAULT_MEAS_IRANGE_DRAIN, label="Drain 读量程", vis=V.ADVANCED,
       widget=W.COMBO, choices=IRANGE_CHOICES, help="Drain 读电流量程"),
    _p("raw_data_mode", K.CHOICE, DEFAULT_RAW_DATA_MODE, label="数据模式", vis=V.ADVANCED,
       widget=W.COMBO, choices=RAW_DATA_MODE_CHOICES, help="averaged/raw;raw 看瞬态但数据量大,仅限短采样"),
)

# ── 写脉冲(只在会写的协议:E1/E2/E5/E6R/E6D) ──────────────────────────────────
WRITE = (
    _p("write_v", K.FLOAT, None, label="写脉冲幅值", unit="V", vis=V.BASIC,
       help="写幅值;设 v 则 ERS=+|v|/PGM=-|v|,覆盖标称 ±5 V。None=±5 V"),
    _p("t_write_s", K.FLOAT, None, label="写脉冲宽度", unit="s", vis=V.BASIC,
       help="写脉冲宽度;None=100 µs"),
)

# ── 读出 Vg 扫描点(只在 S0/S1 读 baseline) ──────────────────────────────────
READ_VG = (
    _p("s1_vg", K.FLOAT_LIST, None, label="读出 Vg 点", unit="V", widget=W.CSV_LINE,
       vis=V.BASIC, help="S0/S1 读出 Vg 扫描点(逗号分隔);None=-0.2,0,0.2"),
)

# ── 逐协议:专属测量旋钮 + reps + 停门,再拼接公共组 ──────────────────────────
_STAGE_PARAMS: dict[str, tuple[ParamSpec, ...]] = {
    "S0": (_reps("s0_reps", 5, "重复次数"), _ig_stop("s0_ig_stop_uA", 5.0),
           *READ_VG, *COMMON),
    "S1": (_reps("s1_reps", 20, "重复次数"), _ig_stop("s1_ig_stop_uA", 5.0),
           *READ_VG, *COMMON),
    "E1": (_reps("e1_reps", 3, "重复次数"), _ig_stop("e1_ig_stop_uA", 20.0),
           _p("e1_wide_vg", K.BOOL, False, label="宽 Vg 网格读", vis=V.ADVANCED,
              widget=W.CHECKBOX, help="用 E5 宽 Vg 网格读,替代默认 [-0.2,0,0.2]"),
           _p("e1_full_delays", K.BOOL, False, label="全延迟序列", vis=V.ADVANCED,
              widget=W.CHECKBOX, help="用 DELAYS_FULL(到 10s)替代 QUICK300(到 300ms)"),
           *WRITE, *COMMON),
    "E2": (_reps("e2_reps", 2, "重复次数"), _ig_stop("e2_ig_stop_uA", 20.0),
           *WRITE, *COMMON),
    "E3W": (_reps("e3_reps", 3, "重复次数"), _ig_stop("e3_ig_stop_uA", 30.0),
            _p("e3_widths", K.FLOAT_LIST, ",".join(str(x) for x in E3_WIDTHS),
               label="脉宽扫描点", unit="s", widget=W.CSV_LINE, vis=V.BASIC,
               help="E3W 固定 ±5 V,扫这些脉宽(逗号分隔,顺序保留)"),
            _p("e3_delay_s", K.FLOAT, E3_DELAY, label="写后读延迟", unit="s", vis=V.ADVANCED,
               help="写脉冲到读取之间的延迟"),
            *COMMON),
    "E3A": (_reps("e3_reps", 3, "重复次数"), _ig_stop("e3_ig_stop_uA", 30.0),
            _p("e3_amps", K.FLOAT_LIST, ",".join(str(x) for x in E3_AMPS),
               label="幅值扫描点", unit="V", widget=W.CSV_LINE, vis=V.BASIC,
               help="E3A 固定 100 µs,扫这些幅值绝对值(逗号分隔,顺序保留)"),
            _p("e3_delay_s", K.FLOAT, E3_DELAY, label="写后读延迟", unit="s", vis=V.ADVANCED,
               help="写脉冲到读取之间的延迟"),
            *COMMON),
    "E4": (_reps("e4_reps", 3, "重复次数"), _ig_stop("e4_ig_stop_uA", 30.0),
           _p("e4_prebias_v", K.FLOAT_LIST, ",".join(str(x) for x in E4_PREBIAS_V),
              label="预偏压幅值集", unit="V", widget=W.CSV_LINE, vis=V.BASIC,
              help="预偏压电压(逗号分隔,顺序保留);默认 0,+2,-2"),
           _p("e4_prebias_s", K.FLOAT_LIST, ",".join(str(x) for x in E4_PREBIAS_S),
              label="预偏压持续集", unit="s", widget=W.CSV_LINE, vis=V.BASIC,
              help="每个预偏压的持续时间(逗号分隔,顺序保留)"),
           _p("e4_post_delay_s", K.FLOAT, E4_POST_DELAY, label="写后读延迟", unit="s",
              vis=V.ADVANCED, help="写脉冲到读取之间的延迟"),
           *COMMON),
    "E5": (_reps("e5_reps", 3, "重复次数"), _ig_stop("e5_ig_stop_uA", 20.0),
           _p("vg_e5", K.FLOAT_LIST, ",".join(str(x) for x in VG_E5),
              label="读出 Vg 网格", unit="V", widget=W.CSV_LINE, vis=V.BASIC,
              help="E5 读窗 Vg 扫描网格(逗号分隔,顺序保留);也是各协议宽 Vg 网格"),
           _p("vd_e5", K.FLOAT_LIST, ",".join(str(x) for x in VD_E5),
              label="读出 Vd 集", unit="V", widget=W.CSV_LINE, vis=V.BASIC,
              help="E5 读窗 Vd 集(逗号分隔)"),
           _p("delays_e5", K.FLOAT_LIST, ",".join(str(x) for x in DELAYS_E5),
              label="写后读延迟集", unit="s", widget=W.CSV_LINE, vis=V.BASIC,
              help="E5 写后到读的延迟集(逗号分隔,顺序保留)"),
           *WRITE, *COMMON),
    "E6R": (_reps("e6r_reps", 3, "重复次数"), _ig_stop("e6r_ig_stop_uA", 20.0),
            *WRITE, *COMMON),
    "E6D": (_reps("e6d_reps", 3, "重复次数"),
            _p("e6d_amps", K.FLOAT_LIST,
               ",".join(str(x) for x in DISTURB_AMPS_DEFAULT),
               label="扰动幅值集", unit="V", widget=W.CSV_LINE, vis=V.BASIC,
               help="扰动绝对幅值(逗号分隔);符号与初态相反"),
            _p("e6d_delays", K.FLOAT_LIST,
               ",".join(str(x) for x in DISTURB_DELAYS_DEFAULT),
               label="扰动-读延迟集", unit="s", widget=W.CSV_LINE, vis=V.BASIC,
               help="扰动到读取的延迟(逗号分隔,秒)"),
            _p("e6d_width_s", K.FLOAT, DISTURB_WIDTH, label="扰动脉宽", unit="s",
               vis=V.BASIC, help="扰动脉冲宽度"),
            _p("e6d_wide_vg", K.BOOL, False, label="宽 Vg 网格读", vis=V.ADVANCED,
               widget=W.CHECKBOX, help="扰动读用 E5 宽 Vg 网格"),
            _p("e6d_randomize", K.BOOL, True, label="随机化顺序", vis=V.ADVANCED,
               widget=W.CHECKBOX, help="随机化延迟顺序"),
            _ig_stop("e6d_ig_stop_uA", 30.0),
            *WRITE, *COMMON),
    "CYCLE": (_p("cycle_count", K.INT, 100000, label="循环总数", vis=V.BASIC,
                 widget=W.SPINBOX, minimum=1, help="ERS/PGM 耐久循环总次数"),
              _p("cycle_checkpoints", K.INT_LIST,
                 ",".join(str(x) for x in CYCLE_CHECKPOINTS_DEFAULT),
                 label="检查点", widget=W.CSV_LINE, vis=V.BASIC,
                 help="在这些循环数处测 ERS/PGM 回读(逗号分隔)"),
              _p("cycle_wide_vg", K.BOOL, False, label="宽 Vg 网格读", vis=V.ADVANCED,
                 widget=W.CHECKBOX, help="检查点读用 E5 宽 Vg 网格"),
              _ig_stop("cycle_ig_stop_uA", 30.0),
              *COMMON),
    "MLC": (_reps("mlc_reps", 3, "重复次数"),
            _p("mlc_amps", K.FLOAT_LIST,
               ",".join(str(x) for x in MLC_AMPS_DEFAULT),
               label="编程幅值集", unit="V", widget=W.CSV_LINE, vis=V.BASIC,
               help="正编程幅值(逗号分隔),扫这些幅值出多值;对应 PPT② 1.5~3.8V"),
            _p("mlc_v_erase", K.FLOAT, MLC_V_ERASE, label="擦除幅值", unit="V", vis=V.BASIC,
               help="每发编程前的固定擦除幅值(绝对值,实际打负),reset 到同起点"),
            _p("mlc_width_s", K.FLOAT, MLC_PULSE_WIDTH, label="擦/写脉宽", unit="s", vis=V.BASIC,
               help="擦除/编程脉宽;PPT② 50µs"),
            _p("mlc_read_vg", K.FLOAT, MLC_READ_VG, label="读 Vg", unit="V", vis=V.BASIC,
               help="编程后单点读的 Vg;PPT③ 0.5V"),
            _p("mlc_vd_read", K.FLOAT, MLC_READ_VD, label="读 Vd", unit="V", vis=V.BASIC,
               help="编程后单点读的 Vd;PPT③ 0.1V"),
            _p("mlc_delay_s", K.FLOAT, MLC_DELAY, label="编程→读延迟", unit="s", vis=V.ADVANCED,
               help="编程脉冲到读取之间的延迟"),
            _p("mlc_n_pts", K.INT, DEFAULT_N_PTS, label="读平均点数", vis=V.ADVANCED, widget=W.SPINBOX,
               minimum=1, help="单点读的硬件平均采样点数"),
            _ig_stop("mlc_ig_stop_uA", 30.0),
            *COMMON),
    "ISPP": (_p("ispp_vg_start", K.FLOAT, ISPP_VG_START, label="起始编程幅值", unit="V", vis=V.BASIC,
                help="闭环第一发程序脉冲幅值"),
             _p("ispp_vg_step", K.FLOAT, ISPP_VG_STEP, label="幅值步进", unit="V", vis=V.BASIC,
                help="每步抬高的幅值增量"),
             _p("ispp_vg_max", K.FLOAT, ISPP_VG_MAX, label="幅值上限", unit="V", vis=V.BASIC,
                help="到此幅值仍未达标即停(安全 + 终止)"),
             _p("ispp_max_steps", K.INT, ISPP_MAX_STEPS, label="步数上限", vis=V.BASIC,
                widget=W.SPINBOX, minimum=1, help="闭环最多迭代步数(保证终止)"),
             _p("ispp_target_id_uA", K.FLOAT, ISPP_TARGET_ID_UA, label="目标 |Id|", unit="µA", vis=V.BASIC,
                help="读 Vg 下 |Id| 达到/超过即收敛停"),
             _p("ispp_id_tol_uA", K.FLOAT, ISPP_ID_TOL_UA, label="饱和阈 |ΔId|", unit="µA", vis=V.ADVANCED,
                help="相邻两步 |ΔId| 低于此 = 无进展即停"),
             _p("ispp_v_erase", K.FLOAT, ISPP_V_ERASE, label="起始擦除幅值", unit="V", vis=V.BASIC,
                help="闭环前擦到统一起点(绝对值,实际打负)"),
             _p("ispp_width_s", K.FLOAT, ISPP_WIDTH, label="脉宽", unit="µs", vis=V.BASIC,
                help="编程/擦除脉冲宽度"),
             _p("ispp_read_vg", K.FLOAT, ISPP_READ_VG, label="读 Vg", unit="V", vis=V.BASIC,
                help="每发后单点读的 Vg"),
             _p("ispp_vd_read", K.FLOAT, ISPP_VD_READ, label="读 Vd", unit="V", vis=V.BASIC,
                help="每发后单点读的 Vd"),
             _p("ispp_read_delay_s", K.FLOAT, ISPP_READ_DELAY, label="编程→读延迟", unit="µs", vis=V.ADVANCED,
                help="程序脉冲到读取的延迟"),
             _ig_stop("ispp_ig_stop_uA", 30.0),
             *COMMON),
}


# ── SMU(DC)族 ParamSpec(增量6b)。cli_flag=None = GUI/引擎专用、不进 WGFMU CLI,
#    故 test_registry_params 的 argparse 比对自动跳过(且 DC 段不在其 STAGES 内,双保险)──
def _dcp(name, kind, default, *, label, unit="", vis=V.BASIC, widget=W.DOUBLE_SPINBOX,
         choices=None, minimum=None, help=""):
    return ParamSpec(name=name, label=label, kind=kind, default=default, unit=unit,
                     visibility=vis, minimum=minimum, maximum=None, choices=choices,
                     widget=widget, cli_flag=None, help=help)


_META_SMU = {
    "DC_IDVG": ("DC 转移特性 Id-Vg(SMU)", "transfer"),
    "DC_IDVD": ("DC 输出特性 Id-Vd(SMU)", "output"),
}

_DC_COMMON = (
    _dcp("gate_ch", K.INT, 4, label="Gate 通道(SMU)", vis=V.LOCKED, widget=W.CHANNEL,
         help="SMU Gate 通道;dry MockB1500 在 ch4 仿真"),
    _dcp("drain_ch", K.INT, 5, label="Drain 通道(SMU)", vis=V.LOCKED, widget=W.CHANNEL,
         help="SMU Drain 通道;dry MockB1500 在 ch5 仿真"),
    _dcp("smu_s_ch", K.INT, 6, label="Source 通道(SMU)", vis=V.LOCKED, widget=W.CHANNEL,
         help="SMU Source 通道"),
    _dcp("dc_vs_fixed", K.FLOAT, 0.0, label="Vs 固定", unit="V"),
    _dcp("live", K.BOOL, False, label="联机(真机)", vis=V.ADVANCED, widget=W.CHECKBOX,
         help="SMU live 待器件;dry 用 MockB1500"),
)

_SMU_PARAMS = {
    "DC_IDVG": (
        _dcp("dc_vg_points", K.FLOAT_LIST, "0,-0.5,-1.0,-1.5,-2.0", label="Vg 扫描点", unit="V",
             widget=W.CSV_LINE, help="Id-Vg 的 Vg 扫描点(逗号分隔)"),
        _dcp("dc_vd_fixed", K.FLOAT, -0.1, label="Vd 固定", unit="V", help="Id-Vg 的固定 Vd"),
        *_DC_COMMON,
    ),
    "DC_IDVD": (
        _dcp("dc_vg_points", K.FLOAT_LIST, "0,-1.0,-2.0", label="Vg 偏置点", unit="V",
             widget=W.CSV_LINE, help="Id-Vd 的各 Vg 偏置(逗号分隔)"),
        _dcp("dc_vd_points", K.FLOAT_LIST, "0,-0.2,-0.4,-0.6,-0.8,-1.0", label="Vd 扫描点", unit="V",
             widget=W.CSV_LINE, help="Id-Vd 的 Vd 扫描点(逗号分隔)"),
        *_DC_COMMON,
    ),
}


def _build_registry() -> dict[str, ProtocolSpec]:
    registry: dict[str, ProtocolSpec] = {}
    for sid, sspec in STAGE_REGISTRY.items():
        title, physics = _META.get(sid, (sid, ""))
        registry[sid] = ProtocolSpec(
            id=sid,
            title=title,
            family="WGFMU",
            physics=physics,
            description=sspec.description,
            params=_STAGE_PARAMS.get(sid, ()),
            csv_schema="fefet_fixedcols",
            output_label=sspec.output_label,
            runner=sspec.runner,
        )
    # ── SMU(DC)族(增量6b):纯加法,WGFMU 循环一字不动 ──
    from ..protocols.smu_dc import SMU_STAGE_REGISTRY
    for sid, sspec in SMU_STAGE_REGISTRY.items():
        title, physics = _META_SMU.get(sid, (sid, ""))
        registry[sid] = ProtocolSpec(
            id=sid,
            title=title,
            family="SMU",
            physics=physics,
            description=sspec.description,
            params=_SMU_PARAMS.get(sid, ()),
            csv_schema="dc",
            output_label=sspec.output_label,
            runner=sspec.runner,
        )
    return registry


REGISTRY: dict[str, ProtocolSpec] = _build_registry()

__all__ = ["REGISTRY"]
