"""ASS/SSA 字幕解析：提取引用字体清单、判断是否已内嵌字体。

与 assfonts 的口径保持一致：
- Style 行的第 2 个字段（Fontname）是该样式的默认字体；
- 行内 `{\\fnXXX}` 覆盖当前字体；
- `{\\r}` / `{\\rStyleName}` 重置为样式默认字体（assfonts v0.7.3 已按此语义解析）；
- `[Fonts]` / `[Glyphs]` 区段存在即视为「已内嵌字体」（子集化成品）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

# 字体文件扩展名（用于字体库文件统计/上传校验）
FONT_EXTENSIONS = (".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2")
SUBTITLE_EXTENSIONS = (".ass", ".ssa")

_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_OVERRIDE_BLOCK_RE = re.compile(r"\{([^}]*)\}")


def decode_ass_text(raw: bytes) -> str:
    """自适应解码 ASS 文本。

    部分字幕站/压制工具输出 UTF-16（带 BOM，或 ASCII 字符间夹 NUL 字节），
    若一律按 UTF-8 解码会导致 Style 行 / `\\fn` 标签全部匹配失败。
    """
    if not raw:
        return ""
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except Exception:
            return raw.decode("utf-16", errors="replace")
    if b"\x00" in raw[:2048]:
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8", errors="replace")


def is_subtitle_file(name: str) -> bool:
    return name.lower().endswith(SUBTITLE_EXTENSIONS)


def is_font_file(name: str) -> bool:
    return name.lower().endswith(FONT_EXTENSIONS)


def parse_styles(text: str) -> Dict[str, str]:
    """解析 [V4+ Styles] / [V4 Styles] 区段：样式名 -> 字体名。

    同时登记原始大小写键与小写键，便于 Events 行按样式名回查。
    """
    styles: Dict[str, str] = {}
    in_styles = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SECTION_RE.match(line)
        if m:
            in_styles = m.group(1).strip().lower() in ("v4+ styles", "v4 styles", "v4++ styles")
            continue
        if not in_styles:
            continue
        if not line.lower().startswith("style:"):
            continue
        # Style: Name, Fontname, Fontsize, ...
        parts = line.split(":", 1)[1].split(",")
        if len(parts) >= 2:
            name = parts[0].strip()
            fontname = parts[1].strip()
            if name and fontname:
                styles[name] = fontname
                styles.setdefault(name.lower(), fontname)
    return styles


def has_embedded_fonts(text: str) -> bool:
    """是否已内嵌字体（子集化成品标志：存在 [Fonts] / [Glyphs] 区段或独立 fontname: 行）。"""
    for line in text.splitlines():
        s = line.strip().lstrip("\ufeff").lower()
        if not s:
            continue
        if s.startswith("[fonts]") or s.startswith("[glyphs]") or s.startswith("[font]"):
            return True
        # 旁证：独立的小写 fontname: 行（Style 行的 Fontname 是行内字段，不会单独成行）
        if s.startswith("fontname:"):
            return True
    return False


def extract_font_names(text: str) -> List[str]:
    """提取字幕实际引用的字体名（按首次出现顺序去重）。

    按 assfonts 语义处理 `\\fn` 覆盖与 `\\r` 重置：重置后回到该行样式的默认字体。
    """
    styles = parse_styles(text)
    ordered: List[str] = []
    seen: Set[str] = set()

    def _add(name: str) -> None:
        name = (name or "").strip()
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)

    # 样式默认字体（只遍历原始大小写键，避免小写别名重复）
    for key, fontname in styles.items():
        if key == key.lower():
            continue
        _add(fontname)

    in_events = False
    for line in text.splitlines():
        s = line.strip()
        m = _SECTION_RE.match(s)
        if m:
            in_events = m.group(1).strip().lower() in ("events", "v4+ events", "v4 events")
            continue
        if not in_events:
            continue
        low = s.lower()
        if not (low.startswith("dialogue:") or low.startswith("comment:") or low.startswith("movie:")):
            continue
        body = s.split(":", 1)[1] if ":" in s else ""
        # Events 行：Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        fields = body.split(",", 9)
        style_name = fields[3].strip() if len(fields) > 3 else ""
        style_font = styles.get(style_name) or styles.get(style_name.lower()) or ""
        text_field = fields[9] if len(fields) > 9 else ""

        if style_font:
            _add(style_font)
        for block in _OVERRIDE_BLOCK_RE.findall(text_field):
            # 同一覆盖块内按出现顺序处理 \fn 与 \r
            for token in re.finditer(r"\\(fn|r)([^\\}]*)", block, re.I):
                tag, val = token.group(1).lower(), token.group(2)
                if tag == "fn":
                    name = val.strip()
                    if name:
                        _add(name)
                else:  # \r / \rStyleName → 重置回样式默认字体
                    target = val.strip()
                    reset_font = (styles.get(target) or styles.get(target.lower()) or target) if target else style_font
                    if reset_font:
                        _add(reset_font)
    return ordered


def inspect_ass(raw: bytes) -> Dict[str, Any]:
    """解析 ASS 字节流 → 结构化摘要（供「检查」与「子集化」共用）。"""
    text = decode_ass_text(raw)
    styles = parse_styles(text)
    is_utf16 = raw.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in raw[:2048]
    return {
        "fonts": extract_font_names(text),
        "style_count": len({k for k in styles if k != k.lower()}),
        "has_embedded_fonts": has_embedded_fonts(text),
        "encoding": "utf-16" if is_utf16 else "utf-8",
        "line_count": text.count("\n") + 1,
    }
