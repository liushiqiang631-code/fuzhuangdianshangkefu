"""
管理后台增强路由
热门问题排行、工具统计、错误率监控、用户满意度趋势
"""
import json
import re
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
from config import settings

logger = logging.getLogger("zhice-platform.admin")

router = APIRouter(prefix="/admin/analytics", tags=["管理分析"])

SESSIONS_DIR = Path(settings.DATA_SESSIONS_DIR)
FEEDBACK_FILE = Path("./data/feedback.jsonl")
LOGS_DIR = Path("./logs")

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@router.get("/hot-questions")
def get_hot_questions(limit: int = 20):
    """获取热门问题排行"""
    try:
        if not SESSIONS_DIR.exists():
            return {"questions": []}

        # 统计问题频率
        question_counts: Dict[str, int] = {}

        for session_file in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                history = data.get("chat_history", [])

                for msg in history:
                    if msg.get("role") == "human":
                        content = msg.get("content", "")
                        # 简单去重和归一化
                        normalized = content.strip()[:50]
                        if normalized:
                            question_counts[normalized] = question_counts.get(normalized, 0) + 1

            except Exception:
                continue

        # 排序
        sorted_questions = sorted(
            question_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:limit]

        return {
            "questions": [
                {"question": q, "count": c}
                for q, c in sorted_questions
            ],
            "total_unique": len(question_counts),
        }

    except Exception as e:
        logger.error(f"[Admin] 获取热门问题失败: {e}")
        raise HTTPException(status_code=500, detail="获取失败")


@router.get("/tool-stats")
def get_tool_stats():
    """获取工具调用统计"""
    try:
        if not SESSIONS_DIR.exists():
            return {"tools": []}

        # 统计工具使用
        tool_counts: Dict[str, int] = {}
        total_calls = 0

        for session_file in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                history = data.get("chat_history", [])

                for msg in history:
                    if msg.get("role") == "ai":
                        # 从消息中提取工具使用信息
                        tools = msg.get("tools_used", [])
                        for tool in tools:
                            tool_counts[tool] = tool_counts.get(tool, 0) + 1
                            total_calls += 1

            except Exception:
                continue

        # 排序
        sorted_tools = sorted(
            tool_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        return {
            "tools": [
                {
                    "name": name,
                    "count": count,
                    "percentage": round(count / total_calls * 100, 1) if total_calls > 0 else 0,
                }
                for name, count in sorted_tools
            ],
            "total_calls": total_calls,
        }

    except Exception as e:
        logger.error(f"[Admin] 获取工具统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取失败")


@router.get("/error-stats")
def get_error_stats():
    """获取错误率统计"""
    try:
        log_path = Path(settings.LOG_FILE)
        if not log_path.exists():
            return {"errors": [], "error_rate": 0}

        # 统计错误
        error_counts: Dict[str, int] = {}
        total_lines = 0
        error_lines = 0

        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                total_lines += 1
                if "ERROR" in line:
                    error_lines += 1
                    # 提取错误类型
                    if "[" in line and "]" in line:
                        error_type = line.split("]")[1].split(":")[0].strip()
                        error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # 排序
        sorted_errors = sorted(
            error_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        error_rate = round(error_lines / total_lines * 100, 2) if total_lines > 0 else 0

        return {
            "errors": [
                {"type": t, "count": c}
                for t, c in sorted_errors
            ],
            "total_errors": error_lines,
            "total_lines": total_lines,
            "error_rate": error_rate,
        }

    except Exception as e:
        logger.error(f"[Admin] 获取错误统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取失败")


@router.get("/satisfaction-trend")
def get_satisfaction_trend(days: int = 7):
    """获取用户满意度趋势"""
    try:
        if not FEEDBACK_FILE.exists():
            return {"trend": []}

        # feedback.jsonl 是 JSONL 格式，逐行读取
        feedback_data = []
        for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    feedback_data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # 按日期统计
        daily_stats: Dict[str, Dict] = {}

        for item in feedback_data:
            timestamp = item.get("timestamp", 0)
            date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            rating = item.get("rating", "")

            if date not in daily_stats:
                daily_stats[date] = {"positive": 0, "negative": 0, "total": 0}

            daily_stats[date]["total"] += 1
            if rating == "positive":
                daily_stats[date]["positive"] += 1
            elif rating == "negative":
                daily_stats[date]["negative"] += 1

        # 生成趋势数据
        trend = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            stats = daily_stats.get(date, {"positive": 0, "negative": 0, "total": 0})

            total = stats["total"]
            satisfaction = round(stats["positive"] / total * 100, 1) if total > 0 else 0

            trend.append({
                "date": date,
                "total": total,
                "positive": stats["positive"],
                "negative": stats["negative"],
                "satisfaction": satisfaction,
            })

        trend.reverse()

        return {"trend": trend}

    except Exception as e:
        logger.error(f"[Admin] 获取满意度趋势失败: {e}")
        raise HTTPException(status_code=500, detail="获取失败")


@router.get("/session-stats")
def get_session_stats():
    """获取会话统计"""
    try:
        if not SESSIONS_DIR.exists():
            return {"total_sessions": 0, "active_sessions": 0}

        sessions = list(SESSIONS_DIR.glob("*.json"))
        total_sessions = len(sessions)

        # 统计活跃会话（最近24小时有活动）
        active_threshold = time.time() - 86400
        active_sessions = 0

        for session_file in sessions:
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                last_active = data.get("last_active", 0)
                if last_active > active_threshold:
                    active_sessions += 1
            except Exception:
                continue

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "inactive_sessions": total_sessions - active_sessions,
        }

    except Exception as e:
        logger.error(f"[Admin] 获取会话统计失败: {e}")
        raise HTTPException(status_code=500, detail="获取失败")


@router.get("/audit-log")
def get_audit_log(date: str = None, limit: int = 100):
    """获取审计日志（仅磁盘记录，date 需为 YYYY-MM-DD 格式）"""
    try:
        if date is not None and not DATE_RE.fullmatch(date):
            raise HTTPException(status_code=400, detail="date 参数格式需为 YYYY-MM-DD")

        disk_log = []
        audit_dir = Path("./data/audit")
        if audit_dir.exists():
            date_str = date or time.strftime("%Y-%m-%d")
            log_file = audit_dir / f"audit-{date_str}.jsonl"
            if log_file.exists():
                for line in log_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line:
                        try:
                            disk_log.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

        return {
            "memory_log": [],
            "disk_log": disk_log[-limit:],
            "disk_count": len(disk_log),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Admin] 获取审计日志失败: {e}")
        raise HTTPException(status_code=500, detail="获取失败")


@router.get("/tools")
async def get_registered_tools():
    """获取所有已注册的工具列表"""
    try:
        from agent import list_tools
        tools = list_tools()
        return {
            "tools": tools,
            "count": len(tools),
        }
    except Exception as e:
        logger.error(f"[Admin] 获取工具列表失败: {e}")
        raise HTTPException(status_code=500, detail="获取失败")
