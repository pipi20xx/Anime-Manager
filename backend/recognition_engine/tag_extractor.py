import regex as re
import cn2an
from typing import Optional, Any, List, Tuple, Union
from .constants import SEASON_PATTERNS, EPISODE_PATTERNS, CN_MAP, NOT_GROUPS, VIDEO_RE, PIX_RE, PLATFORM_RE, DYNAMIC_RANGE_RE, AUDIO_RE, SOURCE_RE

class TagExtractor:
    @staticmethod
    def roman_to_int(s: str) -> Optional[int]:
        s = s.upper().strip()
        if not re.match(r'^[IVX]+$', s): return None
        roman = {'I': 1, 'V': 5, 'X': 10}
        num = 0
        try:
            for i in range(len(s)):
                if i > 0 and roman[s[i]] > roman[s[i - 1]]:
                    num += roman[s[i]] - 2 * roman[s[i - 1]]
                else:
                    num += roman[s[i]]
            return num
        except: return None

    @staticmethod
    def chinese_to_number(text: str) -> Optional[int]:
        try:
            if text in CN_MAP: return CN_MAP[text]
            # 尝试罗马数字
            roman = TagExtractor.roman_to_int(text)
            if roman: return roman
            return int(cn2an.cn2an(text, mode='smart'))
        except: return None

    @staticmethod
    def extract_source(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别介质来源 (如 UHD.Blu-ray.Remux)"""
        matches = re.findall(SOURCE_RE, filename)
        if not matches: return None, []

        res = []
        seen = set()
        mapping = {
            "WEBRIP": "WebRip", "WEB-RIP": "WebRip", "WEBDL": "WEB-DL", "WEB-DL": "WEB-DL",
            "BLURAY": "Blu-ray", "BD": "Blu-ray", "BLU": "Blu-ray",
            "HDTV": "HDTV", "UHDTV": "UHDTV", "DVDRIP": "DVD-Rip", "BDRIP": "BD-Rip",
            "REMUX": "Remux", "UHD": "UHD", "Pdtv": "PDTV", "Dvdscr": "DVD-SCR", "WEB": "WEB"
        }

        for m in matches:
            upper_m = m.upper().replace("-", "")
            final_val = mapping.get(upper_m, m)
            if final_val not in seen:
                res.append(final_val)
                seen.add(final_val)
        
        def sort_source(x):
            order = ["UHD", "Blu-ray", "WEB-DL", "WebRip", "HDTV", "Remux"]
            return order.index(x) if x in order else 99
        
        res.sort(key=sort_source)
        final_str = ".".join(res)
        return final_str, [f"[规则][内置] 介质来源: {'.'.join(matches)} -> {final_str}"]

    @staticmethod
    def extract_year(text: str) -> Tuple[Optional[str], List[str]]:
        match = re.search(r"\b((19|20)\d{2})\b", text)
        if match: return match.group(1), [f"[规则][内置] 上映年份: {match.group(1)}"]
        return None, []

    @staticmethod
    def extract_season(text: str) -> Tuple[Optional[int], List[str]]:
        for p in SEASON_PATTERNS:
            match = re.search(p, text, re.I)
            if match:
                val = TagExtractor.chinese_to_number(match.group(1))
                if val: return val, [f"[规则][内置] 季号: S{val}"]
        
        # [New] 罗马数字季号支持 (Season III, S IV)
        roman_explicit = re.search(r"(?i)(?:Season|S|第)\s*([IVX]+)(?:\s*季)?\b", text)
        if roman_explicit:
            val = TagExtractor.roman_to_int(roman_explicit.group(1))
            if val: return val, [f"[规则][内置] 罗马季号: S{val}"]

        # [New] 罗马数字后缀支持 (Title III [01]...)
        # 匹配位于空格之后，且后面紧跟 [ ( 或 结束符 的罗马数字
        roman_suffix = re.search(r"\s([IVX]+)(?=\s|\[|\(|【|（|$)", text)
        if roman_suffix:
            val = TagExtractor.roman_to_int(roman_suffix.group(1))
            # 限制范围 1-10 防止误伤 I (1) 或过大的词
            if val and 1 < val <= 10:
                return val, [f"[规则][内置] 罗马后缀季号: S{val}"]

        return None, []

    @staticmethod
    def validate_episode(ep_val: Any, filename: str) -> Tuple[Optional[Union[int, float]], List[str]]:
        if ep_val is None: return None, []
        try:
            val_str = str(ep_val[0] if isinstance(ep_val, list) else ep_val)
            # 处理浮点集数 (如 24.5)
            if "." in val_str:
                num_val = float(val_str)
                # 如果是整数浮点 (如 24.0)，转回 int
                if num_val.is_integer():
                    num_val = int(num_val)
            else:
                num_val = int(val_str)

            # 误报拦截：如果是像 H.264 这种被误认为集数的情况
            if re.search(rf"(?i)[Hx]\.?{val_str}\b", filename) or re.search(rf"(?i)\b{val_str}[Pp]\b", filename):
                if not re.search(rf"(?i)(EP|第|E|episode|#)\s*0*{val_str}", filename):
                    return None, [f"[规则][内置] 集数误报拦截: {val_str}"]
            
            return num_val, [f"[规则][内置] 集数校验通过: E{num_val}"]
        except: return None, []

    @staticmethod
    def extract_episode(text: str, filename_context: str = "") -> Tuple[Optional[int], List[str]]:
        for p in EPISODE_PATTERNS:
            match = re.search(p, text, re.I)
            if match:
                val = match.group(1)
                return TagExtractor.validate_episode(val, filename_context)
        return None, []

    @staticmethod
    def extract_release_group(filename: str, info_group: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
        """强化版制作组提取"""
        from .constants import GROUP_KEYWORDS, NOT_GROUPS
        logs = []
        def is_valid_group(g: str) -> bool:
            if not g: return False
            g = g.strip()
            if len(g) < 2: return False
            if re.match(r"^\d+$", g): return False
            if "@" in g:
                parts = g.split("@")
                if len(parts[-1].strip()) < 2: return False
            
            # [Optimization] 语义特征强制校验：
            # 如果包含中文/日文，则必须包含制作组常用后缀关键词
            if re.search(r"[\u4e00-\u9fa5\u3040-\u30ff]", g):
                has_keyword = bool(re.search(GROUP_KEYWORDS, g))
                # 必须包含制作组后缀
                if not has_keyword:
                    return False
                # 排除明显的剧名特征 (如 [第01话])
                has_title_feature = bool(re.search(r"第?\d+[集话話回季]|[上下]卷", g))
                if has_title_feature:
                    return False
            
            # 对于纯英文/数字组名 (如 ANi, VCB-Studio)，只要长度 >= 2 即可通过
            digit_count = sum(c.isdigit() for c in g)
            if digit_count / len(g) > 0.8: return False
            return True

        if info_group and re.search(PLATFORM_RE, info_group):
            logs.append(f"[规则][内置] 平台词纠偏: {info_group}")
            info_group = None

        if info_group and info_group.upper() not in NOT_GROUPS and is_valid_group(info_group):
            return info_group, [f"[规则][内置] 制作组: {info_group}"]
        
        gm = re.match(r"^\[([^\]]+)\]|^【([^】]+)】", filename)
        if gm:
            g_candidate = gm.group(1) or gm.group(2)
            if not re.search(PLATFORM_RE, g_candidate) and is_valid_group(g_candidate):
                return g_candidate, [f"[规则][内置] 首部制作组: {g_candidate}"]
            
        base_name = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)
        # 修复正则语法：匹配末尾由横杠引导的、不含空格和各类括号的连续字符
        # 正确闭合字符集 [^ ... ]
        tm = re.search(r"-([^\s\[\]\(\){}]+)$", base_name) 
        if tm:
            raw = tm.group(1)
            g_candidate = raw
            # 过滤逻辑依然保留
            if g_candidate.upper() not in NOT_GROUPS and is_valid_group(g_candidate):
                 msg = f"[规则][内置] 尾部制作组: {g_candidate}"
                 return g_candidate, [msg]
        return None, []

    @staticmethod
    def extract_platform(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别发布平台"""
        match = re.search(PLATFORM_RE, filename)
        if match:
            raw = match.group(0).lstrip('-')
            mapping = {
                "CR": "Crunchyroll", "NF": "Netflix", "AMZN": "Amazon", 
                "ATVP": "AppleTV+", "DSNP": "Disney+", "iT": "iTunes", 
                "LINETV": "LINE TV", "ABEMA": "AbemaTV", "IQ": "iQIYI", "IQIYI": "iQIYI"
            }
            upper_raw = raw.upper()
            final_val = mapping.get(upper_raw, "iTunes" if raw == "iT" else ("Amazon" if upper_raw == "CRAMZN" else raw))
            log_msg = f"[规则][内置] 发布平台: {raw}"
            if final_val != raw: log_msg += f" -> {final_val}"
            return final_val, [log_msg]
        return None, []

    @staticmethod
    def extract_dynamic_range(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别动态范围指标"""
        matches = re.findall(DYNAMIC_RANGE_RE, filename)
        if not matches: return None, []
        found_tags = set(m.upper().replace(" ", "") for m in matches)
        res = []
        if any(x in found_tags for x in ["DOVI", "DV", "DOLBYVISION"]): res.append("Dolby Vision")
        if "HDR10+" in found_tags: res.append("HDR10+")
        elif "HDR10" in found_tags: res.append("HDR10")
        elif "HDR" in found_tags: res.append("HDR")
        if "HLG" in found_tags: res.append("HLG")
        if "IMAX" in found_tags: res.append("IMAX")
        if "SDR" in found_tags: res.append("SDR")
        final_val = ".".join(res) if res else None
        if final_val: return final_val, [f"[规则][内置] 动态范围: {final_val}"]
        return None, []

    @staticmethod
    def extract_resolution(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别分辨率标准化"""
        match = re.search(PIX_RE, filename)
        if match:
            raw = match.group(0).lower()
            if "4k" in raw or "2160p" in raw: return "4K", [f"[规则][内置] 分辨率标准化: {match.group(0)} -> 4K"]
            if "1080p" in raw: return "1080P", [f"[规则][内置] 分辨率标准化: {match.group(0)} -> 1080P"]
            if "720p" in raw: return "720P", [f"[规则][内置] 分辨率标准化: {match.group(0)} -> 720P"]
            if "x" in raw:
                try:
                    dims = [int(x) for x in re.findall(r"\d+", raw)]
                    if dims:
                        max_d, min_d = max(dims), min(dims)
                        if max_d >= 3840 or min_d >= 2160: final_val = "4K"
                        elif max_d >= 1920 or min_d >= 1080: final_val = "1080P"
                        elif max_d >= 1280 or min_d >= 720: final_val = "720P"
                        else: final_val = f"{min_d}P"
                        return final_val, [f"[规则][内置] 分辨率标准化 ({match.group(0)}): {final_val}"]
                except: pass
            return raw.upper(), []
        return None, []

    @staticmethod
    def extract_audio_encode(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别音频规格"""
        matches = list(re.finditer(AUDIO_RE, filename))
        if matches:
            final_tags, raw_log_parts, seen_combos = [], [], set()
            for m in matches:
                codec_raw = m.group(1).upper().replace(".", "").replace("-", "").replace("_", "")
                codec = codec_raw
                if "ATMOS" in codec_raw: codec = "Dolby Atmos"
                elif "DTSHDMA" in codec_raw or "DTSMA" in codec_raw: codec = "DTS-HD MA"
                elif "DTSHD" in codec_raw: codec = "DTS-HD"
                elif "EAC3" in codec_raw or "DDP" in codec_raw or "DD+" in codec_raw: codec = "E-AC-3"
                elif "AC3" in codec_raw or "DD" == codec_raw: codec = "AC-3"
                elif "TRUEHD" in codec_raw: codec = "TrueHD"
                elif "LPCM" in codec_raw or "PCM" in codec_raw: codec = "LPCM"
                elif "DTS" == codec_raw: codec = "DTS"
                elif "AAC" in codec_raw: codec = "AAC"
                elif "FLAC" in codec_raw: codec = "FLAC"
                elif "OPUS" in codec_raw: codec = "Opus"
                elif "VORBIS" in codec_raw: codec = "Vorbis"
                channel_raw = m.group(2).lower().replace("_", "") if m.group(2) else ""
                channel = "2.0" if "2ch" in channel_raw else ("5.1" if "6ch" in channel_raw else ("7.1" if "8ch" in channel_raw else channel_raw))
                full_tag = f"{codec} {channel}".strip() if channel else codec
                if full_tag not in seen_combos:
                    final_tags.append(full_tag); seen_combos.add(full_tag); raw_log_parts.append(m.group(0))
            def sort_key(x):
                base = x.split()[0] 
                order = ["Dolby", "DTS-HD", "TrueHD", "LPCM", "E-AC-3", "AC-3", "DTS", "FLAC", "Opus", "AAC", "Vorbis"]
                for i, o in enumerate(order):
                    if base.startswith(o): return i
                return 99
            final_tags.sort(key=sort_key)
            final_str = " ".join(final_tags)
            return final_str, [f"[规则][内置] 音频规格: {' '.join(raw_log_parts)} -> {final_str}"]
        return None, []

    @staticmethod
    def extract_video_encode(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别视频规格"""
        match = re.search(VIDEO_RE, filename)
        if match:
            raw = match.group(0).upper().replace(".", "").replace("-", "")
            final_val = "H.265" if ("265" in raw or "HEVC" in raw) else ("H.264" if ("264" in raw or "AVC" in raw) else ("AV1" if "AV1" in raw else match.group(0).upper() if "MPEG" in raw else match.group(0)))
            return final_val, [f"[规则][内置] 视频规格: {match.group(0)} -> {final_val}"]
        return None, []

    @staticmethod
    def extract_subtitle_lang(filename: str) -> Tuple[Optional[str], List[str]]:
        """[规范化] 识别并合成字幕语言标签"""
        logs = []
        f_norm = filename.upper()
        
        # 1. 特征定义
        has_chs = bool(re.search(r"简|簡|CHS|SC|GB|简体|简中", f_norm))
        has_cht = bool(re.search(r"繁|CHT|TC|BIG5|繁体|繁中", f_norm))
        has_jap = bool(re.search(r"日|JAP|JPN|JP|日文|日语", f_norm))
        # [Optimize] 增加对工业标签的语义识别 (如 SRTx2 通常代表简繁双语)
        if not (has_chs or has_cht) and re.search(r"[SA][RS][ST]X2", f_norm):
            has_chs = has_cht = True
        
        # 英文判定需严格边界，防止匹配到 SENSEI 等
        has_eng = bool(re.search(r"(?<![a-zA-Z0-9])(ENG|EN|英文|英语)(?![a-zA-Z0-9])", f_norm))
        
        # 2. 类型定义
        is_internal = bool(re.search(r"内封|內封|ASSx|SRTx|CHI_JPN|JPSC", f_norm))
        is_embedded = bool(re.search(r"内嵌|內嵌|硬字幕|BIG5_MP4|GB_MP4", f_norm))
        is_external = bool(re.search(r"外挂|外掛", f_norm))
        is_dual = bool(re.search(r"双语|雙語|双语字幕", f_norm))
        
        # 3. 规范化合成逻辑
        langs = []
        if has_chs: langs.append("简")
        if has_cht: langs.append("繁")
        if has_jap: langs.append("日")
        if has_eng: langs.append("英")
        
        if not langs: return None, []
        
        # 基础前缀判定：单语言用全称，多语言用简称
        if len(langs) == 1:
            mapping = {"简": "简体", "繁": "繁体", "日": "日文", "英": "英文"}
            base = mapping.get(langs[0], langs[0])
        else:
            base = "".join(langs)
        
        # 属性判定
        suffix = ""
        if is_internal: suffix = "内封"
        elif is_embedded: suffix = "内嵌"
        elif is_external: suffix = "外挂"
        elif is_dual: suffix = "双语"
        else:
            # 默认为内封 (常见于 WebRip/BDRip)
            suffix = "内封" if ("RIP" in f_norm or "BD" in f_norm) else "内嵌"

        final_label = f"{base}{suffix}"
        
        # 特殊情况修正
        if final_label == "简日内封": final_label = "简日双语" # 习惯用法
        if final_label == "繁日内封": final_label = "繁日双语"
        
        logs.append(f"[规则][规范化] 字幕语言: {final_label}")
        return final_label, logs
