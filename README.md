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

>
> IDN: Agilent Technologies,B1500A,MY55231213,A.06.02.2023.0401
> UNT?: B1525A,0;B1530A,0;B1530A,0;B1517A,0;B1517A,0;B1517A,0;B1511B,1;B1520A,0;0,0;0,0
> LOP?: LOP00,00,00,00,00,00,00,00,00,00
>
> === Probe channel 4 ===
> ERRX drained at start: ['+0,"No Error."']
> FMT ok
> CN 4 ok
> DV 4 ok
> ERRX after DV: +0,"No Error."
> DZ 4 ok
> CL 4 ok
> ERRX drained at end: ['+0,"No Error."']
>
> === Probe channel 5 ===
> ERRX drained at start: ['+0,"No Error."']
> FMT ok
> CN 5 ok
> DV 5 ok
> ERRX after DV: +0,"No Error."
> DZ 5 ok
> CL 5 ok
> ERRX drained at end: ['+0,"No Error."']
>
> === Probe channel 6 ===
> ERRX drained at start: ['+0,"No Error."']
> FMT ok
> CN 6 ok
> DV 6 ok
> ERRX after DV: +0,"No Error."
> DZ 6 ok
> CL 6 ok
> ERRX drained at end: ['+0,"No Error."']
>
> === Probe channel 7 ===
> ERRX drained at start: ['+0,"No Error."']
> FMT ok
> CN 7 ok
> DV 7 ok
> ERRX after DV: +0,"No Error."
> DZ 7 ok
> CL 7 ok
> ERRX drained at end: ['+0,"No Error."']

4567 SMU可用
