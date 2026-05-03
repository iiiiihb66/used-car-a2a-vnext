"""
Excel 批量导入解析工具
用于车商上传车辆清单 Excel 文件
"""

from typing import Any, Dict, List, Optional, Tuple


def parse_car_excel(file_path: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    解析车源导入 Excel，返回 (cars, errors)

    Excel 预期列:
        brand, series, model, year, price, mileage
        可选: target_price, color, transmission, fuel_type,
              region, city, report_url, image_urls(逗号分隔), engine,
              original_price, plate_number, configuration(JSON),
              condition_assessment(JSON)

    返回:
        cars:   List[Dict], 每辆车的字段字典
        errors: List[str], 解析中的错误信息
    """
    try:
        import openpyxl
    except ImportError:
        return [], ["缺少 openpyxl 依赖，请执行: pip install openpyxl"]

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        wb.close()
        return [], ["Excel 文件没有有效工作表"]

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        wb.close()
        return [], ["Excel 文件缺少数据行（至少需要表头 + 1行数据）"]

    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    required = {"brand", "model", "year", "price", "mileage"}
    missing = required - set(headers)
    if missing:
        wb.close()
        return [], [f"缺少必需列: {', '.join(sorted(missing))}"]

    cars: List[Dict[str, Any]] = []
    errors: List[str] = []
    field_map = {
        "brand": "brand",
        "series": "series",
        "model": "model",
        "year": "year",
        "price": "price",
        "original_price": "original_price",
        "target_price": "target_price",
        "mileage": "mileage",
        "color": "color",
        "transmission": "transmission",
        "fuel_type": "fuel_type",
        "region": "region",
        "city": "city",
        "engine": "engine",
        "plate_number": "plate_number",
        "report_url": "report_url",
        "image_urls": "image_urls",  # 逗号分隔字符串
    }

    for i, row in enumerate(rows[1:], start=2):
        if all(cell is None or (isinstance(cell, str) and cell.strip() == "") for cell in row):
            continue  # 跳过空行

        car: Dict[str, Any] = {}
        row_errors: List[str] = []
        has_value = False

        for col_idx, header in enumerate(headers):
            if not header:
                continue
            value = row[col_idx] if col_idx < len(row) else None
            target_field = field_map.get(header)
            if target_field:
                has_value = True
                if value is not None:
                    car[target_field] = value

        if not has_value:
            continue

        # 验证必需字段
        brand = car.get("brand")
        model = car.get("model")
        year = car.get("year")
        price = car.get("price")
        mileage = car.get("mileage")

        if not brand:
            row_errors.append("缺少 brand")
        if not model:
            row_errors.append("缺少 model")
        if year is None or not _to_number(year):
            row_errors.append("year 无效")
        if price is None or _to_number(price, 0) <= 0:
            row_errors.append("price 无效或 <= 0")
        if mileage is None or _to_number(mileage, -1) < 0:
            row_errors.append("mileage 无效")

        if row_errors:
            errors.append(f"第 {i} 行: {', '.join(row_errors)}")
            continue

        # 类型转换
        car["year"] = int(_to_number(car["year"]))
        car["price"] = float(_to_number(car["price"]))
        car["mileage"] = float(_to_number(car["mileage"]))

        if car.get("target_price"):
            car["target_price"] = float(_to_number(car["target_price"]))
        if car.get("original_price"):
            car["original_price"] = float(_to_number(car["original_price"]))

        # image_urls 逗号分隔 → 列表
        if isinstance(car.get("image_urls"), str):
            urls = [u.strip() for u in car["image_urls"].split(",") if u.strip()]
            car["image_urls"] = urls if urls else None

        cars.append(car)

    wb.close()
    return cars, errors


def _to_number(value, default=None):
    """安全地将值转为数字"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return default
