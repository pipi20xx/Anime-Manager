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
        return """你是影视剧数据库专家。根据文件名推断TMDB真实标题。

输出JSON格式:
{"real_title":"TMDB真实标题(简洁)","original_name":"日文/英文原名","chinese_name":"中文译名","alternative_titles":["其他可能标题"],"season":null,"episode":null,"confidence":0.9}

字段说明:
- real_title: TMDB上的真实标题，简洁准确
- original_name: 作品原始名称(日文/英文)
- chinese_name: 中文官方译名

分析技巧:
- 文件名中的标题可能是错误/不完整的，需要推断真实标题
- "小鲨鱼去郊游剧场版" → real_title: "Odekake Kozame", original_name: "おでかけ子ザメ"
- 剧场版是电影，不是剧集
- 只输出JSON"""

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

        context = filename
        if current_title:
            context = f"{filename} (标题: {current_title})"
        if current_episode:
            context = f"{context[:-1]}, 集数: {current_episode})" if current_title else f"{filename} (集数: {current_episode})"

        messages = [
            {"role": "system", "content": self._get_fallback_system_prompt()},
            {"role": "user", "content": "[mirufans] 小鲨鱼去郊游剧场版 都市的朋友 [1080p].mkv"},
            {"role": "assistant", "content": '{"real_title":"Odekake Kozame","original_name":"おでかけ子ザメ","chinese_name":"小鲨鱼去郊游","alternative_titles":["Eiga Odekake Kozame"],"season":null,"episode":null,"confidence":0.85}'},
            {"role": "user", "content": "[SubGroup] 葬送的芙莉蓮 - 12 [1080p].mkv"},
            {"role": "assistant", "content": '{"real_title":"Frieren: Beyond Journey\'s End","original_name":"Sousou no Frieren","chinese_name":"葬送的芙莉莲","alternative_titles":["Frieren"],"season":1,"episode":12,"confidence":0.95}'},
            {"role": "user", "content": context}
        ]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 256
        }

        logger.info(f"[AI-Fallback] 📤 请求模型: {model}")
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
                logger.info(f"[AI-Fallback] ⏱️ 响应时间: {elapsed:.2f}s, 状态码: {resp.status_code}")
                
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
                
                logger.info(f"[AI-Fallback] 📥 原始响应: {content}")
                
                result = self._extract_json(content)
                if result:
                    logger.info(f"[AI-Fallback] ✅ 真实标题: {result.get('real_title')}")
                    logger.info(f"[AI-Fallback] 📝 原名: {result.get('original_name')}")
                    logger.info(f"[AI-Fallback] 🇨🇳 中文名: {result.get('chinese_name')}")
                    logger.info(f"[AI-Fallback] � 置信度: {result.get('confidence', 0)}")
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
