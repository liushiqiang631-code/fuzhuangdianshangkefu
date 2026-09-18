"""
AI 客服工作台只读 API
为工作台前端提供客户上下文、订单、商品、推荐、统计数据
全部复用 tools 层的现有数据源，不引入新的存储
"""
import json
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from agent import is_valid_session_id
from tools.user_activation import USERS_DB
from tools.analytics import _all_orders
from tools.product_detail import _load_products, _load_reviews
from tools.logistics import _load_logistics
from config import settings

logger = logging.getLogger("zhice-platform.workbench")

router = APIRouter(prefix="/api/workbench", tags=["客服工作台"])

DEMO_CUSTOMER_ID = "U10001"  # 工作台演示绑定的客户


def _mask_phone(phone: str) -> str:
    """手机号脱敏（保留前3后4）"""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) >= 7:
        return f"{digits[:3]}****{digits[-4:]}"
    return phone


def _customer_view(user_id: str) -> Optional[dict]:
    """客户信息视图（脱敏）"""
    user = USERS_DB.get(user_id.upper())
    if not user:
        return None
    prefs = user.get("preferences", {})
    return {
        "user_id": user["user_id"],
        "nickname": user.get("nickname", ""),
        "gender": user.get("gender", ""),
        "phone": _mask_phone(user.get("phone", "")),
        "member_level": user.get("member_level", "普通"),
        "points": user.get("points", 0),
        "location": user.get("location", ""),
        "total_orders": user.get("total_orders", 0),
        "total_spent": user.get("total_spent", 0),
        "status": user.get("status", ""),
        "registered_at": user.get("registered_at", ""),
        "favorite_styles": prefs.get("favorite_styles", []),
        "favorite_colors": prefs.get("favorite_colors", []),
        "preference_tags": user.get("preference_tags", []),
    }


def _product_view(p: dict) -> dict:
    """商品信息视图"""
    return {
        "id": p.get("id", ""),
        "name": p.get("name", ""),
        "category": p.get("category", ""),
        "price": p.get("price", 0),
        "original_price": p.get("original_price", 0),
        "material": p.get("material", ""),
        "colors": p.get("colors", []),
        "sizes": p.get("sizes", []),
        "description": p.get("description", ""),
        "image_url": p.get("image_url", ""),
        "tags": p.get("tags", []),
        "stock_status": p.get("stock_status", ""),
        "rating": p.get("rating"),
        "rating_count": p.get("rating_count", 0),
    }


def _order_views(user_id: str) -> List[dict]:
    """某客户的订单视图（附带物流摘要与商品图片）"""
    logistics = {l.get("order_id"): l for l in _load_logistics() if l.get("order_id")}
    products = sorted(_load_products(), key=lambda p: len(p.get("name", "")), reverse=True)
    result = []
    for oid, o in _all_orders().items():
        if str(o.get("user_id", "")).upper() != user_id.upper():
            continue
        tracking = logistics.get(oid, {})
        items = []
        for it in o.get("items", []):
            name = it.get("name", "")
            image = ""
            # 订单项名称形如「商品名 颜色 尺码」，按最长商品名回配图片（防子串误配）
            for p in products:
                if p.get("name") and p["name"] in name:
                    image = p.get("image_url", "")
                    break
            items.append({
                "name": name,
                "qty": it.get("qty", 1),
                "price": it.get("price", 0),
                "image_url": image,
            })
        result.append({
            "order_id": oid,
            "status": o.get("status", ""),
            "total": o.get("total", 0),
            "created_at": str(o.get("created_at", "")),
            "items": items,
            "tracking": {
                "number": tracking.get("tracking_number"),
                "carrier": tracking.get("carrier"),
                "status": tracking.get("status"),
                "estimated_delivery": tracking.get("estimated_delivery"),
            } if tracking else None,
        })
    # 按下单时间倒序
    result.sort(key=lambda o: o["created_at"], reverse=True)
    return result


def _match_product_from_messages(messages: List[dict]) -> Optional[dict]:
    """从会话消息中猜测当前咨询的商品（最近提到的优先，最长商品名优先防止子串误配）"""
    products = sorted(_load_products(), key=lambda p: len(p.get("name", "")), reverse=True)
    if not messages:
        return None
    # 从最近的消息往前找商品名命中
    for msg in reversed(messages):
        content = msg.get("content", "")
        if not content:
            continue
        for p in products:
            name = p.get("name", "")
            if len(name) >= 3 and name in content:
                return p
    return None


def _recommendations(exclude_id: str, customer: Optional[dict], limit: int = 4) -> List[dict]:
    """基于客户偏好的简单推荐（偏好标签命中加分，兜底按销量）"""
    products = [p for p in _load_products() if p.get("id") != exclude_id]
    fav_styles = set((customer or {}).get("favorite_styles", []))
    fav_colors = set((customer or {}).get("favorite_colors", []))

    def score(p):
        s = p.get("sales_count", 0) / 10000.0
        tags = set(p.get("tags", [])) | set(p.get("category", "").split("/"))
        s += 2.0 * len(tags & fav_styles)
        s += 1.0 * len(set(p.get("colors", [])) & fav_colors)
        return s

    products.sort(key=score, reverse=True)
    return [_product_view(p) for p in products[:limit]]


@router.get("/context/{session_id}")
def get_session_context(session_id: str, user_id: str = DEMO_CUSTOMER_ID):
    """
    会话上下文（右侧面板一次取全）：
    客户信息 + 最近订单 + 当前咨询商品 + AI 推荐
    """
    if not is_valid_session_id(session_id):
        raise HTTPException(status_code=400, detail="会话ID格式不正确")

    customer = _customer_view(user_id)
    if not customer:
        raise HTTPException(status_code=404, detail=f"未找到客户 {user_id}")

    # 当前咨询商品：优先从会话消息识别，其次最近订单商品，兜底第一个商品
    products = _load_products()
    current = None
    session_file = Path(settings.DATA_SESSIONS_DIR) / f"{session_id}.json"
    if session_file.exists():
        try:
            data = json.loads(session_file.read_text(encoding="utf-8"))
            matched = _match_product_from_messages(data.get("chat_history", []))
            if matched:
                current = _product_view(matched)
        except Exception as e:
            logger.warning(f"[Workbench] 读取会话失败: {e}")

    orders = _order_views(user_id)
    if not current and orders:
        first_item = orders[0]["items"][0]["name"] if orders[0]["items"] else ""
        # 最长商品名优先，避免「碎花连衣裙」抢先匹配「法式收腰碎花连衣裙」
        for p in sorted(products, key=lambda x: len(x.get("name", "")), reverse=True):
            if p.get("name") and p["name"] in first_item:
                current = _product_view(p)
                break
    if not current and products:
        current = _product_view(products[0])

    exclude = current["id"] if current else ""
    return {
        "customer": customer,
        "orders": orders,
        "current_product": current,
        "recommendations": _recommendations(exclude, customer),
    }


@router.get("/products")
def list_products(query: str = "", limit: int = 30):
    """商品列表/搜索"""
    products = _load_products()
    query = (query or "").strip()
    if query:
        products = [p for p in products if query in p.get("name", "") or query in p.get("category", "")]
    return {"products": [_product_view(p) for p in products[:limit]], "total": len(products)}


@router.get("/customers")
def list_customers():
    """客户列表（脱敏）"""
    customers = [_customer_view(uid) for uid in USERS_DB]
    return {"customers": [c for c in customers if c], "total": len(customers)}


@router.get("/orders")
def list_orders(user_id: str = ""):
    """订单列表（可按客户过滤）"""
    if user_id:
        orders = _order_views(user_id)
    else:
        orders = []
        for uid in USERS_DB:
            orders.extend(_order_views(uid))
        orders.sort(key=lambda o: o["created_at"], reverse=True)
    return {"orders": orders, "total": len(orders)}


@router.get("/reviews")
def list_reviews(product_name: str = Query(..., description="商品名称")):
    """某商品的用户评价"""
    reviews = [r for r in _load_reviews() if r.get("product_name") == product_name]
    return {"reviews": reviews[:10], "total": len(reviews)}


@router.get("/stats")
def workbench_stats():
    """工作台概览统计"""
    from feedback import load_feedback_stats
    sessions_dir = Path(settings.DATA_SESSIONS_DIR)
    total_sessions = len(list(sessions_dir.glob("*.json"))) if sessions_dir.exists() else 0

    active_threshold = 0
    try:
        import time as _time
        active_threshold = _time.time() - 86400
    except Exception:
        pass
    active_sessions = 0
    if sessions_dir.exists():
        for f in sessions_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("last_active", 0) > active_threshold:
                    active_sessions += 1
            except Exception:
                continue

    feedback = load_feedback_stats()
    return {
        "total_sessions": total_sessions,
        "active_sessions": active_sessions,
        "total_products": len(_load_products()),
        "total_customers": len(USERS_DB),
        "feedback": feedback,
    }
