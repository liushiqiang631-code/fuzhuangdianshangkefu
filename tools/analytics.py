"""
业务数据查询工具
查询订单、用户订单列表与业务指标
订单数据统一来自 data/docs/orders.json（cart.create_order 写入），
并内置少量种子订单（SAMPLE_ORDERS）作为演示数据。
"""
import json
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from langchain_core.tools import tool

from tools.storage import load_json

ORDERS_FILE = Path("./data/docs/orders.json")


# ========== 种子订单（演示数据，与 data/docs/logistics.json 对应） ==========
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


def _load_file_orders() -> Dict[str, dict]:
    """加载 orders.json 中的真实订单（cart.create_order 写入），归一化字段"""
    data = load_json(ORDERS_FILE, [])
    orders: Dict[str, dict] = {}
    if not isinstance(data, list):
        return orders
    for o in data:
        if not isinstance(o, dict):
            continue
        oid = o.get("order_id", "")
        if not oid:
            continue
        items = []
        for it in o.get("items", []):
            items.append({
                "name": f"{it.get('product_name', '?')} {it.get('color', '')} {it.get('size', '')}".strip(),
                "qty": it.get("quantity", 1),
                "price": it.get("price", 0),
            })
        orders[oid] = {
            "order_id": oid,
            "user_id": o.get("user_id", ""),
            "status": o.get("status", "未知"),
            "items": items,
            "total": o.get("total_amount", 0),
            "address": o.get("address", ""),
            "phone": o.get("phone", ""),
            "created_at": o.get("time_str") or datetime.fromtimestamp(
                o.get("created_at", 0)).strftime("%Y-%m-%d %H:%M:%S"),
        }
    return orders


def _all_orders() -> Dict[str, dict]:
    """合并种子订单与真实订单（真实订单优先）"""
    orders = dict(SAMPLE_ORDERS)
    orders.update(_load_file_orders())
    return orders


@tool
def query_order(order_id: str) -> str:
    """查询订单状态和物流信息。
    当用户询问订单状态、物流进度、发货时间等问题时使用此工具。

    Args:
        order_id: 订单号（如 ORD20260430001）
    """
    orders = _all_orders()
    key = order_id.strip().upper()
    order = orders.get(key)
    if not order:
        # 模糊匹配：订单号需足够长（>=6位）才启用，多命中时返回候选列表
        if len(key) >= 6:
            matches = [oid for oid in orders if key in oid]
            if len(matches) == 1:
                order = orders[matches[0]]
            elif len(matches) > 1:
                return json.dumps({
                    "error": f"找到 {len(matches)} 个可能的订单，请确认完整订单号",
                    "candidates": matches[:10],
                }, ensure_ascii=False)
        if not order:
            return json.dumps({"error": f"未找到订单 {order_id}，请确认订单号是否正确。"}, ensure_ascii=False)

    return json.dumps(order, ensure_ascii=False, indent=2)


@tool
def query_user_orders(user_id: str) -> str:
    """根据用户ID查询该用户的所有订单列表。

    Args:
        user_id: 用户ID（如 U10001）
    """
    orders = _all_orders()
    uid = user_id.strip().upper()
    user_orders = [o for o in orders.values() if str(o.get("user_id", "")).upper() == uid]

    if not user_orders:
        return json.dumps({"error": f"未找到用户 {user_id} 的订单记录。"}, ensure_ascii=False)

    user_orders.sort(key=lambda o: str(o.get("created_at", "")), reverse=True)

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
        days: 查询最近N天的数据，默认7天（最小为1）
    """
    if not isinstance(days, int) or days < 1:
        days = 7
    days = min(days, 365)

    # 以日期为种子，保证同一天内多次查询结果一致
    seed = f"{datetime.now().strftime('%Y-%m-%d')}-{days}"
    rng = random.Random(seed)

    data = {
        "查询周期": f"最近{days}天",
        "活跃用户数": rng.randint(800, 1500),
        "新注册用户": rng.randint(100, 300),
        "下单用户数": rng.randint(400, 800),
        "复购率": f"{rng.uniform(25, 45):.1f}%",
        "客单价": f"¥{rng.uniform(150, 350):.0f}",
        "热销商品TOP5": [
            {"商品": "经典纯棉T恤", "销量": rng.randint(200, 500)},
            {"商品": "修身牛仔裤", "销量": rng.randint(150, 350)},
            {"商品": "运动卫衣", "销量": rng.randint(100, 300)},
            {"商品": "碎花连衣裙", "销量": rng.randint(80, 250)},
            {"商品": "轻薄羽绒服", "销量": rng.randint(50, 150)},
        ],
    }

    return json.dumps(data, ensure_ascii=False, indent=2)
