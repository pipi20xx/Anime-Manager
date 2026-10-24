import json
import logging
import httpx
from typing import Optional, Dict, Any
from config_manager import ConfigManager

logger = logging.getLogger("AIHelper")

class AIHelper:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(AIHelper, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        pass

    @property
    def ai_config(self) -> Dict[str, Any]:
        config = ConfigManager.get_config()
        assistant_config = config.get("assistant_config", {})
        
        return {
            "openai_base_url": assistant_config.get("base_url", ""),
            "openai_api_key": assistant_config.get("api_key", "sk-xxx"),
            "openai_model": assistant_config.get("model", ""),
            "ai_fallback_enabled": assistant_config.get("ai_fallback_enabled", False)
        }

    def is_available(self) -> bool:
        url = self.ai_config.get("openai_base_url", "")
        model = self.ai_config.get("openai_model", "")
        return bool(url and url.startswith("http") and model)

    def is_fallback_enabled(self) -> bool:
        return self.ai_config.get("ai_fallback_enabled", False)

    def guess_title_variants(self, filename: str, current_title: str = None, current_episode: int = None) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            logger.warning("[AI-Fallback] AI 不可用: base_url 或 model 未配置")
            return None
        
        return self._guess_title_variants_openai(filename, current_title, current_episode)

    def _get_fallback_system_prompt(self) -> str:
        return """你是影视剧数据库专家，精通中日英三语的影视动画作品名。根据用户给出的文件名，推断该文件对应的 TMDB 真实标题。

输出格式：只输出一个 JSON 对象，不要输出任何其他文字。

{"real_title":"","original_name":"","chinese_name":"","alternative_titles":[],"media_type":"tv","season":null,"episode":null,"confidence":0.9}

字段说明:
- real_title: TMDB 上的官方标题（英文/罗马音），简洁准确，用于直接搜索 TMDB
- original_name: 作品原始名称（日文原名或英文原名）
- chinese_name: 中文官方译名
- alternative_titles: 其他可能的标题（罗马音、缩写、别名等），用于辅助搜索
- media_type: "tv"（剧集/番剧/有集数的）或 "movie"（电影/剧场版）
- season: 季数（整数或 null，不确定时填 null）
- episode: 集数（整数或 null，不确定时填 null）
- confidence: 置信度 0~1

关键规则:
- 文件名可能包含字幕组、分辨率、编码等无关信息，需要剥离
- 标题可能是中文译名、罗马音、英文或混合，需要推断出 TMDB 上的标准标题
- 全角字符（如／）应转换为半角（/）
- 剧场版、电影版、劇場版 → media_type: "movie"
- 番剧、连续剧、TV 系列、有集数标记 → media_type: "tv"
- 文件名可能同时出现季度内集数（如 [4th - 19]、S04E19）和绝对集数（如 總第85、全集85），episode 填与 season 对应的季度内集数，绝对集数仅作辅助
- 季度标记如 [4th]、S4、第4季、IV 期 → season 填对应数字；无季度标记时不确定就填 null
- 如果提供了已识别的标题或集数信息，作为参考但不一定正确"""

    def _guess_title_variants_openai(self, filename: str, current_title: str = None, current_episode: int = None) -> Optional[Dict[str, Any]]:
        base_url = self.ai_config.get("openai_base_url", "")
        api_key = self.ai_config.get("openai_api_key", "sk-xxx")
        model = self.ai_config.get("openai_model", "")

        if base_url.endswith("/chat/completions"):
            target_url = base_url
        elif base_url.rstrip("/").endswith("/v1"):
            target_url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            target_url = f"{base_url.rstrip('/')}/chat/completions"

        # 构建用户消息：文件名 + 可选的已知信息
        parts = [f"文件名: {filename}"]
        if current_title:
            parts.append(f"已识别标题（可能不准确，仅供参考）: {current_title}")
        if current_episode:
            parts.append(f"已识别集数（可能不准确，仅供参考）: {current_episode}")
        user_content = "\n".join(parts)

        messages = [
            {"role": "system", "content": self._get_fallback_system_prompt()},
            {"role": "user", "content": user_content}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            # 这是「输出上限」，只作用于本文件（AI 介入测试/介入识别），
            # 与 AI 实验室里那个「最大 Token 数 (K)」无关（那个只给助手对话用）。
            # 256 时推理型模型（deepseek-v4.x）的思维链会把额度吃光 → content 为空；
            # 实测单次最长约 2k 思考 token，这里留一倍余量。
            "max_tokens": 4096
        }

        # 思考深度：介入识别是确定性抽取任务，不需要思维链。
        # 只用「探测缓存里已确认可用」的关闭风格；没探测过就不注入（不给不认识的网关塞未知字段）。
        try:
            from assistant import llm_capabilities
        except Exception as e:  # 能力层不可用时退化为「不注入思考参数」
            llm_capabilities = None
            logger.debug(f"[AI-Fallback] 能力层不可用，跳过思考参数注入: {e}")
        if llm_capabilities:
            thinking_fragment = llm_capabilities.thinking_payload_from_cache(base_url, model, "off")
            if thinking_fragment:
                payload.update(thinking_fragment)
                logger.info(f"[AI-Fallback] 🧠 按能力缓存注入思考参数: {thinking_fragment}")

        logger.debug(f"[AI-Fallback] 📤 请求模型: {model}")
        logger.debug(f"[AI-Fallback] 📤 URL: {target_url}")
        logger.debug(f"[AI-Fallback] 📤 文件名: {filename}")

        try:
            import time
            start_time = time.time()
            
            # 超时与上面的 max_tokens 挂钩：推理型模型按实测 ~150 token/s 计，
            # 4096 token 约需 28s，这里给到 120s 以免「调大上限反而撞超时」
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    target_url,
                    json=payload,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                )
                
                elapsed = time.time() - start_time
                logger.debug(f"[AI-Fallback] ⏱️ 响应时间: {elapsed:.2f}s, 状态码: {resp.status_code}")
                
                if resp.status_code != 200:
                    logger.error(f"[AI-Fallback] ❌ API 错误 [{resp.status_code}]: {resp.text[:500]}")
                    return None
                
                data = resp.json()
                
                if not data.get("choices"):
                    logger.error(f"[AI-Fallback] ❌ 无有效响应: {data}")
                    return None
                
                choice = data["choices"][0]
                message = choice.get("message") or {}
                content = message.get("content") or ""
                reasoning = message.get("reasoning_content") or ""
                finish_reason = choice.get("finish_reason")

                logger.info(
                    f"[AI-Fallback] 📥 finish_reason={finish_reason} | "
                    f"content={len(content)} 字符 | reasoning={len(reasoning)} 字符 | "
                    f"usage={data.get('usage')}"
                )

                if not content.strip():
                    if finish_reason == "length":
                        # 额度被思维链吃光：探测一次该 (base_url, model) 支持哪种关闭方式并重试
                        retried = self._retry_with_thinking_off(base_url, api_key, model, target_url, messages)
                        if retried:
                            return retried
                        logger.error(
                            f"[AI-Fallback] ❌ max_tokens 用尽仍未产出正文（模型: {model}，"
                            f"推理内容 {len(reasoning)} 字符）：请调大 max_tokens、改用非推理模型，"
                            f"或在 AI 实验室点「探测能力」"
                        )
                    elif reasoning:
                        logger.error(
                            "[AI-Fallback] ❌ message.content 为空，正文疑似只出现在 reasoning_content 中"
                        )
                    else:
                        logger.error(
                            f"[AI-Fallback] ❌ 模型返回空响应，请确认模型名 '{model}' 在 {base_url} 上可用"
                        )
                    return None

                logger.debug(f"[AI-Fallback] 📥 原始响应: {content}")
                
                result = self._extract_json(content)
                if result:
                    logger.debug(f"[AI-Fallback] ✅ 真实标题: {result.get('real_title')}")
                    logger.debug(f"[AI-Fallback] 📝 原名: {result.get('original_name')}")
                    logger.debug(f"[AI-Fallback] 🇨🇳 中文名: {result.get('chinese_name')}")
                    logger.debug(f"[AI-Fallback] 🔢 置信度: {result.get('confidence', 0)}")
                else:
                    logger.error(f"[AI-Fallback] ❌ JSON 解析失败")
                return result

        except httpx.TimeoutException:
            elapsed = time.time() - start_time
            logger.error(f"[AI-Fallback] ⏱️ 请求超时 ({elapsed:.1f}s)，模型响应过慢")
            return None
        except httpx.ConnectError as e:
            logger.error(f"[AI-Fallback] 🔌 连接失败: {e}")
            return None
        except Exception as e:
            logger.error(f"[AI-Fallback] ❌ 未知错误: {type(e).__name__}: {e}")
            return None

    def _retry_with_thinking_off(
        self, base_url: str, api_key: str, model: str, target_url: str, messages: list
    ) -> Optional[Dict[str, Any]]:
        """
        额度被思维链吃光后的兜底：探测该 (base_url, model) 支持哪种「关闭思考」的参数风格，
        带着它重发一次。探测结果会写入能力缓存，后续调用直接命中，不再重复试。
        找不到可关闭的方式时返回 None（由调用方继续报错）。
        """
        try:
            from assistant import llm_capabilities
        except Exception as e:
            logger.warning(f"[AI-Fallback] 能力层不可用，无法探测思考参数: {e}")
            return None

        probe_result = llm_capabilities.probe(base_url, api_key, model, provider="openai")
        logger.info(f"[AI-Fallback] 🔎 思考能力探测: {probe_result.get('message')}")
        fragment = llm_capabilities.build_thinking_fragment(
            probe_result.get("thinking_style") or "none", "off"
        )
        if not fragment:
            return None

        retry_payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096,
            **fragment,
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    target_url,
                    json=retry_payload,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                )
            if resp.status_code != 200:
                logger.error(f"[AI-Fallback] ❌ 关思考重试失败 [{resp.status_code}]: {resp.text[:300]}")
                return None

            choice = (resp.json().get("choices") or [{}])[0]
            message = choice.get("message") or {}
            content = message.get("content") or ""
            logger.info(
                f"[AI-Fallback] 📥 关思考重试: finish_reason={choice.get('finish_reason')} | "
                f"content={len(content)} 字符 | reasoning={len(message.get('reasoning_content') or '')} 字符"
            )
            if not content.strip():
                return None
            return self._extract_json(content)
        except Exception as e:
            logger.error(f"[AI-Fallback] ❌ 关思考重试异常: {type(e).__name__}: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                json_str = text[start : end + 1]
                try:
                    return json.loads(json_str)
                except:
                    pass
            logger.error(f"[AI-Fallback] 无法提取 JSON: {text[:100]}...")
            return None
