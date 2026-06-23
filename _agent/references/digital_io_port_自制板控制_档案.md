# B1500 Digital I/O 口 · 自制板控制 设计档案

> 来源：本机 `b1500 program guide/9018-01851.pdf`（Keysight B1500 Series Programming Guide, Edition 15），
> 章节 2-71 ~ 2-87「Digital I/O Port / Trigger Function / Initial Settings」+ 命令参考 ERMOD/ERM/ERC/ERS?/TGP/OSX/PAX。
> 建档：2026-06-10（claude，应椰椰要求记录"用 digital 口自制板控制"的新方向）。

## 0. 一句话结论
后面板红框那个口 = **Digital I/O 口，D-Sub 25 针（DB-25，母座）**，里面是 **16 路 TTL 数字 I/O（DIO 1~16）**。
官方文档完整覆盖，**可编程控制**（GPIB/USB/LAN 走 SCPI/FLEX 文本命令，跟现有项目的 VISA 链路同一条），
**自制板控制是这个口的设计本意**（官方 16440A / N1258A / N1259A 选择器就是这么挂上来的）。

⚠️ **关键澄清（纠正"控制 SMU/WGFMU 功能"的说法）**：
这 16 根线 **不能用来"配置/驱动"本机 SMU/WGFMU 的测量功能**（施压、量程、波形那些永远是软件经仪器总线设的）。
它能做的是三类**外设控制 + 同步**：① 输出 16 位 TTL 去驱动你自己的板子（继电器/选择器/开关矩阵）；
② 读 16 位 TTL 外部状态（温控 ready / 探针 contact / interlock）来 gate/abort 测量；
③ 当硬件 trigger 线，零软件延时地触发/同步 SMU/CMU/SPGU 测量。
**所以"自制板被 B1500 控制"完全成立**（典型用法：板上放继电器，B1500 用 ERC 翻这些 DIO 位去切 SMU/SPGU/WGFMU 到不同 DUT 脚——这正是官方 16440A 选择器干的事）；
但"用这个口去控制 SMU/WGFMU 的测量本身"不成立，那是总线软件的活。

## 1. 引脚分配（Table 2-6，已核对原文）
连接器：B1500 后面板 = **D-Sub 25 针母座（f）**；所以你的线/板要 **DB-25 公头（m）** 去对插。
DIO 线初始全为输出、TTL 高（≈2.4 V；低≈0.8 V）。

| 针 | 信号 | 针 | 信号 |
|---|---|---|---|
| 1  | 不用(Do not use) | 14 | 不用 |
| 2  | 不用 | 15 | **DIO 1** |
| 3  | **DIO 2** | 16 | **DIO 3** |
| 4  | **DIO 4** | 17 | **DIO 5** |
| 5  | **DIO 6** | 18 | **DIO 7** |
| 6  | **DIO 8** | 19 | **DIO 9** |
| 7  | **DIO 10** | 20 | **DIO 11** |
| 8  | **DIO 12** | 21 | **DIO 13** |
| 9  | **DIO 14** | 22 | **DIO 15** |
| 10 | **DIO 16** | 23 | 不用 |
| 11 | 不用 | 24 | 不用 |
| 12 | 不用 | 25 | **GND** |
| 13 | **GND** | | |

规律：奇数 DIO(1,3,5,7,9,11,13,15)→针 15~22；偶数 DIO(2,4,6,8,10,12,14,16)→针 3~10；GND=针 13&25。

## 2. 电气特性（每根 DIO 内部电路，Figure 2-45）
- Vcc = 5 V，上拉 R1 = 1 kΩ，串联 R2 = 100 Ω，下管 Q1（Vce(sat)=0.3 V）。
- 本质是 **5V TTL、准开集（open-collector 带 1kΩ 上拉）** 结构 → 能把线拉低、可线或；高电平靠 1kΩ 上拉，**驱动能力弱，别当强推挽用**。
- 自制板设计要点：板侧用 **5V TTL 逻辑**；做输入时给标准 TTL 电平；做输出去拉 B1500 输入线时同理。
- 触发线（Ext Trig In/Out 是另外两个 BNC，内部电路 Figure 2-51/2-52：Vcc=5V，含 1000pF；输出端 74ABT245 等效，R1=150Ω）。

## 3. 控制命令（SCPI/FLEX，全部走现有 VISA session）
先选控制模式 **ERMOD**：
- `ERMOD 0` = 通用模式（General purpose，初始）→ 用 ERM/ERS?/ERC/TGP 自己控这 16 根线。**自制板就用这个模式。**
- `ERMOD 1` = 16440A SMU/PGU 选择器模式（经 16445A 适配器）→ 用 ERSSP/ERSSP?。**（就是 PPT 里"控制 SMU 与 SPGU 切换"那条官方线）**
- `ERMOD 2/4/8/16/32` = N1258A/N1259A、N1265A、N1266A、N1268A、N1272A 各自的官方选择器模式。

通用模式下的四条核心命令：
- `ERM iport` —— 设 16 路方向。iport 是 0~65535 的位图，**每位 0=输出，1=输入**。例：`ERM 255` → DIO1~8 设为输入。
- `ERC 2,value[,rule]` —— 设输出电平位图。value 0~65535，**位值 0=TTL 高(2.4V)，位值 1=TTL 低(0.8V)**（注意是反的）。
  例：`ERC 2,255` → DIO1~8 输出低。mode 必须=2（=1 是 4142B 的，会报错）。前提：ERMOD 0。
- `ERS?` —— 读回 16 路 digital I/O 当前状态（位图）。读外部状态就用它（先 ERM 把相应位设成输入）。
- `TGP port,io,logic,type` —— 把某根 DIO 配成 trigger 口。port 1~16=DIO；-1=Ext Trig In，-2=Ext Trig Out。
  io 1=输入/2=输出；logic 正/负逻辑；type 触发类型(1 起测量 / 2 步进 / 3 步测量)。配合 `OSX port,level`（发触发）、`PAX/WSX port`（等触发）。

初始态（开机/*RST/device clear）：DIO 全部=输出口、TTL 高（ERM/ERC/ERMOD/TGP 复位）。

## 4. 需要买什么线 / 接什么
**自制板最省钱方案（推荐）**：不需要 Keysight 原厂线。买一根 **DB-25 公头转散线 / 转接线端子（screw-terminal breakout）** 的现成线，或自己焊 DB-25 公头(solder-cup)+外壳+排线，引到你的 PCB 即可。只用到针 3~10、15~22（16 根 DIO）+ 针 13/25（GND）。

**官方配件（要原厂插拔/或多机级联时才需要）**：
- **16493G** Digital I/O 连接电缆（DB-25 m ↔ DB-25 f，16493G-001≈1.5m / -002≈3m）。B1500↔B1500 或 B1500↔N1253A-200 BNC 盒。
- **N1253A-100** Digital I/O T 型线（三台及以上 B1500 级联用）。
- **N1253A-200** Digital I/O BNC 盒（把 DB-25 拆成 BNC；**只引出 DIO 1~8** 到 8 个 BNC 母头）。想用 BNC 玩 DIO1-8 就买这个 + 一根 16493G。

**官方"自制板"先例（直接参考做法）**：16440A SMU/PGU 选择器（继电器盒）经 **16445A 选择器适配器** 插到这个 Digital I/O 口，B1500 用 ERMOD 1 + ERSSP 翻继电器把 SMU 力源/SPGU 输出切到探针——你的自制板就是这个套路的"通用模式 DIY 版"。

## 5. 自制板设计方向（待椰椰确认目标后细化）
1. **明确板子要干嘛**：(a) 切换路由（继电器/开关矩阵，把 SMU/WGFMU/SPGU 切到不同 DUT 脚）；(b) 读外部状态做安全联锁（温控 ready / 探针 contact / interlock）；(c) 硬件触发同步。三类可叠加。
2. **位分配**：先画一张 DIO bit → 板上功能的映射表（写进本档）。
3. **驱动侧**：板上 16 根 TTL 直接接 B1500 DIO；若驱继电器要加缓冲/驱动管（DIO 是弱上拉，别直推继电器线圈），用 ULN2003/光耦隔离 + 板上自带 5V/12V 给继电器供电。
4. **软件侧**：在现有 `src/fefetlab/b1500/driver.py` 加 ERMOD/ERM/ERC/ERS?/TGP 薄封装（就是几条 `inst.write(...)`/`inst.query("ERS?")`），跟 DC/WGFMU 一样走 VISA session；先 Mock 验证再上真机。
5. **自检**：`DIAG? 4`（Digital I/O 自检，**需先拔掉 digital 口所有线**）；`DIAG? 1`（Trig In/Out 自检，需 BNC 把 Ext Trig In↔Out 短接）。

## 5.5 架构已确认（2026-06-10，椰椰澄清）
目标板 = **选择器/开关矩阵板**：SMU + WGFMU 的测量线全插到这块自制板上，B1500 用 16 根 DIO 翻板上继电器，把对应源路由到器件。= 自制版的官方 16440A 选择器 / RSU。**架构成立、是正路。** 真正难点只在信号完整性，控制+软件都很轻。

**两套线分开（核心）**：
- 控制路径：16 根 DIO（弱 5V TTL）→ 只决定"哪个继电器闭合"。
- 信号路径：SMU triax(力/感+guard)、WGFMU 同轴脉冲 → **不经 DIO**，单独插板、由继电器切到 DUT。

**工程红线**：
1. **SMU 侧保 guard + Kelvin(力/感)**：继电器会带来漏电/电缆电容/丢 guard，毁低电流精度(pA~nA)。用低漏/干簧(reed)/带保护继电器，布局保 guard。官方 16440A 贵在此。FeFET 到 µA 级可放松但要心里有数。
2. **⚠️ WGFMU 快脉冲(µs/ns)最怕继电器 stub 电容/电感糊快沿**。现拓扑 baseline ~1.14µA 本就是 3m HRSU ~150pF 寄生主导，再串继电器更糟。Keysight 的解法是 RSU(探针端切 WGFMU↔SMU，现有 3 个 RSU 就是它)。→ 用本板切 DC/SMU 路由、或切"SMU 模式↔WGFMU 模式"OK；把 WGFMU 快测路径塞进通用继电器板有风险，要么用射频/干簧继电器+极短 stub，要么照 RSU 思路把开关放在不碍快测处，先单独验快沿。
3. **继电器驱动**：DIO 弱上拉不能直推线圈 → 板上 ULN2003/MOSFET/光耦 + 独立线圈电源。16 根线最多直驱 16 个继电器(1bit/个)，要更多加移位寄存器/IO 扩展。
4. **切源 break-before-make**(先断后通)，别把两源短一起；软件里按位序发 ERC。

## 6. 待核实 / 注意
- WGFMU(B1530A) 的触发：本口的 TGP 触发主要覆盖主机 SMU/CMU/SPGU 测量；**WGFMU 模块自带触发口**，要不要用本口同步 WGFMU 需另查 B1530A 手册（`B1500手册/keysight-b1530a-series-user-guide.pdf`），别默认能直接 TGP 触发 WGFMU。
- 强电/继电器请用板上独立电源 + 隔离，别从这 16 根弱 TTL 取功率。
- 自检 `DIAG? 4` 跑之前务必断开本口所有外接线。
