"""
MCP 工具注册表
管理和注册所有可用的 MCP 工具
"""

from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class MCPTool:
    """
    MCP 工具定义
    """
    name: str                           # 工具名称
    description: str                    # 工具描述
    parameters: Dict[str, Any]          # 参数定义
    handler: Callable                   # 处理函数
    category: str = "general"           # 工具分类
    requires_auth: bool = False         # 是否需要认证
    rate_limit: int = 100               # 速率限制（次/分钟）
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "category": self.category,
            "requires_auth": self.requires_auth,
            "rate_limit": self.rate_limit,
            "created_at": self.created_at
        }


class ToolRegistry:
    """
    MCP 工具注册表
    统一管理所有工具的注册、调用和查询
    """
    _instance = None
    _tools: Dict[str, MCPTool] = {}
    _categories: Dict[str, list] = {}

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, tool: MCPTool) -> None:
        """
        注册工具
        
        Args:
            tool: MCP 工具实例
        """
        self._tools[tool.name] = tool
        
        # 按分类索引
        if tool.category not in self._categories:
            self._categories[tool.category] = []
        if tool.name not in self._categories[tool.category]:
            self._categories[tool.category].append(tool.name)
        
        print(f"✅ 工具注册成功: {tool.name}")

    def get_tool(self, name: str) -> Optional[MCPTool]:
        """
        获取工具
        
        Args:
            name: 工具名称
        """
        return self._tools.get(name)

    def list_tools(self, category: str = None) -> list:
        """
        列出工具
        
        Args:
            category: 分类筛选（可选）
        """
        if category:
            tool_names = self._categories.get(category, [])
            return [self._tools[name] for name in tool_names if name in self._tools]
        return list(self._tools.values())

    def list_categories(self) -> list:
        """列出所有分类"""
        return list(self._categories.keys())

    async def execute(
        self, 
        tool_name: str, 
        params: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行工具
        
        Args:
            tool_name: 工具名称
            params: 工具参数
            context: 执行上下文（包含用户信息、会话信息等）
        
        Returns:
            执行结果
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"工具不存在: {tool_name}",
                "tool_name": tool_name
            }
        
        try:
            # 注入上下文
            if context:
                params["_context"] = context
            
            # 执行工具
            result = await tool.handler(**params)
            return {
                "success": True,
                "tool_name": tool_name,
                "result": result,
                "executed_at": datetime.utcnow().isoformat()
            }
        except TypeError as e:
            # 参数错误
            return {
                "success": False,
                "error": f"参数错误: {str(e)}",
                "tool_name": tool_name,
                "expected_params": tool.parameters
            }
        except Exception as e:
            # 其他错误
            return {
                "success": False,
                "error": f"执行失败: {str(e)}",
                "tool_name": tool_name
            }

    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        """
        获取工具的 JSON Schema
        
        Args:
            tool_name: 工具名称
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return None
        
        return {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters
        }


# 全局注册表实例
_global_registry = None

def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry
