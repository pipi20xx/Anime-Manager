import regex as re
from typing import List, Optional, Dict, Tuple
from difflib import SequenceMatcher
from datetime import datetime
from .constants import TRUNCATION_PATTERNS, FORMAT_CLEAN_PATTERNS

class BangumiMatcher:
    """
    Bangumi 匹配逻辑内核 (L1)
    纯算法实现，不含任何网络请求。
    """
    
    @staticmethod
    def clean_format_keywords(title: str) -> str:
        if not title: return ""
        clean_title = title
        for pattern in FORMAT_CLEAN_PATTERNS:
            clean_title = re.sub(pattern, " ", clean_title, flags=re.IGNORECASE)
        return " ".join(clean_title.split()).strip()

    @staticmethod
    def extract_base_name(title: str) -> str:
        if not title: return ""
        earliest_pos = len(title)
        for pattern in TRUNCATION_PATTERNS:
            match = re.search(pattern, title, flags=re.IGNORECASE)
            if match:
                earliest_pos = min(earliest_pos, match.start())
        truncated = title[:earliest_pos].strip().rstrip(':-~～－—_ ')
        return BangumiMatcher.clean_format_keywords(truncated)

    @staticmethod
    def generate_search_strategies(item: Dict) -> List[Tuple[str, Optional[int], str]]:
        """
        生成用于 TMDB 搜索的多种关键词组合策略 (词, 年份, 语言标记)
        """
        name_cn = item.get('title') or ''
        name_original = item.get('original_title') or ''
        date = item.get('release_date')
        year = int(date.split('-')[0]) if date and '-' in date else None
        
        base_name_cn = BangumiMatcher.extract_base_name(name_cn)
        base_name_original = BangumiMatcher.extract_base_name(name_original)
        
        strategies = []
        seen = set()
        def add(q, y, lang):
            if q and (q, y, lang) not in seen:
                strategies.append((q, y, lang))
                seen.add((q, y, lang))
        
        # 优先级：原名(日文) -> 中文名
        # 为什么原名优先？因为原名是唯一的，中文翻译可能有多种。
        add(name_original, year, "ja")
        add(name_cn, year, "zh")
        add(name_original, None, "ja")
        add(name_cn, None, "zh")
        
        if base_name_original != name_original: add(base_name_original, year, "ja")
        if base_name_cn != name_cn: add(base_name_cn, year, "zh")
        
        return strategies

    @staticmethod
    def score_candidate(candidate: Dict, bgm_item: Dict, query: str, strategy_type: str, query_label: str = "BGM词") -> Tuple[float, List[str], str]:
        """
        计算 TMDB 候选人与 Bangumi 条目的匹配分值 (100分制)，并返回轨迹
        """
        tmdb_title_cn = candidate.get('title') or candidate.get('name', '')
        tmdb_title_orig = candidate.get('original_title') or candidate.get('original_name', '')
        
        if not tmdb_title_cn and not tmdb_title_orig: return 0.0, [], "无标题"
        
        trace = []
        best_ratio = 0.0
        
        # 逐项比对并记录轨迹
        for t in [tmdb_title_cn, tmdb_title_orig]:
            if not t: continue
            ratio = SequenceMatcher(None, query.lower(), t.lower()).ratio()
            trace.append(f"┃   │   - [{query_label}: '{query}'] vs '{t}' -> 相似度({ratio:.2f})")
            if ratio > best_ratio:
                best_ratio = ratio
            
        if best_ratio < 0.4: return 0.0, trace, f"相似度过低({best_ratio:.2f})"
        
        # 基础分 (相似度 * 60)
        score = best_ratio * 60
        reasons = [f"文本分({score:.1f})"]
        
        # 属性权重校正
        tmdb_media_type = candidate.get('media_type')
        bgm_platform = bgm_item.get('platform', '')
        bgm_name_full = (bgm_item.get('title') or bgm_item.get('original_title') or "").lower()
        is_compilation = any(k in bgm_name_full for k in ["总集篇", "特别篇", "special", "剪辑版", "精选"])
        
        # 定义 Bangumi 的归一化类型
        is_bgm_movie = bgm_platform in ['Movie', '剧场版', '电影'] or '剧场版' in bgm_name_full
        target_type = 'movie' if is_bgm_movie else 'tv'

        if tmdb_media_type == target_type:
            score += 20.0
            reasons.append(f"类型一致({tmdb_media_type.upper()})(+20)")
        else:
            # 类型冲突处理
            if target_type == 'tv' and tmdb_media_type == 'movie':
                if is_compilation:
                    score += 5.0
                    reasons.append("TV->Movie(合集修正)(+5)")
                else:
                    score -= 40.0
                    reasons.append("类型冲突(TV->Movie)(-40)")
            elif target_type == 'movie' and tmdb_media_type == 'tv':
                score -= 40.0
                reasons.append("类型冲突(Movie->TV)(-40)")
            
        # 年份逻辑校验
        tmdb_date = candidate.get('release_date') or candidate.get('first_air_date', '')
        bgm_date = bgm_item.get('release_date', '')
        
        if bgm_date and tmdb_date:
            try:
                bgm_year = int(bgm_date.split('-')[0])
                tmdb_year = int(tmdb_date.split('-')[0])
                diff = abs(bgm_year - tmdb_year)
                
                if diff == 0:
                    score += 20.0
                    reasons.append("年份精准(+20)")
                elif diff <= 1:
                    score += 10.0
                    reasons.append("年份微差(+10)")
            except: pass
            
        if 16 in (candidate.get('genre_ids') or []):
            score += 40.0
            reasons.append("动画暴击(+40)")
            
        summary = " | ".join(reasons)
        return score, trace, summary
