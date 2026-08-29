# -*- coding: utf-8 -*-
"""
媒体规格字段的统一条件匹配。

洗版规则 (FilterRule.conditions) 与订阅过滤 (Subscription.filter_*) 的
匹配语义在此统一定义, 两处都必须走这里, 避免语义漂移。

策略说明:
    exact     - 整串精确匹配 (小写), 规则值支持逗号分隔多值
    composite - 复合值 token 匹配: 条目值可能是 "." 拼接的复合串
                (如 "UHD.Blu-ray.Remux"/"Dolby Vision.HDR10+"), 拆 token 后
                只要包含规则目标即可命中
    fuzzy     - 整串归一化匹配 (去 "."/"-" + 别名), 规则值支持逗号分隔多值
    token     - 空格分词 n-gram 匹配, 用于音频 ("FLAC 2.0 DTS 5.1" 这类
                多 codec 标签串, 目标 "FLAC" 或 "FLAC 2.0" 均可命中)
"""
import re

# 匹配端别名归一表: 键/值均为小写、去掉 "." 和 "-" 后的形式。
# 匹配前对规则值和条目 token 统一走 normalize_token, 常见混用写法在这里收敛。
# 只收录真实存在分歧的写法, 归一化后形式相同的无需列出。
TOKEN_ALIASES = {
    # 介质来源
    "bd": "bluray", "blu": "bluray",
    # 视频编码
    "hevc": "h265", "x265": "h265",
    "avc": "h264", "x264": "h264",
    # 音频编码
    "ddp": "eac3", "dd": "ac3",
    "thd": "truehd", "pcm": "lpcm",
    # 视频特效
    "dovi": "dolby vision", "dolbyvision": "dolby vision",
}


def normalize_token(tok: str) -> str:
    """小写并去掉 '.'/'-', 再走别名表。规则值与条目 token 都要过一遍。"""
    t = tok.strip().lower().replace(".", "").replace("-", "")
    return TOKEN_ALIASES.get(t, t)


FIELD_MATCH_STRATEGY = {
    "resolution": "exact",
    "team": "exact",
    "subtitle": "exact",
    "platform": "exact",
    "source": "composite",
    "video_effect": "composite",
    "video_encode": "fuzzy",
    "audio_encode": "token",
}


def rule_targets(rule_val: str) -> list:
    return [t.strip() for t in rule_val.split(',') if t.strip()]


def _norm_tokens(s: str, seps: str) -> list:
    return [normalize_token(t) for t in re.split(seps, s) if t.strip()]


def _token_ngrams(tokens: list) -> set:
    return {" ".join(tokens[i:j + 1])
            for i in range(len(tokens))
            for j in range(i, min(i + 3, len(tokens)))}


def match_field(rule_val, item_val, strategy: str = "exact") -> bool:
    """单字段匹配。规则值为空 -> 不限制; 规则有值而条目为空 -> 不匹配。"""
    if not rule_val or not str(rule_val).strip():
        return True
    if not item_val:
        return False

    rule_val = str(rule_val)
    if strategy == "exact":
        targets = [t.lower() for t in rule_targets(rule_val)]
        return str(item_val).strip().lower() in targets

    if strategy == "fuzzy":
        item_norm = normalize_token(str(item_val))
        return any(normalize_token(t) == item_norm for t in rule_targets(rule_val))

    seps = r'[.\s]+' if strategy == "composite" else r'\s+'
    ngrams = _token_ngrams(_norm_tokens(str(item_val), seps))
    return any(" ".join(_norm_tokens(t, seps)) in ngrams for t in rule_targets(rule_val))


def check_conditions(conditions: dict, item: dict) -> bool:
    """按 FIELD_MATCH_STRATEGY 逐字段检查 conditions (键与 item 键同名)。"""
    conditions = conditions or {}
    for key, strategy in FIELD_MATCH_STRATEGY.items():
        if not match_field(conditions.get(key), item.get(key), strategy):
            return False
    return True
