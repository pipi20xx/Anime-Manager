from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
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
    res = await SubscriptionManager.save_subscription(sub)
    
    if is_new:
        await NotificationManager.push_sub_add_notification(sub)
    
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
            # 在删除前发送包含完整元数据的通知
            await NotificationManager.push_sub_del_notification(sub)
            await SubscriptionManager.delete_subscription(sub_id)
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

async def run_sub_fill_logic(sub: Subscription, logger_func=None, indexer: str = "all"):
    async def _log(msg: str, l_type="info", extra=None):
        if logger_func:
            await logger_func({"type": l_type, "message": msg, **(extra or {})})

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
            result, _ = await MovieRecognizer.recognize_full(
                title, force_filename=True,
                anime_priority=anime_prio, bangumi_priority=bgm_prio,
                bangumi_failover=bgm_failover,
                batch_enhancement=True, # [Force] 补全模式下强制开启合集增强，提高打包资源命中率
                description=item.get('description') # [New] Pass subtitle for better matching
            )
            
            if not result.get("success") or not result.get("final_result"):
                await _log(f"识别失败，跳过: {title}", l_type="info")
                continue
                
            final = result["final_result"]
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
                if sub.start_episode > 0 and episode < sub.start_episode and not is_batch: 
                    await _log(f"早于起始集数 (E{episode}), 跳过: {title}", l_type="info")
                    continue
                if sub.end_episode > 0 and episode > sub.end_episode: 
                    await _log(f"晚于结束集数 (E{episode}), 跳过: {title}", l_type="info")
                    continue
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
async def fill_subscription_gaps(sub_id: int, indexer: Optional[str] = "all"):
    """
    立即针对该任务启动 Jackett 搜索，自动寻找并补全缺失的集数。
    """
    async def fill_generator():
        # 获取基础信息时开启短 Session
        async with db.session_scope():
            sub = await db.get(Subscription, sub_id)
        
        if not sub:
            yield json.dumps({"type": "error", "message": "订阅不存在"}) + "\n"
            return
            
        queue = asyncio.Queue()
        async def _q_logger(data): await queue.put(json.dumps(data) + "\n")
        
        task = asyncio.create_task(run_sub_fill_logic(sub, _q_logger, indexer=indexer))
        while not task.done() or not queue.empty():
            try:
                line = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield line
            except asyncio.TimeoutError: continue

    return StreamingResponse(fill_generator(), media_type="application/x-ndjson")

async def auto_fill_all_subscriptions():
    # 外部不再包裹 session_scope，让内部根据需要开关
    subs = await SubscriptionManager.get_subscriptions(enabled_only=True)
    active_subs = [s for s in subs if getattr(s, 'auto_fill', True)]
    if not active_subs: return
    
    log_audit("订阅", "自动补全", f"开始全量补全任务，共 {len(active_subs)} 个项目")
    total_pushed = 0
    for sub in active_subs:
        try:
            pushed = await run_sub_fill_logic(sub, logger_func=None)
            total_pushed += pushed
        except Exception as e:
            log_audit("订阅", "补全异常", f"处理 '{sub.title}' 时出错: {str(e)}", level="ERROR")
    
    log_audit("订阅", "全量补全完成", f"任务结束，共推送 {total_pushed} 个条目")