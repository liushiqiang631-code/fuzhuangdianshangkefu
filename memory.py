"""
跨会话记忆管理系统
基于文件的持久化记忆，注入到 Agent 系统提示词中

结构：
  data/memory/
  ├── MEMORY.md           ← 索引文件（每行一条摘要）
  ├── user_preferences.md ← 用户偏好
  └── *.md                ← 其他记忆文件

记忆类型（frontmatter type 字段）：
  - user: 用户画像（角色、偏好、知识水平）
  - feedback: 行为反馈（用户纠正或确认的做法）
  - project: 项目动态（进行中的工作、截止日期）
  - reference: 外部资源指针
"""
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from config import settings

logger = logging.getLogger("zhice-platform.memory")

MEMORY_DIR = Path(settings.DATA_MEMORY_DIR)
INDEX_FILE = MEMORY_DIR / "MEMORY.md"


def _ensure_dir():
    """确保记忆目录存在"""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if not INDEX_FILE.exists():
        INDEX_FILE.write_text("# 记忆索引\n\n", encoding="utf-8")


def load_memories(max_files: int = 10, max_chars_per_file: int = 1000) -> str:
    """
    加载所有记忆文件，返回可注入系统提示词的文本

    Args:
        max_files: 最多加载多少个记忆文件
        max_chars_per_file: 每个文件最多读取多少字符

    Returns:
        拼接好的记忆上下文文本，无记忆时返回空字符串
    """
    _ensure_dir()

    memory_files = sorted(
        [f for f in MEMORY_DIR.glob("*.md") if f.name != "MEMORY.md"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )[:max_files]

    if not memory_files:
        return ""

    sections = []
    for f in memory_files:
        try:
            content = f.read_text(encoding="utf-8")[:max_chars_per_file]
            # 去掉 frontmatter（如果有）
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    content = content[end + 3:].strip()
            sections.append(f"## {f.stem}\n{content}")
        except Exception as e:
            logger.warning(f"[Memory] 读取记忆文件失败 {f}: {e}")

    if not sections:
        return ""

    return "以下是你之前记住的关于用户和项目的信息，在回答时参考：\n\n" + "\n\n".join(sections)


def save_memory(name: str, content: str, memory_type: str = "user") -> bool:
    """
    保存一条记忆

    Args:
        name: 记忆名称（用作文件名，kebab-case）
        content: 记忆内容
        memory_type: 记忆类型（user/feedback/project/reference）

    Returns:
        是否保存成功
    """
    _ensure_dir()

    # 清理文件名
    safe_name = "".join(c for c in name if c.isalnum() or c in "-_").strip()
    if not safe_name:
        safe_name = f"memory-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    filepath = MEMORY_DIR / f"{safe_name}.md"

    # 写入带 frontmatter 的 markdown
    file_content = f"""---
name: {safe_name}
type: {memory_type}
created: {datetime.now().isoformat()}
---

{content}
"""

    try:
        filepath.write_text(file_content, encoding="utf-8")
        _update_index(safe_name, content.split("\n")[0][:80])
        logger.info(f"[Memory] 保存记忆: {safe_name}")
        return True
    except Exception as e:
        logger.error(f"[Memory] 保存记忆失败: {e}")
        return False


def delete_memory(name: str) -> bool:
    """删除一条记忆"""
    filepath = MEMORY_DIR / f"{name}.md"
    if filepath.exists():
        filepath.unlink()
        _remove_from_index(name)
        return True
    return False


def list_memories() -> List[Dict[str, str]]:
    """列出所有记忆"""
    _ensure_dir()

    memories = []
    for f in sorted(MEMORY_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
        if f.name == "MEMORY.md":
            continue
        content = f.read_text(encoding="utf-8")[:200]
        # 提取 type
        mem_type = "unknown"
        if "type:" in content:
            for line in content.split("\n"):
                if line.strip().startswith("type:"):
                    mem_type = line.split(":", 1)[1].strip()
                    break
        memories.append({
            "name": f.stem,
            "type": mem_type,
            "preview": content[:100].replace("\n", " "),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })

    return memories


def _update_index(name: str, summary: str):
    """更新 MEMORY.md 索引"""
    _ensure_dir()
    index_content = INDEX_FILE.read_text(encoding="utf-8")

    # 检查是否已有此条目
    if f"[{name}]({name}.md)" in index_content:
        return

    # 追加新条目
    line = f"- [{name}]({name}.md) — {summary}\n"
    INDEX_FILE.write_text(index_content + line, encoding="utf-8")


def _remove_from_index(name: str):
    """从索引中移除条目"""
    if not INDEX_FILE.exists():
        return
    lines = INDEX_FILE.read_text(encoding="utf-8").split("\n")
    filtered = [l for l in lines if f"[{name}]({name}.md)" not in l]
    INDEX_FILE.write_text("\n".join(filtered), encoding="utf-8")
