"""
商品详情页工具
支持查看商品详细信息、库存、评价
"""
import json
from pathlib import Path
from typing import Dict, Optional
from langchain_core.tools import tool

PRODUCTS_FILE = Path("./data/docs/products.json")
REVIEWS_FILE = Path("./data/docs/reviews.json")


def _load_products() -> list:
    """加载商品数据"""
    if not PRODUCTS_FILE.exists():
        return []
    try:
        return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _load_reviews() -> list:
    """加载评价数据"""
    if not REVIEWS_FILE.exists():
        return []
    try:
        return json.loads(REVIEWS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


@tool
def get_product_detail(product_name: str) -> str:
    """获取商品详细信息。当用户说"看看这件"、"详细介绍"、"商品详情"时使用。

    Args:
        product_name: 商品名称（关键词即可）
    """
    products = _load_products()

    # 查找商品
    product = None
    for p in products:
        if product_name in p.get("name", ""):
            product = p
            break

    if not product:
        return f"未找到商品 {product_name}，请确认商品名称。"

    # 构建详情
    result = f"商品详情：{product['name']}\n"
    result += "=" * 40 + "\n\n"

    result += f"分类: {product.get('category', '-')}\n"
    result += f"价格: {product.get('price', 0)} 元"
    if product.get('original_price') and product['original_price'] > product['price']:
        result += f" (原价 {product['original_price']} 元，省 {product['original_price'] - product['price']:.0f} 元)"
    result += "\n\n"

    result += f"材质: {product.get('material', '-')}\n"
    result += f"颜色: {', '.join(product.get('colors', []))}\n"
    result += f"尺码: {', '.join(product.get('sizes', []))}\n\n"

    result += f"商品描述:\n{product.get('description', '-')}\n\n"

    if product.get('care_instructions'):
        result += f"洗护说明:\n{product['care_instructions']}\n\n"

    if product.get('size_chart'):
        result += "尺码表:\n"
        for size_label, size_desc in product['size_chart'].items():
            result += f"  {size_label}: {size_desc}\n"
        result += "\n"

    tags = product.get('tags', [])
    if tags:
        result += f"标签: {', '.join(tags)}\n"

    result += f"库存状态: {product.get('stock_status', '-')}\n"

    # 加载评价
    reviews = _load_reviews()
    product_reviews = [r for r in reviews if r.get('product_name') == product['name']]

    if product_reviews:
        avg_rating = sum(r.get('rating', 0) for r in product_reviews) / len(product_reviews)
        result += f"\n用户评价 (共 {len(product_reviews)} 条，平均 {avg_rating:.1f} 分):\n"
        for r in product_reviews[:3]:  # 只显示前3条
            stars = '*' * int(r.get('rating', 0))
            result += f"  - {stars} {r.get('comment', '-')}\n"

    return result


@tool
def check_stock(
    product_name: str,
    color: str = "",
    size: str = "",
) -> str:
    """查询商品库存。当用户问"有货吗"、"还有库存吗"时使用。

    Args:
        product_name: 商品名称
        color: 颜色
        size: 尺码
    """
    products = _load_products()

    product = None
    for p in products:
        if product_name in p.get("name", ""):
            product = p
            break

    if not product:
        return f"未找到商品 {product_name}。"

    stock_status = product.get("stock_status", "未知")
    available_colors = product.get("colors", [])
    available_sizes = product.get("sizes", [])

    result = f"库存查询：{product['name']}\n\n"
    result += f"整体状态: {stock_status}\n"

    # 当前商品数据只有整体库存状态，无按颜色/尺码的库存明细。
    # 传了颜色/尺码时校验其是否在售，避免对合法颜色误报"无此颜色"。
    if color:
        matched = next((c for c in available_colors if color in c), None)
        if matched:
            result += f"颜色 {matched}: 在售\n"
        else:
            result += f"颜色 {color}: 该商品没有此颜色，可选颜色：{', '.join(available_colors) or '暂无'}\n"

    if size:
        matched_size = next((s for s in available_sizes if size.upper() in s.upper()), None)
        if matched_size:
            result += f"尺码 {matched_size}: 在售\n"
        else:
            result += f"尺码 {size}: 该商品没有此尺码，可选尺码：{', '.join(available_sizes) or '暂无'}\n"

    if "紧张" in stock_status:
        result += "\n提示：部分色号/尺码库存紧张，建议尽快下单。"

    return result
