# 项目3 压缩恢复点 (05_Handoff)

> 当一次会话即将结束、要切换设备/换模型/隔一段时间再回来时，在这里写一段"接力棒"。
> 格式：倒序追加，最新在最上面。每次开场新会话先读 `01_State.md` + 本文件最顶 1-2 条即可。

---

## 2026-05-20 → L0+L1 全过 · 真机适配完成 · 等接器件做 RAWD

**这次干了什么**: yhzang 在新电脑 `D:\test\B1500` 把 WGFMU 链路从代码到真机全验通。`20_dryrun + 22_dryrun + 21_realdevice + 23_realdevice` 四个 notebook 全 PASS, 期间发现并修了 20 个真机适配 bug, 全部 push 到 GitHub。

**关键技术决策 (跟之前不一样)**:
- 真机 baseline 不是 0, 是 RSU+3m HRSU 电缆 + 探针卡的 **440kΩ 漏电路径**, 在 -0.5V 下表现为 ~1.14 µA, 跟电压成线性关系 (实测验证: 0V→11nA, -0.5V→1.14µA, t_rise 改 10x 无影响排除电容主导)
- 这个 baseline 在**栅极通道**(CH201) 上, 不影响**漏极通道**上的 Id 测量
- 项目 4 总台 R1 真正要做的是 **E1 RAWD** (write-after-delay 单点读), 不是传统 IDVG sweep — 必须用 **WGFMU 双通道** (CH201 Vg 脉冲 + CH202/301 Vd 测 Id 瞬态), SMU 跟不上 µs 级 read pulse

**新机器怎么准备**:
```powershell
# 1) 装 Keysight IO Libraries Suite (VISA)
# 2) 装 NI-488.2 GPIB driver (Keysight VISA 不够)
# 3) 装 Keysight B1530A Instrument Library 64-bit (dll 落到 C:\Windows\System32\wgfmu.dll)
# 4) 拉代码
cd <work_dir>
git clone https://github.com/yhzang/B1500.git
cd B1500
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
# 5) 跑测试
pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q  # 期望 11 passed
# 6) 跑 notebook 20→22→21→23
jupyter notebook notebooks/
```

**地雷 / 已知坑** (今天踩过的, 都修了或文档化了):
- PowerShell `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` 要先放行才能激活 venv
- pip 装包: 必须加 `--trusted-host` 或用清华镜像, 不然 SSL 证书错
- B1500 GPIB-USB 偶发 hang, 拔插一次 USB 即恢复
- 双 GPIB 卡时 list_resources 返回 GPIB0 + GPIB1, 真 B1500 可能在 GPIB1 (用 `autodetect_visa_addr("B1500")` 自动找)
- WGFMU CH 没接 RSU 不能 FASTIV: 报 `RSU is not connected; CHANNELxxx` (yhzang 本机 302 没接 RSU)
- WGFMU.cs 真值: enum 全是 offset+小数字 (2000+, 3000+, 4000+, 5001+, 6001+, 7000+, 12000+, 1000+), 不是 0/1/2
- 第一版 real_backend.py 所有 enum 全错 (已修)
- WSL G 盘是 Google Drive 挂载, 不支持 symlink, venv 必须建在本地盘

**下次开场要确认**:
- yhzang 准备好器件 (L10W10, 接 WGFMU 双通道 + RSU + 探针) 了吗
- 明天目标: 写 `24_wgfmu_rawd_device.ipynb` (E1 RAWD 简版 5 个 t_delay 点) → 真器件跑通

**E1 RAWD 设计参数** (要 yhzang 明天确认的):
- Vg 通道: CH201 (已知接 RSU)
- Vd 通道: CH202 或 CH301 (yhzang 明天确认实物接线)
- ERS pulse: +5V / 50µs (yhzang 4 月成功过)
- PGM pulse: -5V / 30µs
- read pulse: Vg = -0.5V / 5µs, Vd = -50 mV 恒定
- t_delay 简版: 1µs / 10µs / 100µs / 1ms / 10ms (5 点验 setup)
- t_delay 完整: 17 点 (1µs → 100s, 半 decade)

**测试人**: **yhzang (本人)**, 不是别人

---

## 2026-05-16 → WGFMU 编码完成 · 等真机 (已合入历史, 由 2026-05-20 取代)

(详见上)
