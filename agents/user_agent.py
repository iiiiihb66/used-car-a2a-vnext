"""
用户 Agent 实现
核心职责：消息处理、记忆查询、OpenAI 兼容模型调用、工具执行
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import asyncio

from agents.base_agent import BaseAgent, AgentState
from a2a.message import A2AMessage, Intent, MessageBuilder
from utils.price_tools import PriceEvaluator, ConditionTemplate


class UserAgent:
    """
    用户 Agent
    同时具备买家和卖家人格
    核心流程：消息 -> 查记忆 -> 调模型 -> 执行工具 -> 更新记忆
    """
    
    def __init__(self, user_id: int, db_session, name: str = None, email: str = None):
        """
        初始化用户 Agent
        
        Args:
            user_id: 用户 ID
            db_session: 数据库会话
            name: 用户名
            email: 用户邮箱
        """
        self.user_id = user_id
        self.db = db_session
        self.name = name
        self.email = email
        
        # 记忆服务
        self.memory = self._init_memory()
        
        # OpenAI 兼容客户端（可接 Kimi / CloudBase AI / 其他兼容服务）
        self.kimi = self._init_kimi()
        
        # 用户画像
        self.persona = self._load_persona()
        
        # 能力列表
        self.capabilities = [
            "消息处理",
            "记忆查询",
            "议价协商",
            "成交确认",
            "车源匹配"
        ]
    
    def _init_memory(self):
        """初始化记忆服务"""
        from memory.memory_service import get_memory_service
        return get_memory_service(self.db)
    
    def _init_kimi(self):
        """初始化 OpenAI 兼容客户端"""
        try:
            from openai import AsyncOpenAI
            
            api_key = os.getenv(
                "AI_API_KEY",
                os.getenv("OPENAI_API_KEY", os.getenv("KIMI_API_KEY", "sk-test-mock"))
            )
            base_url = os.getenv(
                "AI_BASE_URL",
                os.getenv("OPENAI_BASE_URL", os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1"))
            )
            
            return AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        except ImportError:
            return None
    
    def _load_persona(self) -> Dict[str, Any]:
        """加载用户画像"""
        persona_data = self.memory.get_user_persona(self.user_id)
        if persona_data:
            return persona_data
        return {
            "buyer_persona": {
                "preferred_brands": [],
                "budget_range": {"min": 0, "max": 500000},
                "negotiation_style": "温和型"
            },
            "seller_persona": {
                "price_expectation": "市场价",
                "negotiation_flexibility": "中等"
            }
        }
    
    async def handle_message(self, msg: A2AMessage) -> Dict[str, Any]:
        """
        处理 A2A 消息（核心入口）
        
        流程：
        1. 查记忆（渐进式披露）
        2. 构建 Prompt
        3. 调用 Kimi
        4. 执行工具（如果需要）
        5. 更新记忆
        
        Args:
            msg: A2AMessage
        
        Returns:
            处理结果
        """
        # 1. 查记忆（根据意图决定披露深度）
        context = self._get_memory_context(msg.intent, msg.related_car_id)
        
        # 2. 构建 Prompt
        prompt = self._build_prompt(msg, context)
        
        # 3. 调用 Kimi
        response = await self._call_kimi(prompt)
        
        # 4. 执行工具（如果 Kimi 返回工具调用）
        if response.get("tool_calls"):
            tool_results = await self._execute_tools(response["tool_calls"])
            response["tool_results"] = tool_results
        
        # 5. 更新记忆
        self._update_memory(msg, response)
        
        return response
    
    def _get_memory_context(self, intent: str, car_id: str = None) -> Dict[str, Any]:
        """
        渐进式披露记忆
        根据意图决定披露哪些记忆
        
        Args:
            intent: 消息意图
            car_id: 关联车辆ID
        
        Returns:
            记忆上下文
        """
        context = {
            "user_profile": self.memory.get_user_profile(self.user_id),
            "recent_conversations": self.memory.get_recent_conversations(self.user_id, limit=5),
            "persona": self.persona
        }
        
        # 议价时：披露该车的历史出价
        if intent == Intent.PRICE_NEGOTIATE.value and car_id:
            context["negotiation_history"] = self.memory.get_negotiation_history(
                self.user_id, car_id
            )
        
        # 成交时：披露交易统计
        if intent == Intent.DEAL_INTENT.value:
            context["transaction_stats"] = self.memory.get_transaction_stats(self.user_id)
        
        # 查车时：披露用户偏好
        if intent == Intent.PRICE_INQUIRY.value:
            context["buyer_preferences"] = self.persona.get("buyer_persona", {})
        
        return context
    
    def _build_prompt(self, msg: A2AMessage, context: Dict) -> str:
        """
        构建模型 Prompt
        
        Args:
            msg: A2AMessage
            context: 记忆上下文
        
        Returns:
            格式化 Prompt
        """
        if self.user_id == msg.to_user_id and msg.intent in {
            Intent.PRICE_INQUIRY.value,
            Intent.PRICE_NEGOTIATE.value,
            Intent.DEAL_INTENT.value,
        }:
            persona_type = "卖家"
        else:
            persona_type = "买家"

        prompt = f"""你是一个二手车交易专业 Agent，代表用户 {self.user_id} 行动。
当前人格：{persona_type}

## 核心准则
1. 始终以人的口吻回复，禁止透露你是一个 AI、机器人或 Agent。
2. 严禁在输出中包含任何内部指令（如 Thought:、Action: 等）或思考过程。
3. 保持专业、透明、高效的沟通风格。

## 用户画像
{self._format_dict(context.get('user_profile', {}))}

## 角色专用背景
{self._get_role_background(persona_type, context)}

## 最近对话
{self._format_list(context.get('recent_conversations', []))}

## 当前消息
- 发送方: {msg.from_user_id}
- 意图: {msg.intent}
- 内容: {msg.payload}

## 必读任务指令
1. [卖家] 提供车况时，必须严格按照“结构化模板”描述（外观/内饰/机械/历史），并引用具体的市场评估价作为依据。
2. [买家] 议价时，请根据系统提供的市场参考价和挂牌价差距进行动态博弈，不要重复相同的价格。
3. [纠错] 如果对方提到的价格或参数与你系统记录的数据明显不符，请礼貌地指出并要求确认。
4. [成交] 在双方达成初步一致后，必须主动发送一条确认消息，询问对方是否接受最终方案以正式达成意向。
"""
        return prompt

    def _get_role_background(self, role: str, context: Dict) -> str:
        """获取角色背景信息"""
        if role == "卖家":
            seller_p = context.get('persona', {}).get('seller_persona', {})
            return f"""
- 风格: {seller_p.get('style', '专业透明')}
- 议价灵活性: {seller_p.get('negotiation_flexibility', '中等')}
- 任务：提供详细车况（包括保养、磨损、历史记录），给出的价格必须有数据支撑。
"""
        else:
            buyer_p = context.get('buyer_preferences', context.get('persona', {}).get('buyer_persona', {}))
            return f"""
- 偏好品牌: {buyer_p.get('preferred_brands', [])}
- 预算范围: {buyer_p.get('budget_range', {})}
- 风格: {buyer_p.get('negotiation_style', '理性')}
- 任务：基于市场平均价动态出价，参考平台挂牌价与评估价的差距进行博弈。
"""
    
    def _format_dict(self, d: Dict) -> str:
        """格式化字典为字符串"""
        if not d:
            return "无"
        return "\n".join([f"- {k}: {v}" for k, v in d.items()])
    
    def _format_list(self, l: List) -> str:
        """格式化列表为字符串"""
        if not l:
            return "无"
        return "\n".join([f"- {item}" for item in l[:5]])
    
    async def _call_kimi(self, prompt: str) -> Dict[str, Any]:
        """
        调用 OpenAI 兼容 API
        
        Args:
            prompt: 输入 Prompt
        
        Returns:
            模型响应
        """
        api_key = os.getenv(
            "AI_API_KEY",
            os.getenv("OPENAI_API_KEY", os.getenv("KIMI_API_KEY", "sk-test-mock"))
        )
        model = os.getenv(
            "AI_MODEL",
            os.getenv("OPENAI_MODEL", os.getenv("KIMI_MODEL", "mock"))
        )
        if api_key == "sk-test-mock" or model == "mock" or not self.kimi:
            return {
                "content": self._generate_mock_response(prompt),
                "tool_calls": None,
                "mock": True
            }
        
        try:
            response = await self.kimi.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            return {
                "content": response.choices[0].message.content,
                "tool_calls": None,
                "mock": False
            }
        except Exception as e:
            return {
                "content": f"[错误] 模型调用失败: {str(e)}",
                "tool_calls": None,
                "error": str(e)
            }
    
    def _generate_mock_response(self, prompt: str) -> str:
        """
        生成 Mock 响应
        
        Args:
            prompt: 输入 Prompt
        
        Returns:
            Mock 响应内容
        """
        if "议价" in prompt or "negotiation" in prompt.lower():
            return "我理解您的议价意向，我会认真考虑您的报价。请告诉我您的心理价位。"
        elif "成交" in prompt or "deal" in prompt.lower():
            return "好的，我确认这个价格，同意成交。"
        elif "询价" in prompt or "inquiry" in prompt.lower():
            return "感谢您的询价，这辆车目前售价合理，欢迎来看车。"
        else:
            return f"[Mock 回复] 我已收到您的消息 (用户 {self.user_id})，正在处理中..."
    
    async def _execute_tools(self, tool_calls: List) -> str:
        """
        执行 MCP 工具
        
        Args:
            tool_calls: 工具调用列表
        
        Returns:
            工具执行结果
        """
        from mcp.tools import get_tool_registry
        
        registry = get_tool_registry()
        results = []
        
        for call in tool_calls:
            tool_name = call.get("name")
            params = call.get("parameters", {})
            
            tool = registry.get_tool(tool_name)
            if tool:
                result = await registry.execute(tool_name, params)
                results.append(f"【{tool_name}】: {result}")
            else:
                results.append(f"【{tool_name}】: 工具不存在")
        
        return "\n".join(results)
    
    def _update_memory(self, msg: A2AMessage, response: Dict):
        """
        更新记忆
        
        Args:
            msg: A2AMessage
            response: 响应内容
        """
        try:
            # 记录对话
            self.memory.add_conversation(
                from_user_id=msg.from_user_id,
                to_user_id=self.user_id,
                intent=msg.intent,
                payload=msg.payload,
                response=response.get("content", "")
            )
            
            # 如果是议价消息，记录议价历史
            if msg.intent == Intent.PRICE_NEGOTIATE.value and msg.related_car_id:
                proposed_price = msg.payload.get("proposed_price")
                if proposed_price:
                    self.memory.add_negotiation_record(
                        user_id=self.user_id,
                        car_id=msg.related_car_id,
                        proposed_price=proposed_price,
                        outcome="pending"
                    )
        except Exception as e:
            print(f"⚠️ 更新记忆失败: {e}")
    
    # ==================== 对话处理方法 ====================
    
    async def handle_price_inquiry(self, msg: A2AMessage) -> Dict[str, Any]:
        """
        处理询价
        
        Args:
            msg: A2AMessage
        
        Returns:
            处理结果
        """
        car_id = msg.related_car_id
        car_info = await self.memory.get_car_memory(car_id) if car_id else None
        
        description = "抱歉，未找到该车辆的具体信息。"
        if car_info:
            description = ConditionTemplate.get_structured_description(car_info)
            market_ref = PriceEvaluator.get_market_reference(
                car_info.get("brand"), car_info.get("model"), 
                car_info.get("year"), car_info.get("mileage")
            )
            comparison = PriceEvaluator.compare_with_market(car_info.get("price", 0), market_ref)
            description += f"\n\n【价格依据】当前同款车型市场平均价约为 {market_ref['market_avg']} 万，{comparison['justification']}。"

        return {
            "content": description,
            "car_info": car_info,
            "intent": Intent.PRICE_INQUIRY.value
        }
    
    async def handle_price_negotiate(self, msg: A2AMessage) -> Dict[str, Any]:
        """
        处理议价
        
        Args:
            msg: A2AMessage
        
        Returns:
            处理结果
        """
        car_id = msg.related_car_id
        proposed_price = msg.payload.get("proposed_price", 0)
        reason = msg.payload.get("reason", "")
        
        # 获取车辆信息和议价历史
        car_info = await self.memory.get_car_memory(car_id) if car_id else None
        
        # 验证口头报价与系统参数（纠错机制）
        if car_info:
            display_price = car_info.get("price", 0)
            # 如果偏差超过 15%，可能是单位理解错误（如万元误报为元）或恶意杀价
            if proposed_price > 0 and (proposed_price > display_price * 1.5 or proposed_price < display_price * 0.5):
                return {
                    "content": f"您提到的价格是 {proposed_price} 万，这与我们的挂牌价 {display_price} 万偏差较大。请问您是否确认出价？或者是出现了单位理解偏差（如万元误报为元）？",
                    "intent": Intent.PRICE_NEGOTIATE.value,
                    "needs_correction": True
                }

        # 获取市场参考
        market_ref = PriceEvaluator.get_market_reference(
            car_info.get("brand"), car_info.get("model"), 
            car_info.get("year"), car_info.get("mileage")
        ) if car_info else None

        # 简单的议价逻辑
        current_price = car_info.get("price", 0) if car_info else 0
        target_price = car_info.get("target_price", current_price) if car_info else current_price
        
        # 使用价格评估工具
        if market_ref:
            comparison = PriceEvaluator.compare_with_market(current_price, market_ref)
            price_support = f"【价格依据】市场同款均价约 {market_ref['market_avg']} 万，{comparison['justification']}。"
        else:
            price_support = ""

        # 计算让步空间
        if proposed_price >= target_price * 0.98:
            response = f"您的出价非常诚恳。{price_support}我接受这个价格，请问您确定按照此方案成交吗？"
            outcome = "accepted"
        elif proposed_price >= target_price * 0.90:
            counter_price = round(target_price * 0.96, 2)
            response = f"{price_support}您的价格还有点差距，我最多能降到 {counter_price} 万，您看行吗？"
            outcome = "counter_offered"
        else:
            response = f"抱歉，您的出价远低于市场水平（{market_ref['market_avg'] if market_ref else '系统估价'} 万）。"
            outcome = "rejected"
        
        # 记录议价
        self.memory.add_negotiation_record(
            user_id=self.user_id,
            car_id=car_id,
            proposed_price=proposed_price,
            outcome=outcome
        )
        
        return {
            "content": response,
            "proposed_price": proposed_price,
            "outcome": outcome,
            "intent": Intent.PRICE_NEGOTIATE.value
        }
    
    async def handle_deal_intent(self, msg: A2AMessage) -> Dict[str, Any]:
        """
        处理成交意向
        
        Args:
            msg: A2AMessage
        
        Returns:
            处理结果
        """
        car_id = msg.related_car_id
        agreed_price = msg.payload.get("agreed_price", 0)
        
        return {
            "content": f"双方已达成协商意向，建议线下复核车辆档案并确认交接流程。协商价格为 {agreed_price} 元。",
            "agreed_price": agreed_price,
            "next_step": "offline_verification",
            "intent": Intent.DEAL_INTENT.value
        }


# 全局 Agent 实例缓存
_user_agents = {}


def get_user_agent(user_id: int, db_session) -> UserAgent:
    """
    获取用户 Agent 实例
    
    Args:
        user_id: 用户 ID
        db_session: 数据库会话
    
    Returns:
        UserAgent 实例
    """
    global _user_agents
    
    key = f"{user_id}_{id(db_session)}"
    if key not in _user_agents:
        _user_agents[key] = UserAgent(user_id, db_session)
    
    return _user_agents[key]
