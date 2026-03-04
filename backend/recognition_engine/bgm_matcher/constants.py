import regex as re

# 标题截断模式：用于从 BGM 标题中剥离“第x季”、“篇”等干扰项
TRUNCATION_PATTERNS = [
    r"第\s*[一二三四五六七八九十零〇\dIVXLCDM]+.*(?:季|期|章|部|部分|幕|年|年目|クール|Stage|シリーズ|Series)",
    r"\s+[一二三四五六七八九十零〇\d]+\s*(?:季|期)\b",
    r"\s+(?:第)?\s*[一二三四五六七八九十零〇\d]+\s*丁目",
    r"\b(?:Season|Saison|시즌|S|Part|Cour|Stage)[\s.]*(?:[IVXLCDM]+|\d+)",
    r"\b\d+(?:st|nd|rd|th)\s*(?:Season|Stage|Part|Cour)?",
    r"\b(最终季|ファイナルシリーズ|Final Season|Final|最終章|完结編|完结篇)\b",
    r"[\(（【\[][^篇]*篇[\)）】\]]", 
    r"[\s～~～〜]+.*$", # 只要匹配到任何形式的波浪号及其后面的内容，全部截断
    r"\b[上下左右前后终末始序中新旧更真伪\w\s]{1,10}篇\b",
    r"\b[一二三四五六七八九十零〇\w]+之章\b",
    r'\bEpisode\s*[:：.]?\s*(?:[IVXLCDM]+|\d+|“[^”]+”|"[^"]+")',
    r"\s+(?:[IVXLCDM一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾壱弐参ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+|\d+)\s*[:：]\s+",
    r"[:：]\s+",
    r"(?:[\s～~]+)(?:Next|NEXT)(?:\s+(?:Season|Summit|Generation|Level|Stage)|$|[\s～~])",
    r"(?<=[一-鿿])(?:Next|NEXT)$",
    r"\s+([IVXLCDM一二三四五六七八九十壹贰叁肆伍陆柒捌玖拾壱弐参ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+|\d+)$",
    r"['’]+$",
    r"\s+[^\w\s]+$",
    r"[♭ΔθδΨΩαβγζηικλμνξοπρστυφχψω]+$",
    r"\s+[一-鿿぀-ヿ゠-ヿ]{1,2}$"
]

# 格式清洗模式
FORMAT_CLEAN_PATTERNS = [
    r"^[续続]\s*",
    r"剧场版", r"电影版", r"电影", r"映画", r"全天域", r"天文馆",
    r"\bThe Movie\b", r"\bMovie\b", r"\bFilm\b",
    r"\bTHE REAL 4D\b", r"\b4D\b", r"\b3D\b",
    r"\bOVA\b", r"\bOAD\b", r"\bOAV\b", r"\bWeb\b", 
    r"[\(（【\[]\s*(?:OVA|OAD|OAV|Movie|剧场版|Web|4D|3D)\s*[\)）】\]]",
]
