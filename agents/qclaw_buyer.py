"""
Qclaw-buyer 专用 Agent
核心职责：基于平台评估价与挂牌价的差距，实现动态出价逻辑
"""

from typing import Dict, Any, Optional
from agents.user_agent import UserAgent
from utils.price_tools import PriceEvaluator

class QclawBuyer(UserAgent):
    """
    Qclaw 买家 Agent
    专注于动态议价和博弈策略
    """
    
    def __init__(self, user_id: int, db_session, name: str = "Qclaw-buyer", email: str = None):
        super().__init__(user_id, db_session, name, email)
        self.role = "买家"

    def calculate_proposed_price(
        self, 
        car_info: Dict[str, Any], 
        round_index: int, 
        config: Dict[str, Any]
    ) -> float:
        """
        计算动态报价
        
        逻辑：
        1. 获取平台参考评估价
        2. 计算挂牌价与评估价的偏离度
        3. 根据轮次进行动态增量计算
        
        Args:
            car_info: 车辆信息（包含 price, brand, model, year, mileage）
            round_index: 当前议价轮次 (0 为初始询价, 1+ 为议价轮)
            config: 会话配置 (包含 buyer_target_price, buyer_budget_max)
            
        Returns:
            建议出价 (单位：万元)
        """
        display_price = float(car_info.get("price", 0))
        if display_price <= 0:
            return 0.0

        # 1. 获取市场评估参考
        market_ref = PriceEvaluator.get_market_reference(
            car_info.get("brand", ""),
            car_info.get("model", ""),
            car_info.get("year", 2020),
            car_info.get("mileage", 0)
        )
        market_avg = market_ref["market_avg"]
        
        # 2. 确定锚点价 (取展示价和市场均价的较小值)
        # 如果展示价远高于市场价，买家会更保守
        anchor_price = min(display_price, market_avg)
        
        # 3. 初始折扣率 (根据挂牌价相对于市场价的溢价程度决定)
        # 溢价越高，初始砍价越狠
        premium_ratio = display_price / market_avg if market_avg > 0 else 1.0
        
        if premium_ratio > 1.1: # 溢价超过 10%
            initial_discount = 0.90 # 从 9 折起谈
        elif premium_ratio < 0.95: # 挂牌价已经很低了
            initial_discount = 0.98 # 从 98 折起谈
        else:
            initial_discount = 0.94 # 默认从 94 折起谈

        # 4. 考虑用户设定的目标价和预算
        target_price = config.get("buyer_target_price")
        budget_max = config.get("buyer_budget_max")
        
        if target_price:
            base_offer = float(target_price)
        else:
            base_offer = anchor_price * initial_discount
            if budget_max:
                base_offer = min(base_offer, float(budget_max))

        # 5. 动态增量 (非线性)
        # 前几轮让步幅度稍大，后几轮逐渐收窄，表现出“到底了”的姿态
        # 步长系数受市场价与展示价差距的影响
        step_factor = 0.015 if display_price > market_avg else 0.01
        
        # 使用衰减函数计算增量
        # 轮次越多，增量越小
        if round_index <= 1:
            offer = base_offer
        else:
            # 模拟：第一轮出价 base，第二轮增加 1.5%，第三轮再增加 1%，第四轮增加 0.5%
            total_increment = 0
            for i in range(1, round_index):
                decay = 1.0 / i  # 1, 0.5, 0.33...
                total_increment += display_price * step_factor * decay
            offer = base_offer + total_increment

        # 6. 边界约束
        # 出价不能超过预算上限，也不能超过卖家展示价
        if budget_max:
            offer = min(offer, float(budget_max))
        
        final_offer = min(offer, display_price)
        
        return round(final_offer, 2)

    async def get_prompt(self, msg: Optional[Any], context: Dict[str, Any]) -> str:
        """针对 Qclaw 增强的 Prompt，强化评估价引用"""
        # 获取基本 Prompt
        base_prompt = await super().get_prompt(msg, context)
        
        # 获取评估价信息
        car_info = context.get("car_info", {})
        market_ref = PriceEvaluator.get_market_reference(
            car_info.get("brand", ""),
            car_info.get("model", ""),
            car_info.get("year", 2020),
            car_info.get("mileage", 0)
        )
        market_avg = market_ref["market_avg"]
        display_price = car_info.get("price", 0)
        
        # 注入 Qclaw 专用策略指令
        strategy_prompt = f"""
## Qclaw 议价策略 (P2 增强)
- 平台评估价: {market_avg} 万
- 挂牌价: {display_price} 万
- 指令：在议价回复中，请务必明确引用平台评估价。例如：“平台评估价约 {market_avg} 万，当前挂牌价 {display_price} 万，因此本轮出价为 X 万。”
- 逻辑：通过评估价与挂牌价的差距来支撑你的还价合理性。
"""
        return base_prompt + strategy_prompt

    def match_brands(self, brands: List[str], inventory: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量品牌匹配"""
        return [car for car in inventory if car.get("brand") in brands]

    def get_confirmation_message(self, price: float) -> str:
        """成交意向后的主动确认流程"""
        return f"我已确认接受 {price} 万元的方案，请问您那边也确定吗？如果没问题我们就达成意向了。"
