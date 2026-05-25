"""
用户反馈模块
记录对话满意度反馈（点赞/点踩）
"""
import json
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("zhice-platform.feedback")

FEEDBACK_DIR = Path("./data")
FEEDBACK_FILE = FEEDBACK_DIR / "feedback.jsonl"


def save_feedback(session_id: str, message_index: int, rating: str, comment: str = "") -> bool:
    """
    保存一条反馈

    Args:
        session_id: 会话ID
        message_index: 消息在对话中的序号
        rating: "positive" 或 "negative"
        comment: 可选的文字评价
    """
    try:
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "session_id": session_id,
            "message_index": message_index,
            "rating": rating,
            "comment": comment,
            "timestamp": time.time(),
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"[Feedback] session={session_id} rating={rating}")
        return True
    except Exception as e:
        logger.error(f"[Feedback] 保存失败: {e}")
        return False


def load_feedback_stats() -> dict:
    """加载反馈统计"""
    if not FEEDBACK_FILE.exists():
        return {"total": 0, "positive": 0, "negative": 0, "rate": "N/A"}

    positive = 0
    negative = 0
    total = 0

    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                total += 1
                if entry.get("rating") == "positive":
                    positive += 1
                elif entry.get("rating") == "negative":
                    negative += 1
    except Exception as e:
        logger.error(f"[Feedback] 读取失败: {e}")

    rate = f"{positive / total * 100:.1f}%" if total > 0 else "N/A"
    return {"total": total, "positive": positive, "negative": negative, "rate": rate}


def load_recent_feedback(limit: int = 50) -> list:
    """加载最近的反馈记录"""
    if not FEEDBACK_FILE.exists():
        return []

    entries = []
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries[-limit:]
    except Exception as e:
        logger.error(f"[Feedback] 读取失败: {e}")
        return []
