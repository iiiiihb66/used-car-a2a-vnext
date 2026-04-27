"""
二手车价格评估与对比工具
提供基于市场数据的价格参考
"""

from typing import Dict, Any, List
import random

class PriceEvaluator:
    """价格评估器"""
    
    @staticmethod
    def get_market_reference(brand: str, model: str, year: int, mileage: float) -> Dict[str, Any]:
        """
        获取市场参考价
        模拟真实评估逻辑：根据车龄和里程进行折旧计算
        """
        # 基础折旧逻辑（模拟数据）
        current_year = 2026
        age = current_year - year
        
        # 假设新车价（如果模型中没有，则根据品牌大致估算）
        # 这里简化处理，仅作为演示工具
        base_price_map = {
            "丰田": 15.0,
            "本田": 16.0,
            "比亚迪": 14.0,
            "大众": 18.0,
            "宝马": 35.0,
            "奔驰": 40.0
        }
        
        new_car_price = base_price_map.get(brand, 20.0)
        
        # 折旧率计算：前三年每年15%，之后每年10%，每万公里额外折旧1%
        depreciation = 1.0
        for i in range(age):
            if i < 3:
                depreciation *= 0.85
            else:
                depreciation *= 0.90
        
        depreciation -= (mileage / 10.0) * 0.01
        depreciation = max(depreciation, 0.2) # 最低残值 20%
        
        market_avg = round(new_car_price * depreciation, 2)
        
        return {
            "market_avg": market_avg,
            "price_range": {
                "low": round(market_avg * 0.92, 2),
                "high": round(market_avg * 1.08, 2)
            },
            "age": age,
            "mileage": mileage,
            "brand": brand,
            "model": model
        }

    @staticmethod
    def compare_with_market(current_price: float, market_ref: Dict[str, Any]) -> Dict[str, Any]:
        """与市场价对比"""
        avg = market_ref["market_avg"]
        diff = current_price - avg
        diff_percent = (diff / avg) * 100
        
        status = "合理"
        if diff_percent > 5:
            status = "偏高"
        elif diff_percent < -5:
            status = "偏低"
            
        return {
            "status": status,
            "diff_amount": round(diff, 2),
            "diff_percent": round(diff_percent, 1),
            "is_competitive": diff_percent <= 0
        }

class ConditionTemplate:
    """车况描述模板"""
    
    @staticmethod
    def get_structured_description(car_info: Dict[str, Any]) -> str:
        """获取结构化车况描述"""
        return f"""
【基本信息】{car_info.get('year')}年 {car_info.get('brand')} {car_info.get('model')}，行驶 {car_info.get('mileage')} 万公里。
【外观内饰】内饰整洁，仅主驾驶座椅有轻微磨损。外观原漆比例高，仅右前叶子板有喷漆修复。
【机械状况】发动机运行平稳，变速箱换挡顺滑，空调给力。
【历史记录】全程 4S 店保养，保养手册齐全，无事故记录，无泡水，无火烧。
【轮胎磨损】四条轮胎磨损约 30%，预计还能行驶 3-4 万公里。
        """.strip()
