# 预注册时间戳锚 · 2026-06-08

> 本文件唯一用途：为 FeFET 读出投影模型的预注册预测清单提供**外部时间证据**。
> 借用本仓库是因为它是当前唯一带 GitHub remote 的 git 仓库——push 后 GitHub
> 服务器记录的时间即第三方时间戳（证据第二条腿）。

## 被锚定对象

- 文件：`项目2_FEFETva模型\_claude_sandbox_读出投影v0\预注册_预测清单_20260608.md`
- **SHA-256: `E87BF3F08B53E60B3EC4019D38F179B515D1EC781760AD832DAC65924B9A5335`**
- 内容：读出投影模型 v0b 冻结参数给出的 4 条数值预测（先于轮 4 测量写就），
  判据预先写死（≥3/4 命中 → "样本外一致性"可升级为"预注册盲测通过"）。

## 时间证据三条腿

| # | 证据 | 性质 | 状态 |
|---|---|---|---|
| 1 | OpenTimestamps 日历回执 ×3（alice / bob / finney.eternitywall） | 独立第三方、密码学锚定（待 Bitcoin 聚合见证） | ✅ 2026-06-08 已取得，存 `_claude_sandbox_读出投影v0\timestamp_evidence_20260608\`（manifest.json + 3 × .bin） |
| 2 | 本文件的 GitHub push 时间戳 | GitHub 服务器记录 | 待 push（commit 即本条所在） |
| 3 | Google Drive 文件版本历史 | Google 服务器记录预注册文件的创建/修改时间 | 自动存在（Drive 网页端右键 → 版本管理可查证） |

## 验证方法

1. 对预注册文件计算 SHA-256，应等于上述哈希（文件任何一字未改）。
2. 腿 1：将哈希摘要与 .bin 回执交给任何 OTS 工具方重建/升级证明；
   腿 2：`git log` 本文件首次 commit + GitHub 上对应 push 事件时间；
   腿 3：Drive 版本历史界面直读。
