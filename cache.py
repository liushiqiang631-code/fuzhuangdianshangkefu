"""
工具结果缓存模块
基于 TTL 的 LRU 缓存，减少重复的 ChromaDB / LLM 调用
"""
import time
import hashlib
import logging
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger("zhice-platform.cache")


class ToolResultCache:
    """带 TTL 的 LRU 缓存"""

    def __init__(self, max_size: int = 128, ttl: int = 300):
        self._cache: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl  # 秒
        self._hits = 0
        self._misses = 0

    def _make_key(self, tool_name: str, *args, **kwargs) -> str:
        """生成缓存 key"""
        raw = f"{tool_name}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, tool_name: str, *args, **kwargs) -> Optional[str]:
        """查询缓存，命中返回结果，未命中返回 None"""
        key = self._make_key(tool_name, *args, **kwargs)

        if key in self._cache:
            value, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                # 命中，移到末尾（LRU）
                self._cache.move_to_end(key)
                self._hits += 1
                logger.debug(f"[Cache] 命中: {tool_name}")
                return value
            else:
                # 过期，删除
                del self._cache[key]

        self._misses += 1
        return None

    def set(self, tool_name: str, result: str, *args, **kwargs):
        """写入缓存"""
        key = self._make_key(tool_name, *args, **kwargs)

        # 超过容量时淘汰最旧的
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

        self._cache[key] = (result, time.time())
        logger.debug(f"[Cache] 写入: {tool_name}")

    def clear(self):
        """清空缓存"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info("[Cache] 缓存已清空")

    def stats(self) -> dict:
        """返回缓存统计"""
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / total * 100:.1f}%" if total > 0 else "N/A",
        }


# 全局单例
tool_cache = ToolResultCache(max_size=128, ttl=300)
