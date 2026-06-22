# 项目5:FeFET 瞬态表征自动化框架(fefetlab)——为什么必须自研而非用 EasyEXPERT

> 求职亮点版分析。2026-06-22,多智能体研究(EasyEXPERT/B1530A 手册挖掘 + FeFET 瞬态需求 + 怀疑论审稿 → 综合)产出。
> 论点支点已按"经得起内行追问"标准锚定:不卖"EasyEXPERT 测不到瞬态/自研更快",而卖**可编排性(per-shot 编排 + 闭环门禁 + 多阶段自动化)**这条真正的硬边界。

---

## 1. 一句话关键问题(crux)

**EasyEXPERT 的根本短板不是"老"、也不是"测不到瞬态",而是它的抽象层只暴露到"预制开环模板 + 等距采样网格"这一级——它无法把"延迟当作扫描轴、在波形任意时刻逐点放测量事件、按实时测量结果逐炮决策"表达出来;而 FeFET 动态表征的命门恰恰全在这一层。**

更精确地说,EasyEXPERT 把仪器能力封装成两种粒度:(a) SMU 通路的 Classic Test(sweep/list/sampling,等距 interval 网格);(b) WGFMU 的预制 Application Test 表单(固定 schematic + 数值参数槽)。两者都是**开环、预定义**的。FeFET 需要的"任意分段波形 + 事件级定时测量 + 数据相关的逐炮编排"落在这两种抽象的缝隙里——必须下沉到 `wgfmu.dll`(WGFMU2 C API)自己编排。**这是软件可表达性的边界,不是硬件速度或测量精度的边界。**

---

## 2. 为什么 EasyEXPERT 难做 FeFET 瞬态:分清"硬做不到" vs "能做但别扭"

### 2.0 先诚实承认:EasyEXPERT 能做好的部分(基线)

这块必须先说,否则后面所有话不可信。EasyEXPERT + B1500/B1530 本来就是为脉冲/瞬态设计的,以下它开箱即做、且有 Keysight 时序保证:

- **准静态 I-V / 转移 / 输出 / C-V**,内置 Auto Analysis 自动提 Vth/gm_max(公式可自定义)。
- **ms 级以上的 retention / I-t 弛豫**:SMU I/V-t Sampling,2 ms–655 s,支持 log 间隔、negative hold(pre-trigger)。FeFET 的慢 retention(ms 起)它能做。
- **WGFMU Application Test 模板**:Fast IV、Pulse IV、PUND、固定序列 endurance——这些常规脉冲测量都有官方模板,经校准,直接出图。
- **My Favorite 串联多个 test**——顺序播放列表式的弱自动化。

**结论基线:FeFET 里大部分"固定的"脉冲/瞬态测量,EasyEXPERT 够用。** 真正的边界在"非固定、数据相关、多阶段"那一类。

### 2.1 硬做不到(GUI/Application Test 无法表达,必须下沉 C API)

| 需求(FeFET 实际用到) | EasyEXPERT 为什么硬做不到 | 依据 |
|---|---|---|
| **延迟作为扫描轴**:写脉冲 → log/随机化的 µs–10s 延迟 → 读,延迟逐点扫 | Hold/Delay 是单个固定参数,GUI 无"以延迟为 VAR 的扫描轴";LOG 模式只用于连续采样网格,不能把"写-读对"的延迟本身排成 log/随机数组 | 训练手册 4-14/4-17/4-21 |
| **波形任意时刻放测量事件**(同一波形多个不同条件的读窗) | GUI 只有"统一 interval 的等距采样网格",无法在波形绝对时刻 t0 钉下独立读窗、更不能在一条波形上放多个 event | 训练手册;对比 `setMeasureEvent` |
| **数据相关的逐炮闭环**(write-verify/ISPP、自适应翻转点搜索、按测量值收敛的 program/erase) | 模板是开环预定义波形:仪器播放→回采,**无法"读到本炮结果→决定下一炮电压/延迟/是否继续"** | 这是最硬、最经得起追问的边界 |
| **per-shot 实时安全门禁**(每炮测完判 Id 是否超击穿阈→立即停后续脉冲护器件) | GUI 不给测量值驱动的中止插入点 | — |
| **多阶段实验链条件分支**(form→I-V→endurance→中途插 retention→再 endurance→fingerprint,状态机式) | My Favorite 是顺序播放列表,缺条件分支/循环变量/跨阶段状态传递 | — |
| 采样间隔 < 0.1 ms 直到 5 ns;写脉宽 < 0.5 ms / 周期 < 5 ms(SMU pulse 下限以下) | **注意:这是 SMU 通路的限制。** 走 GUI 的 WGFMU 模板硬件本身能到 ns 级,但模板的时序拓扑是固定的,改不了 | SMU pulse 4-5;I/V-t 4-14 |

> 关键澄清(避免自打脸):**WGFMU 在 EasyEXPERT Classic Test 里被官方明文排除**——B1530A 用户指南 1-2 NOTE:"the WGFMU is **not** supported by the EasyEXPERT Classic Test operation",只能通过预制 Application Test 模板或 Instrument Library(约 80 个 API)控制。所以"GUI 里能碰 WGFMU"仅限于改模板预留的数值参数槽,**改不了时序拓扑、加不了任意时刻的测量事件、做不了闭环**——要改就得进 Test Definition Editor 写脚本,而脚本本质还是调同一套 Instrument Library。即"想真正编排 WGFMU,无论如何都得编程"。

### 2.2 能做但别扭(不是硬限制,别说成"测不到")

- PUND、Fast IV、单脉冲 program/erase、固定序列 endurance、retention——**EasyEXPERT 能做**,自研只是参数化更灵活、批量更快、归档更统一。
- 数据导出/二次处理/画图笨——是后处理便利问题,不是测量能力问题。
- "模板里没现成的这个测试"——很多时候 GUI 拼得出,只是麻烦/学习成本,属"难用"非"不可表达"。

**自检判据**:问"下一步动作是否依赖上一步的测量结果?"
否(开环、预定义)→ EasyEXPERT 几乎都能做,自研只是顺手 → **别吹**;
是(闭环、data-dependent、per-shot 判定)→ GUI 真表达不了 → **可以理直气壮**。

---

## 3. 自研工具(fefetlab,直打 WGFMU2 C API)凭什么能做

fefetlab 把每个测量统一成同一骨架(见 `wgfmu_fefet.py` 的 `run_*_shot`):
`add_vector(...)` 拼栅/漏逐段波形(写脉冲 + 任意时长延迟 + 读窗)→ `set_measure_event(pattern, label, t0, n_pts, interval, average)` 在波形**绝对时刻 t0** 钉采样窗 → `execute / wait_until_completed / get_measure_values` 批量取回带时间戳 (time_s, value) → `_summarize_windows` 按时间窗切片求 Id_mean/Id_std。

能力对应到关键问题:

| 关键问题(GUI 表达不了) | fefetlab / WGFMU2 C API 怎么解 |
|---|---|
| 延迟作为扫描轴、log/随机化 | 延迟即波形上一段 `add_vector("gp", delay_s, 0.0)`,10 ns 分辨;延迟数组由程序自由计算(任意 log / 随机排序),逐炮跑 |
| 波形任意时刻多测量事件 | `setMeasureEvent` 的 time/points/interval 可在波形任意时刻放多个不同条件读窗(interval 10 ns–1.34 s) |
| 写脉冲 ≤100µs、sub-µs 边沿 | `createPattern`+`setVector` 10 ns 分辨;Fast IV 最窄脉冲 300 ns、PG 模式 100 ns;边沿 T_RF=100 ns 远短于平顶 |
| 数据相关闭环 | 每炮 `get_measure_values` 回采后在 Python 里判定→生成下一炮波形(write-verify/ISPP、翻转点搜索) |
| per-shot 安全门禁 | 用 sequence/loop 计数 + `getChannelStatus`/`isMeasureEventCompleted` 状态轮询;每炮回采即判 Id 超阈→中止,`setTimeout`/warning-level 容错 |
| 多阶段编排 | online/offline 两阶段会话模型(`openSession→initialize→connect→execute→disconnect→closeSession`),程序里做条件分支/状态机 |
| 海量脉冲 + 向量预算 | 单 pattern 2048 向量 / 单通道 ~4,000,000 测量点上限自管:`_dose_chunk_counts` / `_max_cycle_stress_chunk` 自动分块连发(顺带修了 `WGFMU_initialize` 每会话只能调一次导致的 `status=-6`) |

**已落地的 6 类瞬态原语(全是上面骨架的实例化):**
- **A 写后延迟读 / Retention 瞬态**(延迟 1 µs→10 s,7 个数量级;读窗 5 µs 取 5 点,孔径 ~200 ns)
- **B 编程动力学**:脉宽扫描(1–300 µs)+ 幅值扫描(3/4/5 V)→ switching kinetics / 阈值场
- **C 读扰动累积**:reset+write 后插 N 个 dose 脉冲(1/10/100…)再统一读,超 2048 向量自动分块
- **D 半 Vdd/反极性扰动→延迟→读**(扰动 100 µs,后延迟 1 µs–1 s),配对参考线相减得净扰动
- **E 写后延迟下 Vg×Vd 记忆窗网格**(两延迟 10 µs / 1 s,找最佳读工作点)
- **F 检查点式耐久**:1e5 循环,对数检查点 [10…1e5] 处停下读 MW,其余纯施应力(把读扰动从耐久曲线剔除)

---

## 4. 项目5 定位与叙事(求职亮点)

### 电梯陈述(一段话,经得起追问的版本)

> "EasyEXPERT 能驱动 B1530A WGFMU 测大多数**固定的**脉冲/瞬态(PUND、Fast IV、retention、endurance),但它的 Application Test 是**开环、预定义波形的模板**,无法表达'依赖实时测量结果的逐炮闭环编排',也无法把延迟当扫描轴、在波形任意时刻放测量事件。我基于 WGFMU2 C API 自研了一套 FeFET 瞬态表征框架 fefetlab:用统一的'波形拼接 + 事件级定时采样'骨架,实现了写→可变延迟(µs–10s,7 个数量级)→定时读的逐炮序列、per-shot 测量值驱动的安全门禁、以及多阶段实验链的可编程自动化,落地了 6 类 FeFET 动态表征协议(retention / switching kinetics / read-disturb / 半选扰动 / 记忆窗工作点 / 1e5 耐久),并配了 PySide6 上位机 GUI。本质是把 GUI 模板表达不了的闭环、data-dependent 编排做成了可复用的测量基础设施。"

### 电梯版(更短)

> "瓶颈不在'能不能测瞬态'——硬件和 EasyEXPERT 都能测;瓶颈在'能不能按实时测量结果逐炮决策、把延迟当扫描轴'。GUI 是开环模板,我用 WGFMU2 C API 做了闭环、data-dependent 的逐炮编排 + per-shot 安全门禁 + 多阶段自动化,覆盖 6 类 FeFET 协议。"

### 最能打动内行的 3–5 个技术差异点

1. **延迟作为一等扫描轴 + 事件级定时采样**:在一条波形上用 `setMeasureEvent` 任意时刻钉多个读窗,延迟 log/随机化横跨 7 个数量级(1 µs–10 s)——GUI 等距网格 + 单 Delay 参数做不到。
2. **数据相关闭环**:每炮回采即决定下一炮(write-verify/ISPP、自适应翻转点搜索)。这是开环模板的绝对盲区,也是最硬的卖点。
3. **per-shot 实时安全门禁**:测量值驱动的中止逻辑保护易击穿的 FeFET 栈——GUI 没有插入点。
4. **向量预算工程化**:直面 WGFMU 单 pattern 2048 向量 / ~4M 测量点硬约束,自动分块连发 1e5 循环 / 100+ dose 脉冲,并定位修复 `WGFMU_initialize` 每会话单次调用导致的 `status=-6`。这是"真在硬件层踩过坑"的信号。
5. **统一测量原语 + 上位机**:6 类协议复用同一 `run_*_shot` 骨架,PySide6 GUI 封装多阶段编排——从底层 C API 一路到可用产品。

### 简历/面试可量化点

- **时序范围**:延迟 1 µs–10 s(7 个数量级);写脉冲平顶 100 µs、边沿 100 ns;读窗 5 µs/5 点、采样孔径 ~200 ns;WGFMU 波形/采样分辨 10 ns / 5 ns(硬件规格,引官方 datasheet)。
- **协议数**:6 类瞬态表征协议(retention / kinetics 脉宽×幅值 / read-disturb / 半选扰动+配对参考 / Vg×Vd 记忆窗网格 / 1e5 耐久)。
- **规模**:耐久 1e5 循环对数检查点;dose 累积到 100+ 脉冲;均超单 pattern 2048 向量上限,自动分块。
- **安全门禁**:per-shot 测量值驱动中止(可量化为"超阈即停,保护 N 个器件/无烧毁")。
- **可靠性**:字节级回归(向量/事件序列哈希比对,确保重构不改波形)——已实现(`test_cli_dry_golden` / `test_engine_run` 12 段逐字节金标准 + ALL_DRY 169/640);务必量化。
- **上位机**:PySide6 GUI,封装会话生命周期 + 多阶段编排。

---

## 5. 要避免的过度宣称(诚实边界)

按"被戳穿概率"从高到低:

1. ❌ **"EasyEXPERT 测不到瞬态"** —— 最致命。Sampling + WGFMU Application Test 就是干这个的。改说"GUI 无法表达闭环/逐炮编排/延迟扫描轴"。
2. ❌ **"自研能测到更快/更高分辨率的瞬态"** —— 假的。**时间分辨率由 B1530A 硬件决定,两者驱动同一块卡,物理上限相同;软件不会让硬件变快。**
3. ❌ **"EasyEXPERT 做不了 PUND/Fast IV/endurance/retention"** —— 它都能做,是官方模板。
4. ❌ **"因为 EasyEXPERT 太老"** —— 情绪化归因。换成"它的设计定位就是 GUI 开环模板,即使最新版也不提供任意闭环脚本编排"。
5. ❌ 含糊的 **"更强大/更全面"** —— 内行会追问"具体哪条它表达不了"。永远用 A 类具体闭环例子(write-verify、measurement-gated 中止、可变延迟逐炮扫描)支撑。
6. ⚠️ **"EasyEXPERT 不能自动化"** —— 不准确。它有 My Favorite 串联、可被 .NET/COM(InstrLib)外部调用。准确说法:"GUI 层自动化缺条件分支/闭环",不是"完全不能自动化"。
7. ⚠️ **硬件数字务必引官方 datasheet 核对**(5 ns 采样 / 10 ns 波形 / 300 ns·100 ns 最小脉宽),简历里写硬件数值最忌被抓偏差。

---

## 6. 若要做成真正的"项目5":差异化方向 / scope 建议

让它从"测试脚本集合"升级为"产品级测量基础设施":

1. **把闭环算法做成卖点核心**:实现并 demo 一个完整的 **write-verify / ISPP**(增量步进脉冲编程,按读出 Vth 收敛目标态)和**自适应翻转点二分搜索**。这是 GUI 永远做不到、且面试一讲就懂价值的东西。优先级最高。
2. **声明式协议描述层**:让协议(波形分段 + 事件 + 扫描轴 + 门禁条件)用 YAML/dataclass 声明,框架编译成 WGFMU 向量。卖点从"我写了 6 个脚本"升级为"我做了一个协议 DSL/编排引擎"。
3. **measurement-gated 安全状态机标准化**:把 per-shot 门禁抽象成可复用的 guard(击穿检测、软击穿、电流突变),配可配置阈值与中止/降级策略——器件保护是真实工程价值。
4. **golden-vector 回归 + CI**:对每条协议做字节级向量哈希回归,接 CI。这把项目从"实验脚本"抬到"有测试纪律的软件",是简历差异化的硬信号。(注:项目3 已有 12 段逐字节金标准,可直接迁移成卖点。)
5. **数据层与可追溯性**:统一带时间戳/元数据的数据模型(器件 ID、波形指纹、量程、温度),一键导出可复现实验包。补 EasyEXPERT 导出笨的真实痛点。
6. **量程/无 compliance 的防护层**:WGFMU+RSU **无 SMU 式限流(no compliance)**,自己做量程管理 + 软件过流保护,正好和 #3 的安全门禁合流——这是"懂硬件边界"的体现。
7. **对照基准 demo**:准备一组"同一 FeFET,EasyEXPERT 模板 vs fefetlab"的并排结果,直观展示 GUI 抓不到的初期 retention 衰减 / 逐炮闭环收敛。面试时一张图胜千言。

**scope 收敛建议**:不要追求"取代 EasyEXPERT 的全部功能"。把项目精确定位成 **"EasyEXPERT 表达不了的那一类(闭环 + 逐炮编排 + 多阶段自动化)的专用补充层"**——既诚实,又把工程含量集中在最有说服力的地方。

---

## 相关文件
- 实现:`项目3_B1500自动化\B1500\src\fefetlab\protocols\wgfmu_fefet.py`
- 设计文档:`项目3_B1500自动化\B1500\_agent\references\B1500_GUI架构设计_PySide6.md`
- B1530A WGFMU C API 手册:`项目3_B1500自动化\B1500手册\keysight-b1530a-series-user-guide.pdf`(Ch1 1-2~1-8;Ch3 3-3~3-22;Ch4 4-52~4-76)
- EasyEXPERT 手册:`项目3_B1500自动化\B1500手册\9018-01993 EasyEXPERT Software.pdf`(Module 4 SMU pulse 4-5、I/V-t 4-14、Negative Hold 4-21~4-23;Module 1 Application Test 1-9~1-12;Module 6 Test Definition 6-8~6-10)
