r"""B1500 FeFET 上位机(PySide6 GUI)。

设计文档:`_agent/references/B1500_GUI架构设计_PySide6.md`(§5 GUI)。

分层铁律:本包(`gui/`)依赖 PySide6 + pyqtgraph + `fefetlab.engine`;
**只通过引擎门 `ProtocolEngine.run` 驱动协议**,自己不碰 VISA / wgfmu.dll。
共性壳(本包绝大多数文件)与存储器类型无关——协议树按 `ProtocolSpec.family`
泛化分组、参数表单按 `ParamSpec` 自动生成、绘图按 `csv_schema` 查 `plot_dispatch`
注册表分派。FeFET 专有画法只住在 `gui/adapters/`,加新存储器时只补适配层,壳不改。

运行(在测试机):
    cd D:\test\B1500
    .venv\Scripts\python.exe -m gui

dry-run 铁律:dry 模式走 AuditBackend,无 VISA / 无 DLL / 无硬件输出;
AuditBackend 返回的是**占位电流(非器件数据)**,结果图一律标注 "DRY 占位",
绝不当真器件结果展示(见项目 02_Plan 的"弯路"教训:不要假数据/不要 demo)。
"""

__all__ = []
