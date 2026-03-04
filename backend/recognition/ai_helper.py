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
        # AIHelper is stateless regarding config now
        pass

    @property
    def ai_config(self) -> Dict[str, Any]:
        return ConfigManager.get_config().get("ai_config", {})

    def is_available(self) -> bool:
        # Check if OpenAI compatible API is configured
        url = self.ai_config.get("openai_base_url", "")
        return bool(url and url.startswith("http"))

    def parse_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None

        return self._parse_openai(filename)

    def _get_system_prompt(self) -> str:
        return """你是一个专业的影视剧文件名解析专家。请将输入的文件名解析为 JSON 格式。
要求：
1. 只输出纯 JSON，不要解释。
2. 字段：title (中文名/主标题), original_title (原名/英文名), season (整数, 默认1), episode (整数), group (字幕组/发布组), resolution (如 1080P), video_encode (如 HEVC, AVC), audio_encode (如 AAC, FLAC), source (如 WebRip, BD)。
3. 如果无法确定的字段设为 null。
4. 注意：文件名中孤立的数字（如 " - 12" 或 "[12]"）通常表示集数。
5. 规则：罗马数字 III, IV 等通常表示季号 (Season 3, 4)。
6. 规则：以 "p" 结尾的数字 (如 720p, 1080p) 是分辨率。
7. 规则：[x265_flac] 表示 视频编码=x265, 音频编码=flac。
8. 规则：[Ma10p_1080p] 表示 10bit色深, 分辨率=1080p。
9. 必须在一行或多行内输出合法的 JSON。"""

    def _get_few_shot_messages(self) -> list:
        return [
            {"role": "user", "content": "[VCB-Studio] Mob Psycho 100 III [05][Ma10p_1080p][x265_flac].mkv"},
            {"role": "assistant", "content": '{"title": "路人超能100", "original_title": "Mob Psycho 100", "season": 3, "episode": 5, "group": "VCB-Studio", "resolution": "1080P", "video_encode": "HEVC", "audio_encode": "FLAC", "source": "BD"}'},
            {"role": "user", "content": "[DMG&LoliHouse] FAIRY TAIL - 100 YEARS QUEST - 24 [WebRip 1080p HEVC-10bit AAC ASSx2].mkv"},
            {"role": "assistant", "content": '{"title": "妖精的尾巴 百年任务", "original_title": "FAIRY TAIL - 100 YEARS QUEST", "season": 1, "episode": 24, "group": "DMG&LoliHouse", "resolution": "1080P", "video_encode": "HEVC", "audio_encode": "AAC", "source": "WebRip"}'},
            {"role": "user", "content": "[Ohys-Raws] One Piece - 1000 (TX 1280x720 x264 AAC).mp4"},
            {"role": "assistant", "content": '{"title": "海贼王", "original_title": "One Piece", "season": 1, "episode": 1000, "group": "Ohys-Raws", "resolution": "720P", "video_encode": "H.264", "audio_encode": "AAC", "source": "HDTV"}'},
            {"role": "user", "content": "[ANi] 藍色管弦樂 第二季 - 12 [1080P][Baha][WEB-DL].mp4"},
            {"role": "assistant", "content": '{"title": "藍色管弦樂", "original_title": "Blue Orchestra", "season": 2, "episode": 12, "group": "ANi", "resolution": "1080P", "video_encode": null, "audio_encode": null, "source": "WEB-DL"}'}
        ]

    def _parse_openai(self, filename: str) -> Optional[Dict[str, Any]]:
        base_url = self.ai_config.get("openai_base_url")
        api_key = self.ai_config.get("openai_api_key", "sk-xxx")
        model = self.ai_config.get("openai_model", "qwen2.5:1.5b")

        # 构造 endpoint
        # 标准 OpenAI 客户端通常只需 base_url=".../v1"，然后自动接 /chat/completions
        target_url = f"{base_url.rstrip('/')}/chat/completions"
        if "v1" not in base_url and "chat/completions" not in base_url:
             target_url = f"{base_url.rstrip('/')}/v1/chat/completions"
        elif base_url.endswith("/chat/completions"):
             target_url = base_url

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
        ]
        messages.extend(self._get_few_shot_messages())
        messages.append({"role": "user", "content": filename})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 512,
            "response_format": {"type": "json_object"} 
        }

        try:
            logger.debug(f"[AI] Requesting {target_url} model={model}")
            # 使用同步客户端，设置较短超时防止阻塞过久
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(
                    target_url, 
                    json=payload, 
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                )
                resp.raise_for_status()
                data = resp.json()
                
                content = data['choices'][0]['message']['content']
                logger.debug(f"[AI] API Response: {content}")
                
                return self._extract_json(content)

        except Exception as e:
            logger.error(f"[AI] OpenAI API 调用失败: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            # 尝试直接解析
            return json.loads(text)
        except:
            # 尝试提取 ```json ... ``` 或 {...}
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                json_str = text[start : end + 1]
                try:
                    return json.loads(json_str)
                except:
                    pass
            logger.error(f"[AI] 无法从结果中提取 JSON: {text}")
            return None
