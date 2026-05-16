# B1500 本地环境初始化与最小验证

## Purpose
在阿耶工作区里的 B1500 项目副本上，恢复一个可运行的本地 Python 环境，并做最小模拟验证。

## Preconditions
- 工作目录：`/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500`
- 当前副本可能没有 `.venv`
- 当前副本可能不是 git 工作树
- 本 runbook 只处理本地环境与模拟验证，不直接处理真实硬件

## Steps
### 推荐：手动最小安装
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500'
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements/dev.txt
pip install -e .
PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 python scripts/verify_dc_sweep.py
```

### 备选：项目自带脚本
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500'
bash setup.sh
```

## Verification
- `.venv` 成功创建并可激活
- `python -c "import pyvisa"` 不再报错
- `python scripts/verify_dc_sweep.py` 不再停在 `ModuleNotFoundError: No module named 'pyvisa'`
- 如果仍失败，应记录新的第一处错误，而不是一次性展开所有问题

## Rollback / Recovery
- 如安装过程损坏，可删除 `.venv` 后重建：
```bash
cd '/mnt/g/我的云端硬盘/阿耶工作区/项目3_B1500自动化/B1500'
rm -rf .venv
python3 -m venv .venv
```

## Common failures
- `ModuleNotFoundError: No module named 'pyvisa'`
  - 原因：未先安装 `requirements/dev.txt`
  - 处理：激活 `.venv` 后重新执行 `pip install -r requirements/dev.txt`

- `pip install -e .` 成功但运行仍缺依赖
  - 原因：`pyproject.toml` 当前未声明 runtime dependencies
  - 处理：不要只依赖 editable install，必须先装 requirements

- 真实硬件相关错误
  - 当前不在本 runbook 范围内
  - 先把模拟验证恢复，再进入 `configs/instruments.yaml` / `configs/channel_map.yaml` / `src/scripts/connect_test.py` 排查

## Links
- `README.md`
- `TESTING.md`
- `_agent/01_State.md`
- `_agent/02_Plan.md`
