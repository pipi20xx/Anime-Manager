"""
AI 对话会话的数据库存储（PostgreSQL，chat_sessions 表）

- 服务端只负责存取，消息内容仍由前端维护（/chat 端点保持无状态）
- 存储时做体积控制：截断超长工具结果、限制消息条数，避免单行膨胀
"""
import json
import logging
import time
import uuid
from typing import Dict, List, Optional

from sqlmodel import select

from database import db
from models import ChatSession

logger = logging.getLogger(__name__)

MAX_SESSIONS = 50
MAX_MESSAGES = 200
MAX_CONTENT_CHARS = 8000
MAX_TOOL_RESULT_CHARS = 2000


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _sanitize_segments(segments) -> List[Dict]:
    out = []
    for s in (segments or [])[:80]:
        if not isinstance(s, dict):
            continue
        t = s.get("type")
        if t == "text":
            out.append({"type": "text", "content": str(s.get("content") or "")[:MAX_CONTENT_CHARS]})
        elif t == "tool":
            result = s.get("result")
            if result is not None:
                try:
                    rj = json.dumps(result, ensure_ascii=False, default=str)
                    if len(rj) > MAX_TOOL_RESULT_CHARS:
                        result = {"_truncated": rj[:MAX_TOOL_RESULT_CHARS] + "…"}
                except Exception:
                    result = None
            out.append({
                "type": "tool",
                "toolName": str(s.get("toolName") or ""),
                "args": s.get("args"),
                "message": str(s.get("message") or "")[:500],
                "result": result,
                "success": s.get("success"),
                "status": s.get("status") or "done",
            })
        elif t == "skill":
            out.append({"type": "skill", "skillName": str(s.get("skillName") or "")[:100]})
        elif t == "thinking":
            out.append({"type": "thinking", "content": str(s.get("content") or "")[:2000]})
        elif t == "warning":
            out.append({"type": "warning", "message": str(s.get("message") or "")[:1000]})
    return out


def _sanitize_messages(messages) -> List[Dict]:
    cleaned = []
    for m in (messages or [])[-MAX_MESSAGES:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant"):
            continue
        entry = {
            "id": str(m.get("id") or _new_id()),
            "role": m["role"],
            "content": str(m.get("content") or "")[:MAX_CONTENT_CHARS],
            "status": m.get("status") or "done",
        }
        if m.get("skillName"):
            entry["skillName"] = str(m["skillName"])[:100]
        if m.get("skillId"):
            entry["skillId"] = str(m["skillId"])[:100]
        if m["role"] == "assistant" and isinstance(m.get("segments"), list):
            entry["segments"] = _sanitize_segments(m["segments"])
        cleaned.append(entry)
    return cleaned


def _sanitize_agent_history(history) -> List[Dict]:
    """内部历史快照（含 system/摘要/tool 消息），供下轮作为种子回传"""
    allowed_roles = ("system", "user", "assistant", "tool")
    cleaned = []
    for m in (history or [])[-40:]:
        if not isinstance(m, dict) or m.get("role") not in allowed_roles:
            continue
        entry = {"role": m["role"], "content": str(m.get("content") or "")[:4000]}
        if m.get("_is_summary"):
            entry["_is_summary"] = True
        if m.get("tool_calls"):
            entry["tool_calls"] = m["tool_calls"]
        if m.get("tool_call_id"):
            entry["tool_call_id"] = m["tool_call_id"]
        if m.get("name"):
            entry["name"] = m["name"]
        cleaned.append(entry)
    return cleaned


def _title_from_messages(messages) -> str:
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            title = str(m["content"]).strip().replace("\n", " ")
            return title[:24] or "新对话"
    return "新对话"


def _meta_from_row(row: ChatSession) -> Dict:
    return {
        "id": row.id,
        "title": row.title or "新对话",
        "updated_at": row.updated_at or 0,
        "message_count": row.message_count or 0,
    }


async def save_session(session_id: str, messages: List[Dict], title: str = "", agent_history: Optional[List[Dict]] = None) -> Dict:
    if not session_id:
        session_id = _new_id()

    cleaned_messages = _sanitize_messages(messages)
    new_title = (title or "").strip()[:50] or _title_from_messages(cleaned_messages)
    cleaned_history = _sanitize_agent_history(agent_history)
    now = time.time()

    async with db.session_scope():
        row = await db.get(ChatSession, session_id)
        if row:
            row.title = new_title
            row.updated_at = now
            row.message_count = len(cleaned_messages)
            row.messages = cleaned_messages
            row.agent_history = cleaned_history
        else:
            row = ChatSession(
                id=session_id,
                title=new_title,
                updated_at=now,
                message_count=len(cleaned_messages),
                messages=cleaned_messages,
                agent_history=cleaned_history,
            )
        await db.save(row, audit=False)

        # 会话数超上限时清理最旧的
        stmt = select(ChatSession).order_by(ChatSession.updated_at.desc())
        rows = await db.all(ChatSession, stmt)
        for old in rows[MAX_SESSIONS:]:
            await db.delete(old, audit=False)

    return {
        "id": session_id,
        "title": new_title,
        "updated_at": now,
        "message_count": len(cleaned_messages),
    }


async def get_session(session_id: str) -> Optional[Dict]:
    async with db.session_scope():
        row = await db.get(ChatSession, session_id)
        if not row:
            return None
        return {
            "id": row.id,
            "title": row.title or "新对话",
            "updated_at": row.updated_at or 0,
            "message_count": row.message_count or 0,
            "messages": row.messages or [],
            "agent_history": row.agent_history or [],
        }


async def list_sessions() -> List[Dict]:
    async with db.session_scope():
        stmt = select(ChatSession).order_by(ChatSession.updated_at.desc())
        rows = await db.all(ChatSession, stmt)
        return [_meta_from_row(r) for r in rows]


async def delete_session(session_id: str) -> bool:
    async with db.session_scope():
        row = await db.get(ChatSession, session_id)
        if not row:
            return False
        await db.delete(row, audit=False)
        return True
