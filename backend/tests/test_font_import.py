"""字体压缩包导入 —— 解压 / 比对 / 入库 的单元测试。

运行：
    cd backend && python -m unittest discover -s tests -v

只用标准库（项目约定：font_core 不引入第三方依赖），所以不用 pytest。
覆盖点（对应方案里列的 6 组 + 补充）：
    1. GBK 文件名的 zip 能正确还原中文名
    2. 路径穿越条目被拒绝
    3. 条目数/总量超限即中止（zip 炸弹）
    4. 一个包里重名文件加序号，不互相覆盖
    5. .ttc 多 face：一张 face 重复、一张是新 → 整文件判新
    6. 同名不同内容 / 改名的同一字体 / 坏字体 的四类判定
    7. 入库绝不覆盖 + 全重复包不落盘
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from font_core import archive, font_probe, importer  # noqa: E402


# ── 工具 ────────────────────────────────────────────────────

class _GbkZipInfo(zipfile.ZipInfo):
    """模拟国内压缩包：文件名按 GBK 编码且不设 UTF-8 标记位。"""

    def _encodeFilenameFlags(self):      # noqa: N802 (覆盖标准库私有方法)
        return self.filename.encode("cp437"), self.flag_bits & ~0x800


def _gbk_name(real_name: str) -> str:
    return real_name.encode("gbk").decode("cp437")


def _make_zip(path: Path, entries, *, gbk: bool = False) -> Path:
    """entries: [(name, data)] 或 [(name, data, is_dir)]。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as zf:
        for item in entries:
            name, data = item[0], item[1]
            info = _GbkZipInfo(_gbk_name(name)) if gbk else zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, data)
    return path


def _font_face(family: str, psname: str, path: Path, *, weight=400, slant=0, index=0):
    return {"families": [family], "psnames": [psname], "weight": weight, "slant": slant,
            "path": str(path), "filename": path.name, "face_index": index}


def _cfg(tmp: Path) -> dict:
    return {"font_manager": {
        "library_dir": str(tmp / "lib"),
        "import_dir": str(tmp / "import"),
        "imported_dir": str(tmp / "imported"),
        "replaced_dir": str(tmp / "replaced"),
        "import_target": "separate",
    }}


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ── 1. 解压 ─────────────────────────────────────────────────

class TestArchive(unittest.TestCase):

    def test_sniff_format(self):
        self.assertEqual(archive.sniff_format("a.ZIP"), ".zip")
        self.assertEqual(archive.sniff_format("x.tar.gz"), ".tar.gz")
        self.assertEqual(archive.sniff_format("x.rar"), ".rar")
        self.assertEqual(archive.sniff_format("x.txt"), "")
        self.assertTrue(archive.is_archive_name("BDRip Fonts.7z"))

    def test_extracts_fonts_only_with_gbk_names(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = _make_zip(td / "fonts.zip", [
                ("方正兰亭黑.ttf", b"\x00\x01\x00\x00fake-ttf"),
                ("说明.txt", "readme".encode()),
                ("__MACOSX/._x.ttf", b"junk"),
            ], gbk=True)
            dest = td / "out"
            res = _run(archive.extract_archive(zp, dest))
            self.assertTrue(res["success"], res.get("message"))
            names = [f["name"] for f in res["fonts"]]
            self.assertEqual(names, ["方正兰亭黑.ttf"])       # GBK 名还原 + 只留字体
            self.assertEqual(len(res["skipped"]), 2)           # txt + __MACOSX 记账
            self.assertTrue((dest / "方正兰亭黑.ttf").is_file())
            self.assertEqual(res["fonts"][0]["size"], len(b"\x00\x01\x00\x00fake-ttf"))

    def test_traversal_member_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = _make_zip(td / "evil.zip", [("../../evil.ttf", b"x" * 10)])
            dest = td / "out"
            res = _run(archive.extract_archive(zp, dest))
            self.assertEqual(res["fonts"], [])
            self.assertIn("路径不安全", res["skipped"][0]["reason"])
            self.assertFalse((td / "evil.ttf").exists())

    def test_identical_names_get_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            # zipfile 允许同名条目：两个 a.ttf 内容不同 → 第二个应落成 a_1.ttf
            zp = td / "dup.zip"
            with zipfile.ZipFile(zp, "w") as zf:
                zf.writestr("a.ttf", b"first")
                zf.writestr("a.ttf", b"second!")
            dest = td / "out"
            res = _run(archive.extract_archive(zp, dest))
            self.assertEqual(sorted(f["name"] for f in res["fonts"]), ["a.ttf", "a_1.ttf"])
            self.assertEqual((dest / "a.ttf").read_bytes(), b"first")
            self.assertEqual((dest / "a_1.ttf").read_bytes(), b"second!")

    def test_entry_limit_aborts(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = _make_zip(td / "many.zip", [(f"{i}.ttf", b"x") for i in range(5)])
            res = _run(archive.extract_archive(
                zp, td / "out", limits=archive.Limits(max_entries=2)))
            self.assertFalse(res["success"])
            self.assertIn("条目数超过上限", res["message"])

    def test_total_size_limit_aborts(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            zp = _make_zip(td / "big.zip", [("a.ttf", b"x" * 400), ("b.ttf", b"y" * 400)])
            res = _run(archive.extract_archive(
                zp, td / "out", limits=archive.Limits(max_extract_bytes=500)))
            self.assertFalse(res["success"])
            self.assertIn("解压总量超过上限", res["message"])

    def test_unsupported_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "x.iso").write_bytes(b"data")
            self.assertFalse(_run(archive.extract_archive(td / "x.iso", td / "o"))["success"])
            self.assertFalse(_run(archive.extract_archive(td / "nope.zip", td / "o"))["success"])

    def test_corrupt_zip_reports_error(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            bad = td / "bad.zip"
            bad.write_bytes(b"not a zip at all")
            res = _run(archive.extract_archive(bad, td / "out"))
            self.assertFalse(res["success"])
            self.assertIn("损坏", res["message"])


# ── 2. 比对 ─────────────────────────────────────────────────

class TestCompare(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)
        self.lib = self.td / "lib"
        self.lib.mkdir()
        self.existing = self.lib / "SourceHanSansSC-Medium.otf"
        self.existing.write_bytes(b"same-bytes")
        self.lib_faces = [_font_face("Source Han Sans SC", "SourceHanSansSC-Medium", self.existing)]

    def tearDown(self):
        self._td.cleanup()

    def _probe(self, mapping):
        """mapping: {Path: [face]} → probe_directory 的返回结构。"""
        by_path, by_name = {}, {}
        for p, faces in mapping.items():
            by_path[font_probe.norm_path(str(p))] = faces
            by_name.setdefault(Path(p).name.lower(), []).extend(faces)
        return {"success": True, "by_path": by_path, "by_name": by_name, "faces": []}

    def test_same_bytes_same_name_is_duplicate(self):
        f = self.td / "extracted" / "SourceHanSansSC-Medium.otf"
        f.parent.mkdir()
        f.write_bytes(b"same-bytes")
        incoming = [{"name": f.name, "source": f.name, "size": f.stat().st_size,
                     "sha256": importer._sha256(f), "path": str(f)}]
        probe = self._probe({f: [_font_face("Source Han Sans SC", "SourceHanSansSC-Medium", f)]})
        rep = font_probe.compare(incoming, probe, {"exists": True, "faces": self.lib_faces})
        self.assertEqual(rep["counts"]["duplicate"], 1)
        self.assertIn("逐字节相同", rep["duplicate"][0]["reason"])

    def test_renamed_same_face_is_duplicate_via_face_key(self):
        f = self.td / "extracted" / "abc.ttf"
        f.parent.mkdir()
        f.write_bytes(b"different-bytes")
        incoming = [{"name": f.name, "source": f.name, "size": f.stat().st_size,
                     "sha256": importer._sha256(f), "path": str(f)}]
        probe = self._probe({f: [_font_face("Source Han Sans SC", "SourceHanSansSC-Medium", f)]})
        rep = font_probe.compare(incoming, probe, {"exists": True, "faces": self.lib_faces})
        self.assertEqual(rep["counts"]["duplicate"], 1)
        self.assertEqual(rep["duplicate"][0]["existing"], str(self.existing))

    def test_same_family_diff_version_is_conflict(self):
        f = self.td / "extracted" / "new.otf"
        f.parent.mkdir()
        f.write_bytes(b"v2-bytes")
        incoming = [{"name": f.name, "source": f.name, "size": f.stat().st_size,
                     "sha256": importer._sha256(f), "path": str(f)}]
        probe = self._probe({f: [_font_face("Source Han Sans SC",
                                            "SourceHanSansSC-Medium-Build1.005", f)]})
        rep = font_probe.compare(incoming, probe, {"exists": True, "faces": self.lib_faces})
        self.assertEqual(rep["counts"]["conflict"], 1)
        self.assertIn("不同版本", rep["conflict"][0]["reason"])
        self.assertEqual(rep["conflict"][0]["conflicts"][0]["existing"][0]["path"],
                         str(self.existing))

    def test_unknown_family_is_new(self):
        f = self.td / "extracted" / "other.ttf"
        f.parent.mkdir()
        f.write_bytes(b"other")
        incoming = [{"name": f.name, "source": f.name, "size": f.stat().st_size,
                     "sha256": importer._sha256(f), "path": str(f)}]
        probe = self._probe({f: [_font_face("FZLanTingHei", "FZLTZHJW--GB1-0", f)]})
        rep = font_probe.compare(incoming, probe, {"exists": True, "faces": self.lib_faces})
        self.assertEqual(rep["counts"]["new"], 1)
        self.assertEqual(rep["new"][0]["faces"][0]["family"], "FZLanTingHei")

    def test_no_faces_is_invalid(self):
        f = self.td / "extracted" / "broken.ttf"
        f.parent.mkdir()
        f.write_bytes(b"broken")
        incoming = [{"name": f.name, "source": f.name, "size": 6,
                     "sha256": importer._sha256(f), "path": str(f)}]
        rep = font_probe.compare(incoming, self._probe({}), {"exists": True, "faces": []})
        self.assertEqual(rep["counts"]["invalid"], 1)
        self.assertIn("无法解析", rep["invalid"][0]["reason"])

    def test_ttc_one_new_face_makes_file_new(self):
        """.ttc 里一张 face 命中库、一张是新 → 整文件判新（否则会丢掉新字面）。"""
        f = self.td / "extracted" / "collection.ttc"
        f.parent.mkdir()
        f.write_bytes(b"ttc")
        incoming = [{"name": f.name, "source": f.name, "size": 3,
                     "sha256": importer._sha256(f), "path": str(f)}]
        faces = [_font_face("Source Han Sans SC", "SourceHanSansSC-Medium", f, index=0),
                 _font_face("Source Han Sans SC", "SourceHanSansSC-Bold", f,
                            weight=700, index=1)]
        rep = font_probe.compare(incoming, self._probe({f: faces}),
                                 {"exists": True, "faces": self.lib_faces})
        self.assertEqual(rep["counts"]["new"], 1)
        self.assertEqual(len(rep["new"][0]["faces"]), 2)

    def test_same_psname_diff_family_is_conflict(self):
        """同 psname、family 命名不同（一个英文名一个中文名）→ 冲突，不能当新字体入库。

        这是实测踩到的坑：方正 GBK 字体（方正兰亭大黑_GBK.ttf）内部同时有中文 family
        与英文 PostScript 名，不同来源的同一字体 family 可能正好相反。
        """
        f = self.td / "extracted" / "方正兰亭大黑_GBK.ttf"
        f.parent.mkdir()
        f.write_bytes(b"another-source")
        incoming = [{"name": f.name, "source": f.name, "size": f.stat().st_size,
                     "sha256": importer._sha256(f), "path": str(f)}]
        probe = self._probe({f: [_font_face("方正兰亭大黑_GBK", "FZLanTingHei-EB-GBK", f)]})
        lib_faces = [_font_face("FZLanTingHei-EB-GBK", "FZLanTingHei-EB-GBK", self.existing)]
        rep = font_probe.compare(incoming, probe, {"exists": True, "faces": lib_faces})
        self.assertEqual(rep["counts"]["conflict"], 1)
        self.assertIn("PostScript", rep["conflict"][0]["reason"])
        self.assertEqual(rep["conflict"][0]["conflicts"][0]["existing"][0]["path"],
                         str(self.existing))

    def test_library_index_missing_degrades(self):
        f = self.td / "extracted" / "x.ttf"
        f.parent.mkdir()
        f.write_bytes(b"x")
        incoming = [{"name": f.name, "source": f.name, "size": 1,
                     "sha256": importer._sha256(f), "path": str(f)}]
        rep = font_probe.compare(incoming, self._probe({f: [_font_face("A", "A-Regular", f)]}),
                                 {"exists": False, "faces": [], "error": "no index"})
        self.assertEqual(rep["counts"]["new"], 1)
        self.assertFalse(rep["library_index_available"])


# ── 3. 入库 ─────────────────────────────────────────────────

class TestCommit(unittest.TestCase):

    def _prepare(self, td: Path) -> tuple:
        cfg = _cfg(td)
        job = importer.create_job(cfg)
        paths = importer.job_paths(cfg, job["job_id"])
        return cfg, job["job_id"], paths

    def test_commit_moves_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg, job_id, paths = self._prepare(td)
            (paths["extracted"] / "a.ttf").write_bytes(b"new-1")
            report = {"counts": {"new": 2}, "new": [
                {"name": "a.ttf", "source": "a.ttf", "size": 5, "faces": []},
                {"name": "b.ttf", "source": "b.ttf", "size": 5, "faces": []}], "conflict": []}
            paths["report"].write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            (paths["extracted"] / "b.ttf").write_bytes(b"new-2")

            res = importer.commit(cfg, job_id)
            self.assertTrue(res["success"], res.get("message"))
            self.assertEqual(res["count"], 2)
            target = Path(res["target"])
            self.assertTrue((target / "a.ttf").is_file())
            self.assertTrue((target / "b.ttf").is_file())
            self.assertFalse(paths["extracted"].exists())      # 解压目录已清理
            self.assertTrue(paths["report"].exists())          # 报告保留

            # 同名再来一次：不能覆盖已有文件
            job2 = importer.create_job(cfg)
            p2 = importer.job_paths(cfg, job2["job_id"])
            (p2["extracted"] / "a.ttf").write_bytes(b"another")
            p2["report"].write_text(json.dumps(
                {"new": [{"name": "a.ttf", "size": 7, "faces": []}], "conflict": []},
                ensure_ascii=False), encoding="utf-8")
            res2 = importer.commit(cfg, job2["job_id"])
            self.assertEqual(res2["committed"][0]["stored"], "a.ttf")
            self.assertTrue((target / "a.ttf").read_bytes() == b"new-1")
            self.assertEqual((Path(res2["target"]) / "a.ttf").read_bytes(), b"another")

    def test_all_duplicate_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg, job_id, paths = self._prepare(td)
            paths["report"].write_text(json.dumps({
                "new": [], "conflict": [],
                "duplicate": [{"name": "a.ttf", "size": 3, "reason": "dup", "existing": "x"}],
            }, ensure_ascii=False), encoding="utf-8")
            res = importer.commit(cfg, job_id)
            self.assertTrue(res["success"])
            self.assertEqual(res["count"], 0)
            self.assertFalse(importer.imported_root(cfg).exists())

    def test_conflict_keep_does_not_replace(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg, job_id, paths = self._prepare(td)
            lib = Path(cfg["font_manager"]["library_dir"])
            lib.mkdir(parents=True, exist_ok=True)
            old = lib / "x.otf"
            old.write_bytes(b"old")
            (paths["extracted"] / "x.otf").write_bytes(b"new")
            paths["report"].write_text(json.dumps({
                "new": [], "conflict": [{
                    "name": "x.otf", "size": 3, "reason": "同 face 不同版本",
                    "conflicts": [{"existing": [{"path": str(old), "family": "F", "psname": "P"}]}],
                }],
            }, ensure_ascii=False), encoding="utf-8")

            res = importer.commit(cfg, job_id, policy="keep", select=["x.otf"])
            self.assertEqual(res["count"], 0)
            self.assertEqual(old.read_bytes(), b"old")
            # 没有真正入库 → 解压目录必须保留，换策略还能重试
            self.assertTrue(paths["extracted"].exists())

            res2 = importer.commit(cfg, job_id, policy="replace", select=["x.otf"])
            self.assertEqual(res2["count"], 1)
            self.assertEqual((Path(res2["target"]) / "x.otf").read_bytes(), b"new")

    def test_conflict_replace_backs_up_old_file(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg, job_id, paths = self._prepare(td)
            lib = Path(cfg["font_manager"]["library_dir"])
            lib.mkdir(parents=True, exist_ok=True)
            old = lib / "x.otf"
            old.write_bytes(b"old")
            (paths["extracted"] / "x.otf").write_bytes(b"new")
            paths["report"].write_text(json.dumps({
                "new": [], "conflict": [{
                    "name": "x.otf", "size": 3, "reason": "同 face 不同版本",
                    "conflicts": [{"existing": [{"path": str(old), "family": "F", "psname": "P"}]}],
                }],
            }, ensure_ascii=False), encoding="utf-8")

            res = importer.commit(cfg, job_id, policy="replace", select=["x.otf"])
            self.assertEqual(res["count"], 1)
            self.assertTrue(res["committed"][0]["replaced"])
            backup = Path(res["replaced_backup"]) / "x.otf"
            self.assertEqual(backup.read_bytes(), b"old")      # 旧文件没被删，只是移走
            self.assertFalse(old.exists())
            self.assertEqual((Path(res["target"]) / "x.otf").read_bytes(), b"new")

    def test_job_id_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(Path(td))
            self.assertIsNone(importer.find_job(cfg, "../../etc"))
            self.assertIsNone(importer.find_job(cfg, "a/b"))

    def test_list_and_delete_job(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = _cfg(Path(td))
            job = importer.create_job(cfg)
            jobs = importer.list_jobs(cfg)
            self.assertEqual([j["job_id"] for j in jobs], [job["job_id"]])
            self.assertTrue(importer.delete_job(cfg, job["job_id"])["success"])
            self.assertEqual(importer.list_jobs(cfg), [])


# ── 4. 配置映射 ─────────────────────────────────────────────

class TestConfig(unittest.TestCase):

    def test_limits_from_config(self):
        cfg = {"font_manager": {"import_max_archive_mb": 8, "import_max_fonts": 7,
                                "import_max_entries": 3, "import_max_extract_mb": 16,
                                "import_max_font_mb": 2}}
        lim = importer.limits(cfg)
        self.assertEqual(lim.max_archive_bytes, 8 * 1024 * 1024)
        self.assertEqual(lim.max_fonts, 7)
        self.assertEqual(lim.max_entries, 3)
        self.assertEqual(lim.max_extract_bytes, 16 * 1024 * 1024)
        self.assertEqual(lim.max_font_bytes, 2 * 1024 * 1024)

    def test_limits_fallback_on_garbage(self):
        lim = importer.limits({"font_manager": {"import_max_archive_mb": "abc"}})
        self.assertEqual(lim.max_archive_bytes, archive.Limits().max_archive_bytes)

    def test_debounce_default_and_clamp(self):
        self.assertEqual(importer.debounce_seconds({}), 120)
        self.assertEqual(importer.debounce_seconds({"font_manager": {"import_rebuild_debounce": 0}}), 120)
        self.assertEqual(importer.debounce_seconds({"font_manager": {"import_rebuild_debounce": 99999}}), 3600)

    def test_target_mode(self):
        self.assertEqual(importer.import_target_mode({}), "separate")
        self.assertEqual(importer.import_target_mode(
            {"font_manager": {"import_target": "PRIMARY"}}), "primary")
        self.assertEqual(importer.import_target_mode(
            {"font_manager": {"import_target": "nonsense"}}), "separate")


# ── 5. 端到端（无内核时降级）─────────────────────────────────

class TestAnalyzePipeline(unittest.TestCase):

    def test_analyze_degrades_without_kernel_then_commit(self):
        """内核不可用 → 降级成哈希比对（扫库目录同名文件）→ 报告仍可用 → 能入库。"""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg = _cfg(td)
            lib = Path(cfg["font_manager"]["library_dir"])
            lib.mkdir(parents=True, exist_ok=True)
            (lib / "already.ttf").write_bytes(b"old-font-bytes")

            job = importer.create_job(cfg)
            paths = importer.job_paths(cfg, job["job_id"])
            _make_zip(paths["incoming"] / "Fonts.zip", [
                ("new.ttf", b"fresh-font-bytes"),
                ("already.ttf", b"old-font-bytes"),
                ("readme.txt", b"hi"),
            ])

            report = _run(importer.analyze(cfg, td / "no-such-assfonts", job["job_id"]))
            self.assertTrue(report["success"], report.get("message"))
            self.assertFalse(report["probe"]["success"])          # 没有内核 → 降级
            self.assertEqual(report["counts"]["new"], 1)
            self.assertEqual(report["counts"]["duplicate"], 1)
            self.assertEqual(report["skipped_count"], 1)          # readme.txt 被丢弃
            self.assertTrue(paths["report"].is_file())            # 报告已落盘

            res = importer.commit(cfg, job["job_id"])
            self.assertTrue(res["success"], res.get("message"))
            self.assertEqual(res["count"], 1)
            self.assertEqual((Path(res["target"]) / "new.ttf").read_bytes(), b"fresh-font-bytes")
            self.assertEqual((lib / "already.ttf").read_bytes(), b"old-font-bytes")

    def test_analyze_reports_no_fonts(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg = _cfg(td)
            job = importer.create_job(cfg)
            paths = importer.job_paths(cfg, job["job_id"])
            _make_zip(paths["incoming"] / "junk.zip", [("a.txt", b"x")])
            report = _run(importer.analyze(cfg, td / "no-kernel", job["job_id"]))
            self.assertFalse(report["success"])
            self.assertIn("没有", report["message"])


if __name__ == "__main__":
    unittest.main()
