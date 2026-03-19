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
from logger import log_audit
from clients.manager import ClientManager
from .executor import FileExecutor
from notification import NotificationManager
from utils.hash_calculator import HashCalculator, HashResult

logger = logging.getLogger(__name__)

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
            "rule": next((r for r in config.get("rename_rules", Renamer.get_default_rules()) if r["id"] == task.get("rule_id")), None)
        }

    @staticmethod
    async def organize_video_file(v_path: str, task: Dict[str, Any], context: Dict[str, Any] = None, dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        处理单个视频文件及其关联字幕
        """
        if context is None:
            context = FileProcessor.load_context(task)
            
        # [New] History Check
        ignore_history = task.get("ignore_history", False)
        if not dry_run and not ignore_history:
            from database import db
            from models import OrganizeHistory
            async with db.session_scope():
                # 只有当此前确实"成功"整理过该文件时，才跳过
                stmt = select(OrganizeHistory).where(
                    and_(
                        OrganizeHistory.source_path == v_path,
                        OrganizeHistory.status == "success"
                    )
                )
                existing = await db.first(OrganizeHistory, stmt)
                if existing:
                    log_audit("整理", "跳过历史", f"文件此前已整理成功: {os.path.basename(v_path)}")
                    return [{"type": "skip", "source": v_path, "reason": "已成功整理过"}]

        rule = context["rule"]
        if not rule: return [{"type": "error", "source": v_path, "message": "Rule not found"}]

        source_dir = task.get("source_dir")
        target_dir = task.get("target_dir")
        action_type = task.get("action_type", "move")
        conflict_mode = "overwrite" if task.get("overwrite_mode") else "skip"
        
        root = os.path.dirname(v_path)
        v_file = os.path.basename(v_path)
        v_base, v_ext = os.path.splitext(v_file)
        
        results = []

        try:
            # 寻找关联字幕和音轨 - 移至线程执行
            related_files = []
            try:
                all_files_in_dir = await asyncio.to_thread(os.listdir, root)
                for f in all_files_in_dir:
                    f_ext = os.path.splitext(f)[1].lower()
                    if f_ext in FileProcessor.RELATED_EXTS and f.startswith(v_base):
                        related_files.append(f)
            except Exception: pass # 目录可能不存在或无法读取

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
            log_audit("整理", "文件识别", f"正在处理文件: {v_path}")

            result_data, _ = await MovieRecognizer.recognize_full(
                rel_input_path, 
                all_noise=all_noise, 
                all_groups=all_groups, 
                api_key=context["api_key"], 
                anime_priority=context["anime_priority"], 
                all_render=all_render,
                forced_tmdb_id=f_tmdb, 
                forced_type=f_type, 
                forced_season=f_season
            )
            
            final = result_data.get("final_result", {})
            
            # --- [New] Handle Recognition Failure ---
            if not final.get("tmdb_id"):
                log_audit("整理", "识别失败", f"文件识别失败: {v_file}", level="WARN")
                if not dry_run:
                    from models import OrganizeHistory
                    from database import db
                    async with db.session_scope():
                        history = OrganizeHistory(
                            source_path=v_path, filename=v_file,
                            status="failed", message="识别失败 (无 TMDB ID)",
                            action_type=action_type
                        )
                        await db.save(history, audit=False)
                    
                    # [Notify] Add failure notification
                    await NotificationManager.push_organize_error_notification(v_path, "识别失败 (无法获取 TMDB ID)")
                    
                return [{"type": "skip", "source": v_path, "reason": "识别失败 (无 TMDB ID)"}]

            # 补全控制台识别结果日志
            log_audit("整理", "识别成功", f"识别结论: {final['title']} - S{final.get('season','-')}E{final.get('episode','-')} (ID: {final['tmdb_id']})")

            # --- [New] Emby Check ---
            check_emby_exists = task.get("check_emby_exists", False)
            log_audit("整理", "Emby检查", f"Emby检查状态: {'已启用' if check_emby_exists else '未启用'}")
            
            if check_emby_exists:
                from emby_client import get_emby_client
                emby_client = get_emby_client()
                
                tmdb_id = final.get("tmdb_id")
                media_type = final.get("category")
                season = final.get("season")
                episode = final.get("episode")
                
                log_audit("整理", "Emby检查", f"开始检查 Emby 库 - TMDB ID: {tmdb_id}, 类型: {media_type}, 季: {season}, 集: {episode}")
                
                if tmdb_id and emby_client:
                    try:
                        exists = False
                        if media_type == "电影":
                            log_audit("整理", "Emby检查", f"检查电影是否存在: TMDB ID {tmdb_id}")
                            exists = emby_client.check_movie_exists(tmdb_id)
                        elif media_type == "剧集" and season is not None and episode is not None:
                            log_audit("整理", "Emby检查", f"检查剧集是否存在: TMDB ID {tmdb_id}, S{season}E{episode}")
                            exists = emby_client.check_episode_exists(tmdb_id, season, episode)
                        else:
                            log_audit("整理", "Emby检查", f"跳过检查 - 媒体类型: {media_type}, 季: {season}, 集: {episode}")
                        
                        if exists:
                            log_audit("整理", "Emby检查", f"✅ Emby库中已存在: {final['title']} - S{season}E{episode} (TMDB: {tmdb_id})")
                            if not dry_run:
                                from models import OrganizeHistory
                                from database import db
                                async with db.session_scope():
                                    history = OrganizeHistory(
                                        source_path=v_path, filename=v_file,
                                        tmdb_id=str(tmdb_id), title=final.get("title"),
                                        season=season, episode=str(episode),
                                        media_type=media_type,
                                        action_type=action_type,
                                        status="skipped", message="Emby库中已存在"
                                    )
                                    await db.save(history, audit=False)
                            return [{"type": "skip", "source": v_path, "reason": "Emby库中已存在"}]
                        else:
                            log_audit("整理", "Emby检查", f"❌ Emby库中不存在: {final['title']} - S{season}E{episode} (TMDB: {tmdb_id})，继续处理")
                    except Exception as e:
                        log_audit("整理", "Emby检查失败", f"Emby检查异常: {str(e)}", level="WARN")
                        import traceback
                        log_audit("整理", "Emby检查失败", f"异常堆栈: {traceback.format_exc()}", level="WARN")
                else:
                    if not tmdb_id:
                        log_audit("整理", "Emby检查", f"⚠️ 跳过 Emby 检查 - 缺少 TMDB ID")
                    if not emby_client:
                        log_audit("整理", "Emby检查", f"⚠️ 跳过 Emby 检查 - Emby 客户端未初始化（请检查 Emby 配置）")

            final["filename"] = v_file
            final["path"] = v_path
            
            # [New] Get File Size
            try:
                f_stat = os.stat(v_path)
                f_size_mb = f_stat.st_size / (1024 * 1024)
                if f_size_mb > 1024:
                    final["file_size"] = f"{f_size_mb/1024:.2f}GB"
                else:
                    final["file_size"] = f"{f_size_mb:.2f}MB"
            except:
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
            for related_file in related_files:
                file_tag = related_file[len(v_base):] 
                v_new_dir = os.path.dirname(new_rel_path)
                v_new_base = os.path.splitext(os.path.basename(new_rel_path))[0]
                related_rel_path = os.path.join(v_new_dir, v_new_base + file_tag)
                related_abs_old = os.path.join(root, related_file)
                related_abs_new = os.path.join(target_dir, related_rel_path)
                plan_items.append((related_abs_old, related_abs_new))

            # [New] Calculate Hash before move (if enabled)
            hash_result: Optional[HashResult] = None
            if task.get("calculate_hash", False) and not dry_run:
                log_audit("整理", "哈希计算", f"开始计算文件哈希: {v_file}")
                hash_result = await HashCalculator.calculate_hashes(v_path)
                if hash_result:
                    log_audit("整理", "哈希完成", f"SHA1: {hash_result.sha1}")
                    log_audit("整理", "ED2K链接", hash_result.ed2k_link)
                else:
                    log_audit("整理", "哈希失败", f"无法计算哈希: {v_file}", level="WARN")

            # Execute
            if not dry_run and action_type in ["cd2_move", "cd2_copy"]:
                # --- Optimized CD2 Path ---
                # 1. Get Client First
                all_clients = ClientManager.get_all_clients()
                cd2_client = None
                for c_conf in all_clients:
                    if c_conf.get('type') == 'cd2':
                        m_path = c_conf.get('mount_path')
                        if m_path and os.path.abspath(v_path).startswith(os.path.abspath(m_path)):
                            cd2_client = ClientManager.get_client(c_conf.get('id'))
                            break
                
                if not cd2_client:
                    cd2_configs = [c for c in all_clients if c.get('type') == 'cd2']
                    if len(cd2_configs) == 1:
                        cd2_client = ClientManager.get_client(cd2_configs[0].get('id'))

                if cd2_client:
                    # 2. Ensure Directory using API
                    target_parent = os.path.dirname(new_abs_path)
                    await FileExecutor._ensure_cd2_dir(cd2_client, target_parent, context.get("dir_cache"))

                    # 3. Batch Call
                    batch_res = await FileExecutor._execute_cd2_batch(cd2_client, plan_items, action_type)
                    for src, dst in plan_items:
                        # 如果整个批次跳过，则单个项标记为 skip
                        item_status = "error"
                        if batch_res == "success": item_status = "success"
                        elif batch_res == "skipped": item_status = "skip"
                        
                        # 添加识别信息到结果中
                        result_item = {
                            "type": "item", "status": item_status,
                            "source": src, "target": dst, "action": action_type, "msg": FileExecutor.get_status_message(batch_res)
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
                            source_parent = os.path.dirname(v_path)
                            await FileExecutor._cleanup_empty_parents(source_parent, source_dir)

                        # [Notify]
                        await NotificationManager.push_organize_notification(final)

                        # [Record History]
                        if not dry_run:
                            from models import OrganizeHistory, FileHash
                            from database import db
                            async with db.session_scope():
                                history = OrganizeHistory(
                                    source_path=v_path, target_path=new_abs_path,
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
                                    year=str(final.get("year")) if final.get("year") else None
                                )
                                await db.save(history, audit=False)
                                
                                # [New] Save FileHash (按 ED2K 去重)
                                if hash_result:
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
                                            source_path=v_path,
                                            target_path=new_abs_path
                                        )
                                        await db.save(file_hash, audit=False)
                        
                        # [Always Trigger] 使用模拟 Webhook 方式触发 STRM
                        # 不再检查 trigger_strm 开关，交由 STRM 任务自身的 Webhook 响应开关控制
                        cd2_path = cd2_client._to_cd2_path(new_abs_path)
                        asyncio.create_task(FileProcessor._simulate_cd2_webhook(cd2_path))
                    
                    return results

            # --- Standard Path ---
            for src, dst in plan_items:
                v_res = "preview"
                if not dry_run:
                    v_res = await FileExecutor.execute_action(src, dst, action_type, conflict_mode, context.get("dir_cache"))
                
                # 添加识别信息到结果中
                result_item = {
                    "type": "item", "status": "success" if v_res in ["success", "preview"] else "error",
                    "source": src, "target": dst, "action": action_type, "msg": FileExecutor.get_status_message(v_res)
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
                            status="success" if v_res == "success" else "failed",
                            message=None if v_res == "success" else f"物理操作失败: {FileExecutor.get_status_message(v_res)}"
                        )
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
                                    source_path=v_path,
                                    target_path=new_abs_path
                                )
                                await db.save(file_hash, audit=False)

                    if v_res == "success":
                        # [New] 清理源空目录 (向上递归)
                        if task.get("clean_empty_dir", False) and action_type == "move":
                            source_parent = os.path.dirname(src)
                            await FileExecutor._cleanup_empty_parents(source_parent, source_dir)

                        # [Notify]
                        await NotificationManager.push_organize_notification(final)
                        if task.get("trigger_strm", False):
                            FileProcessor._trigger_strm_hook(new_abs_path, context)
                    else:
                        # [Notify Failure]
                        err_detail = FileExecutor.get_status_message(v_res)
                        await NotificationManager.push_organize_error_notification(v_path, f"操作失败: {err_detail}")

        except Exception as e:
            err_msg = f"处理异常: {str(e)}"
            log_audit("整理", "处理错误", err_msg, level="ERROR", details={"file": v_path})
            
            # [Notify] Add failure notification for exceptions
            if not dry_run:
                await NotificationManager.push_organize_error_notification(v_path, err_msg)
            
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
            # 直接调用内部处理函数，不再走 HTTP
            triggered = await process_cd2_notification(payload_data)
            if triggered > 0:
                log_audit("整理", "联动", f"成功触发 CD2 联动: {os.path.basename(cd2_path)}")
            else:
                # 如果没有触发任务（可能没开启 webhook 响应或路径不匹配），也算联动逻辑走通了
                logger.debug(f"[Simulate] CD2 Webhook simulated for {cd2_path}, but no task triggered.")
        except Exception as e:
            log_audit("整理", "联动异常", f"模拟 CD2 联动失败: {e}", level="ERROR")

    @staticmethod
    def _trigger_strm_hook(new_abs_path: str, context: Dict[str, Any]):
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
                    asyncio.create_task(FileProcessor._process_strm_and_notify(new_abs_path, strm_task))
                    log_audit("主动联动STRM", "联动STRM", f"主动触发: {os.path.basename(new_abs_path)}", details=strm_task.get("name"))
                    return
            
            # log_audit("整理", "联动", "未找到匹配的 STRM 任务", level="WARN", details=new_abs_path)
        except Exception as e:
            log_audit("整理", "联动错误", f"触发 STRM 失败: {str(e)}", level="ERROR")

    @staticmethod
    async def _process_strm_and_notify(file_path: str, task_config: Dict[str, Any]):
        """
        处理视频文件及其关联字幕。
        视频生成 STRM，字幕同步到 STRM 目标目录（需开启 copy_meta）。
        """
        from strm.strm_generator import StrmGenerator
        
        try:
            # 1. 处理视频文件（生成 STRM）
            res = await StrmGenerator.process_single_file(file_path, task_config)
            if res.get("status") == "success":
                await NotificationManager.push_strm_link_notification(
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
                                log_audit("STRM", "联动", f"同步字幕: {f}", details=task_config.get("name"))
                except Exception as scan_e:
                    log_audit("STRM", "联动", f"扫描字幕失败: {scan_e}", level="WARN")
                    
        except Exception as e:
            log_audit("STRM", "联动异常", str(e), level="ERROR")
