"""randomize_delays 可见开关:出现在参数里,且 E3W 真的随其开关改变顺序(默认 True 保金标准)。"""
from __future__ import annotations


def test_randomize_delays_is_visible_param():
    from fefetlab.engine import REGISTRY
    from fefetlab.engine.specs import ParamKind, Visibility

    p = {x.name: x for x in REGISTRY["E1"].params}
    assert "randomize_delays" in p
    rd = p["randomize_delays"]
    assert rd.kind is ParamKind.BOOL and rd.default is True
    assert rd.visibility is Visibility.ADVANCED


def _run_e3w(tmp_path, randomize, tag):
    import pandas as pd

    from fefetlab.engine import ProtocolEngine
    from fefetlab.protocols.wgfmu_fefet import make_backend, parse_args

    params = vars(parse_args([]))
    params["randomize_delays"] = randomize
    params["e3_reps"] = 1
    params["out_root"] = str(tmp_path / tag)
    bk, _ = make_backend(False)
    try:
        summ = ProtocolEngine().run("E3W", params, backend=bk)
    finally:
        try:
            bk.close_session()
        except Exception:  # noqa: BLE001
            pass
    return pd.read_csv(summ.out_csv)


def _norm(df):
    # 抹掉随运行时刻变化的列(timestamp_iso),只比"协议产出"本身——否则两次跨秒就假阳性。
    return df.drop(columns=["timestamp_iso"], errors="ignore").reset_index(drop=True)


def test_e3w_honors_randomize_flag(tmp_path):
    a = _norm(_run_e3w(tmp_path, False, "n1"))
    b = _norm(_run_e3w(tmp_path, False, "n2"))
    c = _norm(_run_e3w(tmp_path, True, "r1"))
    assert a.equals(b)          # 关随机化 → 完全确定(两次一致)
    assert not a.equals(c)      # 开/关 → 行顺序不同,证明 flag 真生效
