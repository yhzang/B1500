"""声明式(无代码)协议子系统(项目5 M2 · DSL v1)。

工程师在 library.py 用 DeclaredProtocol 数据类声明一个协议(写/延迟/读 + 可选扫描轴),
compiler.py 把它编译成 WGFMU 向量(写相自展开 + 读相复用 _build_read_phase),
registry_glue.py 自动注册进 REGISTRY(family="CUSTOM",独立隔离,不碰 golden)→ GUI 自动出现。
v1 只覆盖"单炮线性序列 + 至多一条静态扫描轴 + 双极性 + rep";闭环/分块/配对参考留 v2。
"""
