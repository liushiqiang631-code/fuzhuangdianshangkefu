"""
智能推荐工具
根据上下文动态推荐问题，支持基于用户画像的个性化推荐
"""
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path
from langchain_core.tools import tool

logger = logging.getLogger("zhice-platform.recommendation")

PRODUCTS_FILE = Path("./data/docs/products.json")
PROFILES_DIR = Path("./data/profiles")


def _load_products() -> list:
    """加载商品数据"""
    if not PRODUCTS_FILE.exists():
        return []
    try:
        return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def get_context_based_recommendations(
    user_message: str,
    assistant_reply: str = "",
    tools_used: List[str] = None,
) -> List[str]:
    """
    根据上下文生成推荐问题

    Args:
        user_message: 用户消息
        assistant_reply: 助手回复
        tools_used: 使用的工具列表

    Returns:
        推荐问题列表
    """
    recommendations = []

    # 根据用户消息关键词推荐
    if "推荐" in user_message or "搭配" in user_message:
        recommendations.extend([
            "这件有其他颜色吗？",
            "适合什么场合穿？",
            "搭配什么鞋子好看？",
        ])

    elif "订单" in user_message or "物流" in user_message:
        recommendations.extend([
            "还有其他订单吗？",
            "预计什么时候到？",
            "怎么申请退换货？",
        ])

    elif "价格" in user_message or "优惠" in user_message:
        recommendations.extend([
            "有什么优惠活动？",
            "会员有什么折扣？",
            "满多少可以包邮？",
        ])

    elif "尺码" in user_message or "尺寸" in user_message:
        recommendations.extend([
            "我穿多大合适？",
            "有大码吗？",
            "可以退换吗？",
        ])

    elif "材质" in user_message or "面料" in user_message:
        recommendations.extend([
            "怎么洗护？",
            "会起球吗？",
            "透气吗？",
        ])

    # 根据工具使用推荐
    if tools_used:
        if "search_products" in tools_used:
            recommendations.append("还有其他类似款式吗？")
        if "calculate_price" in tools_used:
            recommendations.append("怎么使用优惠券？")

    # 默认推荐
    if not recommendations:
        recommendations = [
            "有什么新品推荐？",
            "最近有什么活动？",
            "怎么联系人工客服？",
        ]

    # 去重并限制数量
    unique_recommendations = list(dict.fromkeys(recommendations))[:4]

    return unique_recommendations


@tool
def get_dynamic_recommendations(
    user_message: str,
    context: str = "",
    user_id: str = "",
) -> str:
    """根据对话上下文和用户画像生成个性化推荐。当用户完成一个问题后自动调用。

    Args:
        user_message: 用户的上一条消息
        context: 对话上下文（可选）
        user_id: 用户ID（用于个性化推荐，可选）
    """
    recommendations = get_context_based_recommendations(user_message)

    # 基于用户画像的个性化推荐
    if user_id:
        personalized = _get_personalized_recommendations(user_id)
        if personalized:
            recommendations = personalized + recommendations

    if not recommendations:
        return ""

    # 去重
    recommendations = list(dict.fromkeys(recommendations))[:5]

    result = "您可能还想问：\n"
    for i, rec in enumerate(recommendations, 1):
        result += f"{i}. {rec}\n"

    return result


def _load_user_profile(user_id: str) -> Optional[Dict]:
    """加载用户画像"""
    profile_file = PROFILES_DIR / f"{user_id}.json"
    if not profile_file.exists():
        return None
    try:
        return json.loads(profile_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def _get_personalized_recommendations(user_id: str) -> List[str]:
    """
    基于用户画像生成个性化推荐

    Args:
        user_id: 用户ID

    Returns:
        个性化推荐问题列表
    """
    profile = _load_user_profile(user_id)
    if not profile:
        return []

    prefs = profile.get("preferences", {})
    recommendations = []

    # 基于偏好品类推荐
    categories = prefs.get("categories", [])
    if categories:
        cat = categories[-1]  # 最近关注的品类
        recommendations.append(f"有什么新款{cat}推荐？")

    # 基于偏好风格推荐
    styles = prefs.get("styles", [])
    if styles:
        style = styles[-1]
        recommendations.append(f"有没有{style}风格的新品？")

    # 基于预算推荐
    budget_max = prefs.get("budget_max", 0)
    if budget_max > 0:
        recommendations.append(f"{budget_max}元以内有什么好推荐？")

    # 基于历史消费推荐
    history = profile.get("history", {})
    if history.get("total_orders", 0) > 0:
        recommendations.append("查看我的会员权益")

    return recommendations


def get_quick_replies(
    category: str = "general",
) -> List[str]:
    """
    获取快捷回复

    Args:
        category: 分类（general/product/order/payment）

    Returns:
        快捷回复列表
    """
    quick_replies = {
        "general": [
            "有什么新品推荐？",
            "最近有什么活动？",
            "怎么联系人工客服？",
        ],
        "product": [
            "这件有其他颜色吗？",
            "有尺码表吗？",
            "材质是什么？",
            "怎么洗护？",
        ],
        "order": [
            "查一下我的订单",
            "物流到哪了？",
            "怎么申请退换货？",
        ],
        "payment": [
            "可以用什么支付方式？",
            "有优惠券吗？",
            "支持分期吗？",
        ],
    }

    return quick_replies.get(category, quick_replies["general"])
