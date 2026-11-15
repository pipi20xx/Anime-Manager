"""压缩包解压（字体包导入用）。

为什么不用 pip 依赖：font_core 的约定是「仅标准库 + 内置 assfonts 二进制」。
zip / tar 用标准库直接解，rar / 7z 交给系统解压器（unar / bsdtar / 7z），
按可用性回退；一个都没有时返回结构化错误，由路由层提示装包。

安全约束（字体包是用户上传的不可信输入）：
1. 只抽字体文件，其余条目丢弃并记账（skipped），不解非字体；
2. 条目路径里的 `..` / 绝对路径 / 盘符 / 空名一律丢弃（本实现只按 basename
   落盘，这是双保险：即便漏判也写不出目标目录）；
3. 限额：条目数、单字体大小、解压总量、字体数，超限即中止（防 zip 炸弹）；
4. 外部解压器先解到目标目录下的临时子目录，逐文件校验后再搬进来，失败清理；
5. 对外函数不抛异常，返回 {"success": bool, "message": str, ...}。

对外的唯一入口是 extract_archive()，返回结构见其 docstring。
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from font_core import ass_parser

logger = logging.getLogger(__name__)

# 可识别的压缩包后缀（长后缀在前，sniff 时按长度倒序匹配）
ARCHIVE_SUFFIXES: Tuple[str, ...] = (
    ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2", ".txz",
    ".zip", ".rar", ".7z", ".tar",
)

# 外部解压器候选（rar 用不了 7z 的部分版本，所以按格式分别排优先级）
_EXTERNAL_BY_FORMAT: Dict[str, Tuple[str, ...]] = {
    ".rar": ("unar", "bsdtar", "7z", "7za"),
    ".7z": ("unar", "bsdtar", "7z", "7za"),
    ".zip": ("unar", "bsdtar", "7z"),
}

_READ_CHUNK = 1024 * 1024


@dataclass
class Limits:
    """解压限额。默认值对「字体包」这个场景足够宽松，但足以挡住炸弹。"""

    max_archive_bytes: int = 512 * 1024 * 1024   # 单个压缩包
    max_extract_bytes: int = 2048 * 1024 * 1024  # 解压总量
    max_entries: int = 5000                      # 条目数（含被丢弃的）
    max_fonts: int = 2000                        # 字体文件数
    max_font_bytes: int = 256 * 1024 * 1024      # 单个字体（与路由层 MAX_FONT_BYTES 一致）

    def as_dict(self) -> Dict[str, int]:
        return {
            "max_archive_bytes": self.max_archive_bytes,
            "max_extract_bytes": self.max_extract_bytes,
            "max_entries": self.max_entries,
            "max_fonts": self.max_fonts,
            "max_font_bytes": self.max_font_bytes,
        }


def sniff_format(name: str) -> str:
    """按文件名判断压缩格式，返回后缀（如 ".zip" / ".tar.gz"），不认识返回 ""。"""
    low = (name or "").strip().lower()
    for suffix in sorted(ARCHIVE_SUFFIXES, key=len, reverse=True):
        if low.endswith(suffix):
            return suffix
    return ""


def is_archive_name(name: str) -> bool:
    return bool(sniff_format(name))


def available_extractors() -> List[Dict[str, Any]]:
    """当前环境可用的解压器（供状态页/诊断显示）。"""
    out: List[Dict[str, Any]] = [{"tool": "zipfile", "kind": "stdlib", "formats": [".zip"]},
                                 {"tool": "tarfile", "kind": "stdlib",
                                  "formats": [".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"]}]
    for tool in ("unar", "bsdtar", "7z", "7za"):
        path = shutil.which(tool)
        if path:
            formats = [f for f, cands in _EXTERNAL_BY_FORMAT.items() if tool in cands]
            out.append({"tool": tool, "kind": "external", "path": path, "formats": formats})
    return out


def _pick_external(fmt: str) -> Optional[str]:
    for tool in _EXTERNAL_BY_FORMAT.get(fmt, ()):
        if shutil.which(tool):
            return tool
    return None


# ── 路径与文件名 ─────────────────────────────────────────────

def _is_unsafe_member(name: str) -> bool:
    """条目名是否含穿越/绝对路径特征（只用于记账，落盘只取 basename）。"""
    raw = (name or "").replace("\\", "/").strip()
    if not raw:
        return True
    if raw.startswith("/") or (len(raw) > 1 and raw[1] == ":"):
        return True
    return any(part == ".." for part in raw.split("/"))


def _basename(name: str) -> str:
    base = (name or "").replace("\\", "/").rstrip("/").split("/")[-1]
    return base.strip().strip(".")


_JUNK_NAMES = {".ds_store", "thumbs.db", "desktop.ini"}


def _is_junk_member(name: str) -> bool:
    """压缩包里的系统垃圾：macOS 资源叉、Windows 缩略图缓存。

    注意 `__MACOSX/._xxx.ttf` 这种「看起来是字体」的条目必须单独拦掉，
    否则会被当成真字体解出来。
    """
    parts = [p for p in (name or "").replace("\\", "/").split("/") if p]
    if any(p == "__MACOSX" for p in parts):
        return True
    base = parts[-1] if parts else ""
    return base.lower() in _JUNK_NAMES or base.startswith("._")


def _decode_zip_name(info: zipfile.ZipInfo) -> str:
    """还原 zip 条目名：UTF-8 标记位缺失时按 cp437→GBK 回退（国内组的常态）。"""
    name = info.filename or ""
    if info.flag_bits & 0x800:      # 压缩包自己声明了 UTF-8
        return name
    try:
        raw = name.encode("cp437")
    except UnicodeEncodeError:
        return name
    for enc in ("gbk", "big5", "utf-8"):
        try:
            cand = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if "\ufffd" not in cand:
            return cand
    return name


def _decode_tar_name(name: str) -> str:
    """tar 里非 UTF-8 的名字会被 surrogateescape 成代理字符，这里按 GBK 还原。"""
    if not name:
        return ""
    try:
        name.encode("utf-8")
        return name
    except UnicodeEncodeError:
        pass
    try:
        return name.encode("utf-8", "surrogateescape").decode("gbk", "replace")
    except Exception:
        return name


def _unique_target(dest: Path, name: str, used: set) -> Path:
    """目标目录内的落盘名：重名加 _1/_2…（同一 job 内多个包也会撞名）。"""
    stem, ext = os.path.splitext(name)
    candidate = f"{name}"
    i = 1
    while candidate.lower() in used or (dest / candidate).exists():
        candidate = f"{stem}_{i}{ext}"
        i += 1
        if i > 9999:
            candidate = f"{stem}_{hashlib.md5(name.encode('utf-8', 'replace')).hexdigest()[:8]}{ext}"
            break
    used.add(candidate.lower())
    return dest / candidate


class _Recorder:
    """解压过程记账：字体清单 / 丢弃清单 / 限额状态。"""

    def __init__(self, dest: Path, limits: Limits):
        self.dest = dest
        self.limits = limits
        self.fonts: List[Dict[str, Any]] = []
        self.skipped: List[Dict[str, str]] = []
        self.total_bytes = 0
        self.entries = 0
        self.used: set = set()
        self.aborted = ""
        self.extractor = ""

    def tick_entry(self) -> bool:
        self.entries += 1
        if self.entries > self.limits.max_entries:
            self.aborted = f"条目数超过上限（{self.limits.max_entries}），疑似压缩炸弹"
            return False
        return True

    def skip(self, name: str, reason: str) -> None:
        if len(self.skipped) < 500:      # 记账有上限，避免报告文件爆炸
            self.skipped.append({"name": name[:200], "reason": reason})

    def accept_size(self, name: str, size: int) -> bool:
        if size <= 0:
            self.skip(name, "空文件")
            return False
        if size > self.limits.max_font_bytes:
            self.skip(name, f"单个字体过大（>{self.limits.max_font_bytes // 1024 // 1024}MB）")
            return False
        if self.total_bytes + size > self.limits.max_extract_bytes:
            self.aborted = f"解压总量超过上限（{self.limits.max_extract_bytes // 1024 // 1024}MB）"
            return False
        if len(self.fonts) >= self.limits.max_fonts:
            self.aborted = f"字体数量超过上限（{self.limits.max_fonts}）"
            return False
        return True

    def add(self, stored_name: str, source_name: str, size: int, sha256: str) -> None:
        self.total_bytes += size
        self.fonts.append({"name": stored_name, "source": source_name,
                           "size": size, "sha256": sha256})

    def result(self, archive_name: str) -> Dict[str, Any]:
        return {
            "success": not self.aborted,
            "message": self.aborted or f"解出 {len(self.fonts)} 个字体",
            "extractor": self.extractor,
            "archive": archive_name,
            "fonts": self.fonts,
            "skipped": self.skipped,
            "skipped_count": len(self.skipped),
            "total_bytes": self.total_bytes,
            "entries": self.entries,
        }


def _write_stream(fh, target: Path, rec: _Recorder, source_name: str) -> bool:
    """把条目流写盘并算 sha256；实际写入量也要卡限额（头部 size 可能撒谎）。"""
    digest = hashlib.sha256()
    written = 0
    try:
        with open(target, "wb") as out:
            while True:
                chunk = fh.read(_READ_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if rec.total_bytes + written > rec.limits.max_extract_bytes:
                    rec.aborted = f"解压总量超过上限（{rec.limits.max_extract_bytes // 1024 // 1024}MB）"
                    out.close()
                    target.unlink(missing_ok=True)
                    return False
                digest.update(chunk)
                out.write(chunk)
    except Exception as e:
        rec.skip(source_name, f"写入失败：{type(e).__name__} {e}")
        target.unlink(missing_ok=True)
        return False
    if written == 0:
        rec.skip(source_name, "空文件")
        target.unlink(missing_ok=True)
        return False
    rec.add(target.name, source_name, written, digest.hexdigest())
    return True


def _extract_zip(archive: Path, rec: _Recorder) -> None:
    rec.extractor = "zipfile"
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if not rec.tick_entry():
                return
            if info.is_dir() or (info.filename or "").endswith("/"):
                continue
            name = _decode_zip_name(info)
            if _is_unsafe_member(name):
                rec.skip(name, "路径不安全（含 .. 或绝对路径）")
                continue
            if _is_junk_member(name):
                rec.skip(name, "系统垃圾文件（__MACOSX / ._ / Thumbs.db）")
                continue
            base = _basename(name)
            if not base:
                rec.skip(name, "文件名为空")
                continue
            if not ass_parser.is_font_file(base):
                rec.skip(name, "非字体文件")
                continue
            if not rec.accept_size(name, info.file_size):
                return
            target = _unique_target(rec.dest, base, rec.used)
            with zf.open(info) as fh:
                if not _write_stream(fh, target, rec, name):
                    return


def _extract_tar(archive: Path, rec: _Recorder) -> None:
    rec.extractor = "tarfile"
    with tarfile.open(archive, mode="r:*") as tf:
        for member in tf:
            if not rec.tick_entry():
                return
            if not member.isfile():
                continue
            name = _decode_tar_name(member.name)
            if _is_unsafe_member(name):
                rec.skip(name, "路径不安全（含 .. 或绝对路径）")
                continue
            if _is_junk_member(name):
                rec.skip(name, "系统垃圾文件（__MACOSX / ._ / Thumbs.db）")
                continue
            base = _basename(name)
            if not base or not ass_parser.is_font_file(base):
                rec.skip(name, "非字体文件")
                continue
            if not rec.accept_size(name, int(member.size or 0)):
                return
            fh = tf.extractfile(member)
            if fh is None:
                rec.skip(name, "读取失败")
                continue
            target = _unique_target(rec.dest, base, rec.used)
            with fh:
                if not _write_stream(fh, target, rec, name):
                    return


def _external_cmd(tool: str, archive: Path, outdir: Path) -> List[str]:
    if tool == "unar":
        # -q 静默 / -f 覆盖 / -D 不保留包内目录 / -o 输出目录
        return [tool, "-q", "-f", "-D", "-o", str(outdir), str(archive)]
    if tool == "bsdtar":
        return [tool, "-xf", str(archive), "-C", str(outdir)]
    return [tool, "x", "-y", f"-o{outdir}", str(archive)]


async def _extract_external(archive: Path, rec: _Recorder, tool: str,
                            timeout: int) -> None:
    """外部解压器：先解到 dest 下的 .tmp_* 子目录，再逐文件校验搬进来。"""
    rec.extractor = tool
    staging = rec.dest / f".tmp_{tool}_{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        staging.mkdir(parents=True, exist_ok=True)
        cmd = _external_cmd(tool, archive, staging)
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            rec.aborted = f"{tool} 解压超时（{timeout}s）"
            return
        if proc.returncode not in (0, 1):      # unar 遇到损坏条目会返回 1，但产物可用
            msg = (out or b"").decode("utf-8", "replace").strip()[-400:]
            rec.aborted = f"{tool} 解压失败（exit {proc.returncode}）：{msg}"
            return
        _harvest_staging(staging, rec)
    except FileNotFoundError:
        rec.aborted = f"{tool} 不可用"
    except Exception as e:
        rec.aborted = f"{tool} 解压异常：{type(e).__name__} {e}"
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _harvest_staging(staging: Path, rec: _Recorder) -> None:
    """把外部解压器产出的字体搬进目标目录，并套用同样的限额。"""
    root = staging.resolve()
    for path in sorted(root.rglob("*")):
        if rec.aborted:
            return
        if not rec.tick_entry():
            return
        try:
            if path.is_symlink() or not path.is_file():
                continue
        except OSError:
            continue
        try:
            rp = path.resolve()
        except Exception:
            rec.skip(path.name, "路径解析失败")
            continue
        if root not in rp.parents:          # 解压器写到了目标目录之外
            rec.skip(path.name, "路径不安全（解析到目标目录之外）")
            continue
        if _is_junk_member(path.relative_to(root).as_posix()):
            rec.skip(path.name, "系统垃圾文件（__MACOSX / ._ / Thumbs.db）")
            continue
        if not ass_parser.is_font_file(path.name):
            rec.skip(path.name, "非字体文件")
            continue
        try:
            size = rp.stat().st_size
        except OSError:
            rec.skip(path.name, "读取大小失败")
            continue
        if not rec.accept_size(path.name, size):
            return
        target = _unique_target(rec.dest, path.name, rec.used)
        try:
            shutil.move(str(rp), str(target))
        except Exception as e:
            rec.skip(path.name, f"搬运失败：{type(e).__name__} {e}")
            continue
        digest = hashlib.sha256()
        try:
            with open(target, "rb") as fh:
                while True:
                    chunk = fh.read(_READ_CHUNK)
                    if not chunk:
                        break
                    digest.update(chunk)
        except OSError:
            pass
        rec.add(target.name, path.relative_to(root).as_posix(), size, digest.hexdigest())


async def extract_archive(archive: Path, dest: Path, *,
                          limits: Optional[Limits] = None,
                          timeout: int = 600) -> Dict[str, Any]:
    """解一个压缩包，只把字体文件落到 dest。

    返回：
        {"success", "message", "extractor", "archive",
         "fonts": [{"name": 落盘名, "size", "sha256", "source"}],
         "skipped": [{"name", "reason"}], "skipped_count", "total_bytes", "entries"}

    约定：不抛异常；单个条目出问题不影响其它条目，整体超限才中止。
    """
    limits = limits or Limits()
    archive = Path(archive)
    dest = Path(dest)
    name = archive.name
    rec = _Recorder(dest, limits)
    try:
        if not archive.is_file():
            return {**rec.result(name), "success": False, "message": "压缩包不存在"}
        size = archive.stat().st_size
        if size > limits.max_archive_bytes:
            return {**rec.result(name), "success": False,
                    "message": f"压缩包过大（>{limits.max_archive_bytes // 1024 // 1024}MB）"}
        fmt = sniff_format(name)
        if not fmt:
            return {**rec.result(name), "success": False,
                    "message": "不支持的压缩格式（支持 zip/rar/7z/tar/tar.gz/tar.bz2/tar.xz）"}
        dest.mkdir(parents=True, exist_ok=True)

        if fmt == ".zip":
            try:
                _extract_zip(archive, rec)
            except zipfile.BadZipFile as e:
                return {**rec.result(name), "success": False, "message": f"压缩包损坏：{e}"}
            except RuntimeError as e:      # 加密 zip
                return {**rec.result(name), "success": False, "message": f"压缩包无法读取：{e}"}
        elif fmt.startswith(".tar") or fmt in (".tgz", ".tbz2", ".txz"):
            try:
                _extract_tar(archive, rec)
            except tarfile.TarError as e:
                return {**rec.result(name), "success": False, "message": f"压缩包损坏：{e}"}
        else:
            tool = _pick_external(fmt)
            if not tool:
                return {**rec.result(name), "success": False,
                        "message": f"未找到可解 {fmt} 的解压器（请安装 unar 或 p7zip / libarchive-tools）"}
            await _extract_external(archive, rec, tool, timeout)

        # 落盘名可能被加过序号（重名保护），source 保留压缩包里的原始路径供 UI 对照
        return rec.result(name)
    except Exception as e:      # 兜底：对外永不抛
        logger.warning(f"[字体导入] 解压异常 {archive}: {type(e).__name__} {e}")
        return {**rec.result(name), "success": False,
                "message": f"解压异常：{type(e).__name__} {e}"}
