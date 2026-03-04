import regex as re
from typing import Optional, Tuple, List

class SpecialEpisodeHandler:
    """
    特权提取器：针对特定命名格式，提取标题和集数。
    规则优先级极高，命中后集数直接锁定，标题作为优先搜索候选。
    支持外部规则加载，格式: 正则|||字幕组索引|||标题索引|||集数索引|||描述
    集数索引可留空，表示只提取标题。
    """
    
    # 外部规则缓存
    _external_rules: List[tuple] = []

    @classmethod
    def load_external_rules(cls, rules: List[str]):
        """
        加载外部规则
        :param rules: 规则列表，格式: 正则|||字幕组索引|||标题索引|||集数索引|||描述
        示例: 
          ^\[(MyGroup)\]\s+(.+?)\s+-\s+(\d{1,4})|||1|||2|||3|||MyGroup 定向
          ^\[(MovieGroup)\]\s+(.+?)\s+\[BD\]|||1|||2|||无|||电影标题锁定
        """
        parsed = []
        for line in rules:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                parts = line.split("|||")
                if len(parts) >= 5:
                    pattern = parts[0]
                    group_idx = int(parts[1]) if parts[1].strip() and parts[1] not in ("无", "null", "None") else None
                    title_idx = int(parts[2]) if parts[2].strip() and parts[2] not in ("无", "null", "None") else None
                    ep_idx = int(parts[3]) if parts[3].strip() and parts[3] not in ("无", "null", "None") else None
                    desc = parts[4]
                    parsed.append((pattern, group_idx, title_idx, ep_idx, desc))
            except Exception:
                continue
        
        cls._external_rules = parsed

    @classmethod
    def get_all_rules(cls) -> List[tuple]:
        """获取所有规则"""
        return cls._external_rules

    @staticmethod
    def extract(filename: str) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[str], List[str]]:
        """
        提取标题和集数
        :param filename: 原始文件名
        :return: (字幕组, 标题, 集数, 集数原文, 日志)
        """
        logs = []
        
        for pattern, group_idx, title_idx, ep_idx, desc in SpecialEpisodeHandler.get_all_rules():
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    group_name = match.group(group_idx).strip() if group_idx and match.group(group_idx) else None
                    title = match.group(title_idx).strip() if title_idx else None
                    
                    # 集数可选
                    ep_str = None
                    episode = None
                    if ep_idx:
                        ep_str = match.group(ep_idx)
                        episode = int(ep_str)
                    
                    # 校验标题有效性
                    if not title or len(title) < 2:
                        continue
                    
                    logs.append(f"[规则][特权] {desc}命中")
                    if group_name:
                        logs.append(f"┣ 字幕组: {group_name}")
                    logs.append(f"┣ 标题: {title}")
                    if episode is not None:
                        logs.append(f"┣ 集数: {episode}")
                    else:
                        logs.append(f"┣ 集数: 未锁定 (仅标题提取)")
                    
                    return group_name, title, episode, ep_str, logs
                except (ValueError, IndexError):
                    continue
        
        return None, None, None, None, []
