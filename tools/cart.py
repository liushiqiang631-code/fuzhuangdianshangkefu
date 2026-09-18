"""
购物车和订单创建工具
支持加入购物车、查看购物车、创建订单
"""
import json
import uuid
import time
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.tools import tool

from tools.storage import is_safe_id, load_json, update_json_file, atomic_write_json

CARTS_DIR = Path("./data/carts")
ORDERS_FILE = Path("./data/docs/orders.json")


def _ensure_dirs():
    """确保目录存在"""
    CARTS_DIR.mkdir(parents=True, exist_ok=True)
    ORDERS_FILE.parent.mkdir(parents=True, exist_ok=True)


def _check_user(user_id: str) -> Optional[str]:
    """校验 user_id，不合法时返回错误文案"""
    if not is_safe_id(user_id):
        return "用户ID格式不正确，只能包含字母、数字、下划线和短横线。"
    return None


def _load_cart(user_id: str) -> Dict:
    """加载用户购物车"""
    _ensure_dirs()
    cart_file = CARTS_DIR / f"{user_id}.json"
    cart = load_json(cart_file, None)
    if isinstance(cart, dict) and "items" in cart:
        return cart
    return {"user_id": user_id, "items": [], "updated_at": time.time()}


def _save_cart(user_id: str, cart: Dict):
    """保存用户购物车（原子写）"""
    _ensure_dirs()
    cart["updated_at"] = time.time()
    atomic_write_json(CARTS_DIR / f"{user_id}.json", cart)


def _load_products() -> list:
    """加载商品数据"""
    products_file = Path("./data/docs/products.json")
    products = load_json(products_file, [])
    return products if isinstance(products, list) else []


def _find_product(product_name: str) -> Optional[Dict]:
    """根据名称查找商品（精确优先，其次唯一子串匹配）"""
    products = _load_products()
    for p in products:
        if product_name == p.get("name", ""):
            return p
    matches = [p for p in products if product_name in p.get("name", "")]
    return matches[0] if len(matches) == 1 else None


@tool
def add_to_cart(
    user_id: str,
    product_name: str,
    color: str = "",
    size: str = "",
    quantity: int = 1,
) -> str:
    """将商品加入购物车。当用户说"加入购物车"、"我要这个"、"帮我加购"时使用。

    Args:
        user_id: 用户ID
        product_name: 商品名称（关键词即可）
        color: 颜色（如"黑色"、"白色"），不指定则选第一个可选颜色
        size: 尺码（如"S"、"M"、"L"），不指定则选第一个可选尺码
        quantity: 数量，默认1
    """
    invalid = _check_user(user_id)
    if invalid:
        return invalid

    if not isinstance(quantity, int) or quantity < 1 or quantity > 99:
        return "商品数量必须是 1-99 之间的整数。"

    product = _find_product(product_name)
    if not product:
        return f"未找到商品 {product_name}，请确认商品名称。"

    # 确定颜色
    available_colors = product.get("colors", [])
    if color:
        selected_color = next((c for c in available_colors if color in c), None)
        if not selected_color:
            return f"商品 {product['name']} 没有颜色 {color}，可选颜色：{', '.join(available_colors)}"
    else:
        selected_color = available_colors[0] if available_colors else "默认"

    # 确定尺码
    available_sizes = product.get("sizes", [])
    if size:
        selected_size = next((s for s in available_sizes if size.upper() in s.upper()), None)
        if not selected_size:
            return f"商品 {product['name']} 没有尺码 {size}，可选尺码：{', '.join(available_sizes)}"
    else:
        selected_size = available_sizes[0] if available_sizes else "均码"

    # 加入购物车（加锁读改写，防止并发丢更新）
    def _mutate(cart):
        cart.setdefault("user_id", user_id)
        cart.setdefault("items", [])
        for item in cart["items"]:
            if (item.get("product_name") == product["name"] and
                item.get("color") == selected_color and
                item.get("size") == selected_size):
                item["quantity"] = item.get("quantity", 0) + quantity
                return
        cart["items"].append({
            "product_name": product["name"],
            "color": selected_color,
            "size": selected_size,
            "quantity": quantity,
            "price": product.get("price", 0),
            "image_url": product.get("image_url", ""),
        })

    _ensure_dirs()
    update_json_file(CARTS_DIR / f"{user_id}.json",
                     {"user_id": user_id, "items": [], "updated_at": time.time()}, _mutate)

    return f"已加入购物车：{product['name']}（{selected_color}，{selected_size}）x {quantity}，单价 {product.get('price', 0)} 元"


@tool
def view_cart(user_id: str) -> str:
    """查看购物车内容。当用户说"看看购物车"、"我加购了什么"时使用。

    Args:
        user_id: 用户ID
    """
    invalid = _check_user(user_id)
    if invalid:
        return invalid

    cart = _load_cart(user_id)

    if not cart["items"]:
        return "购物车是空的，去看看有什么好物吧！"

    result = f"购物车（{len(cart['items'])}件商品）：\n\n"
    total = 0

    for i, item in enumerate(cart["items"], 1):
        subtotal = item["price"] * item["quantity"]
        total += subtotal
        result += f"{i}. {item['product_name']}\n"
        result += f"   颜色: {item['color']} | 尺码: {item['size']} | 数量: {item['quantity']}\n"
        result += f"   单价: {item['price']} 元 | 小计: {subtotal:.2f} 元\n\n"

    result += f"合计：{total:.2f} 元"
    return result


@tool
def remove_from_cart(
    user_id: str,
    product_name: str,
    color: str = "",
    size: str = "",
) -> str:
    """从购物车移除商品。当用户说"去掉这个"、"不要了"、"移除购物车"时使用。

    Args:
        user_id: 用户ID
        product_name: 商品名称
        color: 颜色
        size: 尺码
    """
    invalid = _check_user(user_id)
    if invalid:
        return invalid

    cart = _load_cart(user_id)

    if not cart["items"]:
        return "购物车已经是空的了。"

    # 精确匹配商品全名，避免"裤"误删所有裤装
    candidates = [it["product_name"] for it in cart["items"] if product_name in it["product_name"]]
    exact = [n for n in candidates if n == product_name]
    target_names = set(exact) if exact else set(candidates)

    if not target_names:
        return f"购物车中没有找到 {product_name}。"
    if len(target_names) > 1:
        return ("找到多个匹配的商品，请确认要移除哪一个（使用完整商品名称）：\n" +
                "\n".join(f"- {n}" for n in sorted(target_names)))

    target_name = next(iter(target_names))

    # 加锁读改写
    removed_count = {"n": 0}

    def _mutate(cart_data):
        new_items = []
        for item in cart_data.get("items", []):
            if item.get("product_name") == target_name:
                if color and color not in item.get("color", ""):
                    new_items.append(item)
                    continue
                if size and size.upper() not in item.get("size", "").upper():
                    new_items.append(item)
                    continue
                removed_count["n"] += 1
            else:
                new_items.append(item)
        cart_data["items"] = new_items

    _ensure_dirs()
    update_json_file(CARTS_DIR / f"{user_id}.json", cart, _mutate)

    if removed_count["n"] == 0:
        return f"购物车中没有找到 {product_name} 的匹配条目。"

    return f"已从购物车移除 {target_name}（{removed_count['n']} 条）。"


@tool
def create_order(
    user_id: str,
    address: str = "",
    phone: str = "",
    remark: str = "",
) -> str:
    """创建订单（从购物车结算）。当用户说"下单"、"结算"、"付款"时使用。

    Args:
        user_id: 用户ID
        address: 收货地址
        phone: 联系电话
        remark: 订单备注
    """
    invalid = _check_user(user_id)
    if invalid:
        return invalid

    cart = _load_cart(user_id)

    if not cart["items"]:
        return "购物车是空的，无法创建订单。请先添加商品。"

    # 生成订单
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    total_amount = sum(item["price"] * item["quantity"] for item in cart["items"])

    order = {
        "order_id": order_id,
        "user_id": user_id,
        "items": cart["items"],
        "total_amount": total_amount,
        "address": address or "待填写",
        "phone": phone or "待填写",
        "remark": remark,
        "status": "待支付",
        "created_at": time.time(),
        "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 保存订单（加锁读改写 + 原子写，防止并发下单互相覆盖丢订单）
    _ensure_dirs()

    def _append(orders):
        if not isinstance(orders, list):
            orders = []
        orders.append(order)

    update_json_file(ORDERS_FILE, [], _append)

    # 清空购物车
    cart["items"] = []
    _save_cart(user_id, cart)

    # 构建订单摘要
    result = f"订单创建成功！\n\n"
    result += f"订单号: {order_id}\n"
    result += f"商品明细:\n"
    for item in order["items"]:
        result += f"  - {item['product_name']}（{item['color']}，{item['size']}）x {item['quantity']} = {item['price'] * item['quantity']:.2f} 元\n"
    result += f"\n合计: {total_amount:.2f} 元\n"
    result += f"收货地址: {order['address']}\n"
    result += f"联系电话: {order['phone']}\n"
    if remark:
        result += f"备注: {remark}\n"
    result += f"\n请在30分钟内完成支付，超时订单将自动取消。"

    return result
