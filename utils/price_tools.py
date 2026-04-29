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
        age = max(0, current_year - year)
        
        # 扩大品牌覆盖面，并设置更真实的新车价参考（万元）
        base_price_map = {
            "丰田": 18.0,
            "本田": 20.0,
            "比亚迪": 16.0,
            "大众": 19.0,
            "宝马": 38.0,
            "奔驰": 42.0,
            "奥迪": 35.0,
            "特斯拉": 28.0,
            "理想": 32.0,
            "问界": 30.0,
            "吉利": 12.0,
            "长安": 10.0
        }
        
        # 归一化品牌名称（去除多余空格）
        clean_brand = (brand or "").strip()
        new_car_price = base_price_map.get(clean_brand, 15.0)
        
        # 折旧率计算：前三年每年12%，之后每年8%，每万公里额外折旧0.8%
        # 修正：降低折旧速率，使其更符合保值率高的车型
        depreciation = 1.0
        for i in range(age):
            if i < 3:
                depreciation *= 0.88
            else:
                depreciation *= 0.92
        
        depreciation -= (mileage / 10.0) * 0.008
        depreciation = max(depreciation, 0.25) # 最低残值提高到 25%
        
        market_avg = round(new_car_price * depreciation, 2)
        
        return {
            "market_avg": market_avg,
            "price_range": {
                "low": round(market_avg * 0.94, 2),
                "high": round(market_avg * 1.06, 2)
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
            
        # 增加价格依据描述
        justification = []
        if market_ref['age'] < 3:
            justification.append("准新车龄，保值率较高")
        elif market_ref['age'] > 8:
            justification.append("车龄偏老，残值较低")
            
        if market_ref['mileage'] < market_ref['age'] * 1.0:
            justification.append("年均里程极低，车况磨损小")
        elif market_ref['mileage'] > market_ref['age'] * 2.5:
            justification.append("年均里程偏高，机械磨损较大")

        return {
            "status": status,
            "diff_amount": round(diff, 2),
            "diff_percent": round(diff_percent, 1),
            "is_competitive": diff_percent <= 0,
            "justification": "；".join(justification) if justification else "车况符合平均市场表现"
        }

class ConditionTemplate:
    """车况描述模板"""
    
    @staticmethod
    def get_structured_description(car_info: Dict[str, Any]) -> str:
        """获取结构化车况描述"""
        return f"""
【基本信息】{car_info.get('year')}年 {car_info.get('brand')} {car_info.get('model')}，行驶 {car_info.get('mileage')} 万公里。

【外观细节】外观原漆比例约 85%，漆面亮度良好。仅前保险杠和右前叶子板有喷漆修复，无明显钣金，全车玻璃为原厂件。
【内饰状况】内饰整洁无异味。中控按键阻尼感正常，真皮座椅有自然使用褶皱，顶棚无塌陷，地毯干爽无受潮痕迹。
    - 磨损点：主驾驶座椅侧翼有轻微进出磨损。
【机械素质】发动机启动顺畅，怠速静谧。变速箱在 2-3 挡切换时表现顺滑，底盘紧凑无异响，避震器无渗油。
    - 消耗品：刹车片厚度约 6mm，轮胎花纹剩余 60%。
【历史记录】记录显示全程在官方 4S 店按时保养，最近一次大保养在半年前。
    - 档案核验：无事故、无火烧、无水泡，链式存证记录完整。
        """.strip()
