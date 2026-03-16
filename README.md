# 系统框架

* notebooks
  用于：bring-up，调试，临时分析，探索，参数试验
 *  scripts
  固定流程一键运行，命令行执行，批量任务
* protocols
  把多个基础功能拼成一个完整实验。
* src/fefetlab/measurements/
  可复用的功能层，api层



## 终止符

> A EOI-only raw: 'Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401\r\n' | strip: 'Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401'
> B LF raw: 'Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401\r' | strip: 'Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401'
> C CRLF raw: 'Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401' | strip: 'Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401'

CRLF raw，\r\n，;  且用.strip()，保证返回的字符串没有空格终止符等

## smoke test

最小功能验证;  连接仪器 发送命令 收到回复;

Python ↔ VISA ↔ B1500

## Visasession

* **VisaConfig**：连接参数包（地址、超时、读写结束符、后端）。
* **VisaSession.open()**：真正连上仪器并设置通信参数。
* **VisaSession.write/query()**：统一收发命令，避免到处直接操作 **pyvisa** 对象。

## channel

4567 SMU可用

## 当前已确认约定（2026-03）

- 当前 B1500 自动化项目已确认可用 SMU 候选通道为 4/5/6/7，不再默认使用 1/2/3。
- 当前通信配置固定为：

  - resource: GPIB0::17::INSTR
  - write_termination: "\r\n"
  - read_termination: "\r\n"
  - send_end: true
- 单通道最小 bring-up 流程：

  1. *IDN?
  2. ERRX?
  3. CN ch
  4. DV ch,vrange,voltage,compliance
  5. TI ch,0
  6. DZ ch
  7. CL ch
- TI 当前统一显式使用 `TI ch,0`。
- notebook 调试时，修改结构后必须 Restart Kernel 并 Run All，避免 NameError。
- 当前 `channel_map.yaml` 中的 G/D/S 若标注为 provisional_map，仅代表第一轮实验假设，不代表已最终确认。
- 所有实验必须同时保存 raw / parsed / qc，坏数据不参与主判断。
- ### 当前 Python driver 推荐调用方式：
- b.dv(ch, vrange, voltage, compliance)
- b.ti(ch, irange=0)

### 当前已确认通道映射（本次接线）：

- CH4 / SMU1
- CH5 / SMU2
- CH6 / SMU3
- CH7 / SMU4

## Driver 调用约定

当前项目的 B1500 driver 推荐调用方式为：

- `b.dv(ch, vrange, voltage, compliance)`
- `b.ti(ch, irange=0)`
- `b.cl()` 可用于关闭所有通道
- `b.cl([ch1, ch2, ...])` 可用于关闭指定通道

说明：

- 历史 notebook 中若出现旧式 `dv(ch, voltage, compliance, vrange)`，应逐步迁移，不再推荐新增使用。
- 新 notebook 建议优先使用显式、统一的调用顺序，避免参数混淆。
