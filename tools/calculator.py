"""
安全计算工具
用于价格、折扣、满减等计算
"""
from langchain_core.tools import tool


@tool
def calculate_price(original_price: float, discount: float = 1.0, coupon: float = 0, quantity: int = 1) -> str:
    """计算商品折后价格。
    用于计算折扣价、优惠券抵扣后的最终价格。

    Args:
        original_price: 商品原价（元）
        discount: 折扣系数，如0.9表示9折，默认1.0（无折扣）
        coupon: 优惠券抵扣金额（元），默认0
        quantity: 购买数量，默认1
    """
    if original_price <= 0:
        return "错误：原价必须大于0"
    if not (0 < discount <= 1):
        return "错误：折扣系数必须在0到1之间"
    if coupon < 0:
        return "错误：优惠券金额不能为负数"
    if quantity < 1:
        return "错误：数量必须至少为1"

    subtotal = original_price * quantity
    discount_amount = subtotal * (1 - discount)
    after_discount = subtotal * discount
    final_price = max(after_discount - coupon, 0)  # 最低0元

    result = {
        "原价": f"¥{original_price:.2f}",
        "数量": quantity,
        "小计": f"¥{subtotal:.2f}",
        "折扣": f"{discount * 10:.1f}折",
        "折扣节省": f"¥{discount_amount:.2f}",
        "折后价": f"¥{after_discount:.2f}",
        "优惠券抵扣": f"¥{coupon:.2f}",
        "最终价格": f"¥{final_price:.2f}",
        "总共节省": f"¥{subtotal - final_price:.2f}",
    }

    import json
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def calculate_full_reduction(total: float, threshold: float = 200, reduction: float = 30) -> str:
    """计算满减优惠。
    计算订单是否满足满减条件以及优惠后的价格。

    Args:
        total: 订单总金额（元）
        threshold: 满减门槛金额（元），默认200
        reduction: 满减优惠金额（元），默认30
    """
    if total <= 0:
        return "错误：订单金额必须大于0"

    eligible = total >= threshold
    discount = reduction if eligible else 0
    final = total - discount

    # 计算再买多少可以享受满减
    gap = threshold - total if not eligible else 0

    result = {
        "订单金额": f"¥{total:.2f}",
        "满减规则": f"满{threshold}减{reduction}",
        "是否满足": "是" if eligible else "否",
        "优惠金额": f"¥{discount:.2f}",
        "实付金额": f"¥{final:.2f}",
    }

    if not eligible and gap > 0:
        result["建议"] = f"再买¥{gap:.2f}即可享受满减优惠，推荐查看凑单商品"

    import json
    return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def calculate_member_discount(total: float, member_level: str = "普通") -> str:
    """计算会员折扣价格。

    Args:
        total: 订单总金额（元）
        member_level: 会员等级，可选值：普通、银卡、金卡、钻石
    """
    discount_map = {
        "普通": 1.0,
        "银卡": 0.95,
        "金卡": 0.90,
        "钻石": 0.85,
    }

    discount = discount_map.get(member_level, 1.0)
    saved = total * (1 - discount)
    final = total * discount

    result = {
        "订单金额": f"¥{total:.2f}",
        "会员等级": member_level,
        "会员折扣": f"{discount * 100:.0f}%",
        "节省金额": f"¥{saved:.2f}",
        "实付金额": f"¥{final:.2f}",
    }

    if member_level == "普通":
        result["升级建议"] = "消费满500元可升级银卡会员，享受9.5折优惠"

    import json
    return json.dumps(result, ensure_ascii=False, indent=2)
