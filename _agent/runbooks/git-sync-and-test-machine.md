# Runbook · B1500 代码同步 + 测试机驱动（git / 代理 / scp）

> 用途：把分析机改好的脚本可靠地送到测试机（B1500 上机用），避免"老卡在 git 这一步"。
> 建：2026-06-04。

## 机器拓扑（Tailscale）
| 机器 | Tailscale IP | 角色 | 备注 |
|---|---|---|---|
| 工位/分析机 | `100.72.133.4` | 开发、改代码、push | Google Drive 挂 `G:`；git 仓库 `G:\…\项目3_B1500自动化\B1500` |
| 测试机 | `100.108.189.9`（`desktop-bpj59bj`） | 接 B1500 上机测器件 | **公司公共电脑**；SSH 免密 `ssh administrator@100.108.189.9`；venv `D:\test\B1500\.venv`；**不挂 Drive、不登账号** |

## git 仓库 + 代理
- 源仓库：`G:\…\项目3_B1500自动化\B1500`，remote `github.com/yhzang/B1500.git`，分支 `main`。
- **直连 github 被 GFW 卡（TCP 通但 TLS 握手被丢）→ git 必须走本机代理**：
  - 本机 Clash 代理 `http://127.0.0.1:7897`（端口可能随 Clash 配置变；用 `Test-NetConnection 127.0.0.1 -Port 7897` 确认开着）。
  - push：`git -C <repo> -c http.proxy="http://127.0.0.1:7897" -c https.proxy="http://127.0.0.1:7897" push origin main`

## ⚠ 测试机 git 是岔开的 —— 别 pull，用 scp
- 测试机仓库停在 5-28 老分支（HEAD `7389f01`），和 origin 完全两条线；`wgfmu_single_shot_disturb.py` 在测试机 **untracked**，`wgfmu_next_round_minimal.py` 有未提交本地改动。→ `git pull` 会因 "untracked 文件被覆盖 + 历史分叉" **报错/冲突**。
- **正解：scp 直接覆盖两个脚本（先 `.bak` 备份），不碰它的 git。** 测试机只要 `.py` 跑对就行，git 历史无所谓。

### 标准同步流程（分析机改 → 测试机生效）
1. 只改 `G:\…\项目3\B1500\scripts\*.py`（唯一源）；`python -m py_compile` + dry-run 测试通过。
2. commit + push（走代理，见上）。
3. 备份 + scp 到测试机 + 验哈希：
   ```powershell
   $h="administrator@100.108.189.9"; $dir="G:\我的云端硬盘\阿耶工作区\项目3_B1500自动化\B1500\scripts"
   $f="wgfmu_single_shot_disturb.py"   # 每个文件重复
   ssh $h "copy /Y D:\test\B1500\scripts\$f D:\test\B1500\scripts\$f.bak_YYYYMMDD"
   scp "$dir\$f" "${h}:D:/test/B1500/scripts/$f"
   # 验：两边 SHA256 必须一致
   (Get-FileHash "$dir\$f").Hash
   ssh $h "certutil -hashfile D:\test\B1500\scripts\$f SHA256"
   ```
4. 项目4 的文档/数据/报告走 **Google Drive 自动同步**（仅分析机/宿舍机）；测试机不挂 Drive，要的数据自己拷。

## 官方文档（量程 / 编程规范）位置
- **WGFMU 模块手册**：`G:\…\项目3_B1500自动化\B1500手册\keysight-b1530a-series-user-guide.pdf`（**B1530A = WGFMU**；量程、测量时序、FASTIV 看这本）。
- 编程指南：`B1500手册\B1500-90010_Programming_Guide_9018-01851.pdf`、`b1500 program guide\9018-0185x.pdf`。
- 代码侧量程规范：`src/fefetlab/measurements/wgfmu/real_backend.py` → `MEASURE_CURRENT_RANGE_MAP`（`1UA/10UA/100UA/1MA/10MA`）；force range / measure mode 同文件。

## 读出电流量程（2026-06-04 新增 `--read-irange-drain/gate`）
- base 原把读量程写死 `1MA`（1 mA）；读 ~µA 信号落 0.1% 量程，分辨率噪声主导 → **疑似 `Id_std≈Id_mean` 主因**。
- 脆弱点建议 `--read-irange-drain 100UA`（安全，< 30µA 停门不钳位）或 `10UA`（读数稳 <10µA 时 SNR 最佳）。WGFMU `set_measure_current_range` 即固定量程（非 autorange）。
- WGFMU（B1530A）是快速脉冲 IV，测量速度与量程基本无关（量程定满量程/分辨率，不定采样速度），5µs 读窗够用；**以 B1530A 手册为准**，首颗点看 `Id_std` 是否随降量程显著下降做实证确认。

## 单写纪律（脆弱 L10，2026-06-04）
- `--write-state ERS|PGM|BOTH`：默认 BOTH = 写 ERS 再写 PGM（2 次满幅反极性写/器件，**会触发击穿**）。脆弱点**用 `--write-state ERS`（或 PGM）单写一次**；MW 靠"一颗 ERS 点 vs 一颗 PGM 点"配对得到。E6M 用 `--e6m-state`。
- 停门已修：中途 `|Ig|` 超阈值会先把已采到的行落盘再 raise（不丢首炮数据）。
