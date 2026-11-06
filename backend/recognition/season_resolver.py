"""季号 / 集数的确定性推算（不依赖 AI）。

背景
----
现有识别内核只用正则从文件名里抠一个数字当季号（`SEASON_PATTERNS`），抠不到就默认 1。
但 TMDB 的季表里其实写着每季的名字、集数、首播日期 —— 这些足以把绝大多数季号算对，
不需要调模型。

输入：TMDB 季表 + 文件名（季标 / 标题 / 原始集数）
输出：SeasonDecision(season, episode, reason, detail)

设计原则
--------
1. **证据优先**：每一步都要有可指认的证据；证据不足返回 None，由调用方保留原值。
2. **纯函数**：无 I/O、无全局状态，可以用历史文件名离线做回归测试。
3. **不猜编号模式**：per_season / absolute 两种假设都试，用「集数 ≤ 该季集数」筛掉不成立的。

判定顺序（先强证据，后弱证据）
------------------------------
0. 只有一季                       → 直接采用
1. 季名对齐（中/英/日三语）        → 强证据，唯一命中才采纳；序号由季标或标题尾数给出
2. 标题尾数（"Edgerunners 2"）    → 必须有季名佐证，否则数字属于标题
3. 季标 + 季名佐证                → 季标给序号，季名给对齐
3.5 年份对齐（文件名年份）         → 唯一命中才采纳（强）
4. 集数边界校验                   → 有季标才走 per_season；无季标只做 absolute（弱证据，仅记录）
5. 首播日期                       → 取不晚于参考日期的最新一季（弱证据）
6. 跨年续播偏移                   → 季中结局/大结局后的第一集起算，换算成该季连续集号（弱证据，需逐集数据）
7. 都不成立                       → None（不猜）
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# 归一化后参与比对的最短长度：太短的片段（如 "2"、"ii"）只会制造误匹配
MIN_FRAGMENT = 4

_CN_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
          "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
_EN_ORDINAL = {
    1: ("first", "one"), 2: ("second", "two"), 3: ("third", "three"),
    4: ("fourth", "four"), 5: ("fifth", "five"), 6: ("sixth", "six"),
    7: ("seventh", "seven"), 8: ("eighth", "eight"), 9: ("ninth", "nine"),
    10: ("tenth", "ten"),
}


# 强证据：证据不足时不猜，可放心自动应用。on 模式下只自动应用这些理由。
# 注意：boundary:absolute 不在此列——它假设「绝对集数编号」，证据不足时容易把
# 漏标季号的文件误改，on 模式只记录不应用。
# boundary:per-season 在列，但前提是文件名真的给了季标（见 resolve_season 第 4 步）：
# 没有季标时「默认 base=1」只是把待验假设当结论，不能算证据。
# boundary:year-calendar（整季没有分段标记，只按日历跨年推的）同样不在列：日历不等于 cour 边界。
STRONG_REASONS = frozenset({
    "single-season",
    "name-match",
    "title-suffix",
    "marker",
    "year-match",
    "boundary:per-season",
    # 跨年续播：靠 TMDB 的「季中结局 / 本季大结局」分段标记 + 该段首集播出年份，
    # 且只有季号已定、文件名带年份才走到这一步，证据链完整
    "boundary:year-offset",
})


def _confidence(reason: str) -> str:
    """把判定理由映射成置信度，供 on 模式决定是否自动应用。"""
    if reason in STRONG_REASONS:
        return "high"
    if reason in ("latest-by-air-date", "boundary:absolute", "boundary:year-calendar"):
        return "low"
    return "none"


@dataclass
class SeasonDecision:
    season: Optional[int] = None
    episode: Optional[int] = None
    reason: str = "ambiguous"
    detail: str = ""
    confidence: str = "none"  # high / low / none（on 模式只自动应用 high）
    align: str = ""  # 「标题候选 × 季名」比对明细（多行文本，供日志/前端展示）

    @property
    def ok(self) -> bool:
        return self.season is not None


def normalize_text(value: Any) -> str:
    """统一大小写/全半角，去掉标点与空白，只留字母数字与汉字。"""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).lower()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", text)


def _ordinal_forms(number: int) -> Tuple[str, ...]:
    """一个季号可能出现的所有写法（用于季名比对）。"""
    forms = [str(number), f"{number}st", f"{number}nd", f"{number}rd", f"{number}th"]
    forms.extend(_EN_ORDINAL.get(number, ()))
    for roman, value in _ROMAN.items():
        if value == number:
            forms.append(roman)
    return tuple(forms)


def extract_season_marker(filename: str) -> Optional[int]:
    """从文件名里抽季标数字。比内核的 SEASON_PATTERNS 多覆盖 第N期 / Part N / 罗马。"""
    if not filename:
        return None
    text = unicodedata.normalize("NFKC", filename)

    patterns = (
        r"(?i)(?<![a-z])s(\d{1,2})(?:e\d{1,4})?(?![a-z0-9])",
        r"第\s*([一二三四五六七八九十0-9]{1,3})\s*[季期]",
        r"(?i)(\d{1,2})(?:st|nd|rd|th)\s+season",
        r"(?i)season\s*(\d{1,2})",
        r"(?i)part\s*(\d{1,2})",
        r"(?i)(?<![a-z])([ivx]{1,4})(?![a-z])\s*(?:期|season)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(1).lower()
        if raw in _CN_NUM:
            return _CN_NUM[raw]
        if raw in _ROMAN:
            return _ROMAN[raw]
        if raw.isdigit():
            return int(raw)
    return None


# 标题里的「季序号」不是季标，而是标题的一部分：
#   'Cyberpunk Edgerunners 2'            → 结尾的裸数字
#   '[ANi] 冰劍的魔術師將要統一世界 2 - 05'  → 紧跟集数之前的裸数字
# 只在 2-9 里找：1 和「压根没标季号」没法区分。
_TITLE_TAIL_RE = re.compile(r"(?<=[^\d\s])\s+([2-9])$")
_TITLE_BEFORE_EP_RE = re.compile(r"(?<=[^\d\s])\s+([2-9])\s*[-–—~]\s*\d{1,4}(?!\d)")


def _title_suffix_number(candidates: Iterable[str]) -> Optional[int]:
    """候选标题里作为「季序号」出现的尾数（区别于集数、也区别于季标）。

    命中之后仍不算数：还要 TMDB 季表里真有这一季、且该季季名带同一序号
    （见 resolve_season 第 1 步），才当作证据。
    """
    for candidate in candidates:
        text = unicodedata.normalize("NFKC", str(candidate or ""))
        for pattern in (_TITLE_TAIL_RE, _TITLE_BEFORE_EP_RE):
            match = pattern.search(text)
            if match:
                return int(match.group(1))
    return None


def _season_fields(season: Dict[str, Any]) -> Tuple[int, int, List[str], str]:
    """(季号, 集数, 季名候选, 首播日期)"""
    number = season.get("season_number")
    try:
        number = int(number)
    except (TypeError, ValueError):
        return -1, 0, [], ""
    count = season.get("episode_count")
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 0
    names = [
        str(name).strip()
        for name in (season.get("name"), season.get("name_en"), season.get("name_ja"))
        if name
    ]
    return number, count, names, str(season.get("air_date") or "")


def _lcs_len(left: str, right: str) -> int:
    """最长公共子串长度（归一化后），用来衡量标题与季名的重合程度。"""
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    best = 0
    for char in left:
        current = [0] * (len(right) + 1)
        for index, other in enumerate(right, 1):
            if char == other:
                current[index] = previous[index - 1] + 1
                if current[index] > best:
                    best = current[index]
        previous = current
    return best


def _candidate_list(title_parts: Any) -> List[str]:
    """统一成候选标题列表（去掉空值、保留原顺序）。"""
    if title_parts is None:
        return []
    if isinstance(title_parts, str):
        items = [title_parts]
    else:
        items = list(title_parts)
    return [str(item).strip() for item in items if item and str(item).strip()]


def _name_fragment_score(title_parts: Any, season_names: Iterable[str]) -> int:
    """标题与季名的最长公共子串长度（对所有候选标题取最大值）。

    用长度而不是布尔值：像 "Cyberpunk Edgerunners 2" 这种，
    S2 的季名完全相等（22），S1 只是前缀（20），靠长度就能分出具体程度。

    为什么要多个候选：内核清理标题时会把尾部的 "2" 当集数噪声剥掉
    （"Cyberpunk Edgerunners 2" → "Cyberpunk Edgerunners"），
    只拿它去比对就会让 S1/S2 并列。特权标题和原始文件名里通常还留着。
    """
    norms = [normalize_text(item) for item in _candidate_list(title_parts)]
    norms = [item for item in norms if len(item) >= MIN_FRAGMENT]
    if not norms:
        return 0
    best = 0
    for name in season_names:
        norm = normalize_text(name)
        if len(norm) < MIN_FRAGMENT:
            continue
        for target in norms:
            best = max(best, _lcs_len(target, norm))
    return best


def _ordinal_in_names(number: int, season_names: Iterable[str]) -> bool:
    digits = str(number)
    for name in season_names:
        norm = normalize_text(name)
        if not norm:
            continue
        # 先把"季/第/season/シーズン"这类壳去掉，剩下的纯序号直接比
        compact = norm
        for word in ("season", "シーズン", "第", "季", "期"):
            compact = compact.replace(word, "")
        if compact and compact == digits:
            return True
        # 序数词（second / 2nd / ii …）
        for form in _ordinal_forms(number):
            if form in _ROMAN:
                # 罗马数字太短，只认结尾（"…World II" 结尾是 II；"…World" 不是）
                if len(form) >= 2 and norm.endswith(form):
                    return True
            elif len(form) >= 3 and form in norm:
                return True
    return False


def _absolute_episode_map(
    raw_episode: int, seasons: List[Tuple[int, int, List[str], str]]
) -> Optional[Tuple[int, int]]:
    """绝对集数 → (季号, 季度内集数)，按各季集数累积切分。"""
    acc = 0
    for number, count, _names, _air in seasons:
        if number <= 0 or count <= 0:
            continue
        if raw_episode <= acc + count:
            return number, raw_episode - acc
        acc += count
    return None


def _coerce_episode(value: Any) -> Optional[int]:
    """集数可能是 str / float（合集用 48.5 这种），只接受「整数值」的。"""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() and number > 0 else None


def _coerce_year(value: Any) -> Optional[int]:
    """文件名年份可能是 str / int，只接受 1900-2100 的整数。"""
    try:
        year = int(float(value))
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


def _air_year_matches(air: str, file_year: int) -> bool:
    """该季首播日期的年份是否等于文件名年份。"""
    try:
        return date.fromisoformat(air[:10]).year == file_year
    except (TypeError, ValueError):
        return False


def _best_name(title_parts: Any, season_names: Iterable[str]) -> str:
    """挑出与标题最贴近的季名，仅用于日志展示。"""
    norms = [normalize_text(item) for item in _candidate_list(title_parts)]
    best_name = ""
    best_score = -1
    for name in season_names:
        norm = normalize_text(name)
        score = max((_lcs_len(target, norm) for target in norms), default=0)
        if score > best_score:
            best_name, best_score = name, score
    return best_name


def _align_debug(candidates: List[str], parsed) -> str:
    """「标题候选 × 季名」比对明细，方便人工核对季名对齐为什么命中/没命中。"""
    lines = [f"标题候选: {' | '.join(candidates) if candidates else '—'}"]
    for number, _count, names, _air in parsed:
        names_str = " / ".join(names) if names else "—"
        frag = _name_fragment_score(candidates, names)
        lines.append(f"S{number} 季名: {names_str}（匹配分 {frag}）")
    return "\n".join(lines)


def _episode_year(episode: Dict[str, Any]) -> Optional[int]:
    """单集的播出年份；没有/不是合法日期时返回 None。"""
    air = str((episode or {}).get("air_date") or "")
    try:
        return date.fromisoformat(air[:10]).year
    except (TypeError, ValueError):
        return None


# TMDB episode_type 里表示「这一段播完了」的标记：季中结局 / 本季大结局。
# 它们后面的第一集才是下一段（下一 cour）的起点——这才是番剧分段的真实边界。
_SEASON_BREAK_TYPES = ("mid_season", "finale")


def _year_offset_start(
    episodes: List[Dict[str, Any]], file_year: int
) -> Optional[Tuple[int, str]]:
    """该季在 file_year 年续播的起始集号，返回 (起始集号, 依据说明)。

    **先看 TMDB 的 episode_type**：`mid_season`（季中结局）/ `finale`（本季大结局）
    之后的第一集就是下一段的起点。日历跨年只是它的副产品——2025-10 开播的半年番
    因为停播周多，新年第一集往往并不是 cour 起点，只有分段标记对得上才是真的换段。

    整季都没有可用的分段标记时，才退回「air_date 落在文件年份的第一集」这个日历判据
    （仍要求第 k-1 集属于上一年，挡掉断档/特别篇造成的假边界），依据说明返回空串，
    由调用方降级为弱证据。
    """
    by_number: Dict[int, Dict[str, Any]] = {}
    for episode in episodes or []:
        number = _coerce_episode((episode or {}).get("episode"))
        if number is None:
            continue
        by_number[number] = episode or {}
    if not by_number:
        return None
    ordered = sorted(by_number)
    last = ordered[-1]

    saw_break_marker = False
    for number in ordered:
        marker = str(by_number[number].get("episode_type") or "").lower()
        if marker not in _SEASON_BREAK_TYPES:
            continue
        if number >= last:  # 最后一集的大结局不算分段
            continue
        saw_break_marker = True
        start = number + 1
        # 分段后的第一集必须落在文件年份，否则说明文件名年份和这段续播无关
        if _episode_year(by_number.get(start) or {}) == file_year:
            label = "季中结局" if marker == "mid_season" else "本季大结局"
            return start, f"第 {number} 集{label}"
    if saw_break_marker:
        # 有分段标记、但对不上文件年份 → 证据互相矛盾，不猜
        return None

    # 兜底：整季没有分段标记时，按日历跨年判断
    start = next(
        (number for number in ordered if _episode_year(by_number[number]) == file_year),
        None,
    )
    if start is None or start <= 1:
        return None
    if _episode_year(by_number.get(start - 1) or {}) != file_year - 1:
        return None
    return start, ""


def _season_episode_count(seasons: Sequence[Dict[str, Any]], number: int) -> int:
    for item in seasons or []:
        try:
            if int(item.get("season_number")) == number:
                return int(item.get("episode_count") or 0)
        except (TypeError, ValueError):
            continue
    return 0


def _shift_episode_for_year(
    decision: SeasonDecision,
    seasons: Sequence[Dict[str, Any]],
    season_episodes: Optional[Dict[int, List[Dict[str, Any]]]],
    file_year: Optional[int],
    raw_episode: Optional[int],
) -> Optional[SeasonDecision]:
    """跨年续播偏移：某一季被 TMDB 并成一季、新年份续播时集数又从 1 数起。

    例：S1 共 24 集，第 13 集是季中结局，第 14 集起 2026 年续播；
    文件名 `… (2026) [03]` 实际是该季第 16 集 → 03 + (14-1)。

    只改集数、不改季号：季号仍由前面的规则决定，这里做的只是同一季内的集号校正。

    可信度分两档（走这条路本身已经很窄）：
    - 有 TMDB 分段标记（季中结局/本季大结局）且标记后第一集播于文件年份 → 强证据；
    - 整季没标记、只能按日历跨年推断 → 弱证据，只记录。
    """
    if not season_episodes or decision.season is None:
        return None
    year = _coerce_year(file_year)
    episode = _coerce_episode(raw_episode)
    if year is None or episode is None:
        return None
    # 集数已经被别的规则换算过（如绝对集数映射）就不再叠加，避免双重偏移
    if decision.episode is not None and _coerce_episode(decision.episode) != episode:
        return None
    episodes = season_episodes.get(decision.season)
    found = _year_offset_start(episodes, year)
    if not found:
        return None
    start, source = found
    total = _season_episode_count(seasons, decision.season) or len(episodes or [])
    shifted = episode + start - 1
    if total and shifted > total:
        return None
    reason = "boundary:year-offset" if source else "boundary:year-calendar"
    basis = f"分段标记：{source}" if source else "整季无分段标记，按日历跨年推断"
    detail = (
        f"跨年续播偏移：{year} 年第 {episode} 集按该季连续编号应为第 {shifted} 集"
        f"（该季自第 {start} 集起才是 {year} 年续播的那一段；{basis}）；原判定：{decision.reason}"
    )
    return SeasonDecision(
        decision.season,
        shifted,
        reason,
        detail,
        confidence=_confidence(reason),
        align=decision.align,
    )


def resolve_season(
    seasons: Sequence[Dict[str, Any]],
    *,
    filename: str = "",
    title_parts: Any = None,
    title_part: str = "",
    raw_episode: Optional[int] = None,
    ref_date: Optional[str] = None,
    file_year: Optional[int] = None,
    season_episodes: Optional[Dict[int, List[Dict[str, Any]]]] = None,
) -> SeasonDecision:
    """根据 TMDB 季表推算季号（和必要时换算集数）。

    seasons: [{season_number, name, name_en, name_ja, episode_count, air_date}, ...]
    title_parts: 标题候选（可传 list）。建议把 privileged_title / processed_name /
                 en_name / cn_name 都传进来——内核清理标题时会把尾部序号当噪声剥掉，
                 只用一个字段容易丢关键信息。
    filename: 原始文件名，作为最后一个候选参与比对
    raw_episode: 文件名解析出的原始集数
    ref_date: "YYYY-MM-DD"，判断 air_date 时的参考日；缺省用今天
    file_year: 文件名解析出的年份（如 2026），用于「年份对齐」判定；缺省不启用
    season_episodes: {季号: [{episode, air_date, ...}]}，来自 /tv/{id}/season/{n}。
                 传了才启用「跨年续播偏移」，不传就完全不用——纯函数部分不自己发请求。

    返回 season 为 None 表示「证据不足，不采信」。
    """
    decision = _resolve_season_core(
        seasons,
        filename=filename,
        title_parts=title_parts,
        title_part=title_part,
        raw_episode=raw_episode,
        ref_date=ref_date,
        file_year=file_year,
    )
    shifted = _shift_episode_for_year(decision, seasons, season_episodes, file_year, raw_episode)
    return shifted or decision


def _resolve_season_core(
    seasons: Sequence[Dict[str, Any]],
    *,
    filename: str = "",
    title_parts: Any = None,
    title_part: str = "",
    raw_episode: Optional[int] = None,
    ref_date: Optional[str] = None,
    file_year: Optional[int] = None,
) -> SeasonDecision:
    """判定主体（只读季表与文件名）。跨年续播的集号校正见 resolve_season。"""
    parsed = [_season_fields(s) for s in (seasons or [])]
    # 特别篇（S0）不参与季号判定
    parsed = [item for item in parsed if item[0] > 0]
    parsed.sort(key=lambda item: item[0])
    raw_episode = _coerce_episode(raw_episode)
    file_year = _coerce_year(file_year)

    notes: List[str] = []
    align: str = ""

    def _decision(season, episode, reason, detail) -> SeasonDecision:
        if notes:
            detail = "；".join([*notes, detail])
        return SeasonDecision(season, episode, reason, detail, confidence=_confidence(reason), align=align)

    if not parsed:
        return _decision(None, raw_episode, "no-seasons", "TMDB 没有可用的季数据")

    # 候选标题：标题类字段在前，原始文件名兜底
    candidates = _candidate_list(title_parts)
    if title_part:
        candidates.append(title_part)
    if filename:
        candidates.append(filename)
    candidates = list(dict.fromkeys(item for item in candidates if item))
    align = _align_debug(candidates, parsed)

    marker = extract_season_marker(filename) if filename else None

    # 0. 只有一季：没有歧义。但 TMDB 常把多季合并成一季（如 Re:0 全集并到 S1），
    #    文件名里明确的季标（第四季 / Season 4 / Part 4）就是冲突证据，不能强行压回 S1。
    if len(parsed) == 1:
        number, count, names, _air = parsed[0]
        if marker is not None and marker != number:
            return _decision(
                None, raw_episode, "single-season-merge",
                f"TMDB 只有一季（S{number}，{count or '?'} 集）但文件名明确标为 S{marker}，"
                f"疑似 TMDB 合并季，保留原季号",
            )
        detail = f"TMDB 只有一季（S{number}，{count or '?'} 集）"
        if raw_episode and count and raw_episode > count:
            detail += f"；集数 {raw_episode} 超出该季集数，请留意 TMDB 数据"
        return _decision(number, raw_episode, "single-season", detail)

    by_number = {number: (number, count, names, air) for number, count, names, air in parsed}

    # 序号线索：文件名季标最硬；没有季标时退一步用「标题尾数」（…世界 2 - 05 / Edgerunners 2）。
    # 两者都只是「线索」——必须由 TMDB 某一季的季名自己带同一序号才算该季的证据，
    # 否则光凭一个数字就定季号跟瞎猜没区别。
    ordinal_hint = marker if marker is not None else _title_suffix_number(candidates)

    # 1. 季名对齐（强证据）：标题片段 + 序号词，同时命中者优先
    scored = []
    for number, count, names, _air in parsed:
        frag = _name_fragment_score(candidates, names)
        ordinal_hit = bool(
            ordinal_hint is not None
            and ordinal_hint == number
            and _ordinal_in_names(number, names)
        )
        if frag >= MIN_FRAGMENT or ordinal_hit:
            scored.append((frag, ordinal_hit, number, names))
    if scored:
        def _year_bonus(item) -> int:
            _frag, _o, number, _names = item
            info = by_number.get(number)
            return 1 if (file_year and info and _air_year_matches(info[3], file_year)) else 0

        def _rank(item):
            frag, ordinal_hit, _number, _names = item
            has_frag = frag >= MIN_FRAGMENT
            # 标题片段与序号词同时命中 > 仅标题片段 > 仅序号词；三者同分时年份吻合者优先
            tier = 2 if (has_frag and ordinal_hit) else (1 if has_frag else 0)
            return (tier, frag, _year_bonus(item))

        # 并列判定看 (tier, frag, year)：季号大小不能用来「打破并列」（否则会把
        # 无区分度的情况悄悄判成 S1），但文件名年份是真实证据，可只在同分时优先选年份吻合的季。
        scored.sort(key=lambda item: (_rank(item), -item[2]), reverse=True)
        top = scored[0]
        runner_up = scored[1] if len(scored) > 1 else None
        if runner_up is None or _rank(top) != _rank(runner_up):
            frag, ordinal_hit, number, names = top
            season_info = by_number[number]
            count = season_info[1]
            episode = raw_episode
            # 集数边界校验：超界不能默默放过（也不该硬猜）。
            # 判断依据是「文件自己有没有说这是哪一季」：
            # - 说了（季标 / 标题尾数）→ 集数按季度内理解，超界多半是 TMDB 集数没跟上，
            #   集数原样保留，别把 E14 猜成 E02；
            # - 没说 → 集数可能是绝对编号，但只有换算结果仍落在同一季才采纳，
            #   否则（季名说 S2、绝对集数却指向 S1）只记录，不擅自改集数。
            if raw_episode and count and raw_episode > count:
                mapped = _absolute_episode_map(raw_episode, parsed)
                if ordinal_hint is None and mapped and mapped[0] == number:
                    episode = mapped[1]
                else:
                    notes.append(
                        f"集数 {raw_episode} 超出 S{number} 的 {count} 集（集数原样保留）"
                    )
            year_hit = bool(file_year and _air_year_matches(season_info[3], file_year))
            hint_label = ""
            if ordinal_hit:
                hint_label = "+序号词(季标)" if marker is not None else "+序号词(标题尾数)"
            detail = (
                f"季名命中（{_best_name(candidates, names)}）"
                + hint_label
                + (f"+年份佐证（{file_year}）" if year_hit else "")
                + (f"，集数 {raw_episode}→{episode}" if episode != raw_episode else "")
            )
            return _decision(number, episode, "name-match", detail)

        # 并列：说明候选标题里缺区分信息，记下来方便排查
        tied = "、".join(f"S{number}={frag}" for frag, _o, number, _n in scored[:3])
        notes.append(f"季名对齐并列（{tied}），不采信")

    # 2. 标题尾数：只有当某一季的季名与标题高度重合时才采纳（序号词命中已在第 1 步处理）
    for candidate in candidates:
        tail = _TITLE_TAIL_RE.search(unicodedata.normalize("NFKC", candidate or ""))
        if not tail:
            continue
        number = int(tail.group(1))
        season_info = by_number.get(number)
        if not season_info:
            continue
        if _name_fragment_score(candidates, season_info[2]) < MIN_FRAGMENT:
            continue
        count = season_info[1]
        if raw_episode and count and raw_episode > count:
            # 尾数只用来定季号；集数越界时原样保留，别把 E14 猜成 E02
            notes.append(f"集数 {raw_episode} 超出 S{number} 的 {count} 集（集数原样保留）")
        return _decision(
            number, raw_episode,
            "title-suffix", f"标题尾数 {number} 被季名证实",
        )

    # 3. 季标 → 直接定位（集数边界不合法则不采纳）
    if marker:
        season_info = by_number.get(marker)
        if season_info:
            count = season_info[1]
            if raw_episode is None or not count or raw_episode <= count:
                return _decision(
                    marker, raw_episode, "marker",
                    f"文件名季标 S{marker} 与 TMDB 季表一致",
                )

    # 3.5 年份对齐：文件名年份命中唯一一季（比纯集数边界更具体）
    if file_year:
        year_hits = []
        for number, _count, _names, air in parsed:
            try:
                air_year = date.fromisoformat(air[:10]).year
            except (TypeError, ValueError):
                continue
            if air_year == file_year:
                year_hits.append((number, air))
        if len(year_hits) == 1:
            number, air = year_hits[0]
            return _decision(
                number, raw_episode, "year-match",
                f"文件名年份 {file_year} 命中 S{number}（{air[:4]} 开播）",
            )
        if len(year_hits) > 1:
            notes.append(f"年份 {file_year} 命中多季，不采信")

    # 4. 集数边界校验：per_season 只在「文件名确实给了季标」时才成立。
    #    没有季标时不能默认 base=1——那等于把待验假设直接当结论：任何集数 ≤ S1 集数
    #    的文件都会被判成 S1（S1/S2 集数相同时这条约束永远无法区分两季），
    #    会把前置阶段（记忆/锁定 ID）给的季号无谓地压回 S1。这种情况只能退回
    #    绝对集数换算（boundary:absolute 是弱证据，on 模式只记录不应用）。
    if raw_episode:
        if marker is not None:
            # 有季标且集数在界内时，第 3 步已经返回；这里只是同一规则的兜底
            season_info = by_number.get(marker)
            if season_info and (not season_info[1] or raw_episode <= season_info[1]):
                return _decision(
                    marker, raw_episode, "boundary:per-season",
                    f"按季度内集数成立（S{marker} 共 {season_info[1] or '?'} 集）",
                )
        mapped = _absolute_episode_map(raw_episode, parsed)
        if mapped:
            number, episode = mapped
            return _decision(
                number, episode, "boundary:absolute",
                f"按绝对集数换算：第 {raw_episode} 集 = S{number}E{episode}",
            )

    # 5. 首播日期：取不晚于参考日期的最新一季
    try:
        reference = date.fromisoformat(ref_date) if ref_date else date.today()
    except ValueError:
        reference = date.today()
    past = []
    for number, count, names, air in parsed:
        try:
            air_date = date.fromisoformat(air[:10])
        except (TypeError, ValueError):
            continue
        if air_date <= reference:
            past.append((air_date, number))
    if past:
        air_date, number = max(past)
        return _decision(
            number, raw_episode, "latest-by-air-date",
            f"取不晚于 {reference.isoformat()} 的最新一季 S{number}（{air_date.isoformat()} 开播）",
        )

    return _decision(None, raw_episode, "ambiguous", "季名/季标/日期都无法确定季号")
