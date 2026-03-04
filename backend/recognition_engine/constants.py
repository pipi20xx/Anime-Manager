from enum import Enum

class MediaType(Enum):
    MOVIE = "movie"
    TV = "tv"
    UNKNOWN = "unknown"

# 1. 影音规格
PIX_RE = r"(?i)(?<![a-zA-Z0-9])((\d{3,4}[Pp])|([248][Kk])|(\d{3,4}[xX]\d{3,4}))(?![a-zA-Z0-9])"
VIDEO_RE = r"(?i)(?<![a-zA-Z0-9])(H\.?26[45]|[Xx]26[45]|AVC|HEVC|VC[0-9]?|MPEG[0-9]?|Xvid|DivX|AV1)(?![a-zA-Z0-9])"
AUDIO_RE = r"(?i)(?<![a-zA-Z0-9])(DTS-?HD(?:\.MA|[-\s]MA)?|DTS(?:\.MA|[-\s]MA)?|Atmos|TrueHD|AC-?3|DDP|DD\+|DD|AAC|FLAC|Vorbis|Opus|E-?AC-?3|LPCM|PCM)(?:(?:(?:\s*|\.|_|-)(?=[0-9]))?([0-9]\.[0-9](?:\+[0-9]\.[0-9])?|[0-9]ch))?(?![a-zA-Z0-9])"
SOURCE_RE = r"(?i)(?<![a-zA-Z0-9])(WEB-DL|WEBRIP|WEB-RIP|BDRIP|DVDRIP|HDRip|BLURAY|UHDTV|HDTV|HDDVD|REMUX|UHD|Pdtv|Dvdscr|BLU|WEB|BD)(?![a-zA-Z0-9])"
DYNAMIC_RANGE_RE = r"(?i)(?<![a-zA-Z0-9])(HDR10\+|HDR10|HDR|HLG|Dolby\s*Vision|DoVi|DV|SDR|IMAX)(?![a-zA-Z0-9])"
EFFECT_RE = r"(?i)(?<![a-zA-Z0-9])(3D|REPACK|HQ|Remastered|Extended|Uncut|Internal|Pro|Proper)(?![a-zA-Z0-9])"

# 2. 流媒体平台
PLATFORM_RE = r"(?i)(?:-)?(?<![a-zA-Z0-9])(Baha|Bilibili|Netflix|NF|Amazon|AMZN|DSNP|Crunchyroll|CR|Hulu|HBO|YouTube|YT|playWEB|B-Global|friDay|LINETV|KKTV|ATVP|IQ|IQIYI|CRAMZN|iT|ABEMA|HIDIVE)(?![a-zA-Z0-9])|(?:-)?(?<![a-zA-Z0-9])(Disney\+|AppleTV\+)"

# 2.5 字幕标签正则 (用于标题屏蔽)
# [Optimize] 采用“关键词探测法”：只要括号内包含语言+样式特征，即判定为字幕块并整块切除
SUBTITLE_RE = r"(?i)[\[\(\{（【][^\]\}）】]*?(?:(?:[简繁日中英体文语語]{1,10}(?:内封|内嵌|外挂|双语|多语|样式|字幕))|(?:CHS|CHT|GB|BIG5|JPSC|JP_SC|SRTx|ASSx))[^\]\}）】]*?[\]\)\}）】]"

# 2.6 别名与检索词屏蔽正则
ALIAS_RE = r"(?i)[\[\(\{（【]\s*(?:检索用|检索|檢索|别名|別名|又名|附带|附帶|翻译|翻译自)[:：\s]+.*?[\]\)\}）】]"

# 3. 深度噪音
NOISE_WORDS = [
    r"(?i)PTS|JADE|AOD|CHC|(?!LINETV)[A-Z]{1,4}TV[-0-9UVHDK]*",
    r"(?i)[0-9]{1,2}th|[0-9]{1,2}bit|IMAX|BBC|XXX|DC$",
    r"(?i)Ma10p|Hi10p|Hi10|Ma10|10bit|8bit",
    r"年龄限制版|年齡限制版|修正版|无修正|未删减|无修正版|無修正版",
    r"连载|新番|合集|招募翻译|版本|出品|台版|港版|搬运|搬運|[a-zA-Z0-9]+字幕组|[a-zA-Z0-9]+字幕社|[★☆]*[0-9]{1,2}月新番[★☆]*",
    r"(?i)UNCUT|UNRATE|WITH EXTRAS|RERIP|SUBBED|PROPER|REPACK|Complete|Extended|Version|10bit",
    r"(?i)\b(Movie|OVA|ONA|Special|SP|Specials|劇場版|剧场版|OAD|Extra)\b",
    r"(?i)\b[vV][0-9]{1,2}\b|(?i)\bver[0-9]{1,2}\b",
    r"CD[ ]*[1-9]|DVD[ ]*[1-9]|DISK[ ]*[1-9]|DISC[ ]*[1-9]|[ ]+GB",
    r"(?i)YYeTs|人人影视|弯弯字幕组",
    r"(?i)[简繁中日英双雙多]+[体文语語]+[ ]*(MP4|MKV|AVC|HEVC|AAC|ASS|SRT)*",
    r"(?:繁体|繁體|简体|简体|简日|繁日|简中|繁中|简繁|双语|双语|内嵌|內嵌|内封|內封|外挂|外掛)"
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
    r"[ ]+-[ ]+([0-9]{1,4})"
]

SEASON_PATTERNS = [
    r"(?i)\b([0-9]{1,2})(?:st|nd|rd|th)\b(?:\s*Season)?",
    r"(?i)(?<![a-zA-Z])S([0-9]{1,2})(?![a-zA-Z0-9])",
    r"第([一二三四五六七八九十0-9]+)季",
    r"Season[ ]*([0-9]+)"
]

CN_MAP = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
