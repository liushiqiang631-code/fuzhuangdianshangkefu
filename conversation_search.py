"""
对话搜索模块
搜索历史对话内容（实时扫描会话文件，新会话即时可搜）
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from config import settings

logger = logging.getLogger("zhice-platform.search")

SESSIONS_DIR = Path(settings.DATA_SESSIONS_DIR)


class ConversationSearcher:
    """对话搜索器（实时扫描，无持久化索引）"""

    def _iter_sessions(self):
        """遍历所有会话文件"""
        if not SESSIONS_DIR.exists():
            return
        for session_file in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                yield data.get("session_id", session_file.stem), data
            except Exception as e:
                logger.warning(f"[Search] 读取会话失败 {session_file}: {e}")

    def search(
        self,
        query: str,
        limit: int = 20,
        session_id: str = None,
    ) -> List[Dict]:
        """
        搜索对话内容（子串匹配，中文无需分词）

        Args:
            query: 搜索查询
            limit: 返回结果数量限制
            session_id: 限定会话ID（可选）

        Returns:
            搜索结果列表
        """
        query = (query or "").strip()
        if not query:
            return []

        results: List[Dict] = []

        for sid, data in self._iter_sessions():
            if session_id and sid != session_id:
                continue

            history = data.get("chat_history", [])
            for i, msg in enumerate(history):
                content = msg.get("content", "")
                if not content:
                    continue

                count = content.count(query)
                if count == 0:
                    continue

                # 高亮命中位置
                pos = content.find(query)
                snippet = content[max(0, pos - 20):pos + len(query) + 40]

                results.append({
                    "session_id": sid,
                    "message_index": i,
                    "role": msg.get("role", ""),
                    "content": content[:200],
                    "snippet": f"...{snippet}...",
                    "match_count": count,
                    "timestamp": data.get("last_active", 0),
                })

        # 命中次数多的优先，其次按时间倒序
        results.sort(key=lambda r: (r["match_count"], r["timestamp"]), reverse=True)
        return results[:limit]

    def search_in_session(
        self,
        session_id: str,
        query: str,
        limit: int = 50,
    ) -> List[Dict]:
        """在指定会话中搜索"""
        return self.search(query, limit, session_id)

    def get_recent_conversations(
        self,
        limit: int = 10,
    ) -> List[Dict]:
        """获取最近的对话"""
        sessions = []
        for sid, data in self._iter_sessions():
            history = data.get("chat_history", [])

            # 获取最后一条消息
            last_message = ""
            for msg in reversed(history):
                if msg.get("content"):
                    last_message = msg["content"][:100]
                    break

            sessions.append({
                "session_id": sid,
                "message_count": len(history),
                "last_message": last_message,
                "last_active": data.get("last_active", 0),
            })

        # 按最后活跃时间排序
        sessions.sort(key=lambda x: x["last_active"], reverse=True)

        return sessions[:limit]

    def rebuild_index(self):
        """兼容保留：实时搜索无需重建索引"""
        logger.info("[Search] 实时搜索模式，无需重建索引")


# 全局搜索器
conversation_searcher = ConversationSearcher()


def search_conversations(
    query: str,
    limit: int = 20,
) -> List[Dict]:
    """
    搜索对话（便捷函数）

    Args:
        query: 搜索查询
        limit: 返回数量限制

    Returns:
        搜索结果列表
    """
    return conversation_searcher.search(query, limit)
