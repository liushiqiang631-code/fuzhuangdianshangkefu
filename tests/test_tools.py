"""
工具层测试
覆盖购物车、用户画像、优惠券促销、转人工、订单查询、存储辅助等
所有文件操作均隔离到 pytest 临时目录，不触碰 data/ 下的真实数据
"""
import json
import time
from pathlib import Path

import pytest

from tools.cart import add_to_cart, view_cart, create_order, remove_from_cart
from tools import cart as cart_module
from tools.user_profile import extract_preferences_from_message
from tools import promotions as promotions_module
from tools.promotions import query_active_promotions, validate_coupon, apply_coupon
from tools import escalation as escalation_module
from tools.escalation import create_support_ticket, get_queue_status
from tools import analytics as analytics_module
from tools.analytics import query_order, query_user_orders
from tools.product_detail import check_stock
from tools.storage import is_safe_id, sanitize_id


# ========== 通用夹具：把各工具的数据文件重定向到临时目录 ==========

@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    """将 cart/promotions/escalation/analytics 的数据文件指向临时目录"""
    carts_dir = tmp_path / "carts"
    orders_file = tmp_path / "docs" / "orders.json"
    promos_file = tmp_path / "docs" / "promotions.json"
    coupons_file = tmp_path / "docs" / "coupons.json"
    reviews_file = tmp_path / "docs" / "reviews.json"
    tickets_file = tmp_path / "tickets.json"
    queue_file = tmp_path / "queue.json"

    orders_file.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cart_module, "CARTS_DIR", carts_dir)
    monkeypatch.setattr(cart_module, "ORDERS_FILE", orders_file)
    monkeypatch.setattr(promotions_module, "PROMOTIONS_FILE", promos_file)
    monkeypatch.setattr(promotions_module, "COUPONS_FILE", coupons_file)
    monkeypatch.setattr(escalation_module, "TICKETS_FILE", tickets_file)
    monkeypatch.setattr(escalation_module, "QUEUE_FILE", queue_file)
    monkeypatch.setattr(analytics_module, "ORDERS_FILE", orders_file)

    return {
        "carts_dir": carts_dir,
        "orders_file": orders_file,
        "promos_file": promos_file,
        "coupons_file": coupons_file,
        "reviews_file": reviews_file,
        "tickets_file": tickets_file,
        "queue_file": queue_file,
    }


def _add_sample_item(user="test_user_001"):
    add_to_cart.invoke({
        "user_id": user,
        "product_name": "经典纯棉T恤",
        "color": "黑色",
        "size": "M",
    })


# ========== 存储辅助 ==========

class TestStorage:
    def test_safe_id(self):
        assert is_safe_id("U10001")
        assert is_safe_id("user_1-a")
        assert not is_safe_id("../evil")
        assert not is_safe_id("..\\evil")
        assert not is_safe_id("")
        assert not is_safe_id("a" * 65)

    def test_sanitize_id(self):
        assert sanitize_id("../evil:id") == "evilid"
        assert sanitize_id("正常-123") == "正常-123".replace("/", "").replace("\\", "")


# ========== 购物车工具 ==========

class TestCartTools:
    def test_add_to_cart_success(self, isolated_data):
        result = add_to_cart.invoke({
            "user_id": "test_user_001",
            "product_name": "经典纯棉T恤",
            "color": "黑色",
            "size": "M",
            "quantity": 1,
        })
        assert "已加入购物车" in result

    def test_add_to_cart_product_not_found(self, isolated_data):
        result = add_to_cart.invoke({
            "user_id": "test_user_001",
            "product_name": "不存在的商品",
        })
        assert "未找到商品" in result

    def test_add_to_cart_invalid_quantity(self, isolated_data):
        result = add_to_cart.invoke({
            "user_id": "test_user_001",
            "product_name": "经典纯棉T恤",
            "quantity": 0,
        })
        assert "1-99" in result

    def test_add_to_cart_invalid_user(self, isolated_data):
        result = add_to_cart.invoke({
            "user_id": "../evil",
            "product_name": "经典纯棉T恤",
        })
        assert "格式不正确" in result

    def test_view_cart_empty(self, isolated_data):
        result = view_cart.invoke({"user_id": "test_user_001"})
        assert "购物车是空的" in result

    def test_create_order_success(self, isolated_data):
        _add_sample_item()
        result = create_order.invoke({
            "user_id": "test_user_001",
            "address": "测试地址",
            "phone": "13800138000",
        })
        assert "订单创建成功" in result
        assert "ORD-" in result
        # 订单落盘且购物车已清空
        orders = json.loads(isolated_data["orders_file"].read_text(encoding="utf-8"))
        assert len(orders) == 1
        assert orders[0]["status"] == "待支付"

    def test_create_order_empty_cart(self, isolated_data):
        result = create_order.invoke({
            "user_id": "test_user_001",
            "address": "测试地址",
            "phone": "13800138000",
        })
        assert "购物车是空的" in result

    def test_remove_from_cart_exact_match(self, isolated_data):
        add_to_cart.invoke({
            "user_id": "test_user_001",
            "product_name": "经典纯棉T恤",
            "color": "黑色", "size": "M",
        })
        add_to_cart.invoke({
            "user_id": "test_user_001",
            "product_name": "修身牛仔裤",
            "color": "深蓝色", "size": "30",
        })
        result = remove_from_cart.invoke({
            "user_id": "test_user_001",
            "product_name": "修身牛仔裤",
        })
        assert "已从购物车移除" in result
        assert "T恤" in view_cart.invoke({"user_id": "test_user_001"})
        assert "牛仔裤" not in view_cart.invoke({"user_id": "test_user_001"})


# ========== 用户画像 ==========

class TestUserProfile:
    def test_extract_sizes(self):
        result = extract_preferences_from_message("user1", "我穿M码")
        assert "sizes" in result
        assert "M" in result["sizes"]

    def test_extract_colors(self):
        result = extract_preferences_from_message("user1", "我喜欢黑色和白色")
        assert "黑色" in result["colors"]
        assert "白色" in result["colors"]

    def test_extract_budget_range(self):
        result = extract_preferences_from_message("user1", "预算200-500元")
        assert result["budget_min"] == 200
        assert result["budget_max"] == 500

    def test_extract_budget_not_exceed(self):
        """修复回归：'不超过X元' 应能提取到上限"""
        result = extract_preferences_from_message("user1", "预算不超过500元")
        assert result["budget_max"] == 500

    def test_extract_budget_below(self):
        """修复回归：'低于X元' 应能提取到上限"""
        result = extract_preferences_from_message("user1", "低于300元的裙子")
        assert result["budget_max"] == 300

    def test_extract_styles(self):
        result = extract_preferences_from_message("user1", "我喜欢休闲和商务风格")
        assert "休闲" in result["styles"]
        assert "商务" in result["styles"]

    def test_extract_nothing(self):
        result = extract_preferences_from_message("user1", "今天天气不错")
        assert len(result) == 0


# ========== 优惠券/促销 ==========

class TestPromotions:
    def test_query_promotions_with_data(self, isolated_data):
        """有活动数据时应能列出（种子数据）"""
        now = time.time()
        isolated_data["promos_file"].write_text(json.dumps([
            {"name": "测试活动", "type": "满减", "description": "满100减10",
             "start_time": now - 3600, "end_time": now + 3600},
        ], ensure_ascii=False), encoding="utf-8")
        result = query_active_promotions.invoke({})
        assert "测试活动" in result

    def test_query_promotions_expired_only(self, isolated_data):
        now = time.time()
        isolated_data["promos_file"].write_text(json.dumps([
            {"name": "过期活动", "start_time": now - 7200, "end_time": now - 3600},
        ], ensure_ascii=False), encoding="utf-8")
        result = query_active_promotions.invoke({})
        assert "没有进行中的促销活动" in result

    def _seed_coupon(self, isolated_data, **overrides):
        coupon = {
            "code": "TEST20",
            "name": "测试券",
            "type": "满减券",
            "description": "满100减20",
            "discount_amount": 20,
            "min_amount": 100,
            "expire_time": time.time() + 86400,
            "target_users": [],
        }
        coupon.update(overrides)
        isolated_data["coupons_file"].write_text(
            json.dumps([coupon], ensure_ascii=False), encoding="utf-8")

    def test_validate_coupon_ok(self, isolated_data):
        self._seed_coupon(isolated_data)
        result = validate_coupon.invoke({
            "coupon_code": "TEST20", "user_id": "user1", "order_amount": 200,
        })
        assert "验证成功" in result

    def test_validate_coupon_not_found(self, isolated_data):
        result = validate_coupon.invoke({"coupon_code": "NOTEXIST", "user_id": "user1"})
        assert "不存在" in result

    def test_validate_coupon_below_threshold(self, isolated_data):
        self._seed_coupon(isolated_data)
        result = validate_coupon.invoke({
            "coupon_code": "TEST20", "user_id": "user1", "order_amount": 50,
        })
        assert "满 100" in result

    def test_validate_coupon_expired(self, isolated_data):
        self._seed_coupon(isolated_data, expire_time=time.time() - 3600)
        result = validate_coupon.invoke({
            "coupon_code": "TEST20", "user_id": "user1", "order_amount": 200,
        })
        assert "已过期" in result

    def test_validate_coupon_targeted(self, isolated_data):
        self._seed_coupon(isolated_data, target_users=["someone_else"])
        result = validate_coupon.invoke({
            "coupon_code": "TEST20", "user_id": "user1", "order_amount": 200,
        })
        assert "定向" in result

    def test_apply_coupon_rejects_invalid(self, isolated_data):
        """修复回归：apply_coupon 必须先校验再核销"""
        self._seed_coupon(isolated_data, expire_time=time.time() - 3600)
        result = apply_coupon.invoke({
            "coupon_code": "TEST20", "user_id": "user1", "order_amount": 200,
        })
        assert "已过期" in result
        # 未被核销
        coupons = json.loads(isolated_data["coupons_file"].read_text(encoding="utf-8"))
        assert coupons[0].get("used_by") is None

    def test_apply_coupon_success(self, isolated_data):
        self._seed_coupon(isolated_data)
        result = apply_coupon.invoke({
            "coupon_code": "TEST20", "user_id": "user1", "order_amount": 200,
        })
        assert "使用成功" in result
        coupons = json.loads(isolated_data["coupons_file"].read_text(encoding="utf-8"))
        assert "user1" in coupons[0]["used_by"]

    def test_apply_coupon_twice_rejected(self, isolated_data):
        self._seed_coupon(isolated_data)
        apply_coupon.invoke({"coupon_code": "TEST20", "user_id": "user1", "order_amount": 200})
        result = apply_coupon.invoke({"coupon_code": "TEST20", "user_id": "user1", "order_amount": 200})
        assert "已被使用" in result


# ========== 转人工 ==========

class TestEscalation:
    def test_create_ticket(self, isolated_data):
        result = create_support_ticket.invoke({
            "session_id": "sess_001",
            "user_id": "user_001",
            "reason": "商品质量问题",
            "priority": "high",
            "category": "complaint",
        })
        assert "已为您创建人工客服工单" in result
        assert "TK-" in result

    def test_create_ticket_invalid_priority_fallback(self, isolated_data):
        """非法优先级回退为 normal 而非静默产生脏数据"""
        result = create_support_ticket.invoke({
            "session_id": "sess_001",
            "user_id": "user_001",
            "reason": "测试",
            "priority": "P0",
        })
        assert "已为您创建人工客服工单" in result
        tickets = json.loads(isolated_data["tickets_file"].read_text(encoding="utf-8"))
        assert tickets[0]["priority"] == "normal"

    def test_queue_status_empty(self, isolated_data):
        result = get_queue_status.invoke({"user_id": "user_001"})
        assert "没有在排队" in result

    def test_queue_status_in_queue(self, isolated_data):
        create_support_ticket.invoke({
            "session_id": "sess_001", "user_id": "user_001", "reason": "测试",
        })
        result = get_queue_status.invoke({"user_id": "user_001"})
        assert "排队位置" in result


# ========== 订单查询（双源统一修复回归） ==========

class TestOrders:
    def test_query_order_from_orders_json(self, isolated_data):
        """修复回归：create_order 写入的订单必须能被 query_order 查到"""
        _add_sample_item()
        create_order.invoke({"user_id": "test_user_001", "address": "测试地址"})
        orders = json.loads(isolated_data["orders_file"].read_text(encoding="utf-8"))
        oid = orders[0]["order_id"]

        result = query_order.invoke({"order_id": oid})
        data = json.loads(result)
        assert data["order_id"] == oid
        assert data["status"] == "待支付"

    def test_query_order_sample_still_works(self, isolated_data):
        result = query_order.invoke({"order_id": "ORD20260430001"})
        data = json.loads(result)
        assert data["tracking"] == "SF1234567890"

    def test_query_order_fuzzy_multiple_candidates(self, isolated_data):
        result = query_order.invoke({"order_id": "ORD2026"})
        data = json.loads(result)
        assert "candidates" in data

    def test_query_user_orders_includes_created(self, isolated_data):
        add_to_cart.invoke({
            "user_id": "U10001",
            "product_name": "经典纯棉T恤",
            "color": "黑色", "size": "M",
        })
        create_order.invoke({"user_id": "U10001", "address": "测试地址"})
        result = query_user_orders.invoke({"user_id": "U10001"})
        data = json.loads(result)
        # 既有种子订单也有新下单订单
        assert len(data) >= 2


# ========== 库存查询（修复回归） ==========

class TestStock:
    def test_check_stock_valid_color(self, isolated_data, monkeypatch):
        """修复回归：合法颜色不能再报'无此颜色'"""
        products_file = isolated_data["reviews_file"].parent / "products.json"
        monkeypatch.setattr("tools.product_detail.PRODUCTS_FILE", products_file)
        products_file.write_text(json.dumps([
            {"id": "P001", "name": "测试T恤", "colors": ["黑色", "白色"],
             "sizes": ["M", "L"], "stock_status": "充足"},
        ], ensure_ascii=False), encoding="utf-8")

        result = check_stock.invoke({"product_name": "测试T恤", "color": "黑色"})
        assert "在售" in result
        assert "无此颜色" not in result

        result_bad = check_stock.invoke({"product_name": "测试T恤", "color": "绿色"})
        assert "无此颜色" in result_bad or "没有此颜色" in result_bad


# ========== 运行测试 ==========

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
