import regex as re
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from difflib import SequenceMatcher

class TMDBMatcher:
    """
    TMDB 匹配与归一化逻辑内核 (L1)
    """

    @staticmethod
    def normalize(item: Dict[str, Any], media_type_hint: str = None) -> Dict[str, Any]:
        """
        统一 TMDB 元数据格式
        """
        m_id = item.get("id") or item.get("tmdb_id")
        m_type = item.get("media_type")
        if not m_type:
             if media_type_hint in ["movie", "tv"]: m_type = media_type_hint
             else: m_type = item.get("type")
        
        # 修正媒体类型
        if m_type and m_type.lower() in ["miniseries", "scripted", "reality", "documentary", "news", "talk show"]:
            m_type = "tv"
        if not m_type:
            if "first_air_date" in item or "name" in item: m_type = "tv"
            elif "release_date" in item or "title" in item: m_type = "movie"
        if not m_type: m_type = "unknown"
        
        date_str = item.get("release_date") or item.get("first_air_date")
        if date_str and isinstance(date_str, str) and len(date_str) > 10: date_str = date_str[:10]
            
        year = ""
        if item.get("year"): year = str(item.get("year"))
        elif date_str and isinstance(date_str, str) and len(date_str) >= 4: year = date_str[:4]
            
        category = "电影" if m_type == "movie" else ("剧集" if m_type == "tv" else "未知")
        
        def clean_img_path(p: Any) -> Optional[str]:
            if not p or not isinstance(p, str): return None
            # 如果已经是本地代理路径，保持原样
            if "/api/system/img" in p or "/api/system/bgm_img" in p: return p
            
            if "image.tmdb.org/t/p/" in p: return "/" + p.split('/')[-1]
            if p.startswith("/"):
                match = re.match(r"^/(w\d+|original)(/.*)$", p)
                if match: return match.group(2)
                return p
            return "/" + p

        return {
            "id": m_id, "type": m_type, "category": category,
            "title": item.get("title") or item.get("name"),
            "original_title": item.get("original_title") or item.get("original_name"),
            "year": year, "release_date": date_str,
            "poster_path": clean_img_path(item.get("poster_path")),
            "backdrop_path": clean_img_path(item.get("backdrop_path")),
            "overview": item.get("overview"), "vote_average": item.get("vote_average"),
            "genres": item.get("genres"),
            "secondary_category": item.get("secondary_category"),
            "origin_country": item.get("origin_country")
        }

    @staticmethod
    def prepare_queries(raw_name: Optional[str]) -> List[str]:
        """
        准备多路搜索关键词
        """
        if not raw_name: return []
        q_list = [raw_name]
        
        # 常见无意义短词/虚词过滤
        stop_words = {'NO', 'TO', 'GA', 'NI', 'WA', 'THE', 'AND', 'FOR', 'WITH', 'FROM'}
        
        if len(raw_name) > 10:
            # 这里的拆分主要针对 [中文] + [英文] 或 特殊符号分隔的标题
            segments = re.split(r'[&+\x20　、/]', raw_name)
            for s in segments:
                s_strip = s.strip()
                # 过滤逻辑：1. 长度 > 2; 2. 不在停用词表; 3. 不重复
                if len(s_strip) > 2 and s_strip.upper() not in stop_words and s_strip not in q_list:
                    q_list.append(s_strip)
        return q_list[:3]

    @staticmethod
    def calculate_match_score(item: Dict[str, Any], targets: List[str], cn_name: str, en_name: str, idx: int, anime_priority: bool) -> Tuple[float, List[str]]:
        """
        核心对撞算法：计算候选人分值，并记录详细的对撞轨迹
        """
        c_name = item.get("title") or item.get("name")
        c_oname = item.get("original_title") or item.get("original_name")
        candidate_titles = []
        if c_name: candidate_titles.append(c_name)
        if c_oname and c_oname != c_name: candidate_titles.append(c_oname)
        
        best_sim = 0.0
        best_match_info = ""
        trace = []
        
        for t_idx, target_norm in enumerate(targets):
            # 这里的 target_norm 是预先清洗过的
            t_label = "中文块" if t_idx == 0 and cn_name else "英文块"
            for t in candidate_titles:
                norm_t = re.sub(r"[^\w]", "", t).upper()
                sim = SequenceMatcher(None, target_norm, norm_t).ratio() * 100
                
                score = 0
                reason = "模糊"
                if norm_t == target_norm: 
                    score = 100
                    reason = "精准"
                elif norm_t in target_norm or target_norm in norm_t:
                    # [Optimization] 防止过短的词（如 'No', 'A'）产生误报包含分
                    if len(norm_t) <= 2 or len(target_norm) <= 2:
                        score = sim # 回退到模糊匹配分
                        reason = "模糊(过短)"
                    else:
                        score = 80
                        reason = "包含"
                else: 
                    score = sim
                
                trace.append(f"┃   │   - [{t_label}] vs '{t}' -> {reason}({score:.1f}分)")
                
                if score > best_sim:
                    best_sim = score
                    best_match_info = f"{reason}命中 '{t}'"

        final_score = best_sim
        bonus_log = []
        
        # 动画分类加权
        is_anime = 16 in (item.get("genre_ids") or [])
        if final_score > 0 and anime_priority:
            if is_anime: 
                final_score += 40
                bonus_log.append("动画暴击(+40)")
            else:
                bonus_log.append("非动画")
        
        # 排名红利
        rank_bonus = [15, 10, 5, 0, 0, 0, 0, 0][idx] if idx < 8 else 0
        if final_score > 0: 
            final_score += rank_bonus
            if rank_bonus > 0: bonus_log.append(f"排名红利(+{rank_bonus})")
        
        summary = f"最终分: {final_score:.1f} | {', '.join(bonus_log)}"
        return final_score, trace, best_match_info, summary
