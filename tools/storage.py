"""
工具层数据存储辅助
提供 ID 消毒、原子 JSON 写入、按文件加锁，供各工具模块共用
"""
import json
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict

# 合法 ID：字母/数字/下划线/短横线，1-64 位（防止路径穿越）
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

_locks_registry: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def is_safe_id(value: str) -> bool:
    """检查 ID 是否安全（可安全用作文件名）"""
    return bool(value) and bool(ID_PATTERN.fullmatch(str(value)))


def sanitize_id(value: str) -> str:
    """将任意输入消毒为安全的 ID；不合法字符直接剔除，剔除后为空则返回空串"""
    cleaned = "".join(c for c in str(value) if c.isalnum() or c in "-_")
    return cleaned[:64]


def _lock_for(path: Path) -> threading.Lock:
    """获取某个路径对应的进程内锁（单进程内防并发读改写）"""
    key = str(path.resolve())
    with _locks_guard:
        if key not in _locks_registry:
            _locks_registry[key] = threading.Lock()
        return _locks_registry[key]


def load_json(path: Path, default: Any) -> Any:
    """读取 JSON 文件，失败时返回默认值"""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_write_json(path: Path, data: Any):
    """原子写入 JSON（先写临时文件再替换，避免中途崩溃截断文件）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def update_json_file(path: Path, default: Any, mutate):
    """
    对 JSON 文件做加锁的读-改-写

    Args:
        path: 目标文件
        default: 文件不存在/损坏时的初始值
        mutate: 接收当前数据、原地修改的回调（返回值忽略）
    """
    lock = _lock_for(path)
    with lock:
        data = load_json(path, default)
        result = mutate(data)
        atomic_write_json(path, data)
        return result
