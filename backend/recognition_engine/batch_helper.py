import regex as re
from typing import List, Tuple, Optional, Any
from .data_models import MetaBase

class BatchHelper:
    """
    专门负责合集（Batch）判定的增强模块。
    支持从文件名或描述中提取集数范围。
    """

    @staticmethod
    def analyze_filename(filename: str) -> Tuple[Optional[Any], Optional[Any], List[str]]:
        """
        从文件名中深度挖掘合集区间
        返回: (start, end, logs)
        """
        logs = []
        
        # 1. 针对特定制作组的特色合集格式
        # [LoliHouse] 风格: [48.5-72(00-24) 合集] 或 [01-08 精校合集]
        # [7³ACG] 风格: | 01-13(01-25)
        special_patterns = [
            (r"(?i)LoliHouse.*?\[(\d{1,3})\s?-\s?(\d{1,3})\s?.*?合集.*?\]", "LoliHouse-General"),
            (r"(?i)SweetSub.*?\[(\d{1,3})\s?-\s?(\d{1,3})\s?.*?合集.*?\]", "SweetSub-General"),
            (r"\[(\d+(?:\.\d+)?)\s?-\s?(\d+(?:\.\d+)?)\s?\(\d+(?:\.\d+)?-\d+(?:\.\d+)?\)\s*合集\]", "LoliHouse-Old"),
            (r"\|\s*(\d{1,3})\s?-\s?(\d{1,3})\s?\(\d{1,3}\s?-\s?\d{1,3}\)", "7³ACG")
        ]
        
        for p, group_name in special_patterns:
            match = re.search(p, filename, re.I)
            if match:
                try:
                    s_raw, e_raw = match.group(1), match.group(2)
                    # 尝试转换，如果带小数点则保持 float，否则 int
                    s = float(s_raw) if "." in s_raw else int(s_raw)
                    e = float(e_raw) if "." in e_raw else int(e_raw)
                    
                    logs.append(f"[BatchHelper] 命中 {group_name} 特色合集规则: {s_raw}-{e_raw}")
                    return s, e, logs
                except: pass

        # 2. 强力区间正则 (支持 [01-12], | 01-12, 01-12Fin 等)
        # 核心逻辑: 两个数字，中间有连字符或波浪号，周围有特定的边界符
        patterns = [
            # 括号包裹: [01-13], [01-13Fin], [TV01-25Fin], 【13~24】, [01-24(全集)]
            r"(?:\[|【)(?:TV|EP|E)?\s?(\d{1,3})\s?[-~]\s?(\d{1,3})(?:Fin|END|\]|】|合集|集|话|話|巻|卷|卷|v|\s\[|\()",
            
            # 分隔符前缀: | 01-13, - 01-13 (需紧跟数字)
            r"(?:\|\s?|\-\s)(\d{1,3})\s?[-~]\s?(\d{1,3})(?=\s|\[|\]|】|Fin|END)",
            
            # 中文描述: 第01-13集, 全12话
            r"第(\d{1,3})\s?[-~]\s?(\d{1,3})[集话話期]",
            r"(?:全|共)(\d{1,3})[集话話期]", # 这种情况 Start=1

            # [New] Standard Scene/P2P Batch: S01E09-E10, E01-E12
            r"(?i)(?:S\d{1,2})?EP?(\d{1,4})\s?[-~]\s?EP?(\d{1,4})",
        ]

        for p in patterns:
            match = re.search(p, filename, re.I)
            if match:
                try:
                    # case: 全12集 -> group(1)=12, group(2) missing
                    if match.lastindex == 1:
                        s, e = 1, int(match.group(1))
                    else:
                        s, e = int(match.group(1)), int(match.group(2))
                    
                    # 安全检查
                    if s < e and s < 1900 and e < 1900: 
                        logs.append(f"[BatchHelper] 命中强规则: {p} -> {s}-{e}")
                        return s, e, logs
                except: pass

        return None, None, logs

    @staticmethod
    def enhance_from_description(meta: MetaBase, description: str, logs: List[str]):
        """
        Extracts batch/season info from subtitle description (Existing logic preserved)
        """
        if not description:
            return

        # 中文数字转换辅助
        cn_num_map = {
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20,
            "二十一": 21, "二十二": 22, "二十三": 23, "二十四": 24, "二十五": 25
        }

        # 1. 季号增强 (支持 "第一季", "第1季", "S2")
        if meta.begin_season is None or meta.begin_season == 1:
            m_season = re.search(r"第([一二三四五六七八九十\d]+)季", description)
            if m_season:
                s_val = m_season.group(1)
                if s_val.isdigit():
                    meta.begin_season = int(s_val)
                elif s_val in cn_num_map:
                    meta.begin_season = cn_num_map[s_val]
                logs.append(f"[BatchHelper] 描述增强季号: S{meta.begin_season}")

        if meta.is_batch:
            return

        # 2. 全集数增强: "全12集", "全十集"
        m_full = re.search(r"全([一二三四五六七八九十\d]+)[集期话]", description)
        if m_full:
            s_val = m_full.group(1)
            e_num = None
            if s_val.isdigit():
                e_num = int(s_val)
            elif s_val in cn_num_map:
                e_num = cn_num_map[s_val]
            
            if e_num:
                meta.begin_episode = 1
                meta.end_episode = e_num
                meta.is_batch = True
                logs.append(f"[BatchHelper] 描述增强全集: 1-{e_num}")
                return
        
        # 3. 范围增强: "01-24" or "[01-24Fin]"
        if not meta.is_batch:
            m_range = re.search(r"(\d{1,2})-(\d{1,2})(?:集|期|完|Fin|完结)?", description)
            if m_range:
                s, e = int(m_range.group(1)), int(m_range.group(2))
                if s < e and e < 500: # Sanity check
                    meta.begin_episode = s
                    meta.end_episode = e
                    meta.is_batch = True
                    logs.append(f"[BatchHelper] 描述增强范围: {s}-{e}")
                    return

        # 4. 显式关键字判定
        if not meta.is_batch:
            if any(kw in description for kw in ["完结", "全集", "合集", "Batch", "Pack"]):
                meta.is_batch = True
                logs.append(f"[BatchHelper] 判定为合集 (包含完结关键字)")