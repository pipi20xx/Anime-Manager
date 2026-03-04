import regex as re
from typing import List, Optional, Any
from .constants import MediaType, PLATFORM_RE
from .data_models import MetaBase
from .tag_extractor import TagExtractor
from .title_cleaner import TitleCleaner

def to_str(val: Any) -> Optional[str]:
    if not val: return None
    return " ".join([str(i) for i in val]) if isinstance(val, list) else str(val)

class PostProcessor:
    @staticmethod
    def process(meta_obj: MetaBase, info_dict: dict, input_name: str, processed_title: str, current_logs: List[str], custom_groups: List[str], logger_stub: Any, batch_enhancement: bool = False, fingerprint_data: dict = None):
        """
        Handles Steps 4 to 7 of the recognition process:
        - Conflict Resolution
        - Title Cleaning
        - Specs Extraction
        - Final Type Determination
        """
        if info_dict is None: info_dict = {}
        # --- STEP 4: 属性冲突校验 ---
        current_logs.append(f"┃")
        v_logs = []
        meta_obj.is_batch = False
        meta_obj.end_episode = None

        # [Note] 特权提取已在 STEP 1.5 完成，此处不再重复调用

        if not meta_obj.begin_episode:
            raw_ep = info_dict.get("episode_number")
            if isinstance(raw_ep, list): 
                # Anitopy 识别到了多个数字，执行安全检查
                if len(raw_ep) >= 2:
                    try:
                        s, e = int(raw_ep[0]), int(raw_ep[-1])
                        # 安全阀：结束集数必须大于开始集数，且跨度在合理范围内 (1-300)，且开始集数不能太大
                        if s < e and (e - s) < 300 and s < 500:
                            # 进一步检查：文件名中是否包含合集关键字，或者确实是区间格式
                            batch_keywords = ["合集", "全集", "Batch", "Collection", "Fin", "合訂"]
                            is_explicit_batch = any(k in input_name for k in batch_keywords)
                            if is_explicit_batch or "-" in str(raw_ep):
                                meta_obj.begin_episode = s
                                meta_obj.end_episode = e
                                meta_obj.is_batch = True
                                v_logs.append(f"命中合集校验: E{s}-E{e}")
                    except: pass
                if not meta_obj.is_batch:
                    raw_ep = raw_ep[0]

            if not meta_obj.begin_episode:
                val, debug4 = TagExtractor.validate_episode(raw_ep, processed_title)
                meta_obj.begin_episode = val
                v_logs.extend(debug4)

        # [NEW] 回捞机制：如果 Anitopy 误将集数识别为 release_group (例如 晚街与灯 的 [05_副标题])
        if not meta_obj.begin_episode and info_dict.get("release_group"):
            rg = info_dict.get("release_group")
            # 探测模式: 05_大海啸, 05, 05-v2
            ep_match = re.match(r"^(\d+)(?:[_\-\s]|$)", str(rg))
            if ep_match:
                rescued_ep = int(ep_match.group(1))
                meta_obj.begin_episode = rescued_ep
                v_logs.append(f"┣ [纠偏] 从误判组名 '{rg}' 中回捞集数: E{rescued_ep}")

        if not meta_obj.begin_episode:
            val, debug4_fallback = TagExtractor.extract_episode(processed_title, processed_title)
            meta_obj.begin_episode = val
            v_logs.extend(debug4_fallback)

        if not meta_obj.begin_season and info_dict.get("anime_season"):
            meta_obj.begin_season = int(info_dict.get("anime_season")[0] if isinstance(info_dict.get("anime_season"), list) else info_dict.get("anime_season"))
            v_logs.append(f"同步内核发现的季号: S{meta_obj.begin_season}")
        
        # Call logger_stub only if it has the method
        if hasattr(logger_stub, "debug_out"):
            logger_stub.debug_out("STEP 4: 属性对撞与同步", v_logs)
        else:
            current_logs.extend(v_logs)

        # [New] Step 4.5: 合集增强模式 (Config Controlled)
        # [Note] 只有在特权提取未命中时才执行合集增强
        if batch_enhancement and not meta_obj.begin_episode:
             from .batch_helper import BatchHelper
             s, e, b_logs = BatchHelper.analyze_filename(input_name)
             if s is not None and e is not None:
                 meta_obj.is_batch = True
                 meta_obj.begin_episode = s
                 meta_obj.end_episode = e
                 current_logs.extend(b_logs)
                 current_logs.append(f"┣ [BatchHelper] 增强模式覆盖生效: E{s}-E{e}")
                 # Override Type to TV if it was MOVIE
                 if meta_obj.type == MediaType.MOVIE:
                     meta_obj.type = MediaType.TV
                     if not meta_obj.begin_season: meta_obj.begin_season = 1

        # --- STEP 5: 标题剥离提纯 ---
        current_logs.append(f"┃")
        
        if fingerprint_data:
            meta_obj.cn_name = fingerprint_data.get("title")
            meta_obj.en_name = fingerprint_data.get("original_name") or fingerprint_data.get("original_title")
            current_logs.append(f"┃ [DEBUG][STEP 5]: 记忆命中，跳过标题拆分")
            current_logs.append(f"┣ [Fingerprint] 锁定标题: {meta_obj.cn_name}")
        else:
            raw_name = info_dict.get("anime_title") or processed_title.split('.')[0]
            
            clean_check = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5]", "", raw_name)
            is_invalid_title = len(clean_check) < 2
            
            if meta_obj.resource_team and meta_obj.resource_team in raw_name:
                current_logs.append(f"┣ [清洗] 从标题中剔除已识别制作组: {meta_obj.resource_team}")
                raw_name = raw_name.replace(meta_obj.resource_team, " ")
            
            if custom_groups:
                import zhconv
                # 排序：长词优先匹配
                sorted_groups = sorted([g for g in custom_groups if g and len(g.strip()) >= 2], key=len, reverse=True)
                for g in sorted_groups:
                    # [Fix] 剥离元数据前缀标签
                    g_clean = re.sub(r"^\[(?:REMOTE|私有|社区|内置)\]", "", g).strip()
                    if not g_clean: continue

                    g_simp = zhconv.convert(g_clean, "zh-hans")
                    g_trad = zhconv.convert(g_clean, "zh-hant")
                    
                    # 构造匹配模式：1. 原始匹配 2. 简体匹配 3. 繁体匹配
                    # [Upgrade] 提纯阶段同样使用增强型边界判定，防止误杀剧名的一部分
                    boundary_chars = r"a-zA-Z0-9\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff"
                    patterns = [re.escape(g_clean), re.escape(g_simp), re.escape(g_trad)]
                    matched = False
                    
                    for p in set(patterns):
                        # [Upgrade] 提纯阶段使用智能扩张逻辑
                        pattern = rf"(?i)(?<![{boundary_chars}])([&x\+\s\-_/]*{p}[&x\+\s\-_/]*)(?![{boundary_chars}])"
                        match = re.search(pattern, raw_name)
                        if match:
                            full_match = match.group(0)
                            current_logs.append(f"┣ [清洗] 从剧名中强制剔除制作组及其关联块: {full_match.strip()}")
                            raw_name = raw_name.replace(full_match, " ")
                            matched = True
                            # 继续循环，可能剧名里还粘着其他组名（虽然少见）
                    
                # 再次清理空格
                raw_name = re.sub(r"\s+", " ", raw_name).strip()

            # [Fix] 扩充无效标题黑名单
            invalid_keywords = ["MOVIE", "OVA", "ONA", "TV", "BD", "DVD", "SP", "SPECIAL", "SPECIALS", "OAD", "MP4", "MKV", "BIG5", "GB", "CHS", "CHT", "JAP", "ENG"]
            is_tech_garbage = raw_name.upper() in invalid_keywords or re.match(r"^\d{3,4}[pPXx]?$", raw_name)
            
            # [NEW] 额外检测：如果标题包含 "3rd", "2nd" 这种可能的集数别名，也视为可疑标题
            is_suspicious = re.match(r"^\d+(st|nd|rd|th)$", raw_name, re.I)
            
            # [Strategy] 判定内核识别的组名是否可信
            is_group_credible = False
            detected_group = info_dict.get("release_group")
            if detected_group:
                from .constants import GROUP_KEYWORDS
                # 检查是否命中自定义库
                if custom_groups:
                    for g in custom_groups:
                        g_cl = re.sub(r"^\[(?:REMOTE|私有|社区|内置)\]", "", g).strip()
                        if g_cl and g_cl.lower() in str(detected_group).lower():
                            is_group_credible = True; break
                # 检查是否包含组名特征词
                if not is_group_credible and re.search(GROUP_KEYWORDS, str(detected_group)):
                    is_group_credible = True

            if is_invalid_title or is_tech_garbage or is_suspicious:
                current_logs.append(f"┣ [警告] 内核提取标题 '{raw_name}' 判定为不可信，启动深度回捞")
                brackets = re.findall(r'[\[【](.+?)[\]】]', processed_title)
                potential_titles = []
                
                for b in brackets:
                    b_strip = b.strip()
                    if len(b_strip) < 2: continue 
                    
                    # 1. 排除明显的技术词和类型词
                    if re.search(r"\d{3,4}p|H26|AVC|AAC|CHS|CHT|MP4|MKV|新番|BD|DVD", b_strip, re.I): continue
                    if b_strip.upper() in ["OVA", "ONA", "SP", "SPECIAL", "MOVIE"]: continue
                    if b_strip.isdigit(): continue

                    # [Fix] 排除集数范围模式
                    if re.match(r"^(?:第|Vol\.?)?\s*\d+(?:[-\s~]+\d+)?(?:话|集|話)?$", b_strip, re.I):
                        continue
                    
                    # 2. 除非组名高度可信，否则不排除它作为标题的可能性
                    if is_group_credible and detected_group and b_strip == detected_group: continue
                    
                    # 3. 排除自定义组名库中的组名
                    is_custom_group = False
                    if custom_groups:
                        for g in custom_groups:
                            g_cl = re.sub(r"^\[(?:REMOTE|私有|社区|内置)\]", "", g).strip()
                            if g_cl and g_cl.lower() in b_strip.lower():
                                is_custom_group = True; break
                    if is_custom_group: continue
                    
                    # 4. 检查是否包含中文 (剧名特征优先)
                    if re.search(r"[\u4e00-\u9fa5]", b_strip):
                        potential_titles.insert(0, b_strip)
                    else:
                        potential_titles.append(b_strip)
                
                if potential_titles:
                    raw_name = potential_titles[0]
                    current_logs.append(f"┣ [修正] 成功回捞到标题: {raw_name}")
            
            # [Fix] 获取 Release Version 并传入清洗器
            rel_ver = info_dict.get("release_version")
            residual_title, debug5_clean = TitleCleaner.residual_clean(raw_name, meta_obj.year, meta_obj.begin_episode, version=rel_ver)
            cn_simp, cn_orig, en, debug5_dual = TitleCleaner.extract_dual_title(residual_title, split_mode=batch_enhancement)
            meta_obj.cn_name, meta_obj.original_cn_name, meta_obj.en_name = cn_simp, cn_orig, en
            
            # [AI] 如果正则没分出英文名，尝试使用 AI 提取的原名
            if not meta_obj.en_name and info_dict.get("temp_original_title"):
                meta_obj.en_name = info_dict.get("temp_original_title")
                debug5_dual.append(f"[AI] 补充原名: {meta_obj.en_name}")

            if not meta_obj.cn_name and not meta_obj.en_name: 
                meta_obj.en_name = residual_title
                debug5_dual.append(f"[Fix] 保持原始残差标题: {residual_title}")

            if hasattr(logger_stub, "debug_out"):
                logger_stub.debug_out("STEP 5: 标题残差剥离与拆分", debug5_clean + debug5_dual)
            else:
                current_logs.extend(debug5_clean + debug5_dual)

        # --- STEP 6: 规格属性全量同步 ---
        current_logs.append(f"┃")
        debug6 = []
        
        # [Strategy] 优先策略：如果预处理 (Step 2.5) 已经锁定了制作组（特别是联合发布情况），则直接继承
        matched_from_lib = False
        if meta_obj.resource_team:
            debug6.append(f"┣ [制作组] 继承自预处理 (包含联合发布检测): {meta_obj.resource_team}")
            matched_from_lib = True
        
        from .constants import NOT_GROUPS
        if not matched_from_lib and custom_groups:
            import zhconv
            # 排序：长词优先匹配，防止短词拦截长词
            sorted_groups = sorted([g for g in custom_groups if g and len(g.strip()) >= 2], key=len, reverse=True)
            for g in sorted_groups:
                # [Fix] 剥离元数据前缀标签
                g_clean = re.sub(r"^\[(?:REMOTE|私有|社区|内置)\]", "", g).strip()
                if not g_clean: continue

                g_simp = zhconv.convert(g_clean, "zh-hans")
                g_trad = zhconv.convert(g_clean, "zh-hant")
                
                if re.search(PLATFORM_RE, g_clean): continue
                
                # [Upgrade] 严格边界匹配逻辑：
                # 同时支持原始、简体、繁体三个版本的匹配，并应用 CJK 边界保护
                p_esc, s_esc, t_esc = re.escape(g_clean), re.escape(g_simp), re.escape(g_trad)
                boundary_chars = r"a-zA-Z0-9\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff"
                group_pattern = rf"(?i)(?<![{boundary_chars}])({p_esc}|{s_esc}|{t_esc})(?![{boundary_chars}])"
                
                # [Fix] 同时匹配原始名和预处理名
                if re.search(group_pattern, input_name) or re.search(group_pattern, processed_title):
                    # [Check] 即使匹配到自定义库，也要核验是否属于非法技术词
                    if re.search(f"(?i)^({NOT_GROUPS})$", g_clean):
                        debug6.append(f"┣ [制作组校验] 自定义库命中非法词({g_clean})，已忽略并继续搜索")
                        continue
                    
                    meta_obj.resource_team = g_clean
                    debug6.append(f"┣ [制作组] 优先匹配自定义库: {g_clean}")
                    matched_from_lib = True
                    break

        if not matched_from_lib:
            # 只有前面都没匹配到，才尝试普通的标签提取
            team, d6 = TagExtractor.extract_release_group(input_name, info_dict.get("release_group"))
            meta_obj.resource_team = team
            if d6: debug6.extend(d6)
        
        # [Sync] 来源同步
        if meta_obj.resource_type:
            debug6.append(f"┣ [介质] 继承自预处理: {meta_obj.resource_type}")
        else:
            source_val, d6_s = TagExtractor.extract_source(input_name)
            if source_val:
                meta_obj.resource_type = source_val
                debug6.extend(d6_s)
            else:
                meta_obj.resource_type = to_str(info_dict.get("source"))
                if meta_obj.resource_type: debug6.append(f"┣ [介质] 同步自内核: {meta_obj.resource_type}")

        # [Sync] 分辨率同步
        if meta_obj.resource_pix:
            debug6.append(f"┣ [分辨率] 继承自预处理: {meta_obj.resource_pix}")
        else:
            res_val, d6_r = TagExtractor.extract_resolution(input_name)
            if res_val:
                meta_obj.resource_pix = res_val
                debug6.extend(d6_r)
            else:
                meta_obj.resource_pix = to_str(info_dict.get("video_resolution"))
                if meta_obj.resource_pix: debug6.append(f"┣ [分辨率] 同步自内核: {meta_obj.resource_pix}")
        
        # [Sync] 视频编码同步
        if meta_obj.video_encode:
            debug6.append(f"┣ [视频] 继承自预处理: {meta_obj.video_encode}")
        else:
            v_code, d6_v = TagExtractor.extract_video_encode(input_name)
            if v_code:
                meta_obj.video_encode = v_code
                debug6.extend(d6_v)
            else:
                meta_obj.video_encode = to_str(info_dict.get("video_term") or info_dict.get("video_codec"))
                if meta_obj.video_encode: debug6.append(f"┣ [视频] 同步自内核: {meta_obj.video_encode}")

        # [Sync] 音频编码同步
        if meta_obj.audio_encode:
            debug6.append(f"┣ [音频] 继承自预处理: {meta_obj.audio_encode}")
        else:
            a_code, d6_a = TagExtractor.extract_audio_encode(input_name)
            if a_code:
                meta_obj.audio_encode = a_code
                debug6.extend(d6_a)
            else:
                meta_obj.audio_encode = to_str(info_dict.get("audio_term") or info_dict.get("audio_codec"))
                if meta_obj.audio_encode: debug6.append(f"┣ [音频] 同步自内核: {meta_obj.audio_encode}")
        
        # [Sync] 动态范围与字幕
        if meta_obj.video_effect:
            debug6.append(f"┣ [特效] 继承自预处理: {meta_obj.video_effect}")
        else:
            meta_obj.video_effect, d6_e = TagExtractor.extract_dynamic_range(input_name)
            if d6_e: debug6.extend(d6_e)
        
        if meta_obj.subtitle_lang:
            debug6.append(f"┣ [字幕] 继承自预处理: {meta_obj.subtitle_lang}")
        else:
            meta_obj.subtitle_lang, d6_sub = TagExtractor.extract_subtitle_lang(input_name)
            if d6_sub: debug6.extend(d6_sub)
        
        # [Final Check] 制作组黑名单强制核验 (最终关卡：防止 Remux 等技术词从任何渠道溜进组名)
        from .constants import NOT_GROUPS
        if meta_obj.resource_team:
            if re.search(f"(?i)^({NOT_GROUPS})$", meta_obj.resource_team.strip()):
                debug6.append(f"┣ [Team-Check] 最终拦截：发现组名非法({meta_obj.resource_team})，执行静默清除")
                meta_obj.resource_team = None

        if hasattr(logger_stub, "debug_out"):
            logger_stub.debug_out("STEP 6: 规格属性全量同步", debug6)
        else:
            current_logs.extend(debug6)

        # --- STEP 7: 最终判定 ---
        current_logs.append(f"┃")
        current_logs.append(f"┃ [DEBUG][STEP 7]: 类型判定")
        
        if meta_obj.forced_tmdbid: 
            current_logs.append(f"┣ [类型判定] 已锁定 TMDB ID，跳过自动类型判断")
        else:
            # [Enhancement] 检查原始文件名是否包含电影关键词
            movie_keywords = [
                r"(?i)\bMovie\b",
                r"(?i)\b剧场版\b",
                r"(?i)\b劇場版\b",
                r"(?i)\bThe Movie\b",
                r"(?i)\bMovie Edition\b",
                r"(?i)\b劇場\b",
            ]
            
            movie_keyword_found = None
            for keyword in movie_keywords:
                if re.search(keyword, input_name):
                    movie_keyword_found = keyword
                    break
            
            if movie_keyword_found:
                current_logs.append(f"┣ [类型判定] 原始文件名包含电影关键词 '{movie_keyword_found}'，强制判定为 Movie 模式")
                meta_obj.type = MediaType.MOVIE
                # 清除可能误判的集数
                if meta_obj.begin_episode:
                    current_logs.append(f"┣ [类型判定] 清除误判的集数 E{meta_obj.begin_episode}")
                    meta_obj.begin_episode = None
            # [Fix] 如果集数是一个年份 (如 2019)，则判定为 Movie，并清空集数
            elif meta_obj.begin_episode and isinstance(meta_obj.begin_episode, (int, float)) and meta_obj.begin_episode > 1900:
                current_logs.append(f"┣ [类型判定] 集数 E{meta_obj.begin_episode} 判定为年份，修正为 Movie 模式")
                meta_obj.begin_episode = None
                meta_obj.type = MediaType.MOVIE
            elif meta_obj.begin_season is not None or meta_obj.begin_episode is not None:
                current_logs.append(f"┣ [类型判定] 检测到季号/集数 (S{meta_obj.begin_season}/E{meta_obj.begin_episode})，判定为 TV 类型")
                meta_obj.type = MediaType.TV
                if meta_obj.begin_season is None: meta_obj.begin_season = 1
            else: 
                current_logs.append(f"┣ [类型判定] 未检测到季号/集数，判定为 Movie 类型")
                meta_obj.type = MediaType.MOVIE
            
            # [Fix] 如果提取到了季号，不管有没有集数，都视为 TV
            if meta_obj.begin_season:
                current_logs.append(f"┣ [类型判定] 确认季号存在，最终类型: TV")
                meta_obj.type = MediaType.TV
            else:
                current_logs.append(f"┣ [类型判定] 最终类型: {meta_obj.type.value.upper()}")