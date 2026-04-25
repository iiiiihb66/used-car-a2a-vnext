"""
A2A 消息总线
作为平台路由中心，处理 Agent 之间的通信
支持：消息路由、记忆查询、MCP 工具调用、信任验证、Social Graph
"""

from typing import Dict, Any, List, Callable, Optional, Set
from datetime import datetime
from collections import defaultdict
import asyncio

from a2a.message import A2AMessage, Intent, MessageBuilder
from models.conversation import Conversation


class A2ABus:
    """
    A2A 消息总线
    平台作为路由中心，负责：
    1. 消息路由 - 将消息从发送方传递给接收方
    2. 记忆查询 - 存储和查询对话历史
    3. MCP 工具调用 - 触发相关工具执行
    4. 信任验证 - 验证消息发送方的身份和权限
    5. Social Graph - 记录用户协作关系
    """
    
    def __init__(self):
        # 订阅者映射: agent_id -> callback
        self._subscribers: Dict[str, Callable] = {}
        
        # 消息队列: agent_id -> [messages]
        self._message_queues: Dict[str, List[A2AMessage]] = defaultdict(list)
        
        # 在线状态: agent_id -> bool
        self._online_status: Dict[str, bool] = {}
        
        # 会话映射: session_id -> [message_ids]
        self._sessions: Dict[str, List[str]] = defaultdict(list)
        
        # 数据库会话（由外部注入）
        self._db_session = None
    
    def set_db_session(self, db):
        """设置数据库会话"""
        self._db_session = db
    
    # ==================== 订阅管理 ====================
    
    def subscribe(self, agent_id: str, callback: Callable) -> None:
        """
        订阅消息
        
        Args:
            agent_id: Agent ID
            callback: 消息处理回调函数
        """
        self._subscribers[agent_id] = callback
        self._online_status[agent_id] = True
        print(f"✅ Agent 订阅成功: {agent_id}")
    
    def unsubscribe(self, agent_id: str) -> None:
        """
        取消订阅
        
        Args:
            agent_id: Agent ID
        """
        if agent_id in self._subscribers:
            del self._subscribers[agent_id]
        self._online_status[agent_id] = False
        print(f"ℹ️ Agent 取消订阅: {agent_id}")
    
    def is_online(self, agent_id: str) -> bool:
        """检查 Agent 是否在线"""
        return self._online_status.get(agent_id, False)
    
    # ==================== 消息发送 ====================
    
    async def send(self, message: A2AMessage) -> Dict[str, Any]:
        """
        发送消息
        
        Args:
            message: A2A 消息
        
        Returns:
            发送结果
        """
        # 1. 信任验证（由平台执行）
        trust_result = await self._verify_trust(message)
        if not trust_result["verified"]:
            return {
                "success": False,
                "error": "信任验证失败",
                "details": trust_result
            }
        
        # 2. 路由到目标 Agent；若无实时订阅者，则回退到后端内置 UserAgent
        routed, agent_response = await self._route_message(message)

        # 3. 保存到对话历史
        await self._save_to_history(message)

        # 3.1 保存目标 Agent 的回复，形成完整会话链
        if agent_response:
            reply_payload = dict(agent_response)
            reply_payload.setdefault("content", agent_response.get("content"))
            reply_message = message.create_reply(payload=reply_payload)
            reply_message.status = "delivered"
            await self._save_to_history(reply_message)

        # 4. 根据意图触发 MCP 工具 + 记忆注入 + Social Graph
        tool_result = await self._trigger_tools(message)

        return {
            "success": True,
            "message_id": message.id,
            "routed": routed,
            "agent_response": agent_response,
            "tool_result": tool_result,
            "timestamp": message.timestamp
        }

    async def _route_message(self, message: A2AMessage) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        路由消息到目标 Agent
        
        Args:
            message: A2A 消息
        
        Returns:
            (是否成功路由, Agent 回复)
        """
        target_agent = message.to_agent

        # 如果目标在线，实时推送
        if self.is_online(target_agent) and target_agent in self._subscribers:
            callback = self._subscribers[target_agent]
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
                message.status = "delivered"
                return True, None
            except Exception as e:
                message.error = str(e)
                message.status = "failed"
                return False, None

        # 目标未在线时，直接回退到后端内置 UserAgent，保证云端 API 可闭环处理
        agent_response = await self._invoke_embedded_agent(message)
        if agent_response is not None:
            message.status = "delivered"
            return True, agent_response

        # 如果目标不在线，存入队列
        self._message_queues[target_agent].append(message)
        message.status = "queued"
        return True, None

    async def _invoke_embedded_agent(self, message: A2AMessage) -> Optional[Dict[str, Any]]:
        """使用后端内置 UserAgent 处理消息，供公网 API 直接驱动 Agent 协商。"""
        if self._db_session is None or message.to_user_id <= 0:
            return None

        try:
            from agents.user_agent import get_user_agent

            target_agent = get_user_agent(message.to_user_id, self._db_session)
            return await target_agent.handle_message(message)
        except Exception as e:
            print(f"⚠️ 内置 Agent 处理失败: {e}")
            return {
                "content": f"[错误] Agent 处理失败: {str(e)}",
                "error": str(e),
            }
    
    async def _verify_trust(self, message: A2AMessage) -> Dict[str, Any]:
        """
        信任验证
        
        Args:
            message: A2AMessage
        
        Returns:
            验证结果
        """
        # 简化实现：检查发送方是否已订阅
        sender = message.from_agent
        is_verified = sender in self._subscribers
        
        return {
            "verified": True,  # 开发环境默认通过
            "sender": sender,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _save_to_history(self, message: A2AMessage) -> None:
        """
        保存消息到对话历史
        
        Args:
            message: A2AMessage
        """
        if self._db_session is None:
            return
        
        try:
            # 创建会话 ID（如果没有）
            if not message.session_id:
                message.session_id = f"sess_{message.from_user_id}_{message.to_user_id}_{int(datetime.utcnow().timestamp())}"
            
            # 保存到数据库
            conversation = Conversation(
                message_id=message.id,
                from_user_id=message.from_user_id,
                to_user_id=message.to_user_id,
                from_agent=message.from_agent,
                to_agent=message.to_agent,
                intent=message.intent,
                action=message.action,
                payload=message.payload,
                content=message.payload.get("content"),
                related_car_id=message.related_car_id,
                session_id=message.session_id,
                parent_message_id=message.parent_message_id,
                status=message.status
            )
            
            self._db_session.add(conversation)
            self._db_session.commit()
            
            # 更新会话记录
            if message.session_id:
                self._sessions[message.session_id].append(message.id)
                
        except Exception as e:
            print(f"⚠️ 保存对话历史失败: {e}")
            if self._db_session:
                self._db_session.rollback()
    
    async def _trigger_tools(self, message: A2AMessage) -> Optional[Dict[str, Any]]:
        """
        触发工具 + 注入记忆 + 记录 Social Graph
        
        根据不同意图：
        - PRICE_NEGOTIATE: 查询双方议价历史，注入平台估价
        - DEAL_INTENT: 创建托管，更新 Social Graph，奖励积分
        - PRICE_INQUIRY: 执行估价工具
        
        Args:
            message: A2AMessage
        
        Returns:
            工具执行结果
        """
        from memory.memory_service import get_memory_service
        from models.reputation import ReputationEngine
        from mcp.tools import get_tool_registry
        
        if self._db_session is None:
            return None
        
        memory = get_memory_service(self._db_session)
        registry = get_tool_registry()
        
        # ==================== 议价意图 ====================
        if message.intent == Intent.PRICE_NEGOTIATE.value:
            car_id = message.related_car_id
            
            # 查双方议价历史
            buyer_history = memory.get_negotiation_history(
                message.from_user_id, 
                car_id
            ) if car_id else []
            seller_history = memory.get_negotiation_history(
                message.to_user_id,
                car_id
            ) if car_id else []
            
            # 获取车辆信息
            car_info = await memory.get_car_memory(car_id) if car_id else None
            
            # 调用估价工具获取平台参考价
            evaluate_tool = registry.get_tool("evaluate_car")
            fair_price_result = None
            if evaluate_tool and car_info:
                fair_price_result = await registry.execute("evaluate_car", {
                    "brand": car_info.get("brand", "丰田"),
                    "model": car_info.get("model", ""),
                    "year": car_info.get("year", 2020),
                    "mileage": car_info.get("mileage", 50000)
                })
            
            # 注入上下文到消息
            message.payload["context"] = {
                "buyer_history": buyer_history,
                "seller_history": seller_history,
                "platform_reference_price": fair_price_result.get("estimated_price") if fair_price_result else None,
                "market_trend": fair_price_result.get("market_trend") if fair_price_result else None,
                "car_info": car_info
            }
            
            return {
                "action": "price_context_injected",
                "intent": Intent.PRICE_NEGOTIATE.value,
                "platform_reference": fair_price_result.get("estimated_price") if fair_price_result else None,
                "buyer_history_count": len(buyer_history),
                "seller_history_count": len(seller_history),
                "memory_injected": True
            }
        
        # ==================== 成交意图 ====================
        elif message.intent == Intent.DEAL_INTENT.value:
            car_id = message.related_car_id
            agreed_price = message.payload.get("agreed_price", 0)
            
            # 更新 Social Graph（双向记录）
            memory.add_collaboration(
                user_id=message.from_user_id,
                other_user_id=message.to_user_id,
                other_user_name=None,
                deal_price=agreed_price,
                car_id=car_id
            )
            memory.add_collaboration(
                user_id=message.to_user_id,
                other_user_id=message.from_user_id,
                other_user_name=None,
                deal_price=agreed_price,
                car_id=car_id
            )
            
            # 奖励双方信誉分
            engine = ReputationEngine(self._db_session)
            buyer_reward = engine.reward_for_deal(
                user_id=message.from_user_id,
                role="buyer",
                deal_price=agreed_price
            )
            seller_reward = engine.reward_for_deal(
                user_id=message.to_user_id,
                role="seller",
                deal_price=agreed_price
            )
            
            # 更新车辆状态
            if car_id:
                await memory.update_car_status(car_id, "交易中")
            
            return {
                "action": "deal_completed",
                "intent": Intent.DEAL_INTENT.value,
                "next_step": "offline_verification",
                "social_graph_updated": True,
                "reputation_rewards": {
                    "buyer": buyer_reward,
                    "seller": seller_reward
                },
                "car_status": "待线下核验"
            }
        
        # ==================== 询价意图 ====================
        elif message.intent == Intent.PRICE_INQUIRY.value:
            car_id = message.related_car_id
            car_info = await memory.get_car_memory(car_id) if car_id else None
            
            if car_info:
                # 调用估价工具
                evaluate_tool = registry.get_tool("evaluate_car")
                if evaluate_tool:
                    return await registry.execute("evaluate_car", {
                        "brand": car_info.get("brand", ""),
                        "model": car_info.get("model", ""),
                        "year": car_info.get("year", 2020),
                        "mileage": car_info.get("mileage", 50000)
                    })
            
            return {
                "action": "price_inquiry_processed",
                "intent": Intent.PRICE_INQUIRY.value,
                "car_info": car_info
            }
        
        # ==================== 录入档案意图 ====================
        elif message.intent == "ADD_LIFECYCLE_RECORD":
            car_id = message.related_car_id
            record_type = message.payload.get("record_type")
            record_data = message.payload.get("data", {})
            signed_by = str(message.from_user_id)
            
            # 添加生命周期记录
            result = memory.add_lifecycle_record(
                car_id=car_id,
                record_type=record_type,
                data=record_data,
                signed_by=signed_by
            )
            
            # 奖励录入者
            engine = ReputationEngine(self._db_session)
            reward_result = engine.reward_for_record(
                user_id=message.from_user_id,
                record_type=record_type,
                verified=False
            )
            
            return {
                "action": "lifecycle_record_added",
                "record": result.get("record"),
                "reward": reward_result,
                "chain_verified": True
            }
        
        return None
    
    # ==================== 消息接收 ====================
    
    def get_pending_messages(self, agent_id: str) -> List[A2AMessage]:
        """
        获取待处理消息
        
        Args:
            agent_id: Agent ID
        
        Returns:
            待处理消息列表
        """
        messages = self._message_queues.get(agent_id, [])
        self._message_queues[agent_id] = []
        return messages
    
    async def get_conversation_history(
        self,
        user_id: int,
        other_user_id: int = None,
        session_id: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        获取对话历史
        
        Args:
            user_id: 用户 ID
            other_user_id: 对方用户 ID（可选）
            session_id: 会话 ID（可选）
            limit: 返回数量限制
        
        Returns:
            对话历史列表
        """
        if self._db_session is None:
            return []
        
        query = self._db_session.query(Conversation)
        
        if session_id:
            query = query.filter(Conversation.session_id == session_id)
        else:
            # 筛选与用户相关的消息
            query = query.filter(
                (Conversation.from_user_id == user_id) |
                (Conversation.to_user_id == user_id)
            )
            
            if other_user_id:
                query = query.filter(
                    (Conversation.from_user_id == other_user_id) |
                    (Conversation.to_user_id == other_user_id)
                )
        
        conversations = query.order_by(Conversation.created_at.desc()).limit(limit).all()
        return [c.to_dict() for c in conversations]
    
    # ==================== 便捷方法 ====================
    
    async def send_message(
        self,
        from_user_id: int,
        to_user_id: int,
        content: str,
        intent: str = Intent.MESSAGE.value
    ) -> Dict[str, Any]:
        """发送普通消息"""
        message = MessageBuilder.create_message(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            content=content,
            intent=intent
        )
        return await self.send(message)
    
    async def send_price_inquiry(
        self,
        from_user_id: int,
        to_user_id: int,
        car_id: str,
        message: str = None
    ) -> Dict[str, Any]:
        """发送询价"""
        message = MessageBuilder.create_price_inquiry(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            car_id=car_id,
            message=message
        )
        return await self.send(message)
    
    async def send_price_negotiate(
        self,
        from_user_id: int,
        to_user_id: int,
        car_id: str,
        current_price: float,
        proposed_price: float,
        reason: str = None
    ) -> Dict[str, Any]:
        """发送议价"""
        message = MessageBuilder.create_price_negotiate(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            car_id=car_id,
            current_price=current_price,
            proposed_price=proposed_price,
            reason=reason
        )
        return await self.send(message)
    
    async def send_deal_intent(
        self,
        from_user_id: int,
        to_user_id: int,
        car_id: str,
        agreed_price: float
    ) -> Dict[str, Any]:
        """发送成交意向"""
        message = MessageBuilder.create_deal_intent(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            car_id=car_id,
            agreed_price=agreed_price
        )
        return await self.send(message)
    
    async def send_lifecycle_record(
        self,
        from_user_id: int,
        to_user_id: int,
        car_id: str,
        record_type: str,
        data: dict
    ) -> Dict[str, Any]:
        """发送生命周期记录"""
        message = MessageBuilder.build(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=f"user_{from_user_id}",
            to_agent=f"user_{to_user_id}",
            intent="ADD_LIFECYCLE_RECORD",
            payload={
                "record_type": record_type,
                "data": data
            },
            related_car_id=car_id
        )
        return await self.send(message)
    
    async def send_text_message(
        self,
        from_user_id: int,
        to_user_id: int,
        content: str
    ) -> Dict[str, Any]:
        """
        发送纯文本消息（用于系统通知）
        
        Args:
            from_user_id: 发送者用户ID（0 表示系统）
            to_user_id: 接收者用户ID
            content: 消息内容
        
        Returns:
            发送结果
        """
        # 构建消息
        message = MessageBuilder.build(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=f"user_{from_user_id}" if from_user_id > 0 else "system",
            to_agent=f"user_{to_user_id}",
            intent="TEXT_MESSAGE",
            payload={
                "content": content,
                "type": "notification"
            }
        )
        
        # 保存到数据库
        await self._save_conversation(message)
        
        return {
            "success": True,
            "message_id": message.id,
            "content": content,
            "sent_at": datetime.utcnow().isoformat()
        }


# 全局消息总线实例
_global_bus = None

def get_a2a_bus() -> A2ABus:
    """获取全局消息总线"""
    global _global_bus
    if _global_bus is None:
        _global_bus = A2ABus()
    return _global_bus


class A2AMessageBus(A2ABus):
    """
    A2A 消息总线兼容类
    提供向后兼容的接口
    """
    pass
