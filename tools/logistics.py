"""
物流跟踪查询工具
支持查询物流状态、快递信息
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.tools import tool

LOGISTICS_FILE = Path("./data/docs/logistics.json")


def _load_logistics() -> list:
    """加载物流数据"""
    if not LOGISTICS_FILE.exists():
        return []
    try:
        return json.loads(LOGISTICS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


@tool
def track_logistics(tracking_number: str) -> str:
    """查询物流状态。当用户问"快递到哪了"、"物流信息"时使用。

    Args:
        tracking_number: 快递单号
    """
    logistics = _load_logistics()

    # 查找物流信息
    tracking = None
    for l in logistics:
        if l.get("tracking_number") == tracking_number:
            tracking = l
            break

    if not tracking:
        return f"未找到单号 {tracking_number} 的物流信息，请检查单号是否正确。"

    result = f"物流查询：{tracking_number}\n"
    result += "=" * 40 + "\n\n"
    result += f"快递公司: {tracking.get('carrier', '-')}\n"
    result += f"发货时间: {tracking.get('shipped_at', '-')}\n"
    result += f"预计送达: {tracking.get('estimated_delivery', '-')}\n"
    result += f"当前状态: {tracking.get('status', '-')}\n\n"

    # 物流轨迹
    events = tracking.get("events", [])
    if events:
        result += "物流轨迹：\n"
        for event in events:
            result += f"  [{event.get('time', '-')}] {event.get('location', '-')} - {event.get('description', '-')}\n"
    else:
        result += "暂无物流轨迹信息。"

    return result


@tool
def query_order_logistics(order_id: str) -> str:
    """根据订单号查询物流。当用户说"查一下我的订单物流"时使用。

    Args:
        order_id: 订单号
    """
    logistics = _load_logistics()

    # 查找订单对应的物流
    tracking = None
    for l in logistics:
        if l.get("order_id") == order_id:
            tracking = l
            break

    if not tracking:
        return f"订单 {order_id} 暂无物流信息，可能尚未发货。"

    # StructuredTool 需通过 invoke 调用，不能直接当函数调用
    return track_logistics.invoke({"tracking_number": tracking["tracking_number"]})


@tool
def get_delivery_estimate(
    destination: str = "",
) -> str:
    """查询预计送达时间。当用户问"什么时候能到"、"发货时效"时使用。

    Args:
        destination: 目的地（如"北京"、"上海"）
    """
    # 默认时效规则
    result = "发货时效说明：\n\n"

    result += "1. 下单时间:\n"
    result += "   - 当天 16:00 前下单，当天发货\n"
    result += "   - 16:00 后下单，次日发货\n\n"

    result += "2. 配送时效:\n"
    result += "   - 同城: 1-2 天\n"
    result += "   - 省内: 2-3 天\n"
    result += "   - 跨省: 3-5 天\n"
    result += "   - 偏远地区: 5-7 天\n\n"

    if destination:
        result += f"目的地 {destination} 预计送达时间:\n"
        if any(city in destination for city in ["北京", "上海", "广州", "深圳"]):
            result += "   预计 1-2 天送达\n"
        elif any(province in destination for province in ["浙江", "江苏", "广东"]):
            result += "   预计 2-3 天送达\n"
        else:
            result += "   预计 3-5 天送达\n"

    return result
