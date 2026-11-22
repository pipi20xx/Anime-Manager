"""
批量删除规则（按扩展名 / 按文件名 / 重复副本识别）。

本模块只做纯计算，不接触文件系统与网络，供两条链路共用：
- 本地文件系统：``organizer_core.file_explorer``
- CD2 云盘：``clients.cd2.file_browser``

三种模式的语义：
- ``ext``：按扩展名删除（原有行为），未填要删除的扩展名 = 所有文件。
- ``name``：按文件名删除，支持 ``*`` ``?`` 通配符；无通配符时与完整文件名完全一致
  （不区分大小写），只写名字不带扩展名时匹配该名字所有扩展名的文件。
- ``duplicate``：重复副本清理。把名字末尾的副本标记（如 `` (1)``、``（2）``、
  `` - 副本``、`` - Copy (2)``）去掉后得到"原始名字"，若同一目录下确实存在这个
  原始文件（同扩展名），则把带副本标记且内容大小一致的文件视为重复副本并删除，
  原文件保留。
"""

import re
import unicodedata
from fnmatch import fnmatchcase
from typing import Any, Callable, Dict, List, Optional, Tuple

# 三种批量删除模式
MODE_EXT = "ext"
MODE_NAME = "name"
MODE_DUPLICATE = "duplicate"
VALID_MODES = (MODE_EXT, MODE_NAME, MODE_DUPLICATE)

# 重复副本的保留策略
KEEP_ORIGINAL = "original"
KEEP_NEWEST = "newest"
KEEP_OLDEST = "oldest"
KEEP_LARGEST = "largest"
VALID_KEEP_POLICIES = (KEEP_ORIGINAL, KEEP_NEWEST, KEEP_OLDEST, KEEP_LARGEST)

# 跳过原因（返回给前端做提示）
SKIP_SIZE_MISMATCH = "size_mismatch"   # 大小与原文件不一致，未删除
SKIP_NO_ORIGINAL = "no_original"       # 找不到原文件，未删除

# 名字末尾的副本标记（只处理结尾，迭代多次以兼容 "xxx - 副本 (2)" 这类叠加写法）
_COPY_MARKER_PATTERNS = (
    # xxx (1) / xxx（2）
    r"[\(\（]\s*\d{1,3}\s*[\)\）]$",
    # xxx - 副本 / xxx - Copy / xxx - コピー
    r"\s*-\s*(?:副本|复件|拷贝|copy|コピー|복사)$",
    # xxx_副本 / xxx 副本 / xxx_copy
    r"[_\s](?:副本|复件|拷贝|copy|コピー|복사)$",
    # xxx (copy) / xxx（副本）/ xxx (another copy)
    r"[\(\（]\s*(?:another\s+)?(?:副本|复件|拷贝|copy|コピー|복사)\s*[\)\）]$",
)

_COPY_MARKER_RES = tuple(re.compile(p, re.IGNORECASE) for p in _COPY_MARKER_PATTERNS)


def normalize_mode(mode: Optional[str]) -> str:
    """校验批量删除模式：ext | name | duplicate；缺省按扩展名"""
    value = (mode or MODE_EXT).strip().lower()
    if value not in VALID_MODES:
        raise ValueError(f"不支持的批量删除模式: {mode}")
    return value


def normalize_text(text: str) -> str:
    """比较用的归一化：NFC + 压缩空白 + 去首尾空格 + 小写"""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text or "")).strip().lower()


def split_name(name: str) -> Tuple[str, str]:
    """
    拆分文件名与扩展名（扩展名含点，保持原始大小写）。
    ``.gitignore`` 这类隐藏文件视为没有扩展名。
    """
    name = name or ""
    idx = name.rfind(".")
    if idx <= 0 or idx == len(name) - 1:
        return name, ""
    return name[:idx], name[idx:]


def strip_copy_markers(stem: str) -> str:
    """去掉文件名主体末尾的副本标记；无标记时原样返回"""
    current = stem or ""
    for _ in range(10):
        text = current.rstrip()
        matched = None
        for pattern in _COPY_MARKER_RES:
            m = pattern.search(text)
            if m and m.start() > 0:
                matched = text[: m.start()].rstrip()
                break
        if matched is None or matched == current:
            break
        current = matched
    return current


def normalize_extensions(extensions: Optional[List[str]]) -> List[str]:
    """
    归一化扩展名列表，兼容多种写法：
    '.jpg' / 'jpg' / 'JPG' / '*.jpg' → '.jpg'；多项可用 ; , ， ； 分隔。
    '*' / '.*' / 'all' → '*'（匹配所有文件）。返回空列表表示"不限制扩展名"。
    """
    result: List[str] = []
    for raw in (extensions or []):
        text = str(raw).replace('；', ';').replace('，', ',').replace(',', ';')
        for part in text.split(';'):
            ext = part.strip().lower()
            if not ext:
                continue
            if ext in ('*', '.*', 'all'):
                ext = '*'
            elif ext.startswith('*.'):
                ext = ext[1:]
            elif not ext.startswith('.'):
                ext = '.' + ext
            if ext not in result:
                result.append(ext)
    return result


def normalize_names(names: Optional[List[str]]) -> List[str]:
    """归一化文件名列表；多项可用 ; ； 换行分隔（不对逗号分割，文件名里可能带逗号）"""
    result: List[str] = []
    for raw in (names or []):
        text = str(raw).replace('；', ';').replace('\r', '\n')
        for part in re.split(r'[;\n]', text):
            name = part.strip()
            if name and name not in result:
                result.append(name)
    return result


def extension_matches(name: str, extensions: List[str]) -> bool:
    """文件名是否命中扩展名规则；extensions 为空视为命中所有文件"""
    if not extensions:
        return True
    lower = (name or "").lower()
    return any(lower.endswith(ext) or fnmatchcase(lower, ext) for ext in extensions)


def _glob_match(target: str, pattern: str) -> bool:
    """只把 * 和 ? 当作通配符，[ ] 按字面量处理（番剧文件名里方括号很常见）"""
    return fnmatchcase(target, pattern.replace('[', '[[]'))


def name_matches(name: str, patterns: List[str]) -> bool:
    """
    文件名是否命中文件名规则：
    - 含通配符（* ?）时按 glob 匹配完整文件名（不区分大小写）
    - 不含通配符且不含扩展名时，匹配"去扩展名后同名"的所有文件（如填 xxx 命中 xxx.mkv）
    - 其余情况要求与完整文件名完全一致（不区分大小写）
    """
    target = normalize_text(name)
    target_stem, _ext = split_name(target)
    for pattern in patterns:
        p = normalize_text(pattern)
        if not p:
            continue
        if target == p:
            return True
        if any(ch in p for ch in '*?'):
            if _glob_match(target, p):
                return True
        elif '.' not in p and target_stem == p:
            return True
    return False


def make_matcher(delete_extensions: Optional[List[str]] = None,
                 exclude_extensions: Optional[List[str]] = None,
                 delete_names: Optional[List[str]] = None) -> Callable[[str], bool]:
    """
    生成"是否要删除该文件"的判定函数。
    优先级：不想删除的扩展名（exclude）> 文件名规则（有则忽略扩展名规则）> 要删除的扩展名。
    """
    delete_exts = normalize_extensions(delete_extensions)
    exclude_exts = normalize_extensions(exclude_extensions)
    names = normalize_names(delete_names)

    def _match(name: str) -> bool:
        if exclude_exts and extension_matches(name, exclude_exts):
            return False
        if names:
            return name_matches(name, names)
        return extension_matches(name, delete_exts)

    return _match


def make_exclude_matcher(exclude_extensions: Optional[List[str]] = None) -> Callable[[str], bool]:
    """只生成"被排除"的判定函数（重复副本模式使用，避免误删排除扩展名）"""
    exclude_exts = normalize_extensions(exclude_extensions)

    def _excluded(name: str) -> bool:
        return bool(exclude_exts) and extension_matches(name, exclude_exts)

    return _excluded


def _parent_path(path: str) -> str:
    """取父目录字符串（同时兼容 / 与 \\ 分隔，不依赖当前操作系统）"""
    path = path or ""
    idx = max(path.rfind('/'), path.rfind('\\'))
    if idx < 0:
        return ""
    return path[:idx] or path[:1]


def _public_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    """去掉内部字段，返回给前端/调用方的条目"""
    return {
        "path": entry.get("path"),
        "name": entry.get("name"),
        "size": int(entry.get("size") or 0),
        "mtime": entry.get("mtime") or 0,
    }


def _pick_keep(members: List[Dict[str, Any]], keep_policy: str) -> Dict[str, Any]:
    """在一组重复文件里挑出要保留的那个"""
    def mtime(e: Dict[str, Any]) -> float:
        try:
            return float(e.get("mtime") or 0)
        except (TypeError, ValueError):
            return 0.0

    def size(e: Dict[str, Any]) -> int:
        try:
            return int(e.get("size") or 0)
        except (TypeError, ValueError):
            return 0

    def name(e: Dict[str, Any]) -> str:
        return normalize_text(e.get("name") or "")

    # 有原文件时始终保留原文件（保留策略只在没有原文件时生效）
    plain = [e for e in members if not e.get("_is_copy")]
    pool = plain or members

    if keep_policy == KEEP_NEWEST:
        return max(pool, key=lambda e: (mtime(e), size(e), name(e)))
    if keep_policy == KEEP_OLDEST:
        return min(pool, key=lambda e: (mtime(e), -size(e), name(e)))
    if keep_policy == KEEP_LARGEST:
        return max(pool, key=lambda e: (size(e), mtime(e), name(e)))

    # 默认：保留最早的那个（有原文件时即原文件）
    return min(pool, key=lambda e: (mtime(e), -size(e), name(e)))


def build_duplicate_plan(entries: List[Dict[str, Any]],
                         keep_policy: str = KEEP_ORIGINAL,
                         require_original: bool = True,
                         same_size_only: bool = True) -> Dict[str, Any]:
    """
    根据文件列表生成"重复副本清理计划"。

    :param entries: 待检查文件，每项需含 name/path/size/mtime
    :param keep_policy: 保留策略 original|newest|oldest|largest
    :param require_original: 仅当同目录确实存在"去掉副本标记后的原文件"时才清理
    :param same_size_only: 仅删除与原文件大小一致（大概率内容相同）的副本
    :return: {items, skipped, count, total_size, skipped_count, group_count}
        items: 待删除文件（含 keep_name/keep_path/group_size）
        skipped: 被跳过未删除的文件（含 reason）
    """
    policy = keep_policy if keep_policy in VALID_KEEP_POLICIES else KEEP_ORIGINAL

    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for raw in entries or []:
        name = raw.get("name") or ""
        stem, ext = split_name(name)
        stripped_stem = strip_copy_markers(stem)
        is_copy = normalize_text(stripped_stem) != normalize_text(stem)
        entry = dict(raw)
        entry["_is_copy"] = is_copy
        key = (
            _parent_path(entry.get("path") or ""),
            normalize_text(stripped_stem),
            ext.lower(),
        )
        groups.setdefault(key, []).append(entry)

    items: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    group_count = 0

    for group in groups.values():
        if len(group) < 2:
            continue
        # 只有包含副本标记的组才算"重复副本"，纯同名（仅大小写不同）不处理
        if not any(e["_is_copy"] for e in group):
            continue

        plain = [e for e in group if not e["_is_copy"]]
        if require_original and not plain:
            # 找不到原文件：无法判断哪个是"正本"，整组跳过
            for e in group:
                skipped.append({**_public_entry(e), "reason": SKIP_NO_ORIGINAL})
            continue

        keep = _pick_keep(group, policy)
        keep_size = int(keep.get("size") or 0)
        touched = False
        for entry in group:
            if entry is keep:
                continue
            info = _public_entry(entry)
            info["keep_name"] = keep.get("name")
            info["keep_path"] = keep.get("path")
            info["group_size"] = len(group)
            if same_size_only and int(entry.get("size") or 0) != keep_size:
                skipped.append({**info, "reason": SKIP_SIZE_MISMATCH})
                continue
            items.append(info)
            touched = True
        if touched:
            group_count += 1

    items.sort(key=lambda e: str(e.get("path") or ""))
    skipped.sort(key=lambda e: str(e.get("path") or ""))
    return {
        "items": items,
        "skipped": skipped,
        "count": len(items),
        "total_size": sum(int(e.get("size") or 0) for e in items),
        "skipped_count": len(skipped),
        "group_count": group_count,
    }
