# 项目3 压缩恢复点 (05_Handoff)

> 当一次会话即将结束、要切换设备/换模型/隔一段时间再回来时，在这里写一段"接力棒"。
> 格式：倒序追加，最新在最上面。每次开场新会话先读 `01_State.md` + 本文件最顶 1-2 条即可。

---

## 2026-05-16 05:30 → WGFMU 编码完成 · 等真机

**这次干了什么**：把 WGFMU 模块补齐到与 DC 链路对称的结构（驱动层 + 波形构建 + 测量协议 + 导出）。和椰椰对齐后，移除了之前误加的 demo 画图/假物理模型/汇报文档。

**真机怎么连**：和 DC 完全一样的 VISA 路径。
```python
from fefetlab.measurements.wgfmu import RealWgfmuBackend, WgfmuIVSweepRunner, ...

backend = RealWgfmuBackend()                  # ctypes 自动找 wgfmu.dll
backend.open_session("GPIB0::17::INSTR")      # 跟 DC 用同一 VISA 资源
# 之后 IV sweep / wake-up runner 都走同一个 backend
```

**测试基线**：基线 25 → 33 passed（新增 8 用例，无回归）。

**核心新文件**（4 个 .py + 1 个测试）：
- `src/fefetlab/measurements/wgfmu/real_backend.py` — 驱动层（27 个 C API）
- `src/fefetlab/measurements/wgfmu/pulse_builder.py` — 波形构建
- `src/fefetlab/measurements/wgfmu/iv_sweep.py` — IV sweep runner
- `src/fefetlab/measurements/wgfmu/wakeup.py` — wake-up runner
- `tests/test_wgfmu_iv_and_wakeup.py` — 6 个契约测试

**git 状态**：本地已 commit（之前推不上去），需要椰椰起床在 Windows 端：
```powershell
cd "G:\我的云端硬盘\阿耶工作区\项目3_B1500自动化\B1500"
git push origin main
```

**下次开场要确认**：
- 真机那台 git pull 后是否成功连上 B1500
- 是否进入项目4 R1-A 真实数据回流环节

**地雷 / 已知坑**：
- `RealWgfmuBackend` 只能在 Windows + 装了 Keysight B1530A WGFMU 驱动的机器上 `.load()`。Linux/macOS 上 import OK 调用爆，这是设计预期
- 真机 dll 的 C API 签名若与 User Guide 文档有出入，按错误现象调 `real_backend.py` 里的 `argtypes`
- 当前覆盖 27 / 95 个 WGFMU2 C API，足够 R1-A + R1-B；若后续要 raw 数据 / trigger out / DC bias hold，在 `real_backend.py` 加 `_bind(...)`
- 本机 WSL，G 盘是 Google Drive 挂载，不支持 symlink → 不能在 G 盘建 venv

**测试人是谁**：臧沂豪 (yhzang@mail.ustc.edu.cn)，不是椰椰本人。

---

## (历史 handoff 在这里追加)

(2026-04-28 06:33 那条已合入 01_State，不再保留)
