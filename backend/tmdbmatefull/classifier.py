from typing import List, Dict, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)

class TmdbFullClassifier:
    """
    专门负责“二级分类”逻辑计算的处理器。
    已增强：自动适配 PostgreSQL JSONB 数据类型和字段别名。
    """

    @staticmethod
    async def calculate_with_data(tmdb_id: str, media_type: str, secondary_rules: List[Dict[str, Any]], data: Dict[str, Any]) -> str:
        if not data or not secondary_rules:
            return ""
        
        # 核心增强：全方位提取特征
        def _to_set(val):
            if not val: return set()
            # 如果是列表 (JSONB 直接解析出来的)
            if isinstance(val, list):
                res = set()
                for x in val:
                    if isinstance(x, dict): # 处理 [{'id': 16, 'name': '...'}]
                        res.add(str(x.get('id') or x.get('iso_3166_1') or ""))
                    else:
                        res.add(str(x))
                return {s for s in res if s}
            # 如果是字符串 (16,35)
            return set(str(x).strip() for x in str(val).split(",") if str(x).strip())

        # 智能获取字段 (支持新旧字段名别名)
        def _get_field(keys: List[str]):
            for k in keys:
                if data.get(k): return data[k]
            return None

        meta_feat = {
            "title": str(_get_field(["custom_title", "title", "name"]) or ""),
            "genres": _to_set(_get_field(["genre_ids", "genres"])),
            "companies": _to_set(_get_field(["company_ids", "production_companies"])),
            "keywords": _to_set(_get_field(["keyword_ids", "keywords"])),
            "lang": _get_field(["original_language", "lang"]),
            "countries": _to_set(_get_field(["origin_country", "original_country"])),
            "year": str(_get_field(["first_air_date", "release_date", "year"]) or "")[:4]
        }
        
        # 额外加权：从 full_data 提取中文国家名（如：日本）
        if data.get("full_data") and isinstance(data["full_data"], dict):
            fd = data["full_data"]
            # 提取 production_countries 里的名称
            pcs = fd.get("production_countries", [])
            if isinstance(pcs, list):
                for pc in pcs:
                    if isinstance(pc, dict) and pc.get("name"):
                        meta_feat["countries"].add(pc["name"])

        matched_names = []
        for rule in secondary_rules:
            if not rule.get("enabled", True): continue
            target = rule.get("target", "all")
            if target != "all" and target != media_type: continue
            
            # 兼容规则定义的字段名
            criteria = rule.get("criteria", {})
            if not criteria: continue

            # 执行匹配
            if TmdbFullClassifier._check_rule_match(criteria, meta_feat):
                matched_names.append(rule["name"])

        return "/".join(matched_names)

    @staticmethod
    def _check_rule_match(criteria: Dict[str, Any], meta: Dict[str, Any]) -> bool:
        if not any(v for v in criteria.values() if v):
            return False

        # 定义匹配映射
        mapping = {
            "genre_ids": "genres",
            "origin_country": "countries",
            "original_country": "countries", # 兼容旧规则
            "company_ids": "companies",
            "keyword_ids": "keywords",
            "original_language": "lang"
        }

        for crit_key, meta_key in mapping.items():
            val = criteria.get(crit_key)
            if val:
                rule_set = set(str(x).strip() for x in val.replace(" ", "").split(",") if x)
                # 特殊处理语言 (字符串匹配)
                if meta_key == "lang":
                    if meta["lang"] not in rule_set: return False
                # 其他字段 (集合交集匹配)
                elif not (rule_set & meta[meta_key]):
                    return False
        
        # 年份匹配
        if criteria.get("year"):
            ry = str(criteria["year"]).strip()
            if "-" in ry:
                try:
                    start, end = map(int, ry.split("-"))
                    if not (start <= int(meta["year"]) <= end): return False
                except: return False
            elif meta["year"] != ry:
                return False

        # [NEW] 标题/名称匹配 (支持多个关键词，逗号分隔，命中任意一个即可)
        if criteria.get("title"):
            keywords = [k.strip() for k in criteria["title"].replace("，", ",").split(",") if k.strip()]
            if not any(k.lower() in meta["title"].lower() for k in keywords):
                return False

        return True

    @staticmethod
    async def calculate(tmdb_id: str, media_type: str, secondary_rules: List[Dict[str, Any]], deep_meta: Optional[Union[Dict, Any]]) -> str:
        # 复用 data 计算逻辑
        data = deep_meta if isinstance(deep_meta, dict) else (deep_meta.model_dump() if deep_meta else {})
        return await TmdbFullClassifier.calculate_with_data(tmdb_id, media_type, secondary_rules, data)
