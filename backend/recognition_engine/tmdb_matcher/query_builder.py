"""标题查询词构建（独立模块）

从 TMDBMatcher.prepare_queries 迁出，便于独立演进分词策略与单元测试。
- prepare_queries：完整分词结果（搜索词与评分 targets 共用的基础实现）
- search_queries：受分词开关控制的搜索用查询词
"""
import re
from typing import List, Optional


class QueryBuilder:
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
    def search_queries(raw_name: Optional[str], segmented: bool) -> List[str]:
        """
        搜索用的查询词：segmented=False 时仅保留完整标题。
        评分 targets 请继续使用 prepare_queries 的完整结果，不受此开关影响。
        """
        queries = QueryBuilder.prepare_queries(raw_name)
        return queries if segmented else queries[:1]
