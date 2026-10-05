import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from sqlmodel import select, and_

from recognition.recognizer import MovieRecognizer
from .renamer import Renamer
from config_manager import ConfigManager
from clients.manager import ClientManager
from .executor import FileExecutor
from notification import notification_manager
from utils.hash_calculator import HashCalculator, HashResult

logger = logging.getLogger(__name__)

def _country_str(val):
    """origin_country 落库归一：上游可能传 list（PG 数组列）或 str，file_hashes 表为逗号字符串列"""
    if isinstance(val, (list, tuple)):
        return ",".join(str(x).strip() for x in val if str(x).strip()) or None
    return val

class FileProcessor:
    SUB_EXTS = ['.ass', '.srt', '.ssa', '.sub', '.idx', '.vtt']
    AUDIO_EXTS = ['.mka', '.aac', '.ac3', '.dts', '.flac', '.mp3', '.ogg', '.opus', '.wav']
    RELATED_EXTS = SUB_EXTS + AUDIO_EXTS

    @staticmethod
    def load_context(task: Dict[str, Any]):
        config = ConfigManager.get_config()
        cached_rules = ConfigManager.get_cached_rules()
        
        return {
            "config": config,
            "api_key": config.get("tmdb_api_key"),
            "all_noise": config.get("custom_noise_words", []) + cached_rules.get("noise", []),
            "all_groups": config.get("custom_release_groups", []) + cached_rules.get("groups", []),
            "all_render": config.get("custom_render_words", []) + cached_rules.get("render", []),
            "anime_priority": task.get("anime_priority", config.get("anime_priority", True)),
            "enable_title_segmentation": task.get("enable_title_segmentation"),
            "rule": next((r for r in config.get("rename_rules", Renamer.get_default_rules()) if r["id"] == task.get("rule_id")), None)
        }

    @staticmethod
    async def _log_detail(task_id: str, msg: str, level: str = "INFO"):
        if task_id:
            try:
                from task_history import log_task as _log_task
                await _log_task(task_id, msg, level)
            except Exception:
                pass

    @staticmethod
    async def _log_both(task_id: str, recog_task_id: Optional[str], msg: str, level: str = "INFO"):
        """同时写入外层整理任务与单文件识别任务日志，保证 recog 任务覆盖全流程"""
        await FileProcessor._log_detail(task_id, msg, level)
        await FileProcessor._log_detail(recog_task_id, msg, level)

    @staticmethod
    async def _finish_recog(recog_task_id: Optional[str], status: str, stats: Dict[str, Any] = None):
        """统一收口识别任务，所有出口都必须调用一次，避免任务停留在 running"""
        if not recog_task_id:
            return
        try:
            from task_history import finish_task as _finish_task
            await _finish_task(recog_task_id, status, stats=stats or {})
        except Exception:
            pass

    @staticmethod
    def _related_files_payload(
        related_files: List[str], related_targets: Dict[str, str], outcomes: Dict[str, str] = None
    ) -> List[Dict[str, Any]]:
        """构造随行文件清单（字幕/音轨），用于 OrganizeHistory.related_files 与任务 stats"""
        payload = []
        for f in related_files:
            st = (outcomes or {}).get(f)
            if st in ("skipped", "skipped_conflict"):
                status = "skipped"
            elif st and st not in ("success", "preview"):
                status = "error"
            else:
                # 无单项结果（批量模式）时跟随批次成功状态
                status = "success"
            payload.append({
                "filename": f,
                "target_path": (related_targets or {}).get(f),
                "status": status,
            })
        return payload

    @staticmethod
    async def _save_history_force(history: "OrganizeHistory"):
        """
        保存整理历史记录，同一 source_path 只保留一条记录。
        如果已存在则先删除旧记录，再插入新记录（与 MP 的 add_force 逻辑一致）。
        """
        from models import OrganizeHistory
        from database import db

        async with db.session_scope():
            stmt = select(OrganizeHistory).where(OrganizeHistory.source_path == history.source_path)
            existing = await db.first(OrganizeHistory, stmt)
            if existing:
                await db.delete(existing, audit=False)
            await db.save(history, audit=False)

    @staticmethod
    async def _save_related_file_hashes(
        related_files: List[str], root: str, final: dict, task_id: str = None,
        related_targets: Dict[str, str] = None
    ):
        """
        对关联文件（字幕、音轨等）计算哈希并入库。
        字幕文件继承视频的识别信息（tmdb_id、title、season 等）。
        related_targets: {关联文件名: 整理后目标路径}，用于记录去向。
        """
        from models import FileHash
        from database import db

        for related_file in related_files:
            related_path = os.path.join(root, related_file)
            if not os.path.isfile(related_path):
                continue

            await FileProcessor._log_detail(task_id, f"🔢 计算关联文件哈希: {related_file}")
            hash_result = await HashCalculator.calculate_hashes(related_path)
            if not hash_result:
                await FileProcessor._log_detail(task_id, f"⚠️ 无法计算哈希: {related_file}", "WARN")
                continue

            async with db.session_scope():
                stmt = select(FileHash).where(FileHash.ed2k == hash_result.ed2k)
                existing = await db.first(FileHash, stmt)

                if existing:
                    existing.sha1 = hash_result.sha1
                    existing.ed2k_link = hash_result.ed2k_link
                    existing.original_filename = related_file
                    existing.file_size = hash_result.file_size
                    existing.tmdb_id = str(final.get("tmdb_id")) if final.get("tmdb_id") else None
                    existing.title = final.get("title")
                    existing.season = final.get("season")
                    existing.episode = str(final.get("episode")) if final.get("episode") else None
                    existing.media_type = final.get("category")
                    existing.resolution = final.get("resolution")
                    existing.team = final.get("team")
                    existing.video_encode = final.get("video_encode")
                    existing.audio_encode = final.get("audio_encode")
                    existing.video_effect = final.get("video_effect")
                    existing.source = final.get("source")
                    existing.subtitle = final.get("subtitle")
                    existing.platform = final.get("platform")
                    existing.year = final.get("year")
                    existing.secondary_category = final.get("secondary_category")
                    existing.origin_country = _country_str(final.get("origin_country"))
                    existing.release_date = final.get("release_date")

                    existing.source_path = related_path
                    existing.target_path = (related_targets or {}).get(related_file)
                    existing.calculated_at = datetime.now()
                    await db.save(existing, audit=False)
                    await FileProcessor._log_detail(task_id, f"📝 关联文件哈希已更新: {related_file}")
                else:
                    file_hash = FileHash(
                        sha1=hash_result.sha1,
                        ed2k=hash_result.ed2k,
                        ed2k_link=hash_result.ed2k_link,
                        original_filename=related_file,
                        file_size=hash_result.file_size,
                        tmdb_id=str(final.get("tmdb_id")) if final.get("tmdb_id") else None,
                        title=final.get("title"),
                        season=final.get("season"),
                        episode=str(final.get("episode")) if final.get("episode") else None,
                        media_type=final.get("category"),
                        resolution=final.get("resolution"),
                        team=final.get("team"),
                        video_encode=final.get("video_encode"),
                        audio_encode=final.get("audio_encode"),
                        video_effect=final.get("video_effect"),
                        source=final.get("source"),
                        subtitle=final.get("subtitle"),
                        platform=final.get("platform"),
                        year=final.get("year"),
                        secondary_category=final.get("secondary_category"),
                        origin_country=_country_str(final.get("origin_country")),
                        release_date=final.get("release_date"),

                        source_path=related_path,
                        target_path=(related_targets or {}).get(related_file)
                    )
                    await db.save(file_hash, audit=False)
                    await FileProcessor._log_detail(task_id, f"📝 关联文件哈希已保存: {related_file}")

    @staticmethod
    def _resolve_cd2_client(v_path: str = "", cd2_client_id: str = "", via: str = "local"):
        """
        解析 CD2 客户端：显式 cd2_client_id > mount_path 前缀匹配 > 单实例兜底。
        """
        all_clients = ClientManager.get_all_clients()
        cd2_configs = [c for c in all_clients if c.get('type') == 'cd2']

        if cd2_client_id:
            if any(c.get('id') == cd2_client_id for c in cd2_configs):
                return ClientManager.get_client(cd2_client_id)

        for c_conf in cd2_configs:
            m_path = c_conf.get('mount_path')
            if m_path and v_path and os.path.abspath(v_path).startswith(os.path.abspath(m_path)):
                return ClientManager.get_client(c_conf.get('id'))

        if len(cd2_configs) == 1:
            return ClientManager.get_client(cd2_configs[0].get('id'))
        return None

    @staticmethod
    async def _calculate_hash_for(v_path: str, task: Dict[str, Any], source_via: str, task_id: str = None) -> Optional[HashResult]:
        """
        统一哈希计算入口：本地源读磁盘，云源通过 CD2 下载接口流式计算（不落盘）。
        """
        v_file = os.path.basename(v_path)
        if source_via != "cd2":
            return await HashCalculator.calculate_hashes(v_path)

        try:
            cd2_client = FileProcessor._resolve_cd2_client(v_path, task.get("cd2_client_id"), "cd2")
            if not cd2_client:
                await FileProcessor._log_detail(task_id, "❌ 云源哈希计算失败: 未找到 CD2 客户端", "ERROR")
                return None

            browser = cd2_client._file_browser
            # 大小以下载响应的 Content-Length 为准（open_download_stream 内部已含回退逻辑）
            resp, file_size = await asyncio.to_thread(browser.open_download_stream, v_path)
            await FileProcessor._log_detail(task_id, f"🔢 云源流式计算哈希: {v_file} ({file_size / 1024 / 1024:.2f} MB)")
            try:
                return await HashCalculator.calculate_hashes_from_stream(resp, file_size, v_file)
            finally:
                await asyncio.to_thread(resp.close)
        except Exception as e:
            logger.error(f"云源哈希计算异常: {v_path} | {e}")
            await FileProcessor._log_detail(task_id, f"❌ 云源哈希计算异常: {e}", "ERROR")
            return None

    @staticmethod
    async def organize_video_file(v_path: str, task: Dict[str, Any], context: Dict[str, Any] = None, dry_run: bool = True, task_id: str = None) -> List[Dict[str, Any]]:
        """
        处理单个视频文件及其关联字幕
        """
        if context is None:
            context = FileProcessor.load_context(task)
            
        # [New] History Check
        ignore_history = task.get("ignore_history", False)
        retry_failed = task.get("retry_failed", True)  # 默认重试失败项
        if not dry_run and not ignore_history:
            from database import db
            from models import OrganizeHistory
            async with db.session_scope():
                # 构建状态过滤条件
                skip_statuses = ["success", "skipped"]
                if not retry_failed:
                    skip_statuses.append("failed")  # 不重试失败项时，也跳过 failed
                
                stmt = select(OrganizeHistory).where(
                    and_(
                        OrganizeHistory.source_path == v_path,
                        OrganizeHistory.status.in_(skip_statuses)
                    )
                )
                existing = await db.first(OrganizeHistory, stmt)
                if existing:
                    status_desc = {
                        "success": "已成功整理",
                        "skipped": "已跳过",
                        "failed": "之前识别失败"
                    }.get(existing.status, existing.status)
                    await FileProcessor._log_detail(task_id, f"⏭️ 跳过（{status_desc}）: {os.path.basename(v_path)}")
                    return [{"type": "skip", "skip_type": "history", "source": v_path, "reason": f"{status_desc}，历史记录已存在"}]

        rule = context["rule"]
        if not rule: return [{"type": "error", "source": v_path, "message": "Rule not found"}]

        source_dir = task.get("source_dir")
        target_dir = task.get("target_dir")
        action_type = task.get("action_type", "move")
        source_via = task.get("source_via", "local")
        target_via = task.get("target_via", "local")
        action_label = {'move': '移动', 'copy': '复制', 'cd2_move': 'CD2移动', 'cd2_copy': 'CD2复制', 'hash_only': '仅记录哈希'}.get(action_type, action_type)
        conflict_mode = "overwrite" if task.get("overwrite_mode") else "skip"

        root = os.path.dirname(v_path)
        v_file = os.path.basename(v_path)
        v_base, v_ext = os.path.splitext(v_file)

        results = []
        recog_task_id = None       # 单文件识别任务（覆盖识别+转移全流程）
        recog_stats_base: Dict[str, Any] = {}  # 识别基础信息，各收口点 stats 公共部分
        cd2_client = None

        try:
            # 寻找关联字幕和音轨 - 移至线程执行
            related_files = []
            if source_via != "cd2":
                try:
                    all_files_in_dir = await asyncio.to_thread(os.listdir, root)
                    for f in all_files_in_dir:
                        f_ext = os.path.splitext(f)[1].lower()
                        if f_ext in FileProcessor.RELATED_EXTS and f.startswith(v_base):
                            related_files.append(f)
                except Exception: pass # 目录可能不存在或无法读取
            else:
                # 云盘源：通过 CD2 gRPC 枚举视频同目录的关联文件，规则与本地一致
                try:
                    _disc_client = FileProcessor._resolve_cd2_client(v_path, task.get("cd2_client_id"), "cd2")
                    if _disc_client:
                        listing = await asyncio.to_thread(
                            _disc_client._file_browser.list_dir, os.path.dirname(v_path) or "/"
                        )
                        if listing.get("success"):
                            for entry in listing.get("entries", []):
                                if entry.get("is_dir"):
                                    continue
                                f = entry.get("name", "")
                                f_ext = os.path.splitext(f)[1].lower()
                                if f_ext in FileProcessor.RELATED_EXTS and f.startswith(v_base):
                                    related_files.append(f)
                except Exception as disc_e:
                    logger.warning(f"云源关联文件枚举失败: {disc_e}")

            # 识别
            # [NEW] 实时获取规则，确保预览中新增的规则立即生效
            all_cached = ConfigManager.get_cached_rules()
            cfg = ConfigManager.get_config()
            all_noise = cfg.get("custom_noise_words", []) + all_cached.get("noise", [])
            all_groups = cfg.get("custom_release_groups", []) + all_cached.get("groups", [])
            all_render = cfg.get("custom_render_words", []) + all_cached.get("render", [])

            try:
                rel_input_path = os.path.relpath(v_path, os.path.dirname(source_dir))
            except ValueError:
                rel_input_path = v_file

            f_tmdb = task.get("forced_tmdb_id")
            f_type = task.get("forced_type")
            f_season = task.get("forced_season")

            # 补全控制台日志 - 打印完整路径
            logger.debug(f"正在处理文件: {v_path}")

            result_data, recog_logs = await MovieRecognizer.recognize_full(
                rel_input_path, 
                all_noise=all_noise, 
                all_groups=all_groups, 
                api_key=context["api_key"], 
                anime_priority=context["anime_priority"], 
                enable_title_segmentation=context.get("enable_title_segmentation"),
                all_render=all_render,
                forced_tmdb_id=f_tmdb, 
                forced_type=f_type, 
                forced_season=f_season,
                series_fingerprint=task.get("series_fingerprint", True),
                original_input_path=v_path
            )
            
            await FileProcessor._log_detail(task_id, f"📄 处理文件: {v_path}")
            
            recog_task_id = None
            try:
                from task_history import start_task as _start_task, log_task as _rt_log_task, finish_task as _finish_task
                import uuid as _uuid
                recog_task_id = f"recog_{_uuid.uuid4().hex[:12]}"
                await _start_task(recog_task_id, "识别", f"[识别] {v_file}")
                for log_msg in recog_logs:
                    level = "ERROR" if "❌" in log_msg or "[ERROR]" in log_msg else "WARN" if "⚠️" in log_msg else "INFO"
                    await _rt_log_task(recog_task_id, log_msg, level)
            except Exception:
                recog_task_id = None
            
            final = result_data.get("final_result", {})
            
            if not final.get("tmdb_id"):
                logger.info(f"✨ [整理] 识别失败: {v_file}")
                await FileProcessor._log_detail(task_id, f"❌ 识别失败: 无 TMDB ID", "ERROR")
                if recog_task_id:
                    try:
                        await _rt_log_task(recog_task_id, f"❌ 识别失败: 无 TMDB ID", "ERROR")
                        await _finish_task(recog_task_id, "error", stats={"errors": 1, "message": "识别失败 (无 TMDB ID)"})
                    except Exception:
                        pass
                if not dry_run:
                    from models import OrganizeHistory
                    history = OrganizeHistory(
                        source_path=v_path, filename=v_file,
                        source_via=source_via, target_via=target_via,
                        status="failed", message="识别失败 (无 TMDB ID)",
                        action_type=action_type,
                        rule_id=task.get("rule_id"),
                        source_dir=task.get("source_dir"),
                        target_dir=task.get("target_dir"),
                        overwrite_mode=task.get("overwrite_mode"),
                        check_emby_exists=task.get("check_emby_exists", False),
                        calculate_hash=task.get("calculate_hash", False),
                        clean_empty_dir=task.get("clean_empty_dir", False),
                        trigger_strm=task.get("trigger_strm", False),
                        task_id=recog_task_id
                    )
                    await FileProcessor._save_history_force(history)
                    
                    await notification_manager.notify_organize_failed(v_path, "识别失败 (无法获取 TMDB ID)")
                    
                return [{"type": "skip", "skip_type": "recognition_failed", "source": v_path, "reason": "识别失败 (无 TMDB ID)"}]

            _cat = final.get("category") or "未知"
            _ep_info = f" S{final.get('season','-')}E{final.get('episode','-')}" if _cat == "剧集" else ""
            logger.info(f"✨ [整理] 识别: {v_file} → {final['title']} | {_cat}{_ep_info} (ID: {final['tmdb_id']})")
            await FileProcessor._log_both(task_id, recog_task_id, f"✅ 识别成功: {final['title']} | {_cat}{_ep_info} (ID: {final['tmdb_id']})")

            # 识别基础信息（各收口点的 stats 公共部分）
            recog_stats_base = {
                "title": final.get("title"), "tmdb_id": final.get("tmdb_id"),
                "category": final.get("category"), "season": final.get("season"),
                "episode": final.get("episode"),
            }

            # --- [New] Emby Check ---
            check_emby_exists = task.get("check_emby_exists", False)
            
            if check_emby_exists:
                from emby_client import get_emby_client, EmbyAPIError
                from emby_index_service import wrap_emby_with_index
                emby_client = get_emby_client()
                
                tmdb_id = final.get("tmdb_id")
                media_type = final.get("category")
                season = final.get("season")
                episode = final.get("episode")
                
                if tmdb_id and emby_client:
                    try:
                        exists = False
                        cleanup = await wrap_emby_with_index(emby_client, tmdb_id, media_type)
                        try:
                            if media_type == "电影":
                                exists = await asyncio.to_thread(emby_client.check_movie_exists, tmdb_id)
                            elif media_type == "剧集" and season is not None and episode is not None:
                                exists = await asyncio.to_thread(emby_client.check_episode_exists, tmdb_id, season, episode)
                        except EmbyAPIError as e:
                            logger.warning(f"Emby API 不可用，无法确认库状态，按未入库继续处理: {e}")
                        finally:
                            await cleanup()
                        
                        if exists:
                            logger.info(f"✨ [整理] Emby已存在: {final['title']} - S{season}E{episode}")
                            await FileProcessor._log_both(task_id, recog_task_id, f"✅ Emby库中已存在: {final['title']} - S{season}E{episode} (TMDB: {tmdb_id})")
                            if not dry_run:
                                from models import OrganizeHistory
                                history = OrganizeHistory(
                                    source_path=v_path, filename=v_file,
                                    source_via=source_via, target_via=target_via,
                                    tmdb_id=str(tmdb_id), title=final.get("title"),
                                    season=season, episode=str(episode),
                                    media_type=media_type,
                                    action_type=action_type,
                                    status="skipped", message="Emby库中已存在",
                                    rule_id=task.get("rule_id"),
                                    source_dir=task.get("source_dir"),
                                    target_dir=task.get("target_dir"),
                                    overwrite_mode=task.get("overwrite_mode"),
                                    check_emby_exists=task.get("check_emby_exists", False),
                                    calculate_hash=task.get("calculate_hash", False),
                                    clean_empty_dir=task.get("clean_empty_dir", False),
                                    trigger_strm=task.get("trigger_strm", False),
                                    task_id=recog_task_id
                                )
                                await FileProcessor._save_history_force(history)
                            await FileProcessor._finish_recog(recog_task_id, "completed", {**recog_stats_base, "skipped": 1, "message": "Emby库中已存在"})
                            return [{"type": "skip", "skip_type": "emby_exists", "source": v_path, "reason": "Emby库中已存在"}]
                        else:
                            await FileProcessor._log_both(task_id, recog_task_id, f"❌ Emby库中不存在: {final['title']} - S{season}E{episode} (TMDB: {tmdb_id})，继续处理")
                    except Exception as e:
                        logger.warning(f"Emby检查异常: {str(e)}")
                        await FileProcessor._log_both(task_id, recog_task_id, f"⚠️ Emby检查异常: {str(e)}", "WARN")
                        import traceback
                        await FileProcessor._log_both(task_id, recog_task_id, f"异常堆栈: {traceback.format_exc()}", "WARN")
                else:
                    if not emby_client:
                        await FileProcessor._log_detail(task_id, f"⚠️ 跳过 Emby 检查 - Emby 客户端未初始化")

            final["filename"] = v_file
            final["path"] = v_path
            
            # [New] Get File Size
            try:
                f_stat = os.stat(v_path)
                f_size_bytes = f_stat.st_size
            except Exception:
                # 云源路径本地不存在，通过 CD2 gRPC 获取真实大小
                f_size_bytes = 0
                if source_via == "cd2":
                    try:
                        _size_client = FileProcessor._resolve_cd2_client(v_path, task.get("cd2_client_id"), "cd2")
                        if _size_client:
                            f_size_bytes = await asyncio.to_thread(
                                _size_client._file_browser.get_cloud_file_size, v_path
                            )
                    except Exception as size_e:
                        logger.debug(f"获取云源文件大小失败: {size_e}")
            if f_size_bytes:
                f_size_mb = f_size_bytes / (1024 * 1024)
                if f_size_mb > 1024:
                    final["file_size"] = f"{f_size_mb/1024:.2f}GB"
                else:
                    final["file_size"] = f"{f_size_mb:.2f}MB"
            else:
                final["file_size"] = "Unknown"

            is_batch_item = "-" in str(final.get("episode", ""))
            final["file_count"] = len(related_files) + 1 # Video + Related Files
            
            is_movie = final.get("category") == "电影"
            pattern = rule.get("movie_pattern" if is_movie else "tv_pattern")
            
            new_rel_path = Renamer.format_path(result_data, pattern, v_file)
            new_abs_path = os.path.join(target_dir, new_rel_path)
            
            # Prepare file list (video + related files)
            plan_items = [(v_path, new_abs_path)]
            
            # Related files preparation (subtitles + audio tracks)
            related_targets: Dict[str, str] = {}  # {关联文件名: 整理后目标路径}
            for related_file in related_files:
                file_tag = related_file[len(v_base):]
                v_new_dir = os.path.dirname(new_rel_path)
                v_new_base = os.path.splitext(os.path.basename(new_rel_path))[0]
                related_rel_path = os.path.join(v_new_dir, v_new_base + file_tag)
                related_abs_old = os.path.join(root, related_file)
                related_abs_new = os.path.join(target_dir, related_rel_path)
                plan_items.append((related_abs_old, related_abs_new))
                related_targets[related_file] = related_abs_new

            # [New] Calculate Hash before move (if enabled)
            # 云源通过 CD2 下载接口流式计算（不落盘），本地源直接读磁盘
            hash_result: Optional[HashResult] = None
            if task.get("calculate_hash", False) and not dry_run:
                hash_result = await FileProcessor._calculate_hash_for(v_path, task, source_via, task_id)
                if hash_result:
                    await FileProcessor._log_both(task_id, recog_task_id, f"🔢 SHA1: {hash_result.sha1}")
                    await FileProcessor._log_both(task_id, recog_task_id, f"🔢 ED2K: {hash_result.ed2k_link}")
                else:
                    await FileProcessor._log_both(task_id, recog_task_id, f"❌ 无法计算哈希: {v_file}", "WARN")

            # --- hash_only: 仅识别+记录哈希，不执行文件操作 ---
            if action_type == "hash_only":
                if not dry_run:
                    # hash_only 模式下始终计算哈希（不受 calculate_hash 开关限制）
                    if not hash_result:
                        hash_result = await FileProcessor._calculate_hash_for(v_path, task, source_via, task_id)
                        if hash_result:
                            await FileProcessor._log_both(task_id, recog_task_id, f"🔢 SHA1: {hash_result.sha1}")
                            await FileProcessor._log_both(task_id, recog_task_id, f"🔢 ED2K: {hash_result.ed2k_link}")
                        else:
                            await FileProcessor._log_both(task_id, recog_task_id, f"❌ 无法计算哈希: {v_file}", "ERROR")

                    if hash_result:
                        from models import FileHash
                        from database import db
                        async with db.session_scope():
                            stmt = select(FileHash).where(FileHash.ed2k == hash_result.ed2k)
                            existing = await db.first(FileHash, stmt)
                            if existing:
                                existing.sha1 = hash_result.sha1
                                existing.ed2k_link = hash_result.ed2k_link
                                existing.original_filename = v_file
                                existing.file_size = hash_result.file_size
                                existing.tmdb_id = str(final.get("tmdb_id")) if final.get("tmdb_id") else None
                                existing.title = final.get("title")
                                existing.season = final.get("season")
                                existing.episode = str(final.get("episode")) if final.get("episode") else None
                                existing.media_type = final.get("category")
                                existing.resolution = final.get("resolution")
                                existing.team = final.get("team")
                                existing.video_encode = final.get("video_encode")
                                existing.audio_encode = final.get("audio_encode")
                                existing.video_effect = final.get("video_effect")
                                existing.source = final.get("source")
                                existing.subtitle = final.get("subtitle")
                                existing.platform = final.get("platform")
                                existing.year = final.get("year")
                                existing.secondary_category = final.get("secondary_category")
                                existing.origin_country = _country_str(final.get("origin_country"))
                                existing.release_date = final.get("release_date")

                                existing.source_path = v_path
                                existing.target_path = None
                                existing.calculated_at = datetime.now()
                                await db.save(existing, audit=False)
                                await FileProcessor._log_detail(task_id, f"📝 哈希记录已更新: {v_file}")
                            else:
                                file_hash = FileHash(
                                    sha1=hash_result.sha1,
                                    ed2k=hash_result.ed2k,
                                    ed2k_link=hash_result.ed2k_link,
                                    original_filename=v_file,
                                    file_size=hash_result.file_size,
                                    tmdb_id=str(final.get("tmdb_id")) if final.get("tmdb_id") else None,
                                    title=final.get("title"),
                                    season=final.get("season"),
                                    episode=str(final.get("episode")) if final.get("episode") else None,
                                    media_type=final.get("category"),
                                    resolution=final.get("resolution"),
                                    team=final.get("team"),
                                    video_encode=final.get("video_encode"),
                                    audio_encode=final.get("audio_encode"),
                                    video_effect=final.get("video_effect"),
                                    source=final.get("source"),
                                    subtitle=final.get("subtitle"),
                                    platform=final.get("platform"),
                                    year=final.get("year"),
                                    secondary_category=final.get("secondary_category"),
                                    origin_country=_country_str(final.get("origin_country")),
                                    release_date=final.get("release_date"),
                                    source_path=v_path,
                                    target_path=None
                                )
                                await db.save(file_hash, audit=False)
                                await FileProcessor._log_detail(task_id, f"📝 哈希记录已保存: {v_file}")

                        # [New] 计算关联字幕文件的哈希（云源文件不在本地，跳过）
                        if related_files and source_via != "cd2":
                            await FileProcessor._save_related_file_hashes(related_files, root, final, task_id)

                        results.append({
                            "type": "item", "status": "success",
                            "source": v_path, "target": None, "action": "hash_only",
                            "title": final.get("title"), "season": final.get("season"),
                            "episode": final.get("episode"), "tmdb_id": final.get("tmdb_id"),
                            "msg": "仅记录哈希"
                        })
                        await FileProcessor._finish_recog(recog_task_id, "completed", {**recog_stats_base, "success": 1})
                    else:
                        # 哈希计算失败：记录到整理历史并标记失败
                        await FileProcessor._log_both(task_id, recog_task_id, f"❌ 仅记录哈希失败: {v_file}", "ERROR")
                        from models import OrganizeHistory
                        history = OrganizeHistory(
                            source_path=v_path, filename=v_file,
                            source_via=source_via, target_via=target_via,
                            status="failed", message="哈希计算失败",
                            action_type=action_type,
                            rule_id=task.get("rule_id"),
                            source_dir=task.get("source_dir"),
                            target_dir=task.get("target_dir"),
                            overwrite_mode=task.get("overwrite_mode"),
                            check_emby_exists=task.get("check_emby_exists", False),
                            calculate_hash=task.get("calculate_hash", False),
                            clean_empty_dir=task.get("clean_empty_dir", False),
                            trigger_strm=task.get("trigger_strm", False),
                            task_id=recog_task_id
                        )
                        await FileProcessor._save_history_force(history)

                        results.append({
                            "type": "item", "status": "error",
                            "source": v_path, "target": None, "action": "hash_only",
                            "title": final.get("title"), "season": final.get("season"),
                            "episode": final.get("episode"), "tmdb_id": final.get("tmdb_id"),
                            "msg": "哈希计算失败"
                        })
                        await FileProcessor._finish_recog(recog_task_id, "error", {**recog_stats_base, "errors": 1, "message": "哈希计算失败"})
                else:
                    await FileProcessor._log_both(task_id, recog_task_id, f"🔍 [预览] 仅记录哈希: {v_file} → {final.get('title', '未知')}")

                    results.append({
                        "type": "item", "status": "success",
                        "source": v_path, "target": None, "action": "hash_only",
                        "title": final.get("title"), "season": final.get("season"),
                        "episode": final.get("episode"), "tmdb_id": final.get("tmdb_id"),
                        "msg": "仅记录哈希"
                    })
                    await FileProcessor._finish_recog(recog_task_id, "completed", {**recog_stats_base, "skipped": 1, "message": "预览模式"})

                return results

            # Execute
            if not dry_run and action_type in ["cd2_move", "cd2_copy"]:
                # --- CD2 路径：按源/目标归属域 (via) 路由 ---
                cd2_client = FileProcessor._resolve_cd2_client(
                    v_path, task.get("cd2_client_id"),
                    source_via if source_via == "cd2" else ("cd2" if target_via == "cd2" else "local")
                )

                if cd2_client:
                    related_outcomes: Dict[str, str] = {}  # {关联文件名: 单项执行结果}
                    if source_via == "cd2" or target_via == "cd2":
                        # --- via 路由矩阵：逐项执行（视频 + 关联文件） ---
                        # 秒传配置：仅 local→cd2 且任务开启秒传模式时生效
                        rapid_cfg = None
                        _rapid_mode = task.get("cd2_rapid_mode", "off")
                        if (source_via == "local" and target_via == "cd2"
                                and _rapid_mode in ("rapid_then_upload", "rapid_only")):
                            try:
                                _interval = max(1, int(task.get("cd2_rapid_interval", 60)))
                            except (TypeError, ValueError):
                                _interval = 60
                            try:
                                _max_retries = max(1, int(task.get("cd2_rapid_max_retries", 6)))
                            except (TypeError, ValueError):
                                _max_retries = 6
                            rapid_cfg = {
                                "mode": _rapid_mode,
                                "interval": _interval,
                                "max_retries": _max_retries,
                            }
                        batch_res = "success"
                        any_skipped = False
                        related_outcomes = {}  # {关联文件名: 单项执行结果}
                        for src, dst in plan_items:
                            res = await FileExecutor.execute_action(
                                src, dst, action_type, conflict_mode,
                                context.get("dir_cache"), source_via=source_via, target_via=target_via,
                                rapid=rapid_cfg
                            )
                            if src != v_path:
                                related_outcomes[os.path.basename(src)] = res
                            if res == "success":
                                await FileProcessor._log_both(task_id, recog_task_id, f"📦 CD2 {action_label}成功: {os.path.basename(src)}")
                            elif res in ("skipped", "skipped_conflict"):
                                any_skipped = True
                                await FileProcessor._log_both(task_id, recog_task_id, f"⏭️ {action_label}跳过（目标已存在，未开启覆盖模式）: {os.path.basename(src)}")
                            elif res == "cd2_rapid_miss":
                                batch_res = res
                                # 秒传未命中：加入重试队列，等待网盘哈希库更新后自动重试
                                from clients.cd2.rapid_retry import RapidUploadRetryManager
                                await RapidUploadRetryManager.enqueue(
                                    client_id=(cd2_client.config or {}).get("id"),
                                    local_path=src, cloud_path=dst,
                                    action_type=action_type,
                                    rapid_mode=_rapid_mode,
                                    retry_interval=rapid_cfg["interval"],
                                    max_retries=rapid_cfg["max_retries"],
                                    meta={
                                        "source_path": src,
                                        "filename": os.path.basename(src),
                                        "action_type": action_type,
                                        "final": final,
                                        "task": {
                                            "rule_id": task.get("rule_id"),
                                            "source_dir": task.get("source_dir"),
                                            "target_dir": task.get("target_dir"),
                                            "overwrite_mode": task.get("overwrite_mode"),
                                            "check_emby_exists": task.get("check_emby_exists", False),
                                            "calculate_hash": task.get("calculate_hash", False),
                                            "clean_empty_dir": task.get("clean_empty_dir", False),
                                            "trigger_strm": task.get("trigger_strm", False),
                                        },
                                        "task_id": recog_task_id,
                                        "create_history": src == v_path,
                                    },
                                )
                                await FileProcessor._log_both(task_id, recog_task_id, f"⏳ CD2 秒传未命中，已加入重试队列: {os.path.basename(src)}")
                            else:
                                batch_res = res
                                logger.error(f"❌ CD2 {action_label}失败: {os.path.basename(src)} → {FileExecutor.get_status_message(res)} (状态码: {res})")
                                await FileProcessor._log_both(task_id, recog_task_id, f"❌ CD2 {action_label}失败: {os.path.basename(src)} → {FileExecutor.get_status_message(res)}", "ERROR")
                        if batch_res == "success" and any_skipped:
                            batch_res = "skipped"
                    else:
                        # --- 旧版挂载路径模式（源/目标均为本地挂载视图，行为不变） ---
                        target_parent = os.path.dirname(new_abs_path)
                        await FileExecutor._ensure_cd2_dir(cd2_client, target_parent, context.get("dir_cache"))
                        batch_res = await FileExecutor._execute_cd2_batch(cd2_client, plan_items, action_type)
                        related_outcomes = {f: batch_res for f in related_files}
                        if batch_res == "success":
                            await FileProcessor._log_both(task_id, recog_task_id, f"📦 CD2 {action_label}成功: {v_file} → {new_abs_path}")
                        elif batch_res == "skipped":
                            await FileProcessor._log_both(task_id, recog_task_id, f"⏭️ {action_label}跳过（目标已存在，未开启覆盖模式）: {v_file}")
                        else:
                            await FileProcessor._log_both(task_id, recog_task_id, f"❌ CD2 {action_label}失败: {v_file} → {FileExecutor.get_status_message(batch_res)}", "ERROR")
                    for src, dst in plan_items:
                        # 如果整个批次跳过，则单个项标记为 skip
                        item_status = "error"
                        if batch_res == "success": item_status = "success"
                        elif batch_res == "skipped": item_status = "skip"

                        # 添加识别信息到结果中
                        result_item = {
                            "type": "item", "status": item_status,
                            "source": src, "target": dst, "action": action_type,
                            "source_via": source_via, "target_via": target_via,
                            "msg": FileExecutor.get_status_message(batch_res)
                        }
                        # 只对视频文件添加识别信息
                        if src == v_path:
                            result_item["title"] = final.get("title")
                            result_item["season"] = final.get("season")
                            result_item["episode"] = final.get("episode")
                            result_item["tmdb_id"] = final.get("tmdb_id")
                        results.append(result_item)
                    
                    # STRM Linkage (only if batch succeeded)
                    if batch_res == "success":
                        # [New] 清理源空目录 (向上递归)
                        if task.get("clean_empty_dir", False) and action_type == "cd2_move":
                            if source_via == "local":
                                source_parent = os.path.dirname(v_path)
                                await FileExecutor._cleanup_empty_parents(source_parent, source_dir)
                            elif source_via == "cd2":
                                # 云盘源 (云→云/云→本地): gRPC 向上清理，删到任务源目录为止
                                _cd2_cleanup_client = FileProcessor._resolve_cd2_client(
                                    v_path, task.get("cd2_client_id"), "cd2"
                                )
                                if _cd2_cleanup_client:
                                    try:
                                        _cleaned = await asyncio.to_thread(
                                            _cd2_cleanup_client.cleanup_empty_parents,
                                            os.path.dirname(v_path), source_dir,
                                        )
                                        if _cleaned:
                                            await FileProcessor._log_detail(task_id, f"🧹 已清理云盘源空目录 {_cleaned} 个")
                                    except Exception as _e:
                                        logger.warning(f"云盘源空目录清理失败: {_e}")

                        # [Notify]
                        await notification_manager.notify_organize_complete(final)

                        # [Always Trigger] 使用模拟 Webhook 方式触发 STRM
                        # 不再检查 trigger_strm 开关，交由 STRM 任务自身的 Webhook 响应开关控制
                        cd2_path = new_abs_path if target_via == "cd2" else cd2_client._to_cd2_path(new_abs_path)
                        asyncio.create_task(FileProcessor._simulate_cd2_webhook(cd2_path))
                    
                    # [Record History] - 无论 success 还是 skipped 都保存历史记录
                    if not dry_run and batch_res in ["success", "skipped"]:
                        from models import OrganizeHistory, FileHash
                        from database import db
                        related_payload = FileProcessor._related_files_payload(related_files, related_targets, related_outcomes)
                        async with db.session_scope():
                            history = OrganizeHistory(
                                source_path=v_path, target_path=new_abs_path,
                                source_via=source_via, target_via=target_via,
                                filename=v_file, tmdb_id=str(final.get("tmdb_id")),
                                title=final.get("title"), season=final.get("season"),
                                episode=str(final.get("episode")),
                                media_type=final.get("category"),
                                action_type=action_type,
                                file_size=final.get("file_size"),
                                resolution=final.get("resolution"),
                                team=final.get("team"),
                                video_encode=final.get("video_encode"),
                                year=str(final.get("year")) if final.get("year") else None,
                                status="success" if batch_res == "success" else "skipped",
                                message=None if batch_res == "success" else f"目标已存在 (跳过)",
                                related_files=related_payload,
                                rule_id=task.get("rule_id"),
                                source_dir=task.get("source_dir"),
                                target_dir=task.get("target_dir"),
                                overwrite_mode=task.get("overwrite_mode"),
                                check_emby_exists=task.get("check_emby_exists", False),
                                calculate_hash=task.get("calculate_hash", False),
                                clean_empty_dir=task.get("clean_empty_dir", False),
                                trigger_strm=task.get("trigger_strm", False),
                                task_id=recog_task_id
                            )
                            # 按 source_path 去重后保存
                            stmt = select(OrganizeHistory).where(OrganizeHistory.source_path == v_path)
                            existing = await db.first(OrganizeHistory, stmt)
                            if existing:
                                await db.delete(existing, audit=False)
                            await db.save(history, audit=False)
                            
                            # [New] Save FileHash (按 ED2K 去重) - 仅成功时保存
                            if hash_result and batch_res == "success":
                                stmt = select(FileHash).where(FileHash.ed2k == hash_result.ed2k)
                                existing = await db.first(FileHash, stmt)
                                if existing:
                                    existing.sha1 = hash_result.sha1
                                    existing.ed2k_link = hash_result.ed2k_link
                                    existing.original_filename = v_file
                                    existing.file_size = hash_result.file_size
                                    existing.tmdb_id = str(final.get("tmdb_id"))
                                    existing.title = final.get("title")
                                    existing.season = final.get("season")
                                    existing.episode = str(final.get("episode"))
                                    existing.media_type = final.get("category")
                                    existing.resolution = final.get("resolution")
                                    existing.team = final.get("team")
                                    existing.video_encode = final.get("video_encode")
                                    existing.audio_encode = final.get("audio_encode")
                                    existing.video_effect = final.get("video_effect")
                                    existing.source = final.get("source")
                                    existing.subtitle = final.get("subtitle")
                                    existing.platform = final.get("platform")
                                    existing.year = final.get("year")
                                    existing.secondary_category = final.get("secondary_category")
                                    existing.origin_country = _country_str(final.get("origin_country"))
                                    existing.release_date = final.get("release_date")
                                    existing.source_path = v_path
                                    existing.target_path = new_abs_path
                                    existing.calculated_at = datetime.now()
                                    await db.save(existing, audit=False)
                                else:
                                    file_hash = FileHash(
                                        sha1=hash_result.sha1,
                                        ed2k=hash_result.ed2k,
                                        ed2k_link=hash_result.ed2k_link,
                                        original_filename=v_file,
                                        file_size=hash_result.file_size,
                                        tmdb_id=str(final.get("tmdb_id")),
                                        title=final.get("title"),
                                        season=final.get("season"),
                                        episode=str(final.get("episode")),
                                        media_type=final.get("category"),
                                        resolution=final.get("resolution"),
                                        team=final.get("team"),
                                        video_encode=final.get("video_encode"),
                                        audio_encode=final.get("audio_encode"),
                                        video_effect=final.get("video_effect"),
                                        source=final.get("source"),
                                        subtitle=final.get("subtitle"),
                                        platform=final.get("platform"),
                                        year=final.get("year"),
                                        secondary_category=final.get("secondary_category"),
                                        origin_country=_country_str(final.get("origin_country")),
                                        release_date=final.get("release_date"),

                                        source_path=v_path,
                                        target_path=new_abs_path
                                    )
                                    await db.save(file_hash, audit=False)
                            
                            # [New] 计算关联字幕文件的哈希（云源文件不在本地，跳过）
                            if hash_result and batch_res == "success" and related_files and source_via != "cd2":
                                await FileProcessor._save_related_file_hashes(related_files, root, final, task_id, related_targets)

                    # recog 任务收口（覆盖成功/跳过/秒传未命中/失败四种批次结果）
                    if not dry_run:
                        _rf_stats = {**recog_stats_base, "target_path": new_abs_path,
                                     "related_files": FileProcessor._related_files_payload(related_files, related_targets, related_outcomes)}
                        if batch_res == "success":
                            await FileProcessor._finish_recog(recog_task_id, "completed", {**_rf_stats, "success": 1})
                        elif batch_res == "skipped":
                            await FileProcessor._finish_recog(recog_task_id, "completed", {**_rf_stats, "skipped": 1, "message": "目标已存在 (跳过)"})
                        elif batch_res == "cd2_rapid_miss":
                            await FileProcessor._finish_recog(recog_task_id, "completed", {**_rf_stats, "skipped": 1, "message": "CD2 秒传未命中，已加入重试队列"})
                        else:
                            await FileProcessor._finish_recog(recog_task_id, "error", {**_rf_stats, "errors": 1, "message": FileExecutor.get_status_message(batch_res)})

                    return results

            # --- Standard Path ---
            related_outcomes: Dict[str, str] = {}  # {关联文件名: 单项执行结果}
            for src, dst in plan_items:
                v_res = "preview"
                if not dry_run:
                    v_res = await FileExecutor.execute_action(src, dst, action_type, conflict_mode, context.get("dir_cache"))

                if src != v_path:
                    related_outcomes[os.path.basename(src)] = v_res
                if v_res in ["success", "preview"]:
                    if src == v_path:
                        await FileProcessor._log_both(task_id, recog_task_id, f"📦 {action_label}成功: {v_file} → {dst}")
                    else:
                        await FileProcessor._log_both(task_id, recog_task_id, f"📎 {action_label}成功: {os.path.basename(src)} → {dst}")
                elif v_res in ["skipped", "skipped_conflict"]:
                    await FileProcessor._log_both(task_id, recog_task_id, f"⏭️ {action_label}跳过（目标已存在，未开启覆盖模式）: {os.path.basename(src)}")
                else:
                    await FileProcessor._log_both(task_id, recog_task_id, f"❌ {action_label}失败: {os.path.basename(src)} → {FileExecutor.get_status_message(v_res)}", "ERROR")
                
                # 添加识别信息到结果中
                result_item = {
                    "type": "item",
                    "status": "success" if v_res in ["success", "preview"] else ("skip" if v_res in ["skipped", "skipped_conflict"] else "error"),
                    "source": src, "target": dst, "action": action_type,
                    "source_via": source_via, "target_via": target_via,
                    "msg": FileExecutor.get_status_message(v_res)
                }
                # 只对视频文件添加识别信息
                if src == v_path:
                    result_item["title"] = final.get("title")
                    result_item["season"] = final.get("season")
                    result_item["episode"] = final.get("episode")
                    result_item["tmdb_id"] = final.get("tmdb_id")
                results.append(result_item)
                
                # STRM Linkage for video only
                if not dry_run and src == v_path:
                    # [Record History]
                    from models import OrganizeHistory, FileHash
                    from database import db
                    async with db.session_scope():
                        history = OrganizeHistory(
                            source_path=v_path, target_path=new_abs_path,
                            source_via=source_via, target_via=target_via,
                            filename=v_file, tmdb_id=str(final.get("tmdb_id")),
                            title=final.get("title"), season=final.get("season"),
                            episode=str(final.get("episode")),
                            media_type=final.get("category"),
                            action_type=action_type,
                            file_size=final.get("file_size"),
                            # Details
                            resolution=final.get("resolution"),
                            team=final.get("team"),
                            video_encode=final.get("video_encode"),
                            year=str(final.get("year")) if final.get("year") else None,
                            status="success" if v_res == "success" else ("skipped" if v_res in ["skipped", "skipped_conflict"] else "failed"),
                            message=None if v_res == "success" else f"物理操作失败: {FileExecutor.get_status_message(v_res)}",
                            related_files=FileProcessor._related_files_payload(related_files, related_targets, related_outcomes),
                            rule_id=task.get("rule_id"),
                            source_dir=task.get("source_dir"),
                            target_dir=task.get("target_dir"),
                            overwrite_mode=task.get("overwrite_mode"),
                            check_emby_exists=task.get("check_emby_exists", False),
                            calculate_hash=task.get("calculate_hash", False),
                            clean_empty_dir=task.get("clean_empty_dir", False),
                            trigger_strm=task.get("trigger_strm", False),
                            task_id=recog_task_id
                        )
                        # 按 source_path 去重后保存
                        stmt = select(OrganizeHistory).where(OrganizeHistory.source_path == v_path)
                        existing = await db.first(OrganizeHistory, stmt)
                        if existing:
                            await db.delete(existing, audit=False)
                        await db.save(history, audit=False)
                        
                        # [New] Save FileHash (按 ED2K 去重)
                        if hash_result and v_res == "success":
                            stmt = select(FileHash).where(FileHash.ed2k == hash_result.ed2k)
                            existing = await db.first(FileHash, stmt)
                            if existing:
                                existing.sha1 = hash_result.sha1
                                existing.ed2k_link = hash_result.ed2k_link
                                existing.original_filename = v_file
                                existing.file_size = hash_result.file_size
                                existing.tmdb_id = str(final.get("tmdb_id"))
                                existing.title = final.get("title")
                                existing.season = final.get("season")
                                existing.episode = str(final.get("episode"))
                                existing.media_type = final.get("category")
                                existing.resolution = final.get("resolution")
                                existing.team = final.get("team")
                                existing.video_encode = final.get("video_encode")
                                existing.audio_encode = final.get("audio_encode")
                                existing.video_effect = final.get("video_effect")
                                existing.source = final.get("source")
                                existing.subtitle = final.get("subtitle")
                                existing.platform = final.get("platform")
                                existing.year = final.get("year")
                                existing.secondary_category = final.get("secondary_category")
                                existing.origin_country = _country_str(final.get("origin_country"))
                                existing.release_date = final.get("release_date")

                                existing.source_path = v_path
                                existing.target_path = new_abs_path
                                existing.calculated_at = datetime.now()
                                await db.save(existing, audit=False)
                            else:
                                file_hash = FileHash(
                                    sha1=hash_result.sha1,
                                    ed2k=hash_result.ed2k,
                                    ed2k_link=hash_result.ed2k_link,
                                    original_filename=v_file,
                                    file_size=hash_result.file_size,
                                    tmdb_id=str(final.get("tmdb_id")),
                                    title=final.get("title"),
                                    season=final.get("season"),
                                    episode=str(final.get("episode")),
                                    media_type=final.get("category"),
                                    resolution=final.get("resolution"),
                                    team=final.get("team"),
                                    video_encode=final.get("video_encode"),
                                    audio_encode=final.get("audio_encode"),
                                    video_effect=final.get("video_effect"),
                                    source=final.get("source"),
                                    subtitle=final.get("subtitle"),
                                    platform=final.get("platform"),
                                    year=final.get("year"),
                                    secondary_category=final.get("secondary_category"),
                                    origin_country=_country_str(final.get("origin_country")),
                                    release_date=final.get("release_date"),
                                    source_path=v_path,
                                    target_path=new_abs_path
                                )
                                await db.save(file_hash, audit=False)

                            # [New] 计算关联字幕文件的哈希（云源文件不在本地，跳过）
                            if related_files and source_via != "cd2":
                                await FileProcessor._save_related_file_hashes(related_files, root, final, task_id, related_targets)

                    if v_res == "success":
                        # [New] 清理源空目录 (向上递归)
                        if task.get("clean_empty_dir", False) and action_type == "move":
                            source_parent = os.path.dirname(src)
                            await FileExecutor._cleanup_empty_parents(source_parent, source_dir)
                            await FileProcessor._log_both(task_id, recog_task_id, "🧹 已执行源空目录清理")

                        # [Notify]
                        await notification_manager.notify_organize_complete(final)
                        if task.get("trigger_strm", False):
                            FileProcessor._trigger_strm_hook(new_abs_path, context, task_id=recog_task_id)
                    else:
                        # [Notify Failure]
                        err_detail = FileExecutor.get_status_message(v_res)
                        await notification_manager.notify_organize_failed(v_path, f"操作失败: {err_detail}")

            # --- Standard Path recog 任务收口（以视频项结果为准） ---
            # CD2 动作但客户端缺失时会落到标准路径，此处需一并收口
            if action_type not in ["cd2_move", "cd2_copy"] or dry_run or not cd2_client:
                _std_v_res = next((r for r in results if r.get("source") == v_path), None)
                _std_res = (_std_v_res or {}).get("msg")
                _rf_stats = {**recog_stats_base, "target_path": new_abs_path,
                             "related_files": FileProcessor._related_files_payload(related_files, related_targets, related_outcomes)}
                if not dry_run and _std_v_res and _std_v_res.get("status") == "success":
                    await FileProcessor._finish_recog(recog_task_id, "completed", {**_rf_stats, "success": 1})
                elif not dry_run and _std_v_res and _std_v_res.get("status") == "skip":
                    await FileProcessor._finish_recog(recog_task_id, "completed", {**_rf_stats, "skipped": 1, "message": "目标已存在 (跳过)"})
                elif not dry_run:
                    await FileProcessor._finish_recog(recog_task_id, "error", {**_rf_stats, "errors": 1, "message": _std_res or "物理操作失败"})
                else:
                    await FileProcessor._finish_recog(recog_task_id, "completed", {**_rf_stats, "skipped": 1, "message": "预览模式"})

        except Exception as e:
            err_msg = f"处理异常: {str(e)}"
            logger.error(err_msg)
            await FileProcessor._log_detail(task_id, f"❌ {err_msg}", "ERROR")
            await FileProcessor._finish_recog(recog_task_id, "error", {**recog_stats_base, "errors": 1, "message": err_msg})
            
            # [Notify] Add failure notification for exceptions
            if not dry_run:
                await notification_manager.notify_organize_failed(v_path, err_msg)
            
            results.append({"type": "error", "source": v_path, "message": str(e)})
        
        return results

    @staticmethod
    async def _simulate_cd2_webhook(cd2_path: str):
        """模拟 CD2 Webhook 调用以触发 STRM 生成"""
        from routers.webhook import process_cd2_notification
        
        # 延迟5秒，确保 CD2 云端索引或者 API 状态稳定
        await asyncio.sleep(5)
        
        payload_data = [
            {
                "action": "create",
                "source_file": cd2_path,
                "is_dir": "false"
            }
        ]
        
        try:
            # 直接调用内部处理函数，不再走 HTTP；标注来源为整理联动，与真实的 CD2 Webhook 区分
            result = await process_cd2_notification(payload_data, "整理联动")
            triggered = result.get("triggered", 0) if isinstance(result, dict) else 0
            if triggered > 0:
                logger.debug(f"成功触发 CD2 联动: {os.path.basename(cd2_path)}")
            else:
                # 如果没有触发任务（可能没开启 webhook 响应或路径不匹配），也算联动逻辑走通了
                logger.debug(f"[Simulate] CD2 Webhook simulated for {cd2_path}, but no task triggered.")
        except Exception as e:
            logger.error(f"模拟 CD2 联动失败: {e}")

    @staticmethod
    def _trigger_strm_hook(new_abs_path: str, context: Dict[str, Any], task_id: str = None):
        try:
            # [Fix] 移除错误的 link_strm 检查，直接执行
            # task_config = context.get("task", {})

            from strm.strm_generator import StrmGenerator
            strm_tasks = context["config"].get("strm_tasks", [])

            # 预加载所有客户端配置，用于获取全局挂载路径
            all_clients = {c.get('id'): c for c in context["config"].get("download_clients", [])}

            for strm_task in strm_tasks:
                strm_source = strm_task.get("source_path") or strm_task.get("source_dir")
                if not strm_source: continue

                # --- 智能路径匹配逻辑 ---
                local_match_root = strm_source
                if strm_task.get("sync_mode") == "cd2_api":
                    # 如果是 API 模式，需要拼接映射路径才能进行本地匹配
                    client_id = strm_task.get("cd2_client_id")
                    client_conf = all_clients.get(client_id, {})

                    mapping_root = (strm_task.get("cd2_mapping_path") or client_conf.get("mount_path") or "").strip()
                    mapping_root = mapping_root.rstrip('/')
                    strm_source_clean = '/' + strm_source.lstrip('/')
                    local_match_root = mapping_root + strm_source_clean

                if new_abs_path.startswith(local_match_root):
                    # 匹配成功，触发单文件处理
                    # 注意：处理时需要将正确的映射配置传给 StrmGenerator
                    asyncio.create_task(FileProcessor._process_strm_and_notify(new_abs_path, strm_task, task_id))
                    logger.debug(f"主动触发: {os.path.basename(new_abs_path)}")
                    return

            # log_audit("整理", "联动", "未找到匹配的 STRM 任务", level="WARN", details=new_abs_path)
        except Exception as e:
            logger.error(f"触发 STRM 失败: {str(e)}")

    @staticmethod
    async def _process_strm_and_notify(file_path: str, task_config: Dict[str, Any], task_id: str = None, notify: bool = True):
        """
        处理视频文件及其关联字幕。
        视频生成 STRM，字幕同步到 STRM 目标目录（需开启 copy_meta）。
        返回视频的处理结果 dict（status: success/skipped/error/...），批量调用可传 notify=False 抑制逐条通知。
        """
        from strm.strm_generator import StrmGenerator

        try:
            # 1. 处理视频文件（生成 STRM）
            res = await StrmGenerator.process_single_file(file_path, task_config)
            if res.get("status") == "success":
                await FileProcessor._log_detail(task_id, f"🎬 STRM 生成成功: {os.path.basename(file_path)}")
                if notify:
                    await notification_manager.notify_strm_link_created(
                        os.path.basename(file_path),
                        task_config.get("name", "Unknown Task")
                    )

            # 2. 处理同目录下的字幕文件（需开启同步元数据）
            if task_config.get("copy_meta", False):
                video_dir = os.path.dirname(file_path)
                video_base = os.path.splitext(os.path.basename(file_path))[0]

                try:
                    all_files = await asyncio.to_thread(os.listdir, video_dir)
                    for f in all_files:
                        f_ext = os.path.splitext(f)[1].lower()
                        if f_ext in FileProcessor.SUB_EXTS and f.startswith(video_base):
                            sub_path = os.path.join(video_dir, f)
                            sub_res = await StrmGenerator.process_single_file(sub_path, task_config)
                            if sub_res.get("status") == "success":
                                logger.debug(f"同步字幕: {f}")
                                await FileProcessor._log_detail(task_id, f"📎 STRM 字幕同步: {f}")
                except Exception as scan_e:
                    logger.warning(f"扫描字幕失败: {scan_e}")

            return res
        except Exception as e:
            logger.error(str(e))
            return {"status": "error", "message": str(e)}
