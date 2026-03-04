import regex as re

def extract_season_from_name(title: str) -> int:
    """
    [独立算法] 从番剧名字中提取季号。
    支持格式：第2季, Season 2, 第二期, S2 等。
    如果未匹配到，默认返回 1。
    此函数主要用于 Bangumi 订阅时的元数据处理。
    """
    if not title:
        return 1
    
    # 定义匹配模式：(正则表达式, 捕获组索引)
    patterns = [
        (r'第\s*([0-9一二三四五六七八九十]+)\s*季', 1),
        (r'Season\s*([0-9]+)', 1),
        (r'第\s*([0-9一二三四五六七八九十]+)\s*期', 1),
        (r'S([0-9]+)', 1)
    ]
    
    # 中文数字映射表
    cn_num = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, 
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
    }
    
    for p, g in patterns:
        m = re.search(p, title, re.IGNORECASE)
        if m:
            val = m.group(g)
            # 如果是纯数字
            if val.isdigit():
                return int(val)
            # 如果是中文数字
            if val in cn_num:
                return cn_num[val]
                
    return 1
