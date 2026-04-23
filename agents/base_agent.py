"""
Agent 基类
定义 Agent 的基本属性和行为
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
import uuid


class AgentState(str):
    """Agent 状态"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


@dataclass
class BaseAgent(ABC):
    """
    Agent 基类
    所有 Agent 的抽象基类
    """
    # Agent 标识
    agent_id: str = field(default_factory=lambda: f"agent_{uuid.uuid4().hex[:8]}")
    name: str = "未命名 Agent"
    description: str = ""
    
    # Agent 状态
    state: AgentState = AgentState.IDLE
    
    # 关联的用户 ID
    user_id: Optional[int] = None
    
    # 能力列表
    capabilities: List[str] = field(default_factory=list)
    
    # 消息处理回调
    message_handler: Optional[Callable] = None
    
    # A2A 总线引用
    a2a_bus = None
    
    # 创建时间
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def __post_init__(self):
        """初始化后处理"""
        self._setup_a2a()
    
    def _setup_a2a(self):
        """设置 A2A 通信"""
        from a2a.bus import get_a2a_bus
        self.a2a_bus = get_a2a_bus()
        self.a2a_bus.subscribe(self.agent_id, self.handle_message)
    
    def handle_message(self, message) -> Dict[str, Any]:
        """
        处理收到的消息
        
        Args:
            message: A2AMessage
        
        Returns:
            处理结果
        """
        self.state = AgentState.BUSY
        
        try:
            result = self.on_message(message)
            self.state = AgentState.IDLE
            return result
        except Exception as e:
            self.state = AgentState.IDLE
            return {
                "success": False,
                "error": str(e)
            }
    
    @abstractmethod
    def on_message(self, message) -> Dict[str, Any]:
        """
        处理消息的抽象方法
        子类需要实现具体的消息处理逻辑
        """
        pass
    
    async def send_message(self, to_agent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息给其他 Agent
        
        Args:
            to_agent: 目标 Agent ID
            payload: 消息载荷
        
        Returns:
            发送结果
        """
        from a2a.message import A2AMessage
        
        message = A2AMessage(
            from_agent=self.agent_id,
            to_agent=to_agent,
            from_user_id=self.user_id or 0,
            payload=payload
        )
        
        return await self.a2a_bus.send(message)
    
    def get_info(self) -> Dict[str, Any]:
        """获取 Agent 信息"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "state": self.state.value,
            "capabilities": self.capabilities,
            "created_at": self.created_at
        }
    
    def go_offline(self):
        """离线"""
        self.state = AgentState.OFFLINE
        self.a2a_bus.unsubscribe(self.agent_id)
    
    def go_online(self):
        """上线"""
        self.state = AgentState.IDLE
        self.a2a_bus.subscribe(self.agent_id, self.handle_message)
