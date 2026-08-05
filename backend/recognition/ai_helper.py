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
            "max_tokens": 256
        }

        logger.debug(f"[AI-Fallback] 📤 请求模型: {model}")
        logger.debug(f"[AI-Fallback] 📤 URL: {target_url}")
        logger.debug(f"[AI-Fallback] 📤 文件名: {filename}")

        try:
            import time
            start_time = time.time()
            
            with httpx.Client(timeout=60.0) as client:
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
                
                content = data['choices'][0]['message']['content']
                
                if not content or not content.strip():
                    logger.error(f"[AI-Fallback] ❌ 模型返回空响应，请检查模型名称是否正确")
                    logger.error(f"[AI-Fallback] 💡 智谱AI常用模型: glm-4, glm-4-flash, glm-4-plus")
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
