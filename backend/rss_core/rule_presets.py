# -*- coding: utf-8 -*-
"""
洗版基础规则的内置预设。

预设值均引用 field_options 的派生列表 (源自识别端登记区):
登记区新增规范值时预设自动跟随, 无需维护。
如 "简中字幕" 会随字幕语种登记自动扩充。
"""
from .field_options import AUDIO_ENCODES, SUBTITLES, VIDEO_EFFECTS


def _subs(prefix: str) -> str:
    """所有包含指定语种前缀的字幕规范值, 逗号分隔 (匹配端为 OR 语义)"""
    return ", ".join(s for s in SUBTITLES if s.startswith(prefix))


def _effects(*excluded: str) -> str:
    return ", ".join(e for e in VIDEO_EFFECTS if e not in excluded)


LOSSLESS_AUDIO = [a for a in AUDIO_ENCODES if a in
                  ("Dolby Atmos", "TrueHD", "DTS-HD MA", "DTS-HD", "FLAC", "LPCM")]

RULE_PRESETS = [
    {"name": "1080P", "description": "仅 1080P 规格",
     "conditions": {"resolution": "1080P"}},
    {"name": "4K", "description": "仅 4K 规格",
     "conditions": {"resolution": "4K"}},
    {"name": "4K HDR", "description": "4K + 任意 HDR / 杜比视界",
     "conditions": {"resolution": "4K", "video_effect": _effects("SDR", "IMAX")}},
    {"name": "4K 原盘/Remux", "description": "4K + Blu-ray / Remux 片源",
     "conditions": {"resolution": "4K", "source": "Blu-ray, Remux"}},
    {"name": "WEB-DL", "description": "流媒体 WEB-DL 片源",
     "conditions": {"source": "WEB-DL"}},
    {"name": "简中字幕", "description": "任意含简体的字幕版本",
     "conditions": {"subtitle": _subs("简")}},
    {"name": "繁中字幕", "description": "任意含繁体的字幕版本",
     "conditions": {"subtitle": _subs("繁")}},
    {"name": "无损/全景声音频", "description": "Atmos / TrueHD / DTS-HD / FLAC / LPCM",
     "conditions": {"audio_encode": ", ".join(LOSSLESS_AUDIO)}},
    {"name": "杜比视界", "description": "仅 Dolby Vision",
     "conditions": {"video_effect": "Dolby Vision"}},
]


def get_rule_presets() -> list:
    return RULE_PRESETS
