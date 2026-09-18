"""
转人工完整流程工具
支持工单创建、人工排队、会话交接
"""
import json
import uuid
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.tools import tool

from tools.storage import update_json_file, atomic_write_json

logger = logging.getLogger("zhice-platform.escalation")

TICKETS_FILE = Path("./data/tickets.json")
QUEUE_FILE = Path("./data/queue.json")

VALID_PRIORITIES = ("urgent", "high", "normal", "low")
VALID_CATEGORIES = ("general", "complaint", "return", "exchange", "technical")


def _load_tickets() -> list:
    """加载工单列表"""
    if not TICKETS_FILE.exists():
        return []
    try:
        data = json.loads(TICKETS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_tickets(tickets: list):
    """保存工单列表（原子写）"""
    atomic_write_json(TICKETS_FILE, tickets)


def _load_queue() -> Dict:
    """加载排队队列"""
    if not QUEUE_FILE.exists():
        return {"queue": []}
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"queue": []}
        data.setdefault("queue", [])
        return data
    except Exception:
        return {"queue": []}


def _save_queue(queue: Dict):
    """保存排队队列（原子写）"""
    atomic_write_json(QUEUE_FILE, queue)


@tool
def create_support_ticket(
    session_id: str,
    user_id: str,
    reason: str,
    priority: str = "normal",
    category: str = "general",
) -> str:
    """创建人工客服工单。当用户要求转人工、投诉、情绪激动时使用。

    Args:
        session_id: 当前会话ID
        user_id: 用户ID
        reason: 转人工原因
        priority: 优先级（low/normal/high/urgent）
        category: 工单分类（general/complaint/return/exchange/technical）
    """
    if priority not in VALID_PRIORITIES:
        logger.warning(f"[Escalation] 非法优先级 {priority!r}，回退为 normal")
        priority = "normal"
    if category not in VALID_CATEGORIES:
        logger.warning(f"[Escalation] 非法分类 {category!r}，回退为 general")
        category = "general"

    ticket_id = f"TK-{uuid.uuid4().hex[:8].upper()}"

    ticket = {
        "ticket_id": ticket_id,
        "session_id": session_id,
        "user_id": user_id,
        "reason": reason,
        "priority": priority,
        "category": category,
        "status": "pending",
        "created_at": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "assigned_to": None,
        "resolved_at": None,
        "notes": [],
    }

    tickets = _load_tickets()
    tickets.append(ticket)
    _save_tickets(tickets)

    # 添加到排队队列（加锁读改写）
    def _mutate(queue):
        queue.setdefault("queue", [])
        queue["queue"].append({
            "ticket_id": ticket_id,
            "user_id": user_id,
            "priority": priority,
            "created_at": time.time(),
        })
        # 按优先级排序（urgent > high > normal > low）
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        queue["queue"].sort(key=lambda x: priority_order.get(x.get("priority", "normal"), 2))

    update_json_file(QUEUE_FILE, {"queue": []}, _mutate)

    queue = _load_queue()

    logger.info(f"[Escalation] 创建工单 {ticket_id}: {reason}")

    return f"""已为您创建人工客服工单：

工单号: {ticket_id}
优先级: {priority}
分类: {category}
原因: {reason}

当前排队位置: {len(queue['queue'])} 位
预计等待时间: {len(queue['queue']) * 3}-{len(queue['queue']) * 5} 分钟

人工客服会尽快接入，请稍候。在此期间，我仍可以继续为您解答问题。"""


@tool
def get_queue_status(user_id: str) -> str:
    """查询排队状态。当用户问"还要等多久"、"到我了吗"时使用。

    Args:
        user_id: 用户ID
    """
    queue = _load_queue()

    # 查找用户的排队位置
    position = None
    for i, item in enumerate(queue["queue"]):
        if item["user_id"] == user_id:
            position = i + 1
            break

    if position is None:
        return "您当前没有在排队中。如需人工服务，请告诉我您的问题。"

    return f"""当前排队状态：
- 排队位置: 第 {position} 位
- 前方等待: {position - 1} 人
- 预计等待: {(position - 1) * 3}-{(position - 1) * 5} 分钟

人工客服会按顺序接入，请耐心等待。"""


@tool
def get_ticket_status(ticket_id: str) -> str:
    """查询工单状态。当用户问"我的工单处理得怎么样了"时使用。

    Args:
        ticket_id: 工单号
    """
    tickets = _load_tickets()

    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:
            result = f"工单 {ticket_id} 状态：\n\n"
            result += f"状态: {ticket['status']}\n"
            result += f"优先级: {ticket['priority']}\n"
            result += f"分类: {ticket['category']}\n"
            result += f"创建时间: {ticket['time_str']}\n"

            if ticket["assigned_to"]:
                result += f"处理人: {ticket['assigned_to']}\n"
            if ticket["resolved_at"]:
                from datetime import datetime
                resolved_str = datetime.fromtimestamp(ticket['resolved_at']).strftime("%Y-%m-%d %H:%M:%S")
                result += f"解决时间: {resolved_str}\n"
            if ticket["notes"]:
                result += f"\n处理记录：\n"
                for note in ticket["notes"]:
                    result += f"  - [{note['time']}] {note['content']}\n"

            return result

    return f"未找到工单 {ticket_id}，请检查工单号。"


@tool
def add_ticket_note(
    ticket_id: str,
    note: str,
    operator: str = "system",
) -> str:
    """为工单添加备注。当人工客服记录处理过程时使用。

    Args:
        ticket_id: 工单号
        note: 备注内容
        operator: 操作人
    """
    tickets = _load_tickets()

    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:
            ticket["notes"].append({
                "content": note,
                "operator": operator,
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            _save_tickets(tickets)
            return f"已为工单 {ticket_id} 添加备注。"

    return f"未找到工单 {ticket_id}。"


@tool
def resolve_ticket(
    ticket_id: str,
    resolution: str,
    operator: str = "system",
) -> str:
    """解决工单。当问题处理完毕时使用。

    Args:
        ticket_id: 工单号
        resolution: 解决方案说明
        operator: 操作人
    """
    tickets = _load_tickets()

    for ticket in tickets:
        if ticket["ticket_id"] == ticket_id:
            ticket["status"] = "resolved"
            ticket["resolved_at"] = time.time()
            ticket["notes"].append({
                "content": f"工单已解决: {resolution}",
                "operator": operator,
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            _save_tickets(tickets)

            # 从队列中移除（加锁读改写）
            def _mutate(queue):
                queue["queue"] = [q for q in queue.get("queue", []) if q.get("ticket_id") != ticket_id]

            update_json_file(QUEUE_FILE, {"queue": []}, _mutate)

            return f"工单 {ticket_id} 已标记为已解决。"

    return f"未找到工单 {ticket_id}。"


@tool
def get_escalation_stats() -> str:
    """获取转人工统计信息。管理员查看整体情况时使用。"""
    tickets = _load_tickets()
    queue = _load_queue()

    if not tickets:
        return "暂无工单记录。"

    # 统计各状态数量
    status_counts = {}
    priority_counts = {}
    category_counts = {}

    for ticket in tickets:
        status_counts[ticket["status"]] = status_counts.get(ticket["status"], 0) + 1
        priority_counts[ticket["priority"]] = priority_counts.get(ticket["priority"], 0) + 1
        category_counts[ticket["category"]] = category_counts.get(ticket["category"], 0) + 1

    result = f"工单统计：\n\n"
    result += f"总工单数: {len(tickets)}\n"
    result += f"当前排队: {len(queue['queue'])} 人\n\n"

    result += "按状态：\n"
    for status, count in status_counts.items():
        result += f"  - {status}: {count}\n"

    result += "\n按优先级：\n"
    for priority, count in priority_counts.items():
        result += f"  - {priority}: {count}\n"

    result += "\n按分类：\n"
    for category, count in category_counts.items():
        result += f"  - {category}: {count}\n"

    return result
