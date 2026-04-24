"""
MCP 工具包
Model Context Protocol 工具定义
"""

# 先导入 tool_registry（不触发 tools.py）
from mcp.tool_registry import MCPTool, ToolRegistry, get_tool_registry

# 延迟导入 tools.py 中的函数
def __getattr__(name):
    if name in [
        "evaluate_car",
        "escrow_create", 
        "match_cars",
        "submit_demand",
        "verify_identity",
        "schedule_inspection",
        "transfer_ownership",
        "init_tool_registry"
    ]:
        from mcp import tools
        return getattr(tools, name)
    raise AttributeError(f"module 'mcp' has no attribute '{name}'")

__all__ = [
    "MCPTool",
    "ToolRegistry", 
    "get_tool_registry",
    "evaluate_car",
    "escrow_create",
    "match_cars",
    "submit_demand",
    "verify_identity",
    "schedule_inspection",
    "transfer_ownership",
    "init_tool_registry"
]
