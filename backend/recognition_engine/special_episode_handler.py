import regex as re
from typing import Optional, Tuple, List, Dict, Any

class SpecialEpisodeHandler:
    """
    特权提取器：针对特定命名格式，提取标题和集数。
    规则优先级极高，命中后集数直接锁定，标题作为优先搜索候选。
    
    规则格式: 正则表达式 => {[字段=值;字段=值]}
    
    支持的字段:
    - group: 字幕组名称
    - title: 标题
    - e: 集数
    - s: 季数
    - tmdbid: TMDB ID
    - type: 媒体类型 (tv/movie)
    - year: 年份
    
    示例:
      Yami.Shibai.+?(\d+).+?(\d+).+?^[A-Za-z]+$ => {[tmdbid=56559;type=tv;s=\1;e=\2]}
      ^\[([^\]]+)\]\s+(.+?)\s+-\s+(\d{1,4}) => {[group=\1;title=\2;e=\3]}
    """
    
    # 外部规则缓存
    _external_rules: List[tuple] = []

    @classmethod
    def load_external_rules(cls, rules: List[str]):
        """
        加载外部规则
        :param rules: 规则列表，格式: 正则表达式 => {[字段=值;字段=值]} # 描述
        """
        parsed = []
        for line in rules:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                # 提取规则描述（# 后面的内容）
                desc = ""
                if "#" in line:
                    line, desc = line.split("#", 1)
                    desc = desc.strip()
                    line = line.strip()
                
                # 解析格式: pattern => {[key=value;...]}
                if " => " in line and "{[" in line:
                    parts = line.split(" => ", 1)
                    pattern = parts[0].strip()
                    meta_str = parts[1].strip()
                    
                    # 解析元数据字段
                    meta_dict = {}
                    if meta_str.startswith("{[") and meta_str.endswith("]}"):
                        inner = meta_str[2:-2]
                        for item in inner.split(";"):
                            if "=" in item:
                                k, v = item.split("=", 1)
                                meta_dict[k.strip().lower()] = v.strip()
                    
                    parsed.append((pattern, meta_dict, desc))
            except Exception as e:
                import logging
                logging.warning(f"[PrivilegedRules] 解析规则失败: {line} -> {e}")
                continue
        
        cls._external_rules = parsed

    @classmethod
    def get_all_rules(cls) -> List[tuple]:
        """获取所有规则"""
        return cls._external_rules

    @staticmethod
    def _resolve_capture_group(match: re.Match, value: str) -> str:
        """
        解析捕获组引用（如 \1, \2）
        """
        result = value
        # 匹配 \1, \2 等捕获组引用
        group_refs = re.findall(r'\\(\d+)', result)
        for ref in group_refs:
            idx = int(ref)
            if idx <= len(match.groups()):
                captured = match.group(idx)
                if captured:
                    result = result.replace(f'\\{idx}', captured)
        return result

    @staticmethod
    def extract(filename: str) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str], List[str], Dict[str, Any]]:
        """
        提取标题和集数
        :param filename: 原始文件名
        :return: (字幕组, 标题, 集数, 集数原文, 日志, 额外元数据)
        """
        logs = []
        extra_meta = {}
        
        for pattern, meta_dict, desc in SpecialEpisodeHandler.get_all_rules():
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    group_name = None
                    title = None
                    episode = None
                    ep_str = None
                    
                    # 从 meta_dict 中提取字段
                    group_name = SpecialEpisodeHandler._resolve_capture_group(match, meta_dict.get("group", ""))
                    title = SpecialEpisodeHandler._resolve_capture_group(match, meta_dict.get("title", ""))
                    
                    # 处理集数
                    if "e" in meta_dict:
                        ep_str = SpecialEpisodeHandler._resolve_capture_group(match, meta_dict["e"])
                        if ep_str and ep_str.isdigit():
                            episode = int(ep_str)
                    
                    # 处理季数
                    if "s" in meta_dict:
                        s_str = SpecialEpisodeHandler._resolve_capture_group(match, meta_dict["s"])
                        if s_str and s_str.isdigit():
                            extra_meta["s"] = int(s_str)
                    
                    # 处理 TMDB ID
                    if "tmdbid" in meta_dict:
                        tmdbid = SpecialEpisodeHandler._resolve_capture_group(match, meta_dict["tmdbid"])
                        if tmdbid and tmdbid.isdigit():
                            extra_meta["tmdbid"] = tmdbid
                    
                    # 处理媒体类型
                    if "type" in meta_dict:
                        type_val = SpecialEpisodeHandler._resolve_capture_group(match, meta_dict["type"]).lower()
                        if type_val in ("tv", "movie", "auto"):
                            extra_meta["type"] = type_val
                    
                    # 处理年份
                    if "year" in meta_dict:
                        year = SpecialEpisodeHandler._resolve_capture_group(match, meta_dict["year"])
                        if year and year.isdigit():
                            extra_meta["year"] = year
                    
                    # 校验标题有效性
                    if not title or len(title) < 2:
                        continue
                    
                    # 记录日志 - 使用规则描述
                    rule_desc = desc if desc else "特权规则"
                    if "tmdbid" in extra_meta:
                        rule_desc += f" (TMDB ID: {extra_meta['tmdbid']})"
                    if "type" in extra_meta:
                        rule_desc += f" (类型: {extra_meta['type']})"
                    
                    logs.append(f"[规则][特权] {rule_desc}命中")
                    if group_name:
                        logs.append(f"┣ 字幕组: {group_name}")
                    logs.append(f"┣ 标题: {title}")
                    if episode is not None:
                        logs.append(f"┣ 集数: {episode}")
                    else:
                        logs.append(f"┣ 集数: 未锁定 (仅标题提取)")
                    
                    return group_name, title, episode, ep_str, logs, extra_meta
                except (ValueError, IndexError):
                    continue
        
        return None, None, None, None, [], {}
