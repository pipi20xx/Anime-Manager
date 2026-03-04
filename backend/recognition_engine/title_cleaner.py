import regex as re
import zhconv
from typing import Optional, List, Tuple, Dict, Any
from .constants import NOISE_WORDS, SEASON_PATTERNS, PIX_RE, VIDEO_RE, AUDIO_RE, SOURCE_RE, EFFECT_RE, PLATFORM_RE, DYNAMIC_RANGE_RE

class TitleCleaner:
    @staticmethod
    def _calc_episode(base_val: str, formula: str) -> str:
        """
        处理集数计算公式，支持 @*2+1, EP+1, +1 等多种风格
        """
        try:
            if not base_val.isdigit(): return base_val
            val_int = int(base_val)
            
            # 清理公式前缀
            clean_formula = formula[1:] if formula.startswith("@") else formula
            f_upper = clean_formula.upper().strip()
            
            # 统一转换为 eval 可执行的字符串
            if "EP" in f_upper:
                eval_str = f_upper.replace("EP", str(val_int))
            elif f_upper.startswith(("*", "/", "+", "-")):
                # 如果以运算符开头，补上原始值，例如 "*2" -> "1*2"
                eval_str = str(val_int) + f_upper
            else:
                # 纯数字赋值，例如 "5"
                eval_str = f_upper
                
            # 安全检查并计算
            if re.match(r'^[\d\+\-\*\/\.\(\)\s]+$', eval_str):
                return str(int(eval(eval_str)))
            return str(val_int)
        except:
            return base_val

    @staticmethod
    def pre_clean(filename: str, custom_words: List[str] = [], force_filename: bool = False) -> Tuple[str, Dict[str, str], List[str]]:
        """
        进入内核前的预处理：执行自定义规则、强制元数据提取、基础噪音消除。
        """
        import os
        debug_logs = []
        debug_logs.append(f"原始文件名: {filename}")
        temp = filename
        
        # [NEW] 单文件模式增强：将路径分隔符替换为下划线，防止干扰分词
        if force_filename:
            if "/" in temp or "\\" in temp:
                temp = temp.replace("/", "_").replace("\\", "_")
                debug_logs.append(f"[PreClean] 探测到单文件模式，已对路径分隔符进行脱敏替换")
        
        pure_filename = os.path.basename(filename)
        forced_meta = {}

        if custom_words:
            for rule_line in custom_words:
                if not rule_line or rule_line.startswith("#"): continue
                
                # 判定规则来源
                is_remote = rule_line.startswith("[REMOTE]")
                source_tag = "[社区]" if is_remote else "[私有]"
                actual_line = rule_line[8:] if is_remote else rule_line
                
                # [New] 支持组合规则 (&&)
                sub_rules = actual_line.split("&&")
                
                for word in sub_rules:
                    word = word.strip()
                    if not word: continue
                    
                    import logging
                    # 使用 root logger 确保无视级别设置强制输出
                    # logging.info(f"  [Regex Check] {word[:50]}...") 
                    
                    try:
                        # 1. 集数偏移定位器
                        if "<>" in word and ">>" in word:
                            locator_part, formula = word.split(">>", 1)
                            start_tag, end_tag = locator_part.split("<>", 1)
                            start_tag, end_tag, formula = start_tag.strip(), end_tag.strip(), formula.strip()
                            pat = f"({re.escape(start_tag)})\s*(\d+)\s*({re.escape(end_tag)})"
                            match = re.search(pat, temp, flags=re.I)
                            if match:
                                original_num = match.group(2)
                                new_num = TitleCleaner._calc_episode(original_num, formula)
                                new_str = f"{match.group(1)}{new_num}{match.group(3)}"
                                temp = temp.replace(match.group(0), new_str)
                                debug_logs.append(f"[规则]{source_tag} 集数偏移: {original_num} -> {new_num}")
                            continue

                        # 2. 替换规则: A => B
                        if " => " in word:
                            pattern, target = word.split(" => ", 1)
                            pattern, target = pattern.strip(), target.strip()
                            
                            # [NEW] 路径鲁棒性增强
                            target_is_matched = bool(re.search(pattern, temp, flags=re.I))
                            if not target_is_matched and pure_filename:
                                if re.search(pattern, pure_filename, flags=re.I):
                                    target_is_matched = True
                                    debug_logs.append(f"[规则]{source_tag} 通过文件名锚定匹配到规则: {pattern}")

                            if target_is_matched:
                                # 2.1 强制元数据提取: {[...]}
                                if target.startswith("{["):
                                    # ... (保持原样)
                                    match = re.search(pattern, temp, flags=re.I) or re.search(pattern, pure_filename, flags=re.I)
                                    if match:
                                        debug_logs.append(f"[规则]{source_tag} 命中提取规则: {word}")
                                        inner = target[2:-2]
                                        for item in inner.split(";"):
                                            if "=" in item:
                                                k, v = item.split("=", 1)
                                                k, v = k.strip().lower(), v.strip()
                                                # 处理公式逻辑: 支持 {[e=\1@+12]} 风格
                                                if k == "e" and "\\" in v and "@" in v:
                                                    grp_ref = re.search(r"\\(\d+)", v)
                                                    if grp_ref:
                                                        grp_idx = int(grp_ref.group(1))
                                                        if grp_idx <= len(match.groups()):
                                                            base_val = match.group(grp_idx)
                                                            formula_part = v.split("@", 1)[1]
                                                            v = TitleCleaner._calc_episode(base_val, "@" + formula_part)
                                                forced_meta[k] = v
                                
                                # 2.2 普通正则替换
                                else:
                                    # [Optimization] 防止重复叠加: 如果目标字符串已经包含了 target，且 pattern 只是 target 的一部分，则跳过
                                    if target in temp and pattern in target:
                                        pass
                                    else:
                                        debug_logs.append(f"[规则]{source_tag} 执行正则替换: {pattern} -> {target}")
                                        temp = re.sub(pattern, target, temp, flags=re.I)
                        
                        # 3. 简单屏蔽词
                        else:
                            if re.search(word.strip(), temp, flags=re.I) or re.search(word.strip(), pure_filename, flags=re.I):
                                debug_logs.append(f"[规则]{source_tag} 应用自定义识别词: {word.strip()}")
                                temp = re.sub(word.strip(), " ", temp, flags=re.I)
                                
                    except Exception as e:
                        debug_logs.append(f"[规则] 规则执行异常: {word} -> {str(e)}")

        temp = re.sub(r"\[\s*\]|\(\s*\)|\{\s*\}", " ", temp)
        
        # [NEW] 扫描并提取嵌入式强制元数据 (例如: {[tmdbid=123;s=1]})
        # 这通常由正则替换生成，例如 \1{[...]}
        embedded_meta_match = re.search(r"\{\[(.*?)\]\}", temp)
        if embedded_meta_match:
            meta_str = embedded_meta_match.group(1)
            debug_logs.append(f"[PreClean] 提取到嵌入式元数据: {meta_str}")
            for item in meta_str.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    forced_meta[k.strip().lower()] = v.strip()
            # 提取完后从文件名中移除
            temp = temp.replace(embedded_meta_match.group(0), "")

        # [NEW] 在预处理阶段提前应用通用干扰词清洗，防止干扰内核
        # 比如 "10月新番" 如果不清洗，会被 Anitopy 误认为是标题
        for nw in NOISE_WORDS:
            if re.search(nw, temp, flags=re.I):
                debug_logs.append(f"[规则][内置] 清除干扰词: {nw}")
                temp = re.sub(nw, " ", temp, flags=re.I)
        
        # [NEW] 强制清洗装饰性符号 (★, ☆, ■, ◆, ●, etc.)
        temp = re.sub(r"[★☆■□◆◇●○•]", " ", temp)
        
        # [NEW] 针对 Anitopy 的冒号和斜杠崩溃 Bug 进行脱敏
        temp = temp.replace(":", " ").replace(" / ", "  ").replace("/", " ")
        
        # [NEW] 防止因正则替换产生的名称叠加 (如 桜都字幕组字幕组)
        # 匹配 "字幕组/組" 连在一起的情况并合并
        temp = re.sub(r"(字幕组|字幕組|字幕社|工作室)\s*(字幕组|字幕組|字幕社|工作室)", r"\1", temp, flags=re.I)
        
        # [NEW] 针对 " - 01 - " 结构的脱敏，防止 Anitopy 递归死锁
        temp = re.sub(r" - (\d+) - ", r" [\1] ", temp)
        
        # [NEW] 针对超长标题中的重复符号进行压缩
        temp = re.sub(r"[ \.\-\_=]{3,}", "  ", temp)
        
        # [NEW] 彻底清除不可见字符 (零宽空格等)
        temp = re.sub(r"[\u200b-\u200f\uFEFF\u202a-\u202e]", "", temp)
        
        # [Fix] 移动空壳括号保险清理到最后：移除被掏空后的空壳 (如 [ ], ( ), 【 】)
        shell_pattern = r"[\[\(\{（【][\s\-\._/&+\*★☆]*[\]\)\}）】]"
        temp = re.sub(shell_pattern, " ", temp)
        for _ in range(2): 
            temp = re.sub(shell_pattern, " ", temp)
                
        final_cleaned = re.sub(r"\s+", " ", temp).strip()
        debug_logs.append(f"清洗后结果: {final_cleaned}")
        return final_cleaned, forced_meta, debug_logs

    @staticmethod
    def residual_clean(raw_title: str, year: str = None, episode: int = None, version: int = None) -> Tuple[str, List[str]]:
        """[DEBUG] 执行残差剥离提纯"""
        temp = raw_title
        debug_logs = []
        
        patterns = [
            (PIX_RE, "分辨率"), (VIDEO_RE, "视频编码"), (AUDIO_RE, "音频编码"),
            (SOURCE_RE, "介质来源"), (EFFECT_RE, "特效标签"),
            (PLATFORM_RE, "流媒体平台"), (DYNAMIC_RANGE_RE, "动态范围")
        ]
        
        for pat, name in patterns:
            # 记录所有命中的属性
            matches = re.findall(pat, temp, flags=re.I)
            if matches:
                for m in matches:
                    val = m if isinstance(m, str) else "".join(m)
                    debug_logs.append(f"[规则][内置] 识别并剥离 {name}: {val}")
                temp = re.sub(pat, " ", temp, flags=re.I)
        
        for nw in NOISE_WORDS:
            if re.search(nw, temp, flags=re.I):
                match = re.search(nw, temp, flags=re.I)
                debug_logs.append(f"[规则][内置] 移除预设干扰词: {match.group(0)}")
                temp = re.sub(nw, " ", temp, flags=re.I)

        if year and str(year) in temp:
            debug_logs.append(f"[清洗] 剥离标题中残留的年份: {year}")
            temp = temp.replace(str(year), " ")
            
        # [New] 版本号清洗增强
        if version is not None:
            # 剥离 V2/V3 等版本号 (支持带空格/连字符的情况)
            ver_pat = rf"(?i)(?:\b|[-_. ])[vV]{version}(?:\b|[-_. ])|(?i)\bver{version}\b"
            if re.search(ver_pat, temp):
                debug_logs.append(f"[清洗] 剥离标题中残留的版本号: V{version}")
                temp = re.sub(ver_pat, " ", temp)

        # [New] 针对你反馈的 "ray MV" 这种常见残骸进行剥离
        # 通常出现在标题末尾，包含技术特征
        extra_garbage = r"(?i)\s+(?:ray\s+MV|MV|Web|DL|TV|BD|DVD|Special)\b$"
        if re.search(extra_garbage, temp.strip()):
            match = re.search(extra_garbage, temp.strip())
            debug_logs.append(f"[清洗] 剥离标题末尾技术残骸: {match.group(0)}")
            temp = re.sub(extra_garbage, " ", temp.strip())

        if episode is not None:
            # 增强型集数剥离：支持 E/EP/Episode 等前缀
            ep_pat = rf"(?i)(?:EP|Episode|E|#|第|集|话|話|巻|卷)\s*0*{episode}\b|\b0*{episode}\b"
            if re.search(ep_pat, temp):
                debug_logs.append(f"[清洗] 剥离标题中残留的集数标志: {episode}")
                temp = re.sub(ep_pat, " ", temp)

        # [修正] 通用集数模式剥离 (防止残留如 '第01话' 即使 episode没传进来)
        generic_ep_pat = r"(?i)(?:EP|Episode|E|#|第|Vol\.?)\s*\d{1,4}(?:[-\s~]+\d{1,4})?(?:话|集|話|巻|卷|End|Fin)?"
        # 仅当该模式独立存在（前后有边界）时才剥离，避免误伤 '第9区' 这种标题
        matches = re.finditer(generic_ep_pat, temp)
        for m in matches:
            val = m.group(0).strip()
            # 简单验证：必须包含数字
            if re.search(r"\d", val):
                # 如果是纯数字，且很短(1-2位)，可能是标题的一部分（如 12岁），跳过
                if val.isdigit() and len(val) < 3: continue
                # 如果包含明确的前缀后缀 (第..话)，或者长度适中，视为集数噪音
                debug_logs.append(f"[清洗] 剥离通用集数模式: {val}")
                temp = temp.replace(val, " ")

        # [NEW] 残留字幕/质量标签二次清洗
        # 针对 Step 1 没洗干净的繁体/碎片词 (如: 簡 內封, AVC, AAC)
        # [Optimize] 字幕标签剥离逻辑：增加边界限制，防止切碎制作组名
        residual_tags = [
            r"(?i)\b(?:AVC|HEVC|AAC|AC3|DTS|TRUEHD|OPUS)\b",
            r"\b[简簡繁正中日双雙英多][体文语語]\b",
            r"\b(?:繁体|繁體|简体|简体|简日|繁日|简中|繁中|简繁|双语|双语|内嵌|內嵌|内封|內封|外挂|外掛)\b",
            r"(?i)(?<![\u4e00-\u9fa5])(?:内封|內封|内嵌|內嵌|外挂|外掛|字幕|特效|样式|版本|TC|SC|CHT|CHS)(?![\u4e00-\u9fa5])",
            r"(?i)\b(?:WebRip|WebDL|BluRay|BD|HDTV)\b"
        ]
        for tag in residual_tags:
            if re.search(tag, temp):
                temp = re.sub(tag, " ", temp)
                debug_logs.append(f"[清洗] 剥离残留标签: {tag}")

        for sp in SEASON_PATTERNS:
            match = re.search(sp, temp, flags=re.I)
            if match:
                debug_logs.append(f"[清洗] 剥离标题中残留的季号描述: {match.group(0)}")
                temp = re.sub(sp, " ", temp, flags=re.I)
        
        # [NEW] 剥离标题末尾的制作组/站点残骸 (例如 -ADE, @ADWeb)
        # [Fix] 优化判定逻辑：仅剥离全大写短标签(<=3位)或以@开头的站点标签，防止误伤 '-hime' 等正常标题内容
        tail_garbage_pat = r"(@[a-zA-Z0-9]+|-([A-Z0-9]{1,3}))$"
        if re.search(tail_garbage_pat, temp.strip()):
            match = re.search(tail_garbage_pat, temp.strip())
            debug_logs.append(f"[清洗] 剥离标题末尾站点/组标签: {match.group(0)}")
            temp = re.sub(tail_garbage_pat, " ", temp.strip())
            
        final = re.sub(r"[\[\]\(\)\-\._/]+", " ", temp).strip()
        return re.sub(r"\s+", " ", final), debug_logs

    @staticmethod
    def extract_dual_title(residual_title: str, split_mode: bool = False) -> Tuple[Optional[str], Optional[str], Optional[str], List[str]]:
        """[DEBUG] 执行中英分离"""
        debug_logs = []
        if not residual_title: return None, None, None, debug_logs
        
        # [Fix] 在大量清理符号前，先尝试探测显式的双语分隔符
        # 常见模式: "中文名 / English Title" 或扁平化后的 "中文名 _ English Title"
        # [Optimization] 增加对无空格下划线分隔符的探测 (例如: 中文名_EnglishTitle)
        if " / " in residual_title or " _ " in residual_title:
            sep = " / " if " / " in residual_title else " _ "
            parts = residual_title.split(sep, 1)
            p1, p2 = parts[0].strip(), parts[1].strip()
            if len(p1) >= 2 and len(p2) >= 2:
                cn_orig = p1
                cn_simp = zhconv.convert(p1, "zh-hans")
                debug_logs.append(f"[拆分] 发现显式分隔符 '{sep}', 拆分为: {cn_simp} / {p2}")
                return cn_simp, cn_orig, p2, debug_logs
        elif "_" in residual_title:
            # 探测模式：[CJK]_ [Latin]
            match = re.search(r"([\u4e00-\u9fa5\u3040-\u30ff]+)_([a-zA-Z].+)", residual_title)
            if match:
                p1, p2 = match.group(1).strip(), match.group(2).strip()
                if len(p1) >= 2 and len(p2) >= 2:
                    cn_orig = p1
                    cn_simp = zhconv.convert(p1, "zh-hans")
                    debug_logs.append(f"[拆分] 发现紧凑型下划线分隔符, 拆分为: {cn_simp} / {p2}")
                    return cn_simp, cn_orig, p2, debug_logs

        # [Fix] 扩展符号清理，包含东亚括号 【】
        # [Optimize] 增加对开头残留连接符 (如 &) 的清理
        title = re.sub(r"^[&x\+\s\-_/]+", "", residual_title).strip()
        title = re.sub(r"[\[\]\-\._/【】]+", " ", title).strip()
        debug_logs.append(f"[拆分] 待拆分标题: {title}")
        
        # 兼容旧逻辑：如果还残留 / (虽然上面的 re.sub 已经基本洗掉了，但保留作为兜底)
        if "/" in title:
            parts = title.split("/")
            p1 = parts[0].strip()
            cn_orig = p1
            cn_simp = zhconv.convert(p1, "zh-hans")
            debug_logs.append(f"[拆分] 发现分隔符 '/', 拆分为: {cn_simp} / {parts[1].strip()}")
            return cn_simp, cn_orig, parts[1].strip(), debug_logs

        # [Fix] 扩展 CJK 范围：增加平假名(\u3040-\u309f)和片假名(\u30a0-\u30ff)
        # 同时也保留常见的 CJK 标点符号(\u3000-\u303f)和全角字符(\uff00-\uffef)
        cjk_pattern = r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff0-9\u3000-\u303f\uff00-\uffef×x]{1,}"
        cn_match = re.findall(cjk_pattern, title)
        # [Optimization] 允许英文标题包含更多常见标点 (逗号、冒号、叹号、连接符等)
        en_match = re.findall(r"[a-zA-Z][a-zA-Z0-9\s',:!&?~;]{2,}", title)
        
        # [Fix] 过滤纯数字/纯标点块: 如果已提取到汉字/日文，则丢弃纯数字或纯符号块
        if cn_match:
            has_real_char = any(re.search(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]", c) for c in cn_match)
            if has_real_char:
                # 过滤掉仅由数字、空格或常见标点组成的块
                filtered = [c for c in cn_match if not re.match(r'^[\d\s\u3000-\u303f\uff00-\uffef]+$', c)]
                if filtered:
                    cn_match = filtered
        
        sep = " " if split_mode else ""
        cn_orig = sep.join(cn_match).strip() if cn_match else None
        cn_simp = zhconv.convert(cn_orig, "zh-hans") if cn_orig else None
        
        # [Fix] 再次清理中文名：移除可能残留的开头/结尾标点
        if cn_simp:
            cn_simp = cn_simp.strip(" 、，。！？!?,.：:")
            cn_orig = cn_orig.strip(" 、，。！？!?,.：:")
        
        # [Fix] 如果提取的中文名仅包含数字/符号/xX，或者不含任何汉字/假名，视为无效
        if cn_simp:
            is_invalid_chars = re.match(r'^[\d\s\.\-\+\:\！\!\?\？\：xX]+$', cn_simp)
            has_real_cjk = re.search(r"[\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]", cn_simp)
            
            if is_invalid_chars or not has_real_cjk or len(cn_simp) < 1:
                debug_logs.append(f"[拆分] 丢弃无效/纯符号/无语义中文名: {cn_simp}")
                cn_simp, cn_orig = None, None

        if cn_simp: debug_logs.append(f"[拆分] 提取到中文剧名块: {cn_simp}")
        
        # [Optimization] 允许合并多个英文特征块，提高对复杂标题的覆盖能力
        en_name = " ".join([m.strip() for m in en_match]) if en_match else None
        # [Fix] 英文名校验逻辑：防止将制作组碎屑(SFSub)误认为标题
        if en_name:
            # 1. 过滤掉极短的单词 (如 &)
            if len(en_name) < 2: en_name = None
            # 2. 如果英文名全大写且很短，很有可能是残留的制作组碎屑
            elif (en_name.isupper() and len(en_name) < 6):
                debug_logs.append(f"[拆分] 丢弃疑似制作组残骸的英文名: {en_name}")
                en_name = None
            # 3. 如果英文名末尾还残留了 E01/01 这种模式 (可能由 Anitopy 误吞)，再次强制切除
            else:
                en_name = re.sub(r"(?i)\s+(?:EP|E|S|#)?\d+$", "", en_name).strip()

        if en_name and cn_simp and en_name.lower() in cn_simp.lower(): en_name = None
        if en_name: debug_logs.append(f"[拆分] 提取到英文特征块: {en_name}")
                
        return cn_simp, cn_orig, en_name, debug_logs
