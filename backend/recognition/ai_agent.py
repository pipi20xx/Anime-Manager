"""识别专用智能体（AI「介入识别」的 agent 模式实现）。

与 backend/assistant 里的通用 Agent 刻意保持三处不同：

1. 封闭工具集：只暴露 3 个只读工具（离线库 / TMDB 搜索 / TMDB 详情），
   并且**不注册进全局 ToolRegistry** —— 既不污染聊天助手的工具集，
   也物理上排除了「工具反过来触发一次完整识别」造成的递归。
2. 硬预算：轮数 + 墙钟双上限。AI 介入跑在识别主链路上（RSS 检测、订阅匹配会批量调用），
   一次兜底不能拖住整个批次。
3. 出口与 oneshot 完全一致：仍是一个 dict（real_title / original_name / ...），
   调用方（matcher、AI 实验室）不需要知道自己拿到的是哪种实现。

入口在 AIHelper.guess_title_variants，`ai_mode == "agent"` 时才会走到这里。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger("AIAgent")


# ---------------------------------------------------------------- 预算默认值
# 可被 assistant_config 的 ai_agent_max_iterations / ai_agent_timeout_seconds 覆盖
DEFAULT_MAX_ITERATIONS = 3
DEFAULT_TIMEOUT_SECONDS = 25.0

# 与 AIHelper._guess_title_variants_openai 保持一致：
# 4096 是「输出上限」，推理型模型的思维链会把额度吃光，留一倍余量
MAX_TOKENS = 4096
TEMPERATURE = 0.1


SYSTEM_PROMPT = """你是影视作品识别助手。用户给出一个文件名，你要推断它对应的 TMDB 作品，并给出结构化结论。

你可以调用这些工具（全部只读，不会修改任何数据）：
- resolve_local: 查本地离线元数据库（最快、免费）。未命中返回 null。
- search_tmdb: 在 TMDB 搜索，返回候选列表（tmdb_id / 标题 / 原名 / 年份 / tv|movie / 评分）。
- get_tmdb_detail: 按 tmdb_id 取详情。tv 会返回每一季的 season_number、季名（中文 name / 英文 name_en / 日文 name_ja）、
  该季集数 episode_count、播出日期 air_date，以及整部剧的 status / last_air_date。**判断季号必须用它。**

工作方式：
1. 先从文件名里剥掉字幕组、分辨率、编码、语言等噪声，提取作品名候选。
2. 先 resolve_local；未命中再 search_tmdb。搜索词可以多试几个（中文译名 / 日文原名 / 罗马音 / 英文）。
3. 只要文件里出现季标（S2 / 第2期 / Act II S2 / 2nd Season），或者你判定是 tv，就必须先 get_tmdb_detail 再定季号。

季号判定规则（最容易错，务必按顺序走）：
- 文件名里的季标是「这部作品内部的第 N 部分」，**不等于** TMDB 的 season_number。
  例："Ace of Diamond Act II S2" 指 actII 的第 2 季，它在 TMDB 里是第 4 季（季名 "actII -Second Season-"），不是第 3 季。
- 第一步：用季名对齐。把文件名里的作品名 + 季标，跟每季的 name_en / name_ja 比对——
  "actII"、"Second Season"、"2nd Season"、"第2期" 这类标记会直接写在季名里。
- 第二步：季名如果是 "第 3 季" / "Season 3" 这种纯序号、对不上时，用 air_date 判断：
  取「播出日期不晚于文件来历时期」的最新一季（正在追的新番通常是当年那一季）。
- 第三步：仍然定不下来 → season 填 null。此时系统会保留规则层解析出的季号，比猜一个错的强。
- season 必须是 get_tmdb_detail 返回过的 season_number，且 episode 不得超过该季的 episode_count。

硬规则：
- 标题必须来自工具返回过的结果，不要凭记忆编造作品名或 TMDB ID。
- 工具确实查不到时，可以给出有依据的推断，但 confidence 必须 <= 0.4。
- 不要解释推理过程，不要输出 markdown 或代码块。

最终只输出一个 JSON 对象，字段固定为：
{"real_title":"","original_name":"","chinese_name":"","alternative_titles":[],"media_type":"tv","season":null,"episode":null,"confidence":0.0,"tmdb_id":null}

字段说明：
- real_title: 用于搜索 TMDB 的官方标题（英文/罗马音），必须是工具返回过的标题之一
- original_name: 原始名称（日文原名或英文原名）
- chinese_name: 中文译名
- alternative_titles: 其他可用于搜索的别名
- media_type: "tv" 或 "movie"
- season / episode: 与 media_type 对应的季号与季度内集数；不确定填 null
- confidence: 0 ~ 1 的置信度
- tmdb_id: 你最终选定的 TMDB ID（工具返回的整数），没有就填 null"""


TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "resolve_local",
            "description": "查本地离线元数据库（最快）。返回命中的作品标题、TMDB ID、年份、类型；未命中返回 null。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "作品名（中文译名或原名）"},
                    "year": {"type": "string", "description": "年份，可选"},
                    "media_type": {
                        "type": "string",
                        "enum": ["tv", "movie"],
                        "description": "媒体类型，可选",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_tmdb",
            "description": "在 TMDB 搜索影视作品，返回候选列表（含 tmdb_id、标题、原名、年份、媒体类型）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词（保持原样，不要改动拼写）"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tmdb_detail",
            "description": (
                "按 TMDB ID 获取详情。tv 返回每一季的 season_number、季名（中文 name / 英文 name_en / "
                "日文 name_ja）、该季集数 episode_count、播出日期 air_date，以及整剧的 status / last_air_date。"
                "判断「文件名季标对应 TMDB 第几季」必须用它，不能凭猜测。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tmdb_id": {"type": "integer", "description": "TMDB ID"},
                    "media_type": {"type": "string", "enum": ["tv", "movie"], "description": "媒体类型"},
                },
                "required": ["tmdb_id", "media_type"],
            },
        },
    },
]


def _is_chinese(text: str) -> bool:
    for char in text or "":
        if "\u4e00" <= char <= "\u9fff":
            return True
    return False


def _chat_endpoint(base_url: str) -> str:
    """URL 归一化。规则与 AIHelper._guess_title_variants_openai 保持一致，两处需同步修改。"""
    base_url = (base_url or "").strip().rstrip("/").rstrip(",")
    if base_url.endswith("/chat/completions"):
        return base_url
    if base_url.endswith("/v1"):
        return f"{base_url}/chat/completions"
    return f"{base_url}/chat/completions"


def event_emitter(events: Optional[List[Dict[str, Any]]], t0: Optional[float] = None):
    """生成一个事件收集器：把 agent 的每一步追加进列表，供 AI 实验室页面回放。

    events 为 None 时返回空实现（线上识别路径零开销）。
    事件结构：{"type": "...", "t_ms": 相对开始的毫秒数, ...其余字段}
    """
    if events is None:
        return lambda kind, **payload: None

    start = t0 if t0 is not None else time.monotonic()

    def emit(kind: str, **payload: Any) -> None:
        try:
            events.append(
                {
                    "type": kind,
                    "t_ms": int((time.monotonic() - start) * 1000),
                    **payload,
                }
            )
        except Exception:  # 追踪失败绝不能影响识别
            logger.debug("[AI-Agent] 追踪事件写入失败", exc_info=True)

    return emit


def _clip(text: Any, limit: int = 4000) -> str:
    """事件里的长文本截断，避免把整页撑爆。"""
    if text is None:
        return ""
    value = text if isinstance(text, str) else json.dumps(text, ensure_ascii=False, default=str)
    return value if len(value) <= limit else value[:limit] + f"\n…（已截断，共 {len(value)} 字符）"


class RecognitionAgent:
    """带封闭工具集的识别智能体。run() 返回与 oneshot 相同的 dict，失败返回 None。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        thinking_fragment: Optional[Dict[str, Any]] = None,
        log: Optional[Callable[[str], None]] = None,
        anime_priority: bool = True,
        events: Optional[List[Dict[str, Any]]] = None,
    ):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_iterations = max(1, int(max_iterations))
        self.timeout_seconds = max(5.0, float(timeout_seconds))
        self.thinking_fragment = thinking_fragment or {}
        self._log_fn = log
        self.anime_priority = anime_priority
        self.tool_calls_made = 0
        # get_tmdb_detail 的返回缓存：归一化阶段用它做季号/集数的确定性校验
        self._detail_cache: Dict[str, Dict[str, Any]] = {}
        # 结构化追踪（仅 AI 实验室等需要回放的场景传入）
        self.events = events
        self._emit = event_emitter(events)

    # ------------------------------------------------------------ 基础设施
    def log(self, message: str):
        if self._log_fn:
            try:
                self._log_fn(message)
            except Exception:  # 日志失败不能影响识别
                logger.info(message)
        else:
            logger.info(message)

    @property
    def endpoint(self) -> str:
        return _chat_endpoint(self.base_url)

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _post(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        *,
        with_tools: bool,
        timeout: float,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
            **self.thinking_fragment,
        }
        if with_tools:
            payload["tools"] = TOOL_SCHEMAS
            payload["tool_choice"] = "auto"

        resp = await client.post(self.endpoint, json=payload, headers=self._headers())
        if resp.status_code != 200:
            raise RuntimeError(f"API 错误 [{resp.status_code}]: {resp.text[:300]}")
        return resp.json()

    @staticmethod
    def _message_of(data: Dict[str, Any]) -> Tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        return message, content, tool_calls

    # --------------------------------------------------------------- 工具实现
    async def _tool_resolve_local(
        self, query: str, year: Optional[str] = None, media_type: Optional[str] = None
    ) -> Any:
        from .data_provider.offline import OfflineDAO

        cn = query if _is_chinese(query) else None
        en = None if _is_chinese(query) else query
        match = await OfflineDAO.resolve(
            cn_name=cn,
            en_name=en,
            year=year or None,
            media_type=media_type or None,
            anime_priority=self.anime_priority,
            logs=[],
        )
        if not match:
            return None
        return {
            "title": match.get("title"),
            "tmdb_id": match.get("id"),
            "year": match.get("year"),
            "media_type": match.get("type"),
        }

    async def _tool_search_tmdb(self, query: str) -> Any:
        from .data_provider.tmdb.client import TMDBProvider

        provider = TMDBProvider()
        results, _ok = await provider.search_multi(query)
        items = []
        for item in (results or [])[:8]:
            media_type = item.get("media_type") or "tv"
            date = item.get("release_date") or item.get("first_air_date") or ""
            items.append(
                {
                    "tmdb_id": item.get("id"),
                    "title": item.get("title") or item.get("name"),
                    "original_title": item.get("original_title") or item.get("original_name"),
                    "year": str(date)[:4] or None,
                    "media_type": media_type,
                    "vote_average": item.get("vote_average"),
                    "popularity": item.get("popularity"),
                }
            )
        return items

    async def _tool_get_tmdb_detail(self, tmdb_id: Any, media_type: str) -> Any:
        """季信息必须带上「能用来对齐的多语言季名 + 播出日期」，否则 agent 无法判断
        文件名里的季标（如 Act II S2）对应 TMDB 第几季 —— 中文季名往往只有「第 4 季」。"""
        from .data_provider.tmdb.client import TMDBProvider

        provider = TMDBProvider()
        tmdb_id = str(tmdb_id)

        calls: List[Any] = [provider.get_subject_details(tmdb_id, media_type)]
        if media_type == "tv":
            # _fetch 内部是 params["language"] = params.get("language", "zh-CN")，显式传即覆盖
            calls.append(provider._fetch(f"/tv/{tmdb_id}", {"language": "en-US"}))
            calls.append(provider._fetch(f"/tv/{tmdb_id}", {"language": "ja-JP"}))
        results = await asyncio.gather(*calls, return_exceptions=True)

        data = results[0] if not isinstance(results[0], BaseException) else None
        if not data:
            return None

        # 英文/日文季名（失败就留空，不影响主流程）
        localized: Dict[int, Dict[str, str]] = {}
        if media_type == "tv":
            for lang, result in (("en", results[1]), ("ja", results[2])):
                if isinstance(result, BaseException) or not result:
                    continue
                payload = result[0] if isinstance(result, tuple) else result
                for season in (payload or {}).get("seasons") or []:
                    number = season.get("season_number")
                    name = (season.get("name") or "").strip()
                    if number is not None and name:
                        localized.setdefault(int(number), {})[lang] = name

        seasons: Dict[int, Dict[str, Any]] = {}
        if media_type == "tv":
            for season in (data.get("seasons") or [])[:40]:
                number = season.get("season_number")
                if number is None:
                    continue
                number = int(number)
                seasons[number] = {
                    "season_number": number,
                    "name": season.get("name"),
                    "name_en": localized.get(number, {}).get("en"),
                    "name_ja": localized.get(number, {}).get("ja"),
                    "episode_count": season.get("episode_count"),
                    "air_date": season.get("air_date"),
                }

        compact = {
            "tmdb_id": data.get("id"),
            "title": data.get("title") or data.get("name"),
            "original_title": data.get("original_title") or data.get("original_name"),
            "first_air_date": data.get("first_air_date") or data.get("release_date"),
            "status": data.get("status"),
            "last_air_date": data.get("last_air_date"),
            "number_of_seasons": data.get("number_of_seasons"),
            "number_of_episodes": data.get("number_of_episodes"),
            "seasons": [seasons[number] for number in sorted(seasons)] or None,
        }
        self._detail_cache[str(compact.get("tmdb_id") or tmdb_id)] = compact
        return compact

    async def _exec_tool(self, name: str, arguments: Dict[str, Any], timeout: float) -> str:
        handlers = {
            "resolve_local": self._tool_resolve_local,
            "search_tmdb": self._tool_search_tmdb,
            "get_tmdb_detail": self._tool_get_tmdb_detail,
        }
        handler = handlers.get(name)
        if not handler:
            return json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        try:
            result = await asyncio.wait_for(handler(**arguments), timeout=timeout)
        except asyncio.TimeoutError:
            return json.dumps({"error": f"工具 {name} 超时"}, ensure_ascii=False)
        except TypeError as e:
            return json.dumps({"error": f"参数错误: {e}"}, ensure_ascii=False)
        except Exception as e:  # 工具失败要让模型看见，而不是中断整轮
            logger.warning(f"[AI-Agent] 工具 {name} 失败: {type(e).__name__}: {e}")
            return json.dumps({"error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)
        return json.dumps(result, ensure_ascii=False, default=str)

    # ------------------------------------------------------------- 主循环
    async def run(
        self,
        filename: str,
        current_title: Optional[str] = None,
        current_episode: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        if not filename:
            return None

        deadline = time.monotonic() + self.timeout_seconds
        self.tool_calls_made = 0

        parts = [f"文件名: {filename}"]
        if current_title:
            parts.append(f"规则层已识别的标题（可能不准确，仅供参考）: {current_title}")
        if current_episode:
            parts.append(f"规则层已识别的集数（可能不准确，仅供参考）: {current_episode}")
        user_content = "\n".join(parts)

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        self.log("[AI-Agent] 🤖 agent 模式启动（工具: resolve_local / search_tmdb / get_tmdb_detail）")
        self._emit(
            "start",
            mode="agent",
            filename=filename,
            current_title=current_title,
            current_episode=current_episode,
            model=self.model,
            endpoint=self.endpoint,
            max_iterations=self.max_iterations,
            timeout_seconds=self.timeout_seconds,
            thinking=self.thinking_fragment or None,
            tools=[schema["function"]["name"] for schema in TOOL_SCHEMAS],
            system_prompt=SYSTEM_PROMPT,
            user_message=user_content,
        )

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for iteration in range(1, self.max_iterations + 1):
                    remaining = deadline - time.monotonic()
                    if remaining <= 1.0:
                        self.log(f"[AI-Agent] ⏱️ 预算用尽（第 {iteration} 轮前），要求直接给结论")
                        self._emit("budget", reason="deadline", iteration=iteration)
                        return await self._ask_final(client, messages, deadline)

                    self.log(f"[AI-Agent] ↻ 第 {iteration}/{self.max_iterations} 轮")
                    self._emit("iteration", index=iteration, max=self.max_iterations)
                    llm_started = time.monotonic()
                    data = await asyncio.wait_for(
                        self._post(client, messages, with_tools=True, timeout=remaining),
                        timeout=remaining,
                    )
                    _message, content, tool_calls = self._message_of(data)
                    meta = self._response_meta(data)
                    self._emit(
                        "llm_response",
                        iteration=iteration,
                        elapsed_ms=int((time.monotonic() - llm_started) * 1000),
                        finish_reason=meta["finish_reason"],
                        usage=meta["usage"],
                        content=_clip(content),
                        reasoning=_clip(meta["reasoning"]),
                        tool_calls=len(tool_calls),
                    )

                    if tool_calls:
                        messages.append(
                            {"role": "assistant", "content": content, "tool_calls": tool_calls}
                        )
                        for tool_call in tool_calls:
                            fn = tool_call.get("function") or {}
                            name = fn.get("name") or ""
                            raw_args = fn.get("arguments") or "{}"
                            try:
                                arguments = json.loads(raw_args) if raw_args else {}
                                if not isinstance(arguments, dict):
                                    arguments = {}
                            except json.JSONDecodeError:
                                arguments = {}
                            self.log(f"[AI-Agent] 🔧 调用 {name}({self._brief(arguments)})")
                            self._emit(
                                "tool_call", iteration=iteration, name=name, arguments=arguments
                            )
                            tool_started = time.monotonic()
                            remaining = deadline - time.monotonic()
                            result = await self._exec_tool(
                                name, arguments, timeout=max(3.0, min(remaining, 15.0))
                            )
                            self._emit(
                                "tool_result",
                                iteration=iteration,
                                name=name,
                                elapsed_ms=int((time.monotonic() - tool_started) * 1000),
                                result=_clip(result),
                            )
                            self.log(f"[AI-Agent] 📥 {name} → {self._brief_text(result)}")
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id", ""),
                                    "content": result,
                                }
                            )
                            self.tool_calls_made += 1

                        if self.tool_calls_made >= 8:  # 单文件工具调用总量上限
                            self.log("[AI-Agent] ⏱️ 工具调用达到上限，要求直接给结论")
                            self._emit("budget", reason="tool_calls", iteration=iteration)
                            return await self._ask_final(client, messages, deadline)
                        continue

                    # 没有工具调用 = 它认为可以收尾了
                    parsed = self._extract_json_object(content)
                    if parsed:
                        normalized = self._normalize(parsed)
                        self._emit(
                            "final",
                            source="json",
                            iteration=iteration,
                            result=normalized,
                            raw=_clip(content),
                        )
                        return normalized

                    # 给了文字但不是 JSON：催一次纯 JSON
                    self.log("[AI-Agent] ⚠️ 收尾输出不是合法 JSON，催一次纯 JSON")
                    self._emit("repair", iteration=iteration, raw=_clip(content))
                    messages.append({"role": "assistant", "content": content or ""})
                    messages.append(
                        {
                            "role": "user",
                            "content": "只输出那一个 JSON 对象，不要任何解释、不要 markdown。",
                        }
                    )
                    remaining = deadline - time.monotonic()
                    if remaining <= 1.0:
                        break
                    data = await asyncio.wait_for(
                        self._post(client, messages, with_tools=False, timeout=remaining),
                        timeout=remaining,
                    )
                    _m, content2, _tc = self._message_of(data)
                    meta2 = self._response_meta(data)
                    self._emit(
                        "llm_response",
                        iteration=iteration,
                        phase="repair",
                        finish_reason=meta2["finish_reason"],
                        usage=meta2["usage"],
                        content=_clip(content2),
                        reasoning=_clip(meta2["reasoning"]),
                        tool_calls=0,
                    )
                    parsed = self._extract_json_object(content2)
                    if parsed:
                        normalized = self._normalize(parsed)
                        self._emit(
                            "final",
                            source="repair",
                            iteration=iteration,
                            result=normalized,
                            raw=_clip(content2),
                        )
                        return normalized
                    self._emit("error", message="收尾输出仍不是合法 JSON")
                    return None

                self._emit("budget", reason="iterations")
                return await self._ask_final(client, messages, deadline)
        except asyncio.TimeoutError:
            self.log("[AI-Agent] ⏱️ 请求超时")
            self._emit("error", message="请求超时")
            return None
        except Exception as e:
            self.log(f"[AI-Agent] ❌ 执行失败: {type(e).__name__}: {e}")
            self._emit("error", message=f"{type(e).__name__}: {e}")
            return None

    async def _ask_final(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
        deadline: float,
    ) -> Optional[Dict[str, Any]]:
        """收尾：不再带工具，强制只输出 JSON。"""
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            self._emit("error", message="收尾阶段预算已耗尽")
            return None
        final_messages = messages + [
            {
                "role": "user",
                "content": "现在直接输出最终 JSON 对象（不要调用工具、不要解释）。",
            }
        ]
        try:
            data = await asyncio.wait_for(
                self._post(client, final_messages, with_tools=False, timeout=remaining),
                timeout=remaining,
            )
        except Exception as e:
            self.log(f"[AI-Agent] ❌ 收尾请求失败: {type(e).__name__}: {e}")
            self._emit("error", message=f"收尾请求失败: {type(e).__name__}: {e}")
            return None
        _m, content, _tc = self._message_of(data)
        meta = self._response_meta(data)
        self._emit(
            "llm_response",
            phase="final",
            finish_reason=meta["finish_reason"],
            usage=meta["usage"],
            content=_clip(content),
            reasoning=_clip(meta["reasoning"]),
            tool_calls=0,
        )
        parsed = self._extract_json_object(content)
        if not parsed:
            self.log(f"[AI-Agent] ❌ 收尾输出无法解析为 JSON（{len(content)} 字符）")
            self._emit("error", message="收尾输出无法解析为 JSON", raw=_clip(content))
            return None
        normalized = self._normalize(parsed)
        self._emit("final", source="forced", result=normalized, raw=_clip(content))
        return normalized

    @staticmethod
    def _response_meta(data: Dict[str, Any]) -> Dict[str, Any]:
        """抽出追踪需要的响应元信息（finish_reason / usage / 思维链）。"""
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return {
            "finish_reason": choice.get("finish_reason"),
            "usage": data.get("usage"),
            "reasoning": message.get("reasoning_content") or "",
        }

    # ------------------------------------------------------------- 解析/归一
    @staticmethod
    def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
        """括号配对提取最外层 JSON 对象。

        不能用 find('{')/rfind('}')：agent 的输出里常带候选列表、举例，
        简单截取会跨多个对象。这里按深度扫描，并且从后往前试，
        因为真正的结论通常在最后。
        """
        if not text:
            return None
        candidates: List[str] = []
        depth = 0
        start = -1
        in_string = False
        escaped = False
        for index, char in enumerate(text):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start >= 0:
                        candidates.append(text[start : index + 1])
        for raw in reversed(candidates):
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj
        return None

    def _normalize(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """把模型输出压成 matcher 期望的契约，顺带带上验证信息。"""
        if not isinstance(raw, dict):
            return None

        def _as_int(value: Any) -> Optional[int]:
            if value in (None, "", "null", "None"):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        def _as_text(value: Any) -> Optional[str]:
            text = str(value).strip() if value is not None else ""
            return text or None

        real_title = _as_text(raw.get("real_title"))
        if not real_title:
            self.log("[AI-Agent] ⚠️ 缺少 real_title，丢弃本次结果")
            return None

        media_type = _as_text(raw.get("media_type"))
        media_type = media_type.lower() if media_type else None
        if media_type not in ("tv", "movie"):
            media_type = None

        alternatives = raw.get("alternative_titles") or []
        if isinstance(alternatives, str):
            alternatives = [alternatives]
        if not isinstance(alternatives, list):
            alternatives = []
        cleaned_alts: List[str] = []
        for item in alternatives:
            text = _as_text(item)
            if text and text not in cleaned_alts:
                cleaned_alts.append(text)

        try:
            confidence = float(raw.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        tmdb_id = _as_int(raw.get("tmdb_id"))
        episode = _as_int(raw.get("episode"))

        # 季号确定性校验：模型给的季必须能被 get_tmdb_detail 的事实支持，
        # 否则宁可回 null（matcher 会保留规则层解析出的季号），也不交一个自相矛盾的结论。
        season = _as_int(raw.get("season"))
        if media_type == "movie":
            season = None  # 电影没有季号，避免污染 meta.begin_season
            episode = episode or None
        season, verify_note = self._verify_season(media_type, tmdb_id, season, episode)
        if verify_note:
            self.log(f"[AI-Agent] ⚠️ 季号校验未通过: {verify_note}")
        if verify_note or (media_type == "tv" and season is not None):
            self._emit(
                "verify",
                ok=verify_note is None,
                note=verify_note,
                season=season,
                episode=episode,
                tmdb_id=tmdb_id,
            )

        return {
            "real_title": real_title,
            "original_name": _as_text(raw.get("original_name")),
            "chinese_name": _as_text(raw.get("chinese_name")),
            "alternative_titles": cleaned_alts,
            "media_type": media_type,
            "season": season,
            "episode": episode,
            "confidence": confidence,
            # 以下字段 oneshot 没有，matcher 不读，仅供调试/展示
            "tmdb_id": tmdb_id,
            "agent": {
                "tool_calls": self.tool_calls_made,
                "mode": "agent",
                # None = 不适用（非 tv 或没给季号）；True/False = 是否被 TMDB 数据支持
                "season_verified": (
                    (verify_note is None) if (media_type == "tv" and season is not None) else None
                ),
                "note": verify_note,
            },
        }

    def _verify_season(
        self,
        media_type: Optional[str],
        tmdb_id: Optional[int],
        season: Optional[int],
        episode: Optional[int],
    ) -> Tuple[Optional[int], Optional[str]]:
        """用 get_tmdb_detail 的缓存结果校验季号/集数。

        返回 (可能被修正的 season, 未通过原因)。season 被置 None 表示「不采信 AI 的季号」。
        """
        if media_type != "tv" or season is None:
            return season, None

        detail = self._detail_cache.get(str(tmdb_id)) if tmdb_id is not None else None
        if not detail:
            return None, "未调用 get_tmdb_detail，季号无据可依"

        seasons = {
            int(item["season_number"]): item
            for item in (detail.get("seasons") or [])
            if item.get("season_number") is not None
        }
        info = seasons.get(int(season))
        if info is None:
            return None, f"TMDB 上没有第 {season} 季"
        count = info.get("episode_count")
        if episode is not None and count is not None and int(episode) > int(count):
            return None, f"第 {season} 季只有 {count} 集，装不下第 {episode} 集"
        return season, None

    @staticmethod
    def _brief(arguments: Dict[str, Any]) -> str:
        text = json.dumps(arguments, ensure_ascii=False)
        return text[:120]

    @staticmethod
    def _brief_text(text: str) -> str:
        return (text or "")[:160]
