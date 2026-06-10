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
  - push：`git -C <repo> -c http.sslBackend=openssl -c http.proxy="http://127.0.0.1:7897" -c https.proxy="http://127.0.0.1:7897" push origin main`
  - **⚠ 必须带 `-c http.sslBackend=openssl`（2026-06-11 实证）**：默认 Windows 原生 schannel 后端走 Clash 代理会报 `schannel: failed to receive handshake, SSL/TLS connection failed`；切 openssl 后端即通。代理端口开着但 push 仍握手失败，先怀疑这条。

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

## 测试机 SSH 连接 SOP（2026-06-09 凌晨沉淀 · 踩坑全记录）

> 测试机关机再开机后，远程 SSH 会连续卡在四层。2026-06-09 凌晨逐层踩通，固化如下。**按顺序查，别跳。**

**从分析机视角，远程 SSH 不通的四层：**

1. **Tailscale 数据面**：开机后控制面很快标 `active`，但数据隧道要时间重建。以 `tailscale ping 100.108.189.9` 出现 `pong`（via DERP 即可）为 L3 通的判据；只 `active` 不算（`tx>0 rx=0` = 隧道没通）。
2. **shields-up**：已持久设 `false`（2026-06-08）。若又被开 → 测试机 `tailscale set --shields-up=false`。
3. **sshd 服务**：已设 `Automatic`（开机自启）。若没起 → 测试机 `Start-Service sshd`；确认 `Get-NetTCPConnection -LocalPort 22 -State Listen` 有 `0.0.0.0:22`。
4. **防火墙 WFP 层（真拦路虎，本地无法根治）**：标准防火墙里**无 block 规则、加 port-22 allow 也无效**——挡 22 的是 WFP 层企业安全软件/EDR（`Get-NetFirewallRule` 看不到）。**唯一可靠解 = 临时整体关防火墙**：
   - 连前（测试机，管理员）：`Set-NetFirewallProfile -All -Enabled False`
   - 用完开回：`Set-NetFirewallProfile -All -Enabled True`
   - 关闭窗口内 TCP 22 立即可达，开回即恢复管控。**这是唯一 100% 验证管用的办法，别再试加防火墙规则（已证无效）。**

**连通后拉数据 / 部署（分析机，免密）**：
- 验远端哈希：`ssh administrator@100.108.189.9 "certutil -hashfile D:\test\B1500\scripts\<f>.py SHA256"`
- 拉 run 目录：`scp -r administrator@100.108.189.9:D:/test/B1500/runs/live/<dir> "<本地目标>"`（单目录逐个，tar/多路径不工作）。
- **快速判活（分析机）**：`tailscale ping -c2 100.108.189.9`（L3）+ TcpClient 测 22（L4）。L3 通 L4 不通 = 防火墙没关。
