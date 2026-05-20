# 本次会话遗留问题清单 (B1500 + Hermes vision)

> 创建: 2026-05-20 ~07:30 CST
> 上下文: yhzang 真机 D:\test\B1500 已 pull + venv + 11 个 wgfmu 测试通过, 即将连 B1500 跑 notebook 20-23
> 这份清单专门记录"今天不修, 测完后一起解决"的小坑

---

## 🔧 待修 1: tests/test_verify_dc_sweep_script.py 不在 PYTHONPATH

**症状**:
```
ModuleNotFoundError: No module named 'scripts.verify_dc_sweep'
```

**根因**: tests 用了 `from scripts.verify_dc_sweep import ...`,
但 `scripts/` 目录不在包里, 也不在 sys.path 中。

**和今天任务的关系**: 无关 (WGFMU 测试不依赖它), 但 `pytest tests/ -q` 全量跑会被中断。

**临时绕过** (今天用的):
```powershell
pytest tests/ -q --ignore=tests/test_verify_dc_sweep_script.py
# 或
pytest tests/test_wgfmu_iv_and_wakeup.py tests/test_wgfmu_scaffold.py -q
```

**正式修法选项 (待 yhzang 测完决定)**:
- A) 在 `conftest.py` 加 `sys.path.insert(0, str(Path(__file__).parent.parent))`
- B) 把 `scripts/` 改成 `src/fefetlab/scripts/` 进包
- C) 测试文件改 `import importlib.util` 动态加载, 不走 `from scripts...`

推荐 A (最小侵入, 不动业务代码)。

---

## 🔧 待修 2: vision_analyze auxiliary 修复经验落 skill

**症状**: gpt-5.5 文字能调通但带图就超时, 切 gpt-5-vision 后即解
**修法**: 已切 sub2gpt + gpt-5-vision + timeout 120s 落到 ~/.hermes/config.yaml
**遗留**: 应在 `hermes-auxiliary-and-vision-fixes` skill 加"症状 D: 同 provider 文字过但图挂",
        防止下次再栽

**优先级**: 中 (vision 已能用, 但 skill 没更新会重复踩)

---

## 🎨 待做 3: H6 能带图 v2 → v3 精修

**v2 状态**: 物理正确性 + 排版全过, vision 评估"像 IEEE 风格"
**v3 改进点** (基于 vision 反馈):
- (c)(d) 局部注释偏密 → 删 "large |E_FE,eff|" 等次要箭头
- 字号统一 (标题/标签/电荷符号一致)
- 留更多白 (符合 Nature 标准)

**产物路径** (v2 当前):
- `C:\Users\Administrator\matlab_work\p4_fefet\h6_banddiagram_v2\`
  - `draw_h6_v2.py` (265 行源码)
  - `H6_pfefet_banddiagram_v2.png`
  - `H6_pfefet_banddiagram_v2.pdf`

**v3 完成后归档**:
- `G:\我的云端硬盘\阿耶工作区\项目4_FEFET测试\figures\h6_banddiagram_v3\`
- 更新 `理论分析/2026-05-19_负MW物理机制分析_v2.md` 里 Fig.5 引用

**优先级**: 中 (v2 已能用, v3 只是精修)

---

## 🐛 待查 4: 本次会话 tool API 抽风

会话中多次出现:
```
Error executing tool: Error during OpenAI-compatible API call #N: 'str' object has no attribute 'get'
```

跨工具命中过 `todo` / `read_file` / `skill_view`。重试都能过, 不是工具本身问题, 像是 provider 路由层的瞬时抖动。

**优先级**: 低 (重试都能恢复), 但累积起来很烦, 可以查一下 hermes 这段时间用的 sub2ccmax5 是不是哪台后端在抽

---

## 📂 文档导航 (复习用)

**B1500 项目权威**:
- 真机测试计划: `_agent/runbooks/wgfmu-real-device-test-plan.md`
- 项目状态: `_agent/01_State.md`
- handoff: `_agent/05_Handoff.md`

**项目4 总台权威**:
- `_agent/01_State.md`
- 器件基准: `真实器件基准/device_baseline_pfefet.md`
- 物理约定: `_agent/references/fefet_physics_conventions.md`
- 负 MW 机制: `理论分析/2026-05-19_负MW物理机制分析_v2.md`
- WGFMU 实验设计: `理论分析/2026-05-19_WGFMU实验设计_v1.md`
- 变量映射: `理论分析/2026-05-20_变量物理含义与测试映射_v1.md`

**今天 yhzang 真机操作清单**:
1. D:\test\B1500 (已 pull)
2. venv 已建 (.venv, Python 3.13)
3. pip install 已过 (清华镜像 + --trusted-host)
4. wgfmu 测试已过 (11 passed)
5. 待跑: notebooks 20 -> 22 -> 21 -> 23

每跑完发 "XX PASS" 或截图。
