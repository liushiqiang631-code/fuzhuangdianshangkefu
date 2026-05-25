"""
用户激活与管理模块
处理用户注册、激活、会员等级等功能
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from langchain_core.tools import tool


# ========== 模拟用户数据 ==========
USERS_DB: Dict[str, dict] = {
    "U10001": {
        "user_id": "U10001",
        "nickname": "小明",
        "phone": "138****1234",
        "email": "xiaoming@example.com",
        "member_level": "银卡",
        "points": 1280,
        "registered_at": "2025-12-15 10:30:00",
        "last_active": "2026-05-03 14:22:00",
        "total_orders": 5,
        "total_spent": 1856.00,
        "status": "已激活",
        "preferences": {"favorite_colors": ["黑色", "白色"], "favorite_styles": ["休闲", "运动"]},
    },
    "U10002": {
        "user_id": "U10002",
        "nickname": "小红",
        "phone": "139****5678",
        "email": "xiaohong@example.com",
        "member_level": "金卡",
        "points": 3560,
        "registered_at": "2025-08-20 16:45:00",
        "last_active": "2026-05-04 09:10:00",
        "total_orders": 12,
        "total_spent": 4280.00,
        "status": "已激活",
        "preferences": {"favorite_colors": ["粉色", "米色"], "favorite_styles": ["淑女", "通勤"]},
    },
    "U10003": {
        "user_id": "U10003",
        "nickname": "大壮",
        "phone": "137****9012",
        "email": "dazhuang@example.com",
        "member_level": "普通",
        "points": 200,
        "registered_at": "2026-04-01 08:00:00",
        "last_active": "2026-04-01 08:15:00",
        "total_orders": 1,
        "total_spent": 599.00,
        "status": "已激活",
        "preferences": {"favorite_colors": ["黑色", "军绿色"], "favorite_styles": ["户外", "运动"]},
    },
    "U10004": {
        "user_id": "U10004",
        "nickname": "小美",
        "phone": "136****3456",
        "email": "xiaomei@example.com",
        "member_level": "钻石",
        "points": 8900,
        "registered_at": "2024-06-10 12:00:00",
        "last_active": "2026-05-05 10:30:00",
        "total_orders": 35,
        "total_spent": 12600.00,
        "status": "已激活",
        "preferences": {"favorite_colors": ["花色", "白色"], "favorite_styles": ["法式", "优雅"]},
    },
    "U10005": {
        "user_id": "U10005",
        "nickname": "新人用户",
        "phone": "135****7890",
        "email": "newuser@example.com",
        "member_level": "普通",
        "points": 0,
        "registered_at": "2026-05-05 11:00:00",
        "last_active": "2026-05-05 11:00:00",
        "total_orders": 0,
        "total_spent": 0,
        "status": "未激活",
        "preferences": {},
    },
}


@tool
def activate_user(user_id: str, activation_code: str = "") -> str:
    """激活新注册用户。这是敏感操作，调用前必须先告知用户将要激活账户并获得用户确认。

    Args:
        user_id: 用户ID
        activation_code: 激活码（可选，留空则自动激活）
    """
    user = USERS_DB.get(user_id.upper())
    if not user:
        return json.dumps({"error": f"未找到用户 {user_id}"}, ensure_ascii=False)

    if user["status"] == "已激活":
        return json.dumps({
            "message": f"用户 {user['nickname']} 已经是激活状态，无需重复激活",
            "user_id": user_id,
            "member_level": user["member_level"],
        }, ensure_ascii=False)

    # 激活用户
    user["status"] = "已激活"
    user["last_active"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 新用户赠送优惠券
    coupons = [
        {"type": "新人专享券", "amount": 20, "threshold": 100, "expires": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")},
        {"type": "首单9折券", "amount": 0, "discount": 0.9, "expires": (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")},
    ]

    return json.dumps({
        "message": f"🎉 恭喜 {user['nickname']}，账户激活成功！",
        "user_id": user_id,
        "welcome_gifts": {
            "积分": 100,
            "优惠券": coupons,
        },
        "next_step": "您已获得新人专属福利，快去选购心仪的商品吧！",
    }, ensure_ascii=False, indent=2)


@tool
def get_user_info(user_id: str) -> str:
    """查询用户信息，包括会员等级、积分、消费记录等。

    Args:
        user_id: 用户ID
    """
    user = USERS_DB.get(user_id.upper())
    if not user:
        return json.dumps({"error": f"未找到用户 {user_id}"}, ensure_ascii=False)

    # 计算距离下一等级的消费差额
    level_thresholds = {"普通": 500, "银卡": 2000, "金卡": 5000, "钻石": float("inf")}
    next_levels = {"普通": "银卡", "银卡": "金卡", "金卡": "钻石", "钻石": None}
    current_level = user["member_level"]
    next_level = next_levels.get(current_level)
    gap = 0
    if next_level:
        gap = level_thresholds[next_level] - user["total_spent"]

    result = {
        "用户ID": user["user_id"],
        "昵称": user["nickname"],
        "手机": user["phone"],
        "会员等级": current_level,
        "积分": user["points"],
        "累计消费": f"¥{user['total_spent']:.2f}",
        "订单数": user["total_orders"],
        "注册时间": user["registered_at"],
        "最近活跃": user["last_active"],
        "账户状态": user["status"],
    }

    if next_level and gap > 0:
        result["升级提示"] = f"再消费 ¥{gap:.0f} 即可升级为{next_level}会员"
    elif current_level == "钻石":
        result["会员特权"] = "您已是最高级别会员，享受8.5折优惠和专属客服"

    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def recommend_for_user(user_id: str) -> str:
    """根据用户的偏好和消费历史，推荐适合的商品。

    Args:
        user_id: 用户ID
    """
    user = USERS_DB.get(user_id.upper())
    if not user:
        return json.dumps({"error": f"未找到用户 {user_id}"}, ensure_ascii=False)

    prefs = user.get("preferences", {})
    fav_colors = prefs.get("favorite_colors", [])
    fav_styles = prefs.get("favorite_styles", [])

    # 基于偏好推荐
    recommendations = []

    if "休闲" in fav_styles or "运动" in fav_styles:
        recommendations.append({
            "商品": "经典纯棉T恤",
            "价格": "¥89",
            "推荐理由": "休闲百搭，适合日常穿着",
            "推荐颜色": [c for c in fav_colors if c in ["白色", "黑色", "灰色"]] or ["白色", "黑色"],
        })
        recommendations.append({
            "商品": "运动卫衣",
            "价格": "¥199",
            "推荐理由": "运动休闲风格，秋冬必备",
            "推荐颜色": [c for c in fav_colors if c in ["黑色", "灰色", "粉色"]] or ["黑色"],
        })

    if "淑女" in fav_styles or "法式" in fav_styles or "优雅" in fav_styles:
        recommendations.append({
            "商品": "碎花连衣裙",
            "价格": "¥329",
            "推荐理由": "法式浪漫设计，优雅气质",
            "推荐颜色": ["花色A", "花色B"],
        })

    if "通勤" in fav_styles or "户外" in fav_styles:
        recommendations.append({
            "商品": "轻薄羽绒服",
            "价格": "¥599",
            "推荐理由": "轻薄保暖，通勤户外两相宜",
            "推荐颜色": [c for c in fav_colors if c in ["黑色", "藏青色", "军绿色"]] or ["黑色"],
        })

    if not recommendations:
        recommendations.append({
            "商品": "经典纯棉T恤",
            "价格": "¥89",
            "推荐理由": "百搭基础款，适合所有人",
        })
        recommendations.append({
            "商品": "修身牛仔裤",
            "价格": "¥259",
            "推荐理由": "经典版型，四季皆宜",
        })

    # 添加会员专属优惠
    member_discount = {"普通": None, "银卡": "9.5折", "金卡": "9折", "钻石": "8.5折"}
    discount = member_discount.get(user["member_level"])

    result = {
        "用户": user["nickname"],
        "会员等级": user["member_level"],
        "推荐商品": recommendations,
    }
    if discount:
        result["会员优惠"] = f"您是{user['member_level']}会员，可享{discount}优惠"
    if user.get("points", 0) > 0:
        result["积分提示"] = f"您有{user['points']}积分，可抵扣¥{user['points'] // 100}"

    return json.dumps(result, ensure_ascii=False, indent=2)
