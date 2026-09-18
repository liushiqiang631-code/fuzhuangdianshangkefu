"""
用户画像自动提取工具
从对话中自动提取用户偏好（尺码、风格、预算）并持久化
"""
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from langchain_core.tools import tool
from memory import save_memory
from tools.storage import is_safe_id

PROFILES_DIR = Path("./data/profiles")

_DEFAULT_PROFILE = {
    "preferences": {
        "sizes": [],
        "colors": [],
        "styles": [],
        "budget_min": 0,
        "budget_max": 0,
        "categories": [],
    },
    "history": {
        "total_orders": 0,
        "total_spent": 0,
        "last_order_date": None,
    },
}


def _ensure_dir():
    """确保目录存在"""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


def _default_profile(user_id: str) -> Dict:
    profile = json.loads(json.dumps(_DEFAULT_PROFILE))  # 深拷贝默认结构
    profile["user_id"] = user_id
    profile["extracted_at"] = time.time()
    profile["updated_at"] = time.time()
    return profile


def _load_profile(user_id: str) -> Dict:
    """加载用户画像，缺键时用默认结构补齐（兼容旧版画像文件）"""
    _ensure_dir()
    profile_file = PROFILES_DIR / f"{user_id}.json"
    stored = None
    if profile_file.exists():
        try:
            stored = json.loads(profile_file.read_text(encoding="utf-8"))
        except Exception:
            stored = None
    if not isinstance(stored, dict):
        return _default_profile(user_id)

    profile = _default_profile(user_id)
    # 深合并：磁盘数据优先，缺失键用默认值补齐
    for section, defaults in _DEFAULT_PROFILE.items():
        section_data = stored.pop(section, {})
        if isinstance(section_data, dict):
            defaults.update(section_data)
        profile[section] = defaults
    profile.update(stored)
    return profile


def _save_profile(user_id: str, profile: Dict):
    """保存用户画像"""
    _ensure_dir()
    profile["updated_at"] = time.time()
    profile_file = PROFILES_DIR / f"{user_id}.json"
    profile_file.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同步到记忆系统
    memory_content = f"""用户画像（自动提取）：
- 偏好尺码: {', '.join(profile['preferences']['sizes']) or '未记录'}
- 偏好颜色: {', '.join(profile['preferences']['colors']) or '未记录'}
- 偏好风格: {', '.join(profile['preferences']['styles']) or '未记录'}
- 预算范围: ¥{profile['preferences']['budget_min']}-{profile['preferences']['budget_max']}
- 偏好品类: {', '.join(profile['preferences']['categories']) or '未记录'}
- 历史订单: {profile['history']['total_orders']}笔
- 累计消费: ¥{profile['history']['total_spent']:.0f}
"""
    save_memory(f"user-profile-{user_id}", memory_content, "user")


def extract_preferences_from_message(user_id: str, message: str) -> Dict:
    """
    从用户消息中提取偏好信息（规则引擎）

    Returns:
        提取到的偏好信息字典
    """
    extracted = {}

    # 提取尺码
    size_patterns = [
        r'[尺码码号][\s:：]*([SsMmLlXx]+)',
        r'([SsMmLlXx]+)[\s]*码',
        r'我(?:穿|要|想)[\s]*([SsMmLlXx]+)',
    ]
    for pattern in size_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            size = match.group(1).upper()
            if size in ['S', 'M', 'L', 'XL', 'XXL', 'XXXL']:
                extracted.setdefault('sizes', []).append(size)
                break

    # 提取颜色偏好
    color_keywords = ['黑色', '白色', '红色', '蓝色', '绿色', '黄色', '紫色', '粉色',
                      '灰色', '棕色', '米色', '卡其', '深蓝', '浅蓝', '酒红', '墨绿']
    for color in color_keywords:
        if color in message:
            extracted.setdefault('colors', []).append(color)

    # 提取风格偏好
    style_keywords = ['休闲', '商务', '运动', '时尚', '简约', '复古', '可爱',
                      '通勤', '街头', '学院', '田园', '韩版', '日系', '欧美']
    for style in style_keywords:
        if style in message:
            extracted.setdefault('styles', []).append(style)

    # 提取预算（注意分组形式：`(?:不超过|低于...)` 是非捕获组）
    budget_patterns = [
        r'预算[\s:：]*(\d+)[\s]*[-到至~][\s]*(\d+)',          # 预算100到200
        r'(\d+)[\s]*[-到至~][\s]*(\d+)[\s]*元',               # 100-200元
        r'(?:预算)?(?:不超过|不超过了|低于|最多|最高|最多不超过)[\s:：]*(\d+)[\s]*元?',  # 不超过500元
        r'(\d+)[\s]*元[\s]*(?:以内|以下)',                     # 500元以内
    ]
    for pattern in budget_patterns:
        match = re.search(pattern, message)
        if match:
            groups = match.groups()
            if len(groups) == 2:
                extracted['budget_min'] = int(groups[0])
                extracted['budget_max'] = int(groups[1])
            elif len(groups) == 1:
                extracted['budget_max'] = int(groups[0])
            break

    # 提取品类偏好
    category_keywords = ['上装', '裤装', '外套', '连衣裙', 'T恤', '衬衫', '牛仔裤',
                         '休闲裤', '西装', '风衣', '羽绒服', '毛衣', '卫衣']
    for cat in category_keywords:
        if cat in message:
            extracted.setdefault('categories', []).append(cat)

    return extracted


@tool
def update_user_profile(
    user_id: str,
    message: str,
) -> str:
    """从对话中自动提取用户偏好并更新画像。当用户提到尺码、风格、预算等偏好信息时自动调用。

    Args:
        user_id: 用户ID
        message: 用户的原始消息内容
    """
    if not is_safe_id(user_id):
        return "用户ID格式不正确，只能包含字母、数字、下划线和短横线。"

    profile = _load_profile(user_id)
    extracted = extract_preferences_from_message(user_id, message)

    if not extracted:
        return "未从消息中提取到偏好信息。"

    # 合并偏好（去重）
    prefs = profile["preferences"]

    if "sizes" in extracted:
        for size in extracted["sizes"]:
            if size not in prefs["sizes"]:
                prefs["sizes"].append(size)

    if "colors" in extracted:
        for color in extracted["colors"]:
            if color not in prefs["colors"]:
                prefs["colors"].append(color)

    if "styles" in extracted:
        for style in extracted["styles"]:
            if style not in prefs["styles"]:
                prefs["styles"].append(style)

    if "budget_max" in extracted:
        if extracted["budget_max"] > 0:
            prefs["budget_max"] = max(prefs["budget_max"], extracted["budget_max"])
        if "budget_min" in extracted:
            # 下限以最新表述为准（用户改口"预算50到200"时应能下调）
            prefs["budget_min"] = extracted["budget_min"]
        elif prefs["budget_min"] > prefs["budget_max"]:
            prefs["budget_min"] = 0

    if "categories" in extracted:
        for cat in extracted["categories"]:
            if cat not in prefs["categories"]:
                prefs["categories"].append(cat)

    _save_profile(user_id, profile)

    # 构建更新摘要
    updates = []
    if "sizes" in extracted:
        updates.append(f"尺码: {', '.join(extracted['sizes'])}")
    if "colors" in extracted:
        updates.append(f"颜色: {', '.join(extracted['colors'])}")
    if "styles" in extracted:
        updates.append(f"风格: {', '.join(extracted['styles'])}")
    if "budget_max" in extracted:
        updates.append(f"预算: ¥{extracted.get('budget_min', 0)}-{extracted['budget_max']}")
    if "categories" in extracted:
        updates.append(f"品类: {', '.join(extracted['categories'])}")

    return f"已更新用户画像：{'; '.join(updates)}"


@tool
def get_user_profile(user_id: str) -> str:
    """获取用户画像信息。当需要了解用户偏好、历史消费时使用。

    Args:
        user_id: 用户ID
    """
    if not is_safe_id(user_id):
        return "用户ID格式不正确。"

    profile = _load_profile(user_id)
    prefs = profile["preferences"]
    history = profile["history"]

    result = f"用户 {user_id} 的画像：\n\n"

    # 偏好信息
    result += "【偏好信息】\n"
    result += f"  偏好尺码: {', '.join(prefs['sizes']) or '未记录'}\n"
    result += f"  偏好颜色: {', '.join(prefs['colors']) or '未记录'}\n"
    result += f"  偏好风格: {', '.join(prefs['styles']) or '未记录'}\n"
    result += f"  预算范围: ¥{prefs['budget_min']}-{prefs['budget_max']}\n"
    result += f"  偏好品类: {', '.join(prefs['categories']) or '未记录'}\n\n"

    # 消费历史
    result += "【消费历史】\n"
    result += f"  历史订单: {history['total_orders']}笔\n"
    result += f"  累计消费: ¥{history['total_spent']:.0f}\n"
    if history['last_order_date']:
        result += f"  最近下单: {history['last_order_date']}\n"

    return result


@tool
def update_order_history(
    user_id: str,
    order_amount: float,
) -> str:
    """更新用户订单历史。当用户下单成功后调用。

    Args:
        user_id: 用户ID
        order_amount: 订单金额
    """
    if not is_safe_id(user_id):
        return "用户ID格式不正确。"
    if order_amount < 0:
        return "订单金额不能为负数。"

    profile = _load_profile(user_id)
    profile["history"]["total_orders"] += 1
    profile["history"]["total_spent"] += order_amount
    profile["history"]["last_order_date"] = time.strftime("%Y-%m-%d %H:%M:%S")

    _save_profile(user_id, profile)

    return f"已更新用户 {user_id} 的订单历史：累计{profile['history']['total_orders']}笔，消费¥{profile['history']['total_spent']:.0f}"
