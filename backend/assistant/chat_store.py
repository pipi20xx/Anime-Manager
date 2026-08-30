"""
AI 对话会话的本地文件存储

- 每个会话一个 JSON 文件，存放在 assistant/chat_sessions/ 下
- 服务端只负责存取，消息内容仍由前端维护（/chat 端点保持无状态）
- 存储时做体积控制：截断超长工具结果、限制消息条数，避免单文件膨胀
"""
import json
import logging
import os
import time
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_sessions")
MAX_SESSIONS = 50
MAX_MESSAGES = 200
MAX_CONTENT_CHARS = 8000
MAX_TOOL_RESULT_CHARS = 2000


def _ensure_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def _session_path(session_id: str) -> str:
    # 只允许安全字符，防路径穿越
    safe = "".join(c for c in str(session_id) if c.isalnum() or c in "-_")
    if not safe:
        safe = uuid.uuid4().hex[:16]
    return os.path.join(SESSIONS_DIR, f"{safe}.json")


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


def _meta(data: Dict) -> Dict:
    return {
        "id": data.get("id"),
        "title": data.get("title") or "新对话",
        "updated_at": data.get("updated_at") or 0,
        "message_count": data.get("message_count") or 0,
    }


def save_session(session_id: str, messages: List[Dict], title: str = "", agent_history: Optional[List[Dict]] = None) -> Dict:
    _ensure_dir()
    if not session_id:
        session_id = _new_id()

    cleaned_messages = _sanitize_messages(messages)
    data = {
        "id": session_id,
        "title": (title or "").strip()[:50] or _title_from_messages(cleaned_messages),
        "updated_at": time.time(),
        "message_count": len(cleaned_messages),
        "messages": cleaned_messages,
        "agent_history": _sanitize_agent_history(agent_history),
    }

    path = _session_path(session_id)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)

    _enforce_session_cap()
    return _meta(data)


def get_session(session_id: str) -> Optional[Dict]:
    path = _session_path(session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"[ChatStore] 读取会话失败 {session_id}: {e}")
        return None


def list_sessions() -> List[Dict]:
    _ensure_dir()
    metas = []
    for name in os.listdir(SESSIONS_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(SESSIONS_DIR, name), "r", encoding="utf-8") as f:
                metas.append(_meta(json.load(f)))
        except Exception:
            continue
    metas.sort(key=lambda x: x.get("updated_at") or 0, reverse=True)
    return metas


def delete_session(session_id: str) -> bool:
    path = _session_path(session_id)
    if not os.path.exists(path):
        return False
    try:
        os.remove(path)
        return True
    except Exception as e:
        logger.warning(f"[ChatStore] 删除会话失败 {session_id}: {e}")
        return False


def _enforce_session_cap():
    metas = list_sessions()
    for meta in metas[MAX_SESSIONS:]:
        delete_session(meta["id"])
    if len(metas) > MAX_SESSIONS:
        logger.info(f"[ChatStore] 会话数超上限，已清理 {len(metas) - MAX_SESSIONS} 个最旧会话")
