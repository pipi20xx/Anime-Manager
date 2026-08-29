# -*- coding: utf-8 -*-
"""
洗版规则/订阅筛选字段的规范值选项 (下拉数据源)。

封闭字段的值域全部由 recognition_engine.constants 的"规格值登记区"派生:
识别端新增规范值时这里自动跟随, 无需维护。
唯一需要人工补充的是 field_match.TOKEN_ALIASES (匹配端的宽容别名层)。

team 为开放字段, 由 routers/priority 从已识别的 feed_items 按频次聚合。
"""
from itertools import combinations

from recognition_engine import constants as C


def _dedupe(seq) -> list:
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            out.append(x); seen.add(x)
    return out


# extract_resolution 输出: "4K"/"1080P"/"720P"/"{min_d}P"
RESOLUTIONS = list(C.COMMON_RESOLUTIONS)

# extract_video_encode 输出: 规则归一值 + 原文直通值
VIDEO_ENCODES = _dedupe(
    [val for _, val in C.VIDEO_ENCODE_RULES] + list(C.VIDEO_ENCODE_PASSTHROUGH)
)

# extract_audio_encode 输出: codec 规范值 (声道后缀由 token 匹配层处理, 不枚举)
AUDIO_ENCODES = _dedupe(val for _, _, val in C.AUDIO_CODEC_RULES)

# extract_source 输出: SOURCE_VALUE_MAP 的映射值域
SOURCES = _dedupe(C.SOURCE_VALUE_MAP.values())

# extract_dynamic_range 输出: 各组的规范值
VIDEO_EFFECTS = _dedupe(
    v for key_map, _ in C.DYNAMIC_RANGE_DEFS for v in key_map.values()
)

# extract_platform 输出: 映射值 + 未映射 token 的原文直通值
PLATFORMS = _dedupe(
    list(C.PLATFORM_VALUE_MAP.values())
    + [t for t in C.PLATFORM_TOKENS + C.PLATFORM_PLUS_TOKENS
       if t.upper() not in C.PLATFORM_VALUE_MAP]
)


def _build_subtitles() -> list:
    """extract_subtitle_lang 的合成值域: 语种前缀 x 类型后缀"""
    vals = []
    # 单语言用全称
    for lang in C.SUB_LANG_ORDER:
        for t in C.SUB_TYPES:
            vals.append(C.SUB_LANG_FULL[lang] + t)
    # 多语言用简称, 按 SUB_LANG_ORDER 顺序拼接的任意 >=2 组合
    for n in range(2, len(C.SUB_LANG_ORDER) + 1):
        for combo in combinations(C.SUB_LANG_ORDER, n):
            for t in C.SUB_TYPES:
                vals.append("".join(combo) + t)
    # extract_subtitle_lang 会把 "简日内封"/"繁日内封" 修正为 "双语", 排除不可能出现的值
    for impossible in ("简日内封", "繁日内封"):
        if impossible in vals:
            vals.remove(impossible)
    return vals


SUBTITLES = _build_subtitles()


def get_static_options() -> dict:
    return {
        "resolution": RESOLUTIONS,
        "video_encode": VIDEO_ENCODES,
        "audio_encode": AUDIO_ENCODES,
        "source": SOURCES,
        "video_effect": VIDEO_EFFECTS,
        "platform": PLATFORMS,
        "subtitle": SUBTITLES,
    }
