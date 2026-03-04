import regex as re
from .ai_helper import AIHelper

class AIIntegration:
    @staticmethod
    def enhance_parsing(info_dict, original_input, processed_title, current_logs):
        """
        Extracts AI-based enhancement logic from local_parser.py
        Refines info_dict with AI predictions if necessary.
        """
        ai_data = None
        raw_title = info_dict.get("anime_title")
        invalid_keywords = ["MOVIE", "OVA", "TV", "BD", "MP4", "MKV", "AVI", "BIG5", "GB", "CHS", "CHT", "JAP", "ENG", "BIG5_MP4", "GB_MP4", "WEB-DL", "PGS"]
        is_garbage = not raw_title or raw_title.upper() in invalid_keywords
        has_ambiguous_ep = bool(info_dict.get("episode_number") and info_dict.get("episode_number_alt"))
        
        # [Fix] 如果集数 >= 50，极有可能是标题里的数字被误判，强制启动 AI 复核
        is_high_episode = False
        raw_ep = info_dict.get("episode_number")
        if raw_ep and str(raw_ep).isdigit() and int(raw_ep) >= 50:
            is_high_episode = True
        
        # [Optimization] 罗马数字季号现已由 Regex 内核原生支持，不再作为 AI 触发条件

        if is_garbage or has_ambiguous_ep or is_high_episode:
            ai = AIHelper()
            if ai.is_available():
                current_logs.append(f"┃")
                trigger_reason = "标题无效"
                if has_ambiguous_ep: trigger_reason = "集数歧义"
                elif is_high_episode: trigger_reason = "集数过大疑误判"
                
                current_logs.append(f"┃ [DEBUG][STEP 3.5]: 启动 AI 语义增强 ({trigger_reason})...")
                current_logs.append(f"┣ [DEBUG] AI Input: {processed_title}")
                ai_data = ai.parse_filename(processed_title)
                if ai_data:
                    # [Fix] AI 结果防蠢校验: 防止 AI 把分辨率 (如 1280x720) 当作集数 (1280)
                    ai_ep = ai_data.get("episode")
                    ai_ep_valid = True
                    if ai_ep:
                        bad_eps = [720, 1080, 1280, 1920, 2160, 3840]
                        # 如果 AI 识别的集数是常见分辨率数字，且原名里包含类似 "1280x" 或 "x1280" 的结构
                        if int(ai_ep) in bad_eps:
                            if re.search(rf"{ai_ep}[xX]|[xX]{ai_ep}", original_input):
                                current_logs.append(f"┣ [AI-Check] 驳回 AI 集数 E{ai_ep}: 疑似分辨率数字误判")
                                ai_ep_valid = False
                                ai_data["episode"] = None # 清空以防后续误用
                    
                    current_logs.append(f"┣ [AI] 识别成功: {ai_data.get('title')} S{ai_data.get('season')} E{ai_data.get('episode')} (Specs: {ai_data.get('resolution')}/{ai_data.get('video_encode')})")
                    # 注入 AI 结果到内核字典，辅助后续流程
                    if ai_data.get("title"): info_dict["anime_title"] = ai_data["title"]
                    if ai_data.get("original_title"): info_dict["temp_original_title"] = ai_data["original_title"]
                    
                    # [Fix] 季数安全阀：防止 S1071 这种离谱数据
                    ai_season = ai_data.get("season")
                    if ai_season:
                        try:
                            if int(ai_season) > 100:
                                # 季数过大，视为异常。如果集数为空，尝试将其作为集数
                                if not ai_data.get("episode") and ai_ep_valid: # 只有当 AI 集数也被判定无效或为空时才替补
                                    info_dict["episode_number"] = str(ai_season)
                                current_logs.append(f"┣ [AI] 修正: 忽略异常季数 S{ai_season}")
                            else:
                                info_dict["anime_season"] = str(ai_season)
                        except: pass

                    if ai_data.get("episode") and ai_ep_valid: info_dict["episode_number"] = str(ai_data["episode"])
                    if ai_data.get("group"): info_dict["release_group"] = ai_data["group"]
                    
                    # 注入技术规格 (Specs)
                    if ai_data.get("resolution"): info_dict["video_resolution"] = ai_data["resolution"]
                    if ai_data.get("video_encode"): info_dict["video_term"] = ai_data["video_encode"]
                    if ai_data.get("audio_encode"): info_dict["audio_term"] = ai_data["audio_encode"]
                    if ai_data.get("source"): info_dict["source"] = ai_data["source"]
                else:
                    current_logs.append(f"┣ [AI] 解析未返回有效数据")
            else:
                # 如果 AI 模型不存在，不报错，保持静默
                pass
