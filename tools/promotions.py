"""
优惠券和促销活动查询工具
支持查询当前活动、用户优惠券、可用折扣
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.tools import tool

from tools.storage import is_safe_id, load_json, update_json_file, atomic_write_json

PROMOTIONS_FILE = Path("./data/docs/promotions.json")
COUPONS_FILE = Path("./data/docs/coupons.json")


def _load_promotions() -> list:
    """加载促销活动数据"""
    promos = load_json(PROMOTIONS_FILE, [])
    return promos if isinstance(promos, list) else []


def _load_coupons() -> list:
    """加载优惠券数据"""
    coupons = load_json(COUPONS_FILE, [])
    return coupons if isinstance(coupons, list) else []


def _save_coupons(coupons: list):
    """保存优惠券数据（原子写）"""
    atomic_write_json(COUPONS_FILE, coupons)


def _find_coupon(coupons: list, coupon_code: str) -> Optional[dict]:
    """按券码查找优惠券"""
    for coupon in coupons:
        if coupon.get("code") == coupon_code:
            return coupon
    return None


def _coupon_issue(coupon: dict, user_id: str, order_amount: float) -> Optional[str]:
    """
    校验优惠券是否可被该用户使用。

    Returns:
        返回 None 表示可用，否则返回不可用的原因文案
    """
    current_time = time.time()

    # 检查是否过期（expire_time 为空表示长期有效）
    expire_time = coupon.get("expire_time")
    if expire_time and expire_time < current_time:
        return f"优惠券 {coupon.get('code')} 已过期。"

    # 检查是否已被当前用户使用
    used_by = coupon.get("used_by", [])
    if user_id and user_id in used_by:
        return f"优惠券 {coupon.get('code')} 已被使用。"

    # 检查定向用户
    target_users = coupon.get("target_users", [])
    if user_id and target_users and user_id not in target_users:
        return f"优惠券 {coupon.get('code')} 是定向发放的券，当前用户不可使用。"

    # 检查使用门槛
    min_amount = coupon.get("min_amount", 0)
    if order_amount > 0 and min_amount > 0 and order_amount < min_amount:
        return f"优惠券 {coupon.get('code')} 需要满 {min_amount} 元使用，当前订单 {order_amount} 元不满足条件。"

    return None


@tool
def query_active_promotions() -> str:
    """查询当前进行中的促销活动。当用户问"有什么优惠"、"现在有什么活动"、"打折吗"时使用。"""
    promotions = _load_promotions()
    current_time = time.time()

    if not promotions:
        # 数据缺失与"没有活动"是两回事，如实告知
        return "促销系统数据暂不可用，请稍后再试或联系人工客服确认最新活动。"

    active_promos = []
    for promo in promotions:
        start_time = promo.get("start_time", 0)
        end_time = promo.get("end_time")  # 为空表示长期有效

        if start_time <= current_time and (not end_time or current_time <= end_time):
            active_promos.append(promo)

    if not active_promos:
        return "当前没有进行中的促销活动。"

    result = f"当前有 {len(active_promos)} 个进行中的活动：\n\n"

    for i, promo in enumerate(active_promos, 1):
        result += f"{i}. {promo.get('name', '未命名活动')}\n"
        result += f"   类型: {promo.get('type', '-')}\n"
        result += f"   描述: {promo.get('description', '-')}\n"

        if promo.get("discount"):
            result += f"   优惠: {promo['discount']}\n"
        if promo.get("min_amount"):
            result += f"   门槛: 满 {promo['min_amount']} 元\n"
        if promo.get("end_time"):
            from datetime import datetime
            end_str = datetime.fromtimestamp(promo['end_time']).strftime("%Y-%m-%d %H:%M")
            result += f"   截止: {end_str}\n"

        result += "\n"

    return result


@tool
def query_user_coupons(user_id: str) -> str:
    """查询用户可用的优惠券。当用户问"我有什么券"、"优惠券"时使用。

    Args:
        user_id: 用户ID
    """
    if not is_safe_id(user_id):
        return "用户ID格式不正确。"

    coupons = _load_coupons()
    if not coupons:
        return "暂无可用优惠券。"

    # 筛选用户可用的优惠券
    available_coupons = []
    for coupon in coupons:
        if _coupon_issue(coupon, user_id, 0) is None:
            available_coupons.append(coupon)

    if not available_coupons:
        return "您当前没有可用的优惠券。"

    result = f"您有 {len(available_coupons)} 张可用优惠券：\n\n"

    for i, coupon in enumerate(available_coupons, 1):
        result += f"{i}. {coupon.get('name', '未命名券')}\n"
        result += f"   类型: {coupon.get('type', '-')}\n"
        result += f"   优惠: {coupon.get('description', '-')}\n"

        if coupon.get("min_amount"):
            result += f"   门槛: 满 {coupon['min_amount']} 元\n"
        if coupon.get("discount_amount"):
            result += f"   减免: {coupon['discount_amount']} 元\n"
        if coupon.get("discount_rate"):
            result += f"   折扣: {coupon['discount_rate'] * 10:.1f} 折\n"
        if coupon.get("expire_time"):
            from datetime import datetime
            expire_str = datetime.fromtimestamp(coupon['expire_time']).strftime("%Y-%m-%d %H:%M")
            result += f"   有效期至: {expire_str}\n"

        result += f"   券码: {coupon.get('code', '-')}\n\n"

    return result


@tool
def validate_coupon(
    coupon_code: str,
    user_id: str = "",
    order_amount: float = 0,
) -> str:
    """验证优惠券是否可用。当用户使用优惠券结算时调用。

    Args:
        coupon_code: 优惠券码
        user_id: 用户ID（可选）
        order_amount: 订单金额（可选，用于检查门槛）
    """
    coupons = _load_coupons()

    target_coupon = _find_coupon(coupons, coupon_code)
    if not target_coupon:
        return f"优惠券 {coupon_code} 不存在，请检查券码。"

    issue = _coupon_issue(target_coupon, user_id, order_amount)
    if issue:
        return issue

    # 计算优惠金额
    discount = 0
    if target_coupon.get("discount_amount"):
        discount = target_coupon["discount_amount"]
    elif target_coupon.get("discount_rate") and order_amount > 0:
        discount = order_amount * (1 - target_coupon["discount_rate"])

    result = f"优惠券 {coupon_code} 验证成功！\n"
    result += f"优惠类型: {target_coupon.get('type', '-')}\n"
    result += f"优惠说明: {target_coupon.get('description', '-')}\n"
    if discount > 0:
        result += f"预计减免: {discount:.2f} 元\n"

    return result


@tool
def apply_coupon(
    coupon_code: str,
    user_id: str,
    order_amount: float = 0,
    order_id: str = "",
) -> str:
    """使用优惠券（核销）。当用户确认使用优惠券时调用。核销前会校验有效期、使用门槛和定向用户。

    Args:
        coupon_code: 优惠券码
        user_id: 用户ID
        order_amount: 订单金额（用于校验使用门槛，已知时务必传入）
        order_id: 订单ID（可选）
    """
    if not is_safe_id(user_id):
        return "用户ID格式不正确。"

    def _mutate(coupons):
        target_coupon = _find_coupon(coupons, coupon_code)
        if not target_coupon:
            return f"优惠券 {coupon_code} 不存在。"

        # 核销前执行与 validate_coupon 相同的全套校验
        issue = _coupon_issue(target_coupon, user_id, order_amount)
        if issue:
            return issue

        used_by = target_coupon.get("used_by", [])
        used_by.append(user_id)
        target_coupon["used_by"] = used_by

        if order_id:
            target_coupon.setdefault("used_orders", []).append(order_id)

        discount = 0
        if target_coupon.get("discount_amount"):
            discount = target_coupon["discount_amount"]
        elif target_coupon.get("discount_rate") and order_amount > 0:
            discount = order_amount * (1 - target_coupon["discount_rate"])

        result = f"优惠券 {coupon_code} 使用成功！"
        if discount > 0:
            result += f" 本次减免 {discount:.2f} 元。"
        return result

    return update_json_file(COUPONS_FILE, [], _mutate)
