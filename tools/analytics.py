"""
业务数据查询工具
模拟查询订单、用户、销售等业务数据
"""
import json
import random
from datetime import datetime, timedelta
from langchain_core.tools import tool


# ========== 模拟订单数据 ==========
SAMPLE_ORDERS = {
    "ORD20260430001": {
        "order_id": "ORD20260430001",
        "user_id": "U10001",
        "status": "已发货",
        "items": [{"name": "经典纯棉T恤 白色 L", "qty": 1, "price": 89.00}],
        "total": 89.00,
        "payment": "微信支付",
        "tracking": "SF1234567890",
        "carrier": "顺丰速运",
        "created_at": "2026-04-30 14:22:00",
        "shipped_at": "2026-05-01 09:15:00",
        "address": "上海市浦东新区张江高科技园区",
    },
    "ORD20260501002": {
        "order_id": "ORD20260501002",
        "user_id": "U10002",
        "status": "待发货",
        "items": [
            {"name": "修身牛仔裤 深蓝色 32", "qty": 1, "price": 259.00},
            {"name": "经典纯棉T恤 黑色 M", "qty": 2, "price": 89.00},
        ],
        "total": 437.00,
        "payment": "支付宝",
        "tracking": None,
        "carrier": None,
        "created_at": "2026-05-01 10:30:00",
        "shipped_at": None,
        "address": "北京市海淀区中关村大街",
    },
    "ORD20260502003": {
        "order_id": "ORD20260502003",
        "user_id": "U10003",
        "status": "已完成",
        "items": [{"name": "轻薄羽绒服 黑色 L", "qty": 1, "price": 599.00}],
        "total": 599.00,
        "payment": "信用卡",
        "tracking": "YT9876543210",
        "carrier": "圆通速递",
        "created_at": "2026-05-02 16:45:00",
        "shipped_at": "2026-05-03 08:30:00",
        "address": "广州市天河区珠江新城",
    },
    "ORD20260503004": {
        "order_id": "ORD20260503004",
        "user_id": "U10004",
        "status": "退款中",
        "items": [{"name": "碎花连衣裙 花色A S", "qty": 1, "price": 329.00}],
        "total": 329.00,
        "payment": "微信支付",
        "tracking": None,
        "carrier": None,
        "created_at": "2026-05-03 09:10:00",
        "shipped_at": None,
        "address": "深圳市南山区科技园",
    },
}


@tool
def query_order(order_id: str) -> str:
    """查询订单状态和物流信息。
    当用户询问订单状态、物流进度、发货时间等问题时使用此工具。

    Args:
        order_id: 订单号（如 ORD20260430001）
    """
    order = SAMPLE_ORDERS.get(order_id.upper())
    if not order:
        # 尝试模糊匹配
        matches = [oid for oid in SAMPLE_ORDERS if order_id.upper() in oid]
        if matches:
            order = SAMPLE_ORDERS[matches[0]]
        else:
            return json.dumps({"error": f"未找到订单 {order_id}，请确认订单号是否正确。"}, ensure_ascii=False)

    return json.dumps(order, ensure_ascii=False, indent=2)


@tool
def query_user_orders(user_id: str) -> str:
    """根据用户ID查询该用户的所有订单列表。

    Args:
        user_id: 用户ID（如 U10001）
    """
    user_orders = [
        o for o in SAMPLE_ORDERS.values()
        if o["user_id"] == user_id.upper()
    ]

    if not user_orders:
        return json.dumps({"error": f"未找到用户 {user_id} 的订单记录。"}, ensure_ascii=False)

    # 简化返回
    result = []
    for o in user_orders:
        result.append({
            "订单号": o["order_id"],
            "状态": o["status"],
            "商品": [i["name"] for i in o["items"]],
            "总价": o["total"],
            "下单时间": o["created_at"],
        })

    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def query_active_users(days: int = 7) -> str:
    """查询最近N天的活跃用户数据和业务指标。

    Args:
        days: 查询最近N天的数据，默认7天
    """
    # 模拟业务数据
    data = {
        "查询周期": f"最近{days}天",
        "活跃用户数": random.randint(800, 1500),
        "新注册用户": random.randint(100, 300),
        "下单用户数": random.randint(400, 800),
        "复购率": f"{random.uniform(25, 45):.1f}%",
        "客单价": f"¥{random.uniform(150, 350):.0f}",
        "热销商品TOP5": [
            {"商品": "经典纯棉T恤", "销量": random.randint(200, 500)},
            {"商品": "修身牛仔裤", "销量": random.randint(150, 350)},
            {"商品": "运动卫衣", "销量": random.randint(100, 300)},
            {"商品": "碎花连衣裙", "销量": random.randint(80, 250)},
            {"商品": "轻薄羽绒服", "销量": random.randint(50, 150)},
        ],
    }

    return json.dumps(data, ensure_ascii=False, indent=2)
