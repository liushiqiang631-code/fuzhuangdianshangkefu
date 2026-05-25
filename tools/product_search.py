"""
结构化商品搜索工具
支持按分类、价格、颜色、尺码等条件过滤商品
"""
import json
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool

PRODUCTS_FILE = Path("./data/docs/products.json")


def _load_products() -> list:
    """加载商品数据"""
    if not PRODUCTS_FILE.exists():
        return []
    try:
        return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


@tool
def search_products(
    category: str = "",
    min_price: float = 0,
    max_price: float = 99999,
    color: str = "",
    size: str = "",
) -> str:
    """结构化搜索商品，支持按分类、价格区间、颜色、尺码筛选。
    当用户提出明确的筛选条件时使用此工具（如"200元以下的上装"、"有黑色的S码吗"）。

    Args:
        category: 商品分类关键词（如"上装"、"裤装"、"外套"、"连衣裙"），留空则不限
        min_price: 最低价格，留空则不限
        max_price: 最高价格，留空则不限
        color: 颜色关键词（如"黑色"、"白色"），留空则不限
        size: 尺码关键词（如"S"、"M"、"L"），留空则不限
    """
    products = _load_products()
    if not products:
        return "商品数据暂未加载，请稍后再试。"

    results = []
    for p in products:
        # 分类过滤
        if category and category not in p.get("category", "") and category not in p.get("name", ""):
            continue
        # 价格过滤
        price = p.get("price", 0)
        if price < min_price or price > max_price:
            continue
        # 颜色过滤
        if color:
            colors = p.get("colors", [])
            if not any(color in c for c in colors):
                continue
        # 尺码过滤
        if size:
            sizes = p.get("sizes", [])
            if not any(size.upper() in s.upper() for s in sizes):
                continue

        # 格式化结果
        image_url = p.get("image_url", "")
        original_price = p.get("original_price", 0)
        price = p.get("price", 0)
        discount = ""
        if original_price and original_price > price:
            discount = f"（原价¥{original_price}，省¥{original_price - price:.0f}）"

        card = f"【{p['name']}】\n"
        card += f"  分类: {p.get('category', '-')}\n"
        card += f"  价格: ¥{price}{discount}\n"
        card += f"  材质: {p.get('material', '-')}\n"
        card += f"  颜色: {', '.join(p.get('colors', []))}\n"
        card += f"  尺码: {', '.join(p.get('sizes', []))}\n"
        card += f"  描述: {p.get('description', '-')}"
        tags = p.get("tags", [])
        if tags:
            card += f"\n  标签: {', '.join(tags)}"
        stock = p.get("stock_status", "")
        if stock:
            card += f"\n  库存: {stock}"
        if image_url:
            card += f"\n  图片: {image_url}"
        results.append(card)

    if not results:
        return "没有找到符合条件的商品，试试放宽筛选条件？"

    header = f"找到 {len(results)} 件符合条件的商品：\n\n"
    return header + "\n\n".join(results)


@tool
def list_categories() -> str:
    """列出所有商品分类。当用户问"有什么品类"、"你们卖什么"时使用。"""
    products = _load_products()
    if not products:
        return "商品数据暂未加载。"

    categories = set()
    for p in products:
        cat = p.get("category", "")
        if cat:
            categories.add(cat)

    result = "本店商品分类：\n"
    for cat in sorted(categories):
        count = sum(1 for p in products if p.get("category") == cat)
        result += f"- {cat}（{count}件）\n"
    result += f"\n共 {len(categories)} 个分类，{len(products)} 件商品。"
    return result
