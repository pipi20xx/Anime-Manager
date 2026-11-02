from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional, Tuple
import json
import asyncio

from models import Subscription, SubscribedEpisode, Rule, DownloadHistory, SubscriptionTemplate
from rss_core.subscription_manager import SubscriptionManager
from rss_core.manager import RssManager
from search_service import run_subscription_fill
from logger import log_audit
from database import db
import logging
logger = logging.getLogger(__name__)
from notification import notification_manager
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

@router.get("/subscriptions", summary="获取订阅任务列表")
async def get_subscriptions(enabled_only: bool = False):
    """
    返回系统当前的全部追剧订阅任务。支持仅查看已启用的任务。
    每条订阅附带 pushed_count（已推送去重集数）字段。
    """
    subs = await SubscriptionManager.get_subscriptions(enabled_only)
    # 批量查询所有已推送集数
    result = []
    async with db.session_scope():
        for sub in subs:
            sub_dict = sub.model_dump()
            # 查询该订阅已推送的去重集数
            if sub.media_type == "tv":
                stmt = (
                    select(SubscribedEpisode.season, SubscribedEpisode.episode)
                    .where(
                        SubscribedEpisode.tmdb_id == sub.tmdb_id,
                        SubscribedEpisode.media_type == "tv",
                        SubscribedEpisode.season == sub.season,
                    )
                    .distinct()
                )
                ep_result = await db.session.execute(stmt)
                pushed = len(ep_result.all())
            else:
                # 电影: 只要有推送记录就算1
                stmt = (
                    select(SubscribedEpisode.id)
                    .where(
                        SubscribedEpisode.tmdb_id == sub.tmdb_id,
                        SubscribedEpisode.media_type == "movie",
                    )
                    .limit(1)
                )
                ep_result = await db.session.execute(stmt)
                pushed = 1 if ep_result.first() else 0
            sub_dict["pushed_count"] = pushed
            result.append(sub_dict)
    return result

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
        await notification_manager.notify_sub_added(sub)
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
                    await notification_manager.notify_sub_deleted(sub)
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
            await notification_manager.notify_sub_deleted(sub)
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
    """兼容入口 — 实现已统一收敛到 search_service.run_subscription_fill。

    保留此函数是因为 monitor.py / 自动补全等处仍按旧名字引用。
    """
    return await run_subscription_fill(sub, logger_func=logger_func, indexer=indexer, task_id=task_id)

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