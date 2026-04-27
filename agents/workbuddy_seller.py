"""
WorkBuddy-seller 专用 Agent
核心职责：结构化车况描述、价格依据支持、理解纠错机制
"""

from typing import Dict, Any, Optional, List
from agents.user_agent import UserAgent
from utils.price_tools import PriceEvaluator, ConditionTemplate

class WorkBuddySeller(UserAgent):
    """
    WorkBuddy 卖家 Agent
    专注于透明展示和专业议价
    """
    
    def __init__(self, user_id: int, db_session, name: str = "WorkBuddy-seller", email: str = None):
        super().__init__(user_id, db_session, name, email)
        self.role = "卖家"

    def get_structured_car_description(self, car_info: Dict[str, Any]) -> str:
        """提供结构化车况描述（外观/内饰/机械/历史）"""
        return ConditionTemplate.get_structured_description(car_info)

    def get_price_justification(self, car_info: Dict[str, Any]) -> str:
        """基于市场平均价、车龄、里程提供价格依据"""
        market_ref = PriceEvaluator.get_market_reference(
            car_info.get("brand", ""),
            car_info.get("model", ""),
            car_info.get("year", 2020),
            car_info.get("mileage", 0)
        )
        comparison = PriceEvaluator.compare_with_market(car_info.get("price", 0), market_ref)
        
        return f"【价格依据】同款市场价均值约为 {market_ref['market_avg']} 万。{comparison['justification']}。因此我们的挂牌价 {car_info.get('price')} 万是非常合理的。"

    def verify_price_consistency(self, verbal_price: float, system_price: float) -> Optional[str]:
        """
        理解纠错机制：检查口头报价与系统参数是否一致
        如果偏差超过 1%（排除浮点数误差），则触发纠错
        """
        if abs(verbal_price - system_price) / system_price > 0.01:
            return f"注意到您刚才提到的价格是 {verbal_price} 万，但我系统记录的挂牌价是 {system_price} 万，请问是以哪一个为准？"
        return None

    def hide_internal_instructions(self, content: str) -> str:
        """隐藏内部指令和思考过程"""
        # 简单实现：移除常见的内部指令前缀（如果模型不小心输出了）
        bad_prefixes = ["Thought:", "System:", "Instruction:", "Internal:"]
        for prefix in bad_prefixes:
            if content.startswith(prefix):
                content = content[len(prefix):].strip()
        return content
