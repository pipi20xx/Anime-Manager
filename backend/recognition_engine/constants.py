from enum import Enum

class MediaType(Enum):
    MOVIE = "movie"
    TV = "tv"
    UNKNOWN = "unknown"
    AUTO = "auto"

# 1. 影音规格
PIX_RE = r"(?i)(?<![a-zA-Z0-9])((\d{3,4}[Pp])|([248][Kk])|(\d{3,4}[xX]\d{3,4}))(?![a-zA-Z0-9])"

# ---------- 规格值登记区 (识别归一化与外部选项的唯一事实来源) ----------
# 在识别逻辑中新增/调整一个规范值时, 只改这里:
# 正则由登记表生成, 洗版规则/订阅筛选的下拉选项也由此派生 (rss_core/field_options.py)。

# --- 介质来源: 识别 token (顺序敏感: 长词在前, 如 WEB-DL 必须先于 WEB) + 归一化映射 ---
SOURCE_TOKENS = ["WEB-DL", "WEBRIP", "WEB-RIP", "BDRIP", "DVDRIP", "HDRip", "BLURAY",
                 "UHDTV", "HDTV", "HDDVD", "REMUX", "UHD", "Pdtv", "Dvdscr", "BLU", "WEB", "BD"]
SOURCE_VALUE_MAP = {
    "WEBRIP": "WebRip", "WEB-RIP": "WebRip", "WEBDL": "WEB-DL", "WEB-DL": "WEB-DL",
    "BLURAY": "Blu-ray", "BD": "Blu-ray", "BLU": "Blu-ray",
    "HDTV": "HDTV", "UHDTV": "UHDTV", "DVDRIP": "DVD-Rip", "BDRIP": "BD-Rip",
    "REMUX": "Remux", "UHD": "UHD", "PDTV": "PDTV", "DVDSCR": "DVD-SCR",
    "WEB": "WEB", "HDDVD": "HDDVD",
}
SOURCE_RE = r"(?i)(?<![a-zA-Z0-9])(" + "|".join(SOURCE_TOKENS) + r")(?![a-zA-Z0-9])"

# --- 视频编码: 识别片段 + 归一化规则 ---
VIDEO_ENCODE_PATTERNS = [r"H\.?26[45]", r"[Xx]26[45]", "AVC", "HEVC", r"VC[0-9]?", r"MPEG[0-9]?", "Xvid", "DivX", "AV1"]
# (命中关键字组, 规范值); 组内任一关键字命中即取该值
VIDEO_ENCODE_RULES = [
    (("265", "HEVC"), "H.265"),
    (("264", "AVC"), "H.264"),
    (("AV1",), "AV1"),
]
# 不走归一化规则、原文返回的编码 (供下拉展示, 与 VIDEO_ENCODE_PATTERNS 对应)
VIDEO_ENCODE_PASSTHROUGH = ["VC1", "MPEG2", "MPEG4", "Xvid", "DivX"]
VIDEO_RE = r"(?i)(?<![a-zA-Z0-9])(" + "|".join(VIDEO_ENCODE_PATTERNS) + r")(?![a-zA-Z0-9])"
AUDIO_RE = r"(?i)(?<![a-zA-Z0-9])(DTS-?HD(?:\.MA|[-\s]MA|MA)?|DTS(?:\.MA|[-\s]MA|MA)?|DTS|Atmos|TrueHD|THD|AC-?3|DDP|DD\+|DD|AAC|FLAC|Vorbis|Opus|E-?AC-?3|LPCM|PCM)(?:(?:(?:\s*|\.|_|-|x)(?=[0-9]))?([0-9]\.[0-9](?:\+[0-9]\.[0-9])?|[0-9]ch|[0-9]))?(?![a-zA-Z0-9])"

# --- 音频编码: 归一化规则 (顺序敏感, codec_raw 已去 "."/"-"/"_") ---
# (匹配方式: in=包含/eq=全等, 关键字, 规范值)
AUDIO_CODEC_RULES = [
    ("in", "ATMOS", "Dolby Atmos"),
    ("in", "DTSHDMA", "DTS-HD MA"), ("in", "DTSMA", "DTS-HD MA"),
    ("in", "DTSHD", "DTS-HD"),
    ("in", "EAC3", "E-AC-3"), ("in", "DDP", "E-AC-3"), ("in", "DD+", "E-AC-3"),
    ("in", "AC3", "AC-3"), ("eq", "DD", "AC-3"),
    ("in", "TRUEHD", "TrueHD"), ("in", "THD", "TrueHD"),
    ("in", "LPCM", "LPCM"), ("in", "PCM", "LPCM"),
    ("eq", "DTS", "DTS"),
    ("in", "AAC", "AAC"), ("in", "FLAC", "FLAC"), ("in", "OPUS", "Opus"), ("in", "VORBIS", "Vorbis"),
]

# --- 视频特效 (动态范围): 每组为独立的 if, 组内键按优先级取第一个命中的 (elif 语义) ---
# ({命中键: 规范值}, 标题识别片段列表)
DYNAMIC_RANGE_DEFS = [
    ({"DOVI": "Dolby Vision", "DV": "Dolby Vision", "DOLBYVISION": "Dolby Vision"},
     [r"Dolby\s*Vision", "DoVi", "DV"]),
    ({"HDR10+": "HDR10+", "HDR10": "HDR10", "HDR": "HDR"},
     [r"HDR10\+", "HDR10", "HDR"]),
    ({"HLG": "HLG"}, ["HLG"]),
    ({"IMAX": "IMAX"}, ["IMAX"]),
    ({"SDR": "SDR"}, ["SDR"]),
]
DYNAMIC_RANGE_RE = r"(?i)(?<![a-zA-Z0-9])(" + "|".join(
    p for _, frags in DYNAMIC_RANGE_DEFS for p in frags) + r")(?![a-zA-Z0-9])"

# --- 分辨率 (extract_resolution 的输出除 "{min_d}P" 外均为固定形式) ---
COMMON_RESOLUTIONS = ["4K", "1440P", "1080P", "720P", "540P", "480P", "360P"]

# --- 字幕语言 (extract_subtitle_lang 的合成词表) ---
SUB_LANG_ORDER = ["简", "繁", "日", "英"]
SUB_LANG_FULL = {"简": "简体", "繁": "繁体", "日": "日文", "英": "英文"}
SUB_TYPES = ["内封", "内嵌", "外挂", "双语"]
# ------------------------------------------------------------

EFFECT_RE = r"(?i)(?<![a-zA-Z0-9])(3D|REPACK|HQ|Remastered|Extended|Uncut|Internal|Pro|Proper)(?![a-zA-Z0-9])"

# 2. 流媒体平台
# 识别 token (顺序敏感, 同上) + 归一化映射 (键为 token 大写)
PLATFORM_TOKENS = ["Baha", "Bilibili", "Netflix", "NF", "Amazon", "AMZN", "DSNP",
                   "Crunchyroll", "CR", "Hulu", "HBO", "YouTube", "YT", "playWEB",
                   "B-Global", "friDay", "LINETV", "KKTV", "ATVP", "IQ", "IQIYI",
                   "CRAMZN", "iT", "ABEMA", "HIDIVE", "Viu", "CATCHPLAY"]
PLATFORM_PLUS_TOKENS = ["Disney+", "AppleTV+"]
PLATFORM_VALUE_MAP = {
    "CR": "Crunchyroll", "NF": "Netflix", "AMZN": "Amazon", "ATVP": "AppleTV+",
    "DSNP": "Disney+", "IT": "iTunes", "LINETV": "LINE TV", "ABEMA": "AbemaTV",
    "IQ": "iQIYI", "IQIYI": "iQIYI", "CRAMZN": "Amazon",
}
PLATFORM_RE = (
    r"(?i)(?:-)?(?<![a-zA-Z0-9])(" + "|".join(PLATFORM_TOKENS) + r")(?![a-zA-Z0-9])"
    r"|(?:-)?(?<![a-zA-Z0-9])(" + "|".join(
        t.replace("+", r"\+") for t in PLATFORM_PLUS_TOKENS) + r")"
)

# 2.5 字幕标签正则 (用于标题屏蔽)
# [Optimize] 采用"关键词探测法"：只要括号内包含语言+样式特征，即判定为字幕块并整块切除
SUBTITLE_RE = r"(?i)[\[\(\{（【][^\]\}）】]*?(?:(?:[简繁日中英体文语語]{1,10}(?:内封|内嵌|外挂|双语|多语|样式|字幕))|(?:CHS|CHT|GB|BIG5|JPSC|JP_SC|SRTx|ASSx|JPTC|JPSC|JP_TC|CHS_JP|CHT_JP|CHSJP|CHTJP))[^\]\}）】]*?[\]\)\}）】]"

# 2.6 别名与检索词屏蔽正则
ALIAS_RE = r"(?i)[\[\(\{（【]\s*(?:检索用|检索|檢索|别名|別名|又名|附带|附帶|翻译|翻译自)[:：\s]+.*?[\]\)\}）】]"

# 3. 深度噪音
NOISE_WORDS = [
    r"(?i)PTS|JADE|AOD|CHC|(?!LINETV)[A-Z]{1,4}TV[-0-9UVHDK]*",
    r"(?i)[0-9]{1,2}bit|BBC|XXX|DC$",
    r"(?i)Ma10p|Hi10p|Hi10|Ma10|10bit|8bit",
    r"(?i)Full-?HD",
    r"(?i)\(vfr\)|\(cfr\)|\(VFR\)|\(CFR\)",
    r"年龄限制版|年齡限制版|修正版|无修正|未删减|无修正版|無修正版",
    r"连载|新番|合集|招募翻译|版本|出品|台版|港版|搬运|搬運|[a-zA-Z0-9]+字幕组|[a-zA-Z0-9]+字幕社|[★☆]*[0-9]{1,2}月新番[★☆]*",
    r"(?i)UNCUT|UNRATE|WITH EXTRAS|RERIP|SUBBED|PROPER|REPACK|Complete|Extended|Version|10bit",
    r"(?i)\b(Movie|OVA|ONA|Special|SP|Specials|劇場版|剧场版|OAD|Extra)\b",
    r"(?i)\b[vV][0-9]{1,2}\b|(?i)\bver[0-9]{1,2}\b",
    r"CD[ ]*[1-9]|DVD[ ]*[1-9]|DISK[ ]*[1-9]|DISC[ ]*[1-9]|[ ]+GB",
    r"(?i)YYeTs|人人影视|弯弯字幕组",
    r"(?i)[简繁中日英双雙多]+[体文语語]+[ ]*(MP4|MKV|AVC|HEVC|AAC|ASS|SRT)*",
    r"(?:简繁日内封|简繁日内嵌|简繁日外挂|简繁日双语|简繁英内封|简繁英内嵌|简繁英外挂|简繁英双语|简日繁日内封|简日繁日内嵌|繁体|繁體|简体|简体|简日|繁日|简中|繁中|简繁|双语|双语|内嵌|內嵌|内封|內封|外挂|外掛)",
    r"(?i)\[(?:JPN|CHS|CHT|ENG|JP|CN|EN|TC|SC)\]"
]

# 4. 发布组排除词
NOT_GROUPS = "1080P|720P|4K|2160P|H264|H265|X264|X265|AVC|HEVC|AAC|DTS|AC3|DDP|ATMOS|WEB-DL|WEBRIP|BLURAY|BD|HD|HDR|SDR|DV|TRUEHD|HIRES|10BIT|EAC3|UHD 4K|Ma10p|Hi10p|Hi10|Ma10|(?i)REMUX"

# 4.5 发布组语义特征词 (用于提高首部制作组识别的置信度)
GROUP_KEYWORDS = r"组|組|社|制作|製作|字幕|工作|家族|学园|學園|压制|壓制|发布|發佈|协会|協會|联盟|聯盟|论坛|論壇|中心|屋|团|團|亭|园|園"

# 5. 季集匹配
EPISODE_PATTERNS = [
    r"(?i)EP?([0-9]{2,4})", 
    r"(?i)DR([0-9]{2,4})",
    r"第[ ]*([0-9]{1,4})[ ]*[集话話期幕]", 
    r"[[]([0-9]{1,4})[]]",
    r"\[(\d{1,4})[^\]\d][^\]]*\]",
    r"[ ]+-[ ]+([0-9]{1,4})"
]

SEASON_PATTERNS = [
    r"(?i)\b([0-9]{1,2})(?:st|nd|rd|th)\b\s+Season",
    # [Fix] 优先匹配 SxxExx 标准季集格式 (如 S10E08)，提取季号
    r"(?i)(?<![a-zA-Z])S([0-9]{1,2})E[0-9]{1,4}",
    r"(?i)(?<![a-zA-Z])S([0-9]{1,2})(?![a-zA-Z0-9])",
    r"第([一二三四五六七八九十0-9]+)季",
    r"Season[ ]*([0-9]+)"
]

CN_MAP = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
