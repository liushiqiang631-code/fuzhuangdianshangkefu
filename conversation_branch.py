"""
对话分支/回退模块
支持回到某轮对话重新提问
"""
import json
import time
import copy
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from config import settings

logger = logging.getLogger("zhice-platform.branch")

BRANCHES_DIR = Path("./data/branches")


@dataclass
class ConversationBranch:
    """对话分支"""
    branch_id: str
    session_id: str
    parent_branch_id: Optional[str] = None
    fork_point: int = 0  # 分支点（消息索引）
    messages: List[Dict] = field(default_factory=list)
    created_at: float = 0.0
    name: str = ""


class BranchManager:
    """分支管理器"""

    def __init__(self):
        BRANCHES_DIR.mkdir(parents=True, exist_ok=True)
        self._branches: Dict[str, ConversationBranch] = {}
        self._session_branches: Dict[str, List[str]] = {}  # session_id -> branch_ids
        self._load_branches()

    def _load_branches(self):
        """加载所有分支"""
        for branch_file in BRANCHES_DIR.glob("*.json"):
            try:
                data = json.loads(branch_file.read_text(encoding="utf-8"))
                branch_id = data.get("branch_id", branch_file.stem)

                branch = ConversationBranch(
                    branch_id=branch_id,
                    session_id=data.get("session_id", ""),
                    parent_branch_id=data.get("parent_branch_id"),
                    fork_point=data.get("fork_point", 0),
                    messages=data.get("messages", []),
                    created_at=data.get("created_at", 0),
                    name=data.get("name", ""),
                )

                self._branches[branch_id] = branch

                # 更新会话分支映射
                session_id = branch.session_id
                if session_id not in self._session_branches:
                    self._session_branches[session_id] = []
                if branch_id not in self._session_branches[session_id]:
                    self._session_branches[session_id].append(branch_id)

            except Exception as e:
                logger.warning(f"[Branch] 加载分支失败 {branch_file}: {e}")

    def _save_branch(self, branch_id: str):
        """保存分支到磁盘"""
        branch = self._branches.get(branch_id)
        if not branch:
            return

        branch_file = BRANCHES_DIR / f"{branch_id}.json"
        data = {
            "branch_id": branch.branch_id,
            "session_id": branch.session_id,
            "parent_branch_id": branch.parent_branch_id,
            "fork_point": branch.fork_point,
            "messages": branch.messages,
            "created_at": branch.created_at,
            "name": branch.name,
        }

        branch_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create_branch(
        self,
        session_id: str,
        messages: List[Dict],
        fork_point: int,
        parent_branch_id: str = None,
        name: str = "",
    ) -> ConversationBranch:
        """创建新分支"""
        import hashlib

        branch_id = hashlib.md5(
            f"{session_id}{fork_point}{time.time()}".encode()
        ).hexdigest()[:8]

        branch = ConversationBranch(
            branch_id=branch_id,
            session_id=session_id,
            parent_branch_id=parent_branch_id,
            fork_point=fork_point,
            messages=copy.deepcopy(messages),
            created_at=time.time(),
            name=name or f"分支 {len(self._session_branches.get(session_id, [])) + 1}",
        )

        self._branches[branch_id] = branch

        # 更新会话分支映射
        if session_id not in self._session_branches:
            self._session_branches[session_id] = []
        self._session_branches[session_id].append(branch_id)

        self._save_branch(branch_id)

        logger.info(f"[Branch] 创建分支: {branch_id} for session {session_id}")
        return branch

    def get_branch(self, branch_id: str) -> Optional[ConversationBranch]:
        """获取分支"""
        return self._branches.get(branch_id)

    def get_session_branches(self, session_id: str) -> List[Dict]:
        """获取会话的所有分支"""
        branch_ids = self._session_branches.get(session_id, [])

        branches = []
        for branch_id in branch_ids:
            branch = self._branches.get(branch_id)
            if branch:
                branches.append({
                    "branch_id": branch.branch_id,
                    "name": branch.name,
                    "fork_point": branch.fork_point,
                    "message_count": len(branch.messages),
                    "created_at": branch.created_at,
                })

        return branches

    def add_message(
        self,
        branch_id: str,
        role: str,
        content: str,
        metadata: Dict = None,
    ):
        """向分支添加消息"""
        branch = self._branches.get(branch_id)
        if not branch:
            return

        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        if metadata:
            message["metadata"] = metadata

        branch.messages.append(message)
        self._save_branch(branch_id)

    def get_messages(
        self,
        branch_id: str,
        from_index: int = 0,
    ) -> List[Dict]:
        """获取分支消息"""
        branch = self._branches.get(branch_id)
        if not branch:
            return []

        return branch.messages[from_index:]

    def fork_at(
        self,
        branch_id: str,
        message_index: int,
        new_name: str = "",
    ) -> Optional[ConversationBranch]:
        """在指定位置创建分支"""
        branch = self._branches.get(branch_id)
        if not branch:
            return None

        if message_index < 0 or message_index >= len(branch.messages):
            return None

        # 截取到指定位置的消息
        messages = branch.messages[:message_index + 1]

        return self.create_branch(
            session_id=branch.session_id,
            messages=messages,
            fork_point=message_index,
            parent_branch_id=branch_id,
            name=new_name,
        )

    def delete_branch(self, branch_id: str) -> bool:
        """删除分支"""
        branch = self._branches.get(branch_id)
        if not branch:
            return False

        # 从会话分支映射中移除
        session_id = branch.session_id
        if session_id in self._session_branches:
            self._session_branches[session_id] = [
                bid for bid in self._session_branches[session_id]
                if bid != branch_id
            ]

        del self._branches[branch_id]

        branch_file = BRANCHES_DIR / f"{branch_id}.json"
        if branch_file.exists():
            branch_file.unlink()

        logger.info(f"[Branch] 删除分支: {branch_id}")
        return True


# 全局分支管理器
branch_manager = BranchManager()
