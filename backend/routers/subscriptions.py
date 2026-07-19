from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Tuple
import json
import asyncio

from models import Subscription, SubscribedEpisode, Rule, DownloadHistory, SubscriptionTemplate
from rss_core.subscription_manager import SubscriptionManager
from rss_core.manager import RssManager
from clients.jackett import JackettClient
from clients.manager import ClientManager
from recognition.recognizer import MovieRecognizer
from config_manager import ConfigManager
from logger import log_audit
from database import db
import logging
logger = logging.getLogger(__name__)
from notification import NotificationManager
from sqlmodel import select, delete, and_, or_, update

router = APIRouter(tags=["追剧订阅管理"])

@router.get("/subscriptions/templates", response_model=List[SubscriptionTemplate], summary="获取订阅模板列表")
async def get_templates():
    async with db.session_scope():
        stmt = select(SubscriptionTemplate).order_by(SubscriptionTemplate.id.desc())
        return await db.all(SubscriptionTemplate, stmt)

@router.post("/subscriptions/templates", summary="保存/更新订阅模板")
async def save_template(tmpl: SubscriptionTemplate):
    async with db.session_scope():
        if tmpl.is_default:
            # 取消其他默认设置
            await db.session.execute(update(SubscriptionTemplate).values(is_default=False))
        
        if tmpl.id:
            db_tmpl = await db.get(SubscriptionTemplate, tmpl.id)
            if db_tmpl:
                data = tmpl.model_dump(exclude={"id", "created_at"})
                for k, v in data.items(): setattr(db_tmpl, k, v)
                return await db.save(db_tmpl)
        
        tmpl.id = None
        return await db.save(tmpl)

@router.delete("/subscriptions/templates/{tmpl_id}", summary="删除订阅模板")
async def delete_template(tmpl_id: int):
    async with db.session_scope():
        tmpl = await db.get(SubscriptionTemplate, tmpl_id)
        if tmpl:
            await db.delete(tmpl)
    return {"success": True}

@router.get("/subscriptions", response_model=List[Subscription], summary="获取订阅任务列表")
async def get_subscriptions(enabled_only: bool = False):
    """
    返回系统当前的全部追剧订阅任务。支持仅查看已启用的任务。
    """
    return await SubscriptionManager.get_subscriptions(enabled_only)

@router.post("/subscriptions", summary="保存/更新订阅任务")
async def save_subscription(sub: Subscription):
    """
    新增或修改追剧订阅任务，包含过滤条件、保存路径、TMDB ID 等。
    """
    # Determine if it's a new subscription or update
    is_new = sub.id is None
    media_label = "剧集" if sub.media_type == "tv" else "电影"
    # 集数范围: E1-12 / E1+ / 空（电影）
    start_ep = sub.start_episode or 0
    end_ep = sub.end_episode or 0
    ep_range = f"E{start_ep}-{end_ep}" if end_ep > 0 else (f"E{start_ep}+" if start_ep > 0 else "")
    season_ep = f"S{sub.season}" + (f" {ep_range}" if ep_range else "")
    logger.info(
        f"{'📌 创建订阅' if is_new else '✏️ 更新订阅'}: 《{sub.title}》"
        f" ({media_label} {season_ep}, TMDB={sub.tmdb_id}"
        + (f", BGM={sub.bangumi_id}" if getattr(sub, 'bangumi_id', None) else "")
        + ")"
    )
    try:
        res = await SubscriptionManager.save_subscription(sub)
    except Exception as e:
        logger.error(f"❌ 订阅保存失败《{sub.title}》: {e}", exc_info=True)
        raise

    if is_new:
        logger.info(f"✅ 订阅创建成功: 《{sub.title}》(ID={getattr(res, 'id', None)}, {season_ep})")
        log_audit("订阅", "创建", f"已创建订阅: 《{sub.title}》(ID={getattr(res, 'id', None)}, TMDB={sub.tmdb_id} {season_ep})")
        await NotificationManager.push_sub_add_notification(sub)
    else:
        logger.info(f"✅ 订阅更新成功: 《{sub.title}》(ID={sub.id}, {season_ep})")
        log_audit("订阅", "更新", f"已更新订阅: 《{sub.title}》(ID={sub.id}, {season_ep})")

    return res

@router.delete("/subscriptions/clear_all", summary="清空所有订阅任务")
async def clear_all_subscriptions(background_tasks: BackgroundTasks):
    """
    立即返回并启动后台任务清空所有订阅。
    """
    async def perform_clear():
        # 1. 先获取所有 ID
        async with db.session_scope():
            stmt = select(Subscription.id)
            result = await db.session.execute(stmt)
            sub_ids = result.scalars().all()
        
        # 2. 逐个开启短事务进行删除
        import logging
        logger = logging.getLogger("Subscription")
        for sid in sub_ids:
            async with db.session_scope():
                sub = await db.get(Subscription, sid)
                if sub:
                    title = sub.title
                    await NotificationManager.push_sub_del_notification(sub)
                    await db.delete(sub)
                    logger.info(f"已清理订阅项: {title}")
            await asyncio.sleep(0.1) # 给数据库和网络一点喘息时间

        log_audit("订阅", "全量清空", f"后台任务已完成，共清理 {len(sub_ids)} 条记录")
        # WS 推送：通知前端订阅列表已变更
        try:
            from event_broadcaster import EventBroadcaster
            await EventBroadcaster.broadcast_subscriptions_changed({"action": "clear_all", "count": len(sub_ids)})
        except Exception:
            pass

    background_tasks.add_task(perform_clear)
    log_audit("订阅", "清空启动", "用户触发了全量清空，后台任务已启动")
    return {"success": True, "message": "已在后台启动清空任务，请稍后刷新列表"}

@router.delete("/subscriptions/{sub_id}", summary="删除订阅任务")
async def delete_subscription(sub_id: int):
    """
    通过 ID 移除订阅任务。
    """
    async with db.session_scope():
        sub = await db.get(Subscription, sub_id)
        if sub:
            _start_ep = sub.start_episode or 0
            _end_ep = sub.end_episode or 0
            _ep_range = f"E{_start_ep}-{_end_ep}" if _end_ep > 0 else (f"E{_start_ep}+" if _start_ep > 0 else "")
            _season_ep = f"S{sub.season}" + (f" {_ep_range}" if _ep_range else "")
            logger.info(f"🗑️ 删除订阅: 《{sub.title}》(ID={sub_id}, TMDB={sub.tmdb_id} {_season_ep})")
            # 在删除前发送包含完整元数据的通知
            await NotificationManager.push_sub_del_notification(sub)
            await SubscriptionManager.delete_subscription(sub_id)
            log_audit("订阅", "删除", f"已删除订阅: 《{sub.title}》(ID={sub_id})")
        else:
            logger.warning(f"🗑️ 删除订阅失败: ID={sub_id} 不存在")
    return {"success": True}

@router.get("/subscriptions/{sub_id}/episodes", response_model=List[SubscribedEpisode], summary="获取已下载集数历史")
async def get_subscribed_episodes(sub_id: int):
    """
    查询该订阅任务下已经成功推送下载的季度和集数列表。
    """
    async with db.session_scope():
        sub = await db.get(Subscription, sub_id)
        if not sub: return []
        return await SubscriptionManager.get_downloaded_episodes(sub.tmdb_id, sub.media_type)

@router.delete("/subscriptions/{sub_id}/episodes", summary="清空订阅下载记录")
async def clear_subscribed_episodes(sub_id: int):
    """
    清空该订阅任务关联的已下载历史，允许系统重头开始追剧或补全。
    """
    async with db.session_scope():
        sub = await db.get(Subscription, sub_id)
        if not sub:
            raise HTTPException(status_code=404, detail="订阅任务不存在")
        # 传入 sub.title 以便同时清理 download_history
        await SubscriptionManager.clear_downloaded_episodes(sub.tmdb_id, sub.media_type, title=sub.title)
        return {"success": True, "message": f"已彻底清空作品 {sub.title} 的所有相关下载记录"}

async def run_sub_fill_logic(sub: Subscription, logger_func=None, indexer: str = "all", task_id: str = None):
    async def _log(msg: str, l_type="info", extra=None):
        if logger_func:
            await logger_func({"type": l_type, "message": msg, **(extra or {})})
        if task_id:
            try:
                from task_history import log_task as _log_task
                level = "ERROR" if l_type == "error" else "WARN" if l_type == "warn" else "INFO"
                await _log_task(task_id, msg, level)
            except Exception:
                pass

    # [优化] 不再在整个函数外层包裹 session_scope，避免长时网络 IO 占用 DB 连接
    await _log(f"开始搜寻补全: {sub.title} (范围: {indexer})", l_type="start")
    
    search_results = await JackettClient.search(sub.title, indexer=indexer)
    if not search_results:
        await _log("未发现搜索结果", l_type="error")
        return 0
        
    config = ConfigManager.get_config()
    anime_prio = config.get("anime_priority", True)
    bgm_prio = config.get("bangumi_priority", False)
    bgm_failover = config.get("bangumi_failover", True)
    
    pushed_count = 0
    total = len(search_results)

    async def check_is_completed():
        # 内部方法按需开启 session
        async with db.session_scope():
            if sub.media_type == "movie":
                return await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, 0, 0)
            else:
                if sub.end_episode > 0:
                    for ep in range(sub.start_episode, sub.end_episode + 1):
                        if not await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, sub.season or 1, ep):
                            return False
                    return True
                return False
    
    for idx, item in enumerate(search_results):
        if await check_is_completed():
            await _log("检测到订阅已全部补全，跳过后续搜索条目。", l_type="info")
            break

        title = item['title']
        await _log(title, l_type="process", extra={"index": idx, "total": total, "title": title})
        
        try:
            result, recog_logs = await MovieRecognizer.recognize_full(
                title, force_filename=True,
                anime_priority=anime_prio, bangumi_priority=bgm_prio,
                bangumi_failover=bgm_failover,
                batch_enhancement=True,
                description=item.get('description')
            )
            
            recog_task_id = None
            try:
                from task_history import start_task as _start_task, log_task as _log_task, finish_task as _finish_task
                import uuid as _uuid
                recog_task_id = f"recog_{_uuid.uuid4().hex[:12]}"
                await _start_task(recog_task_id, "识别", title)
                for log_msg in recog_logs:
                    level = "ERROR" if "❌" in log_msg or "[ERROR]" in log_msg else "WARN" if "⚠️" in log_msg else "INFO"
                    await _log_task(recog_task_id, log_msg, level)
            except Exception:
                recog_task_id = None
            
            if not result.get("success") or not result.get("final_result"):
                await _log(f"识别失败，跳过: {title}", l_type="info")
                if recog_task_id:
                    try:
                        await _log_task(recog_task_id, "❌ 识别失败", "ERROR")
                        await _finish_task(recog_task_id, "error")
                    except Exception:
                        pass
                continue
                
            final = result["final_result"]
            if recog_task_id:
                try:
                    stats = {"title": final.get("title"), "tmdb_id": final.get("tmdb_id"), "category": final.get("category"), "season": final.get("season"), "episode": final.get("episode")}
                    await _finish_task(recog_task_id, "completed", stats=stats)
                except Exception:
                    pass
            if str(final.get("tmdb_id")) != str(sub.tmdb_id):
                # 仅记录同名但 ID 不匹配的情况，或者完全不匹配
                await _log(f"ID 不匹配 ({final.get('tmdb_id') or '未知'}), 跳过: {title}", l_type="info")
                continue
            
            try:
                season = int(final.get("season")) if final.get("season") is not None else 1
                episode_raw = str(final.get("episode") or "")
                if "-" in episode_raw:
                    episode = int(episode_raw.split("-")[0])
                    is_batch, end_ep = True, int(episode_raw.split("-")[1])
                else:
                    episode = int(episode_raw) if episode_raw else None
                    is_batch, end_ep = False, episode
            except (ValueError, TypeError): 
                await _log(f"集数解析失败, 跳过: {title}", l_type="warn")
                continue
            
            if sub.media_type == "tv":
                if episode is None: 
                    await _log(f"未识别到集数, 跳过: {title}", l_type="info")
                    continue
                if sub.season != 0 and sub.season != season: 
                    await _log(f"季度不匹配 (S{season}), 跳过: {title}", l_type="info")
                    continue
                
                if is_batch and end_ep:
                    if sub.start_episode > 0 and end_ep < sub.start_episode:
                        await _log(f"合集范围 [{episode}-{end_ep}] 早于订阅起始集数, 跳过: {title}", l_type="info")
                        continue
                    if sub.end_episode > 0 and episode > sub.end_episode:
                        await _log(f"合集范围 [{episode}-{end_ep}] 晚于订阅结束集数, 跳过: {title}", l_type="info")
                        continue
                else:
                    if sub.start_episode > 0 and episode < sub.start_episode: 
                        await _log(f"早于起始集数 (E{episode}), 跳过: {title}", l_type="info")
                        continue
                    if sub.end_episode > 0 and episode > sub.end_episode: 
                        await _log(f"晚于结束集数 (E{episode}), 跳过: {title}", l_type="info")
                        continue
                
                if is_batch and end_ep:
                    all_exist = True
                    missing_eps = []
                    for ep_num in range(episode, end_ep + 1):
                        if not await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, season, ep_num):
                            all_exist = False
                            missing_eps.append(ep_num)
                    if all_exist:
                        await _log(f"合集集数已全部存在 (S{season}E{episode}-{end_ep}), 跳过: {title}", l_type="info")
                        continue
                else:
                    if await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, season, episode):
                        await _log(f"集数已存在 (S{season}E{episode}), 跳过: {title}", l_type="info")
                        continue
            else:
                if await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, 0, 0):
                    await _log(f"电影已存在, 跳过: {title}", l_type="info")
                    continue
            
            if hasattr(SubscriptionManager, 'check_subscription_filter'):
                filter_ok, filter_err = SubscriptionManager.check_subscription_filter(sub, final, title)
                if not filter_ok:
                    await _log(f"过滤: {title} ({filter_err})", l_type="warn")
                    continue
            
            success, msg = await ClientManager.add_task(
                sub.target_client_id, item['link'], save_path=sub.save_path, category=sub.category
            )
            
            if success:
                # 写入操作依然开启短 session
                async with db.session_scope():
                    if sub.media_type == "tv":
                        if is_batch and end_ep:
                            for ep_num in range(episode, end_ep + 1):
                                await SubscriptionManager.add_subscribed_episode(sub.tmdb_id, sub.media_type, season or 1, ep_num, title=title)
                        else:
                            await SubscriptionManager.add_subscribed_episode(sub.tmdb_id, sub.media_type, season or 1, episode, title=title)
                    else:
                        await SubscriptionManager.add_subscribed_episode(sub.tmdb_id, sub.media_type, 0, 0, title=title)
                    
                    # [彻底解耦] 补全操作不再写入全局 DownloadHistory，只维护 SubscribedEpisode
                    # history = DownloadHistory(guid=item['guid'], title=title, download_client_id=sub.target_client_id)
                    # await RssManager.add_history(history)
                    
                pushed_count += 1
                await _log(f"成功补全推送: {title}", l_type="hit")

                # [Notify]
                await NotificationManager.push_sub_push_notification(
                    sub=sub,
                    item=final
                )
                
                if await check_is_completed():
                    await _log("补全圆满结束。", l_type="finish")
                    break

        except Exception as e:
            await _log(f"处理错误: {str(e)}", l_type="warn")
        
        await asyncio.sleep(0.05)
        
    await _log(f"任务完成，共推送 {pushed_count} 个集数", l_type="finish", extra={"pushed": pushed_count})

    if await check_is_completed():
        log_audit("订阅", "自动完结", f"检测到订阅 '{sub.title}' 已全部完成，自动清理任务")
        # [Notify]
        await NotificationManager.push_sub_complete_notification(sub)
        async with db.session_scope():
            await db.delete(sub)

    return pushed_count

@router.post("/subscriptions/{sub_id}/fill", summary="执行手动补全")
async def fill_subscription_gaps(sub_id: int, indexer: Optional[str] = "all", request: Request = None):
    """
    立即针对该任务启动 Jackett 搜索，自动寻找并补全缺失的集数。
    """
    async def fill_generator():
        async with db.session_scope():
            sub = await db.get(Subscription, sub_id)
        
        if not sub:
            yield json.dumps({"type": "error", "message": "订阅不存在"}) + "\n"
            return
        
        fill_task_id = None
        try:
            from task_history import start_task as _start_task, log_task as _log_task, finish_task as _finish_task
            import uuid as _uuid
            fill_task_id = f"fill_{_uuid.uuid4().hex[:12]}"
            await _start_task(fill_task_id, "订阅补全", f"[手动] {sub.title}")
            await _log_task(fill_task_id, f"🚀 开始手动补全: {sub.title}")
            await _log_task(fill_task_id, f"🔍 搜索范围: {indexer}")
            await _log_task(fill_task_id, "──────────────────")
        except Exception:
            fill_task_id = None
        
        logger.info(f"✨ [订阅补全] 手动: {sub.title}")
        
        queue = asyncio.Queue()
        async def _q_logger(data): await queue.put(json.dumps(data) + "\n")
        
        task = asyncio.create_task(run_sub_fill_logic(sub, _q_logger, indexer=indexer, task_id=fill_task_id))
        pushed_count = 0
        try:
            while not task.done() or not queue.empty():
                if request and await request.is_disconnected():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    yield json.dumps({"type": "warn", "message": "操作已被用户中断"}) + "\n"
                    return
                    
                try:
                    line = await asyncio.wait_for(queue.get(), timeout=0.1)
                    data = json.loads(line.strip())
                    if data.get("type") == "hit":
                        pushed_count += 1
                    yield line
                except asyncio.TimeoutError: continue
        except asyncio.CancelledError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if fill_task_id:
            try:
                from task_history import log_task as _log_task, finish_task as _finish_task
                await _log_task(fill_task_id, "──────────────────")
                await _log_task(fill_task_id, f"🏁 补全完成，共推送 {pushed_count} 个集数")
                await _finish_task(fill_task_id, "completed", pushed_count)
            except Exception:
                pass
        
        logger.info(f"✨ [订阅补全] 完成: {sub.title} - 推送 {pushed_count} 个")

    return StreamingResponse(fill_generator(), media_type="application/x-ndjson")

async def auto_fill_all_subscriptions():
    subs = await SubscriptionManager.get_subscriptions(enabled_only=True)
    active_subs = [s for s in subs if getattr(s, 'auto_fill', True)]
    if not active_subs: return
    
    auto_task_id = None
    try:
        from task_history import start_task as _start_task, log_task as _log_task
        import uuid as _uuid
        auto_task_id = f"autofill_{_uuid.uuid4().hex[:12]}"
        await _start_task(auto_task_id, "订阅补全", "自动搜寻补全")
        await _log_task(auto_task_id, f"🚀 开始自动补全，共 {len(active_subs)} 个订阅项目")
        await _log_task(auto_task_id, "──────────────────")
    except Exception:
        auto_task_id = None
    
    logger.info(f"✨ [订阅补全] 自动: 开始，共 {len(active_subs)} 个项目")
    
    total_pushed = 0
    for sub in active_subs:
        try:
            pushed = await run_sub_fill_logic(sub, logger_func=None, task_id=auto_task_id)
            if pushed > 0:
                total_pushed += pushed
                logger.info(f"✨ [订阅补全] {sub.title}: 补全 {pushed} 集")
        except Exception as e:
            if auto_task_id:
                try:
                    from task_history import log_task as _log_task
                    await _log_task(auto_task_id, f"❌ [{sub.title}]: 处理失败 - {str(e)}", "ERROR")
                except Exception:
                    pass
            logger.error(f"✨ [订阅补全] {sub.title}: 失败 - {str(e)}")
    
    if auto_task_id:
        try:
            from task_history import log_task as _log_task, finish_task as _finish_task
            await _log_task(auto_task_id, "──────────────────")
            await _log_task(auto_task_id, f"🏁 自动补全完成，累计推送 {total_pushed} 个项目")
            await _finish_task(auto_task_id, "completed", total_pushed)
        except Exception:
            pass
    
    logger.info(f"✨ [订阅补全] 自动完成: 累计推送 {total_pushed} 个")