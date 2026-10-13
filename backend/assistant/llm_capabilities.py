"""
llm_capabilities.py — LLM 能力档案与「思考深度」适配层

为什么需要这一层
----------------
1. OpenAI 兼容协议里**没有**「思考深度」的标准字段，各家网关/推理框架叫法不同：
   - OpenAI 系：``reasoning_effort``（minimal/low/medium/high）
   - Anthropic 风格网关：``thinking: {"type": "disabled"}``
   - vLLM / SGLang 系：顶层 ``enable_thinking`` 或 ``chat_template_kwargs.enable_thinking``
   - DeepSeek 官方：靠模型名区分（deepseek-chat / deepseek-reasoner），没有开关参数
2. 上下文长度、最大输出、是否支持思考，也**不是** ``/v1/models`` 的标准字段。

因此本模块做三件事：
- ``build_thinking_fragment``：把统一档位（off/auto/minimal/low/medium/high/max/xhigh）
  映射成某个「参数风格」下的实际请求体片段，不支持的档位**就近降级**；
- ``probe``：对某个 ``(base_url, model)`` 依次尝试各风格，用「HTTP 200 且思考 token 归零」
  判定哪种风格能真正关掉思考，结果按 (base_url, model) 缓存进配置，避免反复试；
- ``list_models``：拉模型列表，并尽力从非标准字段里提取上下文长度等元数据。

所有核心函数都是**同步**的（httpx.Client），异步调用方请用 ``asyncio.to_thread`` 包一层，
避免同步/异步两套实现漂移。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("LLMCapabilities")

# 缓存写在 assistant_config 下的这个键里：{ "<base_url>|<model>": {...} }
CACHE_CONFIG_KEY = "llm_capabilities"

# 统一档位（顺序即「思考由少到多」）
THINKING_LEVELS: tuple = ("off", "auto", "minimal", "low", "medium", "high", "max", "xhigh")

THINKING_LEVEL_LABELS: Dict[str, str] = {
    "off": "关闭思考",
    "auto": "跟随服务端默认",
    "minimal": "最低（minimal）",
    "low": "低（low）",
    "medium": "中（medium）",
    "high": "高（high）",
    "max": "最高（max）",
    "xhigh": "极高（xhigh）",
}


# ============================================================ 端点与请求头

def normalize_base_url(base_url: str) -> str:
    """去掉尾部斜杠/多余逗号（与 routers/assistant.py 既有处理保持一致）"""
    return (base_url or "").strip().rstrip(",").rstrip("/")


def chat_endpoint(base_url: str) -> str:
    """聊天补全端点。规则与既有代码一致：base 里已含 v1 就不再补 v1。"""
    base = normalize_base_url(base_url)
    return f"{base}/chat/completions" if "v1" in base else f"{base}/v1/chat/completions"


def models_endpoint(base_url: str, provider: str = "openai") -> str:
    """模型列表端点：Ollama 用原生 /api/tags，其余用 OpenAI 兼容的 /v1/models"""
    base = normalize_base_url(base_url)
    if provider == "ollama":
        return f"{base}/api/tags"
    return f"{base}/models" if "v1" in base else f"{base}/v1/models"


def build_headers(api_key: str, provider: str = "openai") -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if provider != "ollama" and api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


# ============================================================ 思考档位 → 参数片段

# 每种风格：label 供 UI 展示；levels 是「统一档位 → 该风格实际取值」的映射；
# true_off 表示该风格是否存在真正意义上的「关闭」（reasoning_effort 只能降到 minimal）。
THINKING_STYLES: Dict[str, Dict[str, Any]] = {
    "enable_thinking": {
        "label": "enable_thinking（vLLM / SGLang 风格）",
        "true_off": True,
        "levels": {
            "off": False,
            "minimal": True,
            "low": True,
            "medium": True,
            "high": True,
            "max": True,
            "xhigh": True,
        },
    },
    "chat_template_kwargs": {
        "label": "chat_template_kwargs.enable_thinking（vLLM / SGLang 模板参数）",
        "true_off": True,
        "levels": {
            "off": {"enable_thinking": False},
            "minimal": {"enable_thinking": True},
            "low": {"enable_thinking": True},
            "medium": {"enable_thinking": True},
            "high": {"enable_thinking": True},
            "max": {"enable_thinking": True},
            "xhigh": {"enable_thinking": True},
        },
    },
    "thinking_type": {
        "label": "thinking.type（Anthropic 风格）",
        "true_off": True,
        "levels": {
            "off": {"type": "disabled"},
            "minimal": {"type": "enabled"},
            "low": {"type": "enabled"},
            "medium": {"type": "enabled"},
            "high": {"type": "enabled"},
            "max": {"type": "enabled"},
            "xhigh": {"type": "enabled"},
        },
    },
    "reasoning_effort": {
        "label": "reasoning_effort（OpenAI 风格，只能降到 minimal，无法真正关闭）",
        "true_off": False,
        "levels": {
            "off": "minimal",  # 就近降级：该风格没有 off
            "minimal": "minimal",
            "low": "low",
            "medium": "medium",
            "high": "high",
            "max": "high",     # 就近降级
            "xhigh": "high",   # 就近降级
        },
    },
    "none": {
        "label": "不注入思考参数（靠模型名区分，如 deepseek-chat / deepseek-reasoner）",
        "true_off": False,
        "levels": {},
    },
}

# 探测顺序：越「无害」的风格越先试（顶层布尔开关对多数网关是未知字段，被忽略也不会报错）
PROBE_ORDER: tuple = ("enable_thinking", "chat_template_kwargs", "thinking_type", "reasoning_effort")


def style_label(style: str) -> str:
    return (THINKING_STYLES.get(style) or {}).get("label") or style


def supported_levels(style: str) -> List[str]:
    """该风格实际可用的统一档位（始终包含 auto）"""
    levels = (THINKING_STYLES.get(style) or {}).get("levels") or {}
    return ["auto"] + [lv for lv in THINKING_LEVELS if lv in levels]


def build_thinking_fragment(style: str, level: str) -> Dict[str, Any]:
    """
    把统一档位映射成要合并进请求体的片段。
    level == "auto"、风格为 none、或该风格不支持该档位时返回 {}（即不注入任何参数）。
    """
    if level == "auto" or level not in THINKING_LEVELS:
        return {}
    style_def = THINKING_STYLES.get(style) or {}
    value = (style_def.get("levels") or {}).get(level)
    if value is None:
        return {}
    if style == "reasoning_effort":
        return {"reasoning_effort": value}
    if style == "thinking_type":
        return {"thinking": value}
    if style == "enable_thinking":
        return {"enable_thinking": value}
    if style == "chat_template_kwargs":
        return {"chat_template_kwargs": value}
    return {}


# ============================================================ 能力缓存（落在配置里）

def cache_key(base_url: str, model: str) -> str:
    return f"{normalize_base_url(base_url)}|{(model or '').strip()}"


def _load_cache() -> Dict[str, Any]:
    try:
        from config_manager import ConfigManager

        cfg = ConfigManager.get_config() or {}
        cache = (cfg.get("assistant_config") or {}).get(CACHE_CONFIG_KEY)
        return cache if isinstance(cache, dict) else {}
    except Exception as e:  # 配置读取失败不应影响主流程
        logger.debug(f"[LLMCap] 读取能力缓存失败: {e}")
        return {}


def get_cached(base_url: str, model: str) -> Optional[Dict[str, Any]]:
    return _load_cache().get(cache_key(base_url, model))


def save_cached(base_url: str, model: str, data: Dict[str, Any]) -> None:
    try:
        from config_manager import ConfigManager

        cfg = ConfigManager.get_config() or {}
        assistant_cfg = dict(cfg.get("assistant_config") or {})
        cache = assistant_cfg.get(CACHE_CONFIG_KEY)
        cache = dict(cache) if isinstance(cache, dict) else {}
        cache[cache_key(base_url, model)] = data
        assistant_cfg[CACHE_CONFIG_KEY] = cache
        ConfigManager.update_config({"assistant_config": assistant_cfg})
    except Exception as e:
        logger.warning(f"[LLMCap] 写入能力缓存失败: {e}")


def clear_cached(base_url: str = "", model: str = "") -> int:
    """清空能力缓存（可按 base_url/model 过滤），返回清掉的条数"""
    try:
        from config_manager import ConfigManager

        cfg = ConfigManager.get_config() or {}
        assistant_cfg = dict(cfg.get("assistant_config") or {})
        cache = assistant_cfg.get(CACHE_CONFIG_KEY)
        cache = dict(cache) if isinstance(cache, dict) else {}
        if not base_url and not model:
            removed = len(cache)
            cache = {}
        else:
            prefix = cache_key(base_url, model) if model else normalize_base_url(base_url) + "|"
            keys = [k for k in cache if k.startswith(prefix)]
            removed = len(keys)
            for k in keys:
                cache.pop(k, None)
        assistant_cfg[CACHE_CONFIG_KEY] = cache
        ConfigManager.update_config({"assistant_config": assistant_cfg})
        return removed
    except Exception as e:
        logger.warning(f"[LLMCap] 清理能力缓存失败: {e}")
        return 0


def thinking_payload_from_cache(base_url: str, model: str, level: str) -> Dict[str, Any]:
    """
    取缓存里探测到的风格，生成请求体片段。
    没有缓存（还没探测过）时返回 {} —— 宁可不动，也不要给不认识的网关塞未知字段。
    """
    cached = get_cached(base_url, model)
    if not cached:
        return {}
    style = cached.get("thinking_style") or "none"
    return build_thinking_fragment(style, level)


# ============================================================ 探测

def _extract_reasoning_tokens(usage: Optional[Dict[str, Any]]) -> Optional[int]:
    """从各家五花八门的 usage 里抠出「思考 token」数；取不到返回 None"""
    if not isinstance(usage, dict):
        return None
    for key in ("completion_thinking_tokens", "reasoning_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            return value
    details = usage.get("completion_tokens_details")
    if isinstance(details, dict) and isinstance(details.get("reasoning_tokens"), int):
        return details["reasoning_tokens"]
    return None


def _probe_call(
    base_url: str,
    api_key: str,
    provider: str,
    model: str,
    extra: Dict[str, Any],
    timeout: float,
) -> Dict[str, Any]:
    """
    发一次最小探测请求。返回 {ok, status, reasoning_tokens, error}
    提示词刻意选「需要一点点推理」的题，好让推理型模型暴露思考 token。
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "1+1=? 只回答数字"}],
        "temperature": 0,
        "max_tokens": 64,
    }
    payload.update(extra or {})

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                chat_endpoint(base_url),
                json=payload,
                headers=build_headers(api_key, provider),
            )
        if resp.status_code != 200:
            return {
                "ok": False,
                "status": resp.status_code,
                "reasoning_tokens": None,
                "error": resp.text[:300],
            }
        data = resp.json()
        choices = data.get("choices") or []
        usage = data.get("usage") or {}
        content = ""
        if choices:
            content = ((choices[0].get("message") or {}).get("content") or "")
        return {
            "ok": True,
            "status": 200,
            "reasoning_tokens": _extract_reasoning_tokens(usage),
            "content_length": len(content),
            "error": "",
        }
    except Exception as e:
        return {"ok": False, "status": None, "reasoning_tokens": None, "error": f"{type(e).__name__}: {e}"}


def probe(
    base_url: str,
    api_key: str,
    model: str,
    provider: str = "openai",
    timeout: float = 30.0,
    persist: bool = True,
) -> Dict[str, Any]:
    """
    探测某个 (base_url, model) 的思考控制能力：

    1. 基线：不带任何思考参数发一次，看服务端**默认**是否思考（reasoning_tokens > 0）；
    2. 依次尝试候选风格，带各自的「off」取值再发一次：
       - HTTP 200 且思考 token 归零 → 该风格能**真正关掉**思考，采用；
       - HTTP 200 但仍有思考 token → 参数被忽略（或该风格无法真正关闭），继续试下一个；
       - 非 200 → 该风格不被接受，记录错误后继续。

    结果按 (base_url, model) 写入配置缓存（persist=True 时），下次直接复用。
    """
    result: Dict[str, Any] = {
        "base_url": normalize_base_url(base_url),
        "model": model,
        "provider": provider,
        "probed_at": int(time.time()),
        "default_thinking": None,      # 服务端默认是否思考
        "thinking_style": "none",      # 能真正关掉思考的风格；none = 关不掉
        "true_off": False,             # 是否找到「真正关闭」的方式
        "tried": [],
        "errors": {},
    }

    baseline = _probe_call(base_url, api_key, provider, model, {}, timeout)
    if not baseline.get("ok"):
        result["errors"]["__baseline__"] = baseline.get("error") or f"HTTP {baseline.get('status')}"
        result["ok"] = False
        result["message"] = "探测请求失败，请检查 API 地址 / Key / 模型名"
        return result

    baseline_reasoning = baseline.get("reasoning_tokens")
    result["default_thinking"] = None if baseline_reasoning is None else baseline_reasoning > 0

    if baseline_reasoning == 0:
        # 服务端默认就不思考，省掉后面 4 次探测
        result["ok"] = True
        result["thinking_style"] = "none"
        result["true_off"] = False
        result["message"] = "服务端默认就不思考，无需注入任何关闭参数"
        if persist:
            save_cached(base_url, model, result)
        return result

    for style in PROBE_ORDER:
        if not (THINKING_STYLES.get(style) or {}).get("true_off"):
            continue  # 关不掉的风格不参与「关思考」探测
        fragment = build_thinking_fragment(style, "off")
        if not fragment:
            continue
        attempt = _probe_call(base_url, api_key, provider, model, fragment, timeout)
        entry = {
            "style": style,
            "status": attempt.get("status"),
            "reasoning_tokens": attempt.get("reasoning_tokens"),
            "ok": bool(attempt.get("ok")),
        }
        result["tried"].append(entry)
        if not attempt.get("ok"):
            result["errors"][style] = attempt.get("error") or f"HTTP {attempt.get('status')}"
            continue
        reasoning = attempt.get("reasoning_tokens")
        if reasoning == 0:
            result["thinking_style"] = style
            result["true_off"] = True
            break
        if reasoning is None and baseline_reasoning is None:
            # 网关不报思考 token：只能退而求其次，认为「200 即接受」
            result["thinking_style"] = style
            result["true_off"] = None
            break

    # 兜底第二遍：找不到「真正关闭」的风格时，试一下 reasoning_effort=minimal。
    # 它关不掉思考，但可能显著压低思考量 —— 这就是「不支持该档位时就近映射」的落地方式。
    if result["thinking_style"] == "none" and isinstance(baseline_reasoning, int) and baseline_reasoning > 0:
        fragment = build_thinking_fragment("reasoning_effort", "off")
        attempt = _probe_call(base_url, api_key, provider, model, fragment, timeout)
        result["tried"].append({
            "style": "reasoning_effort",
            "status": attempt.get("status"),
            "reasoning_tokens": attempt.get("reasoning_tokens"),
            "ok": bool(attempt.get("ok")),
        })
        if attempt.get("ok"):
            reduced = attempt.get("reasoning_tokens")
            if isinstance(reduced, int) and reduced < baseline_reasoning:
                result["thinking_style"] = "reasoning_effort"
                result["true_off"] = False
                result["reduced_thinking"] = True
        else:
            result["errors"]["reasoning_effort"] = attempt.get("error") or f"HTTP {attempt.get('status')}"

    result["ok"] = True
    if result["true_off"]:
        result["message"] = f"已找到可关闭思考的参数风格：{style_label(result['thinking_style'])}"
    elif result.get("reduced_thinking"):
        result["message"] = (
            f"无法真正关闭思考，但已找到可压低思考量的参数：{style_label(result['thinking_style'])}"
        )
    elif result["thinking_style"] == "none":
        result["message"] = "未找到能关闭思考的参数，只能靠调大输出上限兜底"
    else:
        result["message"] = f"参数被接受但思考未归零，风格：{style_label(result['thinking_style'])}"

    if persist:
        save_cached(base_url, model, result)
    return result


# ============================================================ 模型列表

_CONTEXT_KEYS = ("context_length", "context_window", "max_model_len", "max_context_length", "max_context_tokens")
_OUTPUT_KEYS = ("max_output_tokens", "max_completion_tokens", "max_tokens")


def _pick_int(source: Dict[str, Any], keys) -> Optional[int]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _normalize_model_entry(raw: Any) -> Optional[Dict[str, Any]]:
    """把各家 /models 返回的一条记录归一化成 {id, context_length, max_output_tokens}"""
    if isinstance(raw, str):
        return {"id": raw, "context_length": None, "max_output_tokens": None}
    if not isinstance(raw, dict):
        return None

    # Ollama /api/tags: {name, model, details:{...}}；OpenAI: {id, ...}
    model_id = raw.get("id") or raw.get("name") or raw.get("model")
    if not model_id:
        return None

    merged: Dict[str, Any] = dict(raw)
    for nested_key in ("details", "meta", "capabilities", "metadata", "limits", "spec"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            merged.update(nested)

    return {
        "id": str(model_id),
        "context_length": _pick_int(merged, _CONTEXT_KEYS),
        "max_output_tokens": _pick_int(merged, _OUTPUT_KEYS),
    }


def list_models(
    base_url: str,
    api_key: str,
    provider: str = "openai",
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """
    拉取模型列表。返回 {ok, endpoint, models:[{id, context_length, max_output_tokens}], message}
    非标准字段（上下文长度等）能拿到就带上，拿不到就是 None —— 不做任何猜测。
    """
    endpoint = models_endpoint(base_url, provider)
    result: Dict[str, Any] = {"ok": False, "endpoint": endpoint, "models": [], "message": ""}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(endpoint, headers=build_headers(api_key, provider))
        if resp.status_code != 200:
            result["message"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return result
        data = resp.json()
    except Exception as e:
        result["message"] = f"{type(e).__name__}: {e}"
        return result

    raw_items: List[Any] = []
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        for key in ("data", "models", "items", "result"):
            value = data.get(key)
            if isinstance(value, list):
                raw_items = value
                break

    models: List[Dict[str, Any]] = []
    seen = set()
    for raw in raw_items:
        entry = _normalize_model_entry(raw)
        if entry and entry["id"] not in seen:
            seen.add(entry["id"])
            models.append(entry)

    models.sort(key=lambda m: m["id"].lower())
    result["ok"] = True
    result["models"] = models
    result["message"] = f"共 {len(models)} 个模型"
    return result
