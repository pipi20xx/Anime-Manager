from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from recognition.data_provider.bangumi.client import BangumiProvider
from config_manager import ConfigManager
from logger import log_audit

router = APIRouter(prefix="/api/bangumi", tags=["Bangumi 二次元数据"])

@router.get("/calendar", summary="获取每日放送表")
async def get_calendar():
    """
    获取 Bangumi (番组计划) 的每日新番放送表，支持本地缓存。
    """
    return await BangumiProvider.get_calendar()

@router.get("/calendar/full", summary="获取增强版追剧日历")
async def get_calendar_full():
    """
    获取带订阅状态的每日放送表。
    """
    from database import db
    from models import Subscription, SubscribedEpisode
    from sqlmodel import select
    from sqlalchemy import func

    # 1. 获取原始日历数据
    calendar_data = await BangumiProvider.get_calendar()
    if not calendar_data or "data" not in calendar_data:
        return calendar_data

    async with db.session_scope():
        # 2. 获取所有已订阅的番剧 (按 bangumi_id 索引)
        sub_stmt = select(Subscription).where(Subscription.bangumi_id != None)
        subscriptions = await db.all(Subscription, sub_stmt)
        sub_map = {str(s.bangumi_id): s for s in subscriptions}

        # 3. 获取下载进度
        # 我们按 tmdb_id 聚合已下载的剧集数量
        ep_stmt = select(SubscribedEpisode.tmdb_id, func.count(SubscribedEpisode.id).label("count")).group_by(SubscribedEpisode.tmdb_id)
        ep_results = await db.execute(ep_stmt)
        ep_count_map = {row[0]: row[1] for row in ep_results.all()}

        # 4. 组装增强数据
        for day in calendar_data["data"]:
            for item in day["items"]:
                bgm_id = str(item["id"])
                if bgm_id in sub_map:
                    sub = sub_map[bgm_id]
                    item["is_subscribed"] = True
                    item["subscription_id"] = sub.id
                    item["tmdb_id"] = sub.tmdb_id
                    item["local_episodes"] = ep_count_map.get(sub.tmdb_id, 0)
                    item["total_episodes"] = sub.end_episode
                else:
                    item["is_subscribed"] = False
                    item["local_episodes"] = 0

    return calendar_data

@router.get("/subject/{subject_id}", summary="获取条目详情")
async def get_subject(subject_id: int):
    """
    获取 Bangumi 指定条目（动画、电影）的详细元数据。
    """
    result = await BangumiProvider.get_subject_details(subject_id, include_cast=True)
    if not result:
        raise HTTPException(status_code=404, detail="Bangumi 条目未找到")
    return result

@router.get("/match_tmdb/{subject_id}", summary="Bangumi 匹配 TMDB")
async def match_tmdb(subject_id: int):
    """
    根据 Bangumi ID 自动寻找对应的 TMDB 条目，并计算季号和集数。
    用于前端“订阅此番”时的自动填充。
    """
    import logging
    logger = logging.getLogger("BGM-Link")

    # 1. 获取 BGM 详情
    bgm_item = await BangumiProvider.get_subject_details(subject_id)
    if not bgm_item:
        raise HTTPException(status_code=404, detail="Bangumi 条目未找到")
    
    config = ConfigManager.get_config()
    tmdb_key = config.get("tmdb_api_key")
    
    logger.info(f"正在为《{bgm_item.get('title')}》寻找 TMDB 关联...")

    tmdb_item = None
    if tmdb_key:
        # 2. 调用已有的映射逻辑
        # 将级别设为 info，确保实时日志控制台能看到匹配细节
        class RemoteLogger:
            def log(self, msg):
                logger.info(msg)

        tmdb_item = await BangumiProvider.map_to_tmdb(bgm_item, tmdb_key, logs=RemoteLogger())
    
    # 3. 提取季号 (使用指定的 utils.py)
    from recognition_engine.bgm_matcher.utils import extract_season_from_name
    bgm_title = bgm_item.get('title') or bgm_item.get('original_title')
    season = extract_season_from_name(bgm_title)
    
    # 4. 集数使用 BGM 的
    total_episodes = bgm_item.get('total_episodes') or 0
    
    # 5. 海报回退逻辑：如果匹配不到 TMDB 或 TMDB 没海报，用 BGM 的
    final_poster = bgm_item.get('poster_path')
    if tmdb_item and tmdb_item.get('poster_path'):
        final_poster = tmdb_item.get('poster_path')

    if not tmdb_item:
        return {
            "success": False, 
            "message": "未能自动建立 TMDB 映射",
            "bgm_info": {
                "title": bgm_title,
                "subject_id": subject_id,
                "poster_path": bgm_item.get('poster_path'),
                "total_episodes": total_episodes
            }
        }

    return {
        "success": True,
        "tmdb_id": str(tmdb_item['id']),
        "media_type": tmdb_item['type'],
        "title": tmdb_item['title'],
        "year": tmdb_item.get('year'),
        "season": season,
        "total_episodes": total_episodes,
        "poster_path": final_poster,
        "bgm_info": {
            "title": bgm_title,
            "subject_id": subject_id
        }
    }

@router.post("/one_click_subscribe/{subject_id}", summary="一键快速订阅")
async def one_click_subscribe(subject_id: int, template_id: Optional[int] = None):
    # ... (前置逻辑)
    # 3. 准备订阅模型
    # 获取默认客户端 (如果模板没指定)
    from rss_core.subscription_manager import SubscriptionManager
    from clients.manager import ClientManager
    from models import Subscription, SubscriptionTemplate
    from notification import NotificationManager
    from database import db
    from sqlmodel import select

    # 1. 执行匹配逻辑
    import logging
    logger = logging.getLogger("BGM-Link")
    
    match_res = await match_tmdb(subject_id)
    if not match_res.get("success"):
        logger.warning("自动建立映射失败，准备回退至手动设置")
        return {"success": False, "message": "匹配失败，请尝试手动添加"}

    # 2. 获取配置模板
    target_tmpl = None
    async with db.session_scope():
        if template_id:
            target_tmpl = await db.get(SubscriptionTemplate, template_id)
        else:
            stmt = select(SubscriptionTemplate).where(SubscriptionTemplate.is_default == True)
            target_tmpl = await db.first(SubscriptionTemplate, stmt)

    default_client = ClientManager.get_client()
    default_client_id = default_client.config.get('id') if default_client else None

    sub = Subscription(
        tmdb_id=match_res['tmdb_id'],
        media_type=match_res['media_type'],
        title=match_res['title'],
        year=match_res.get('year'), # [Fix] 保存年份
        poster_path=match_res['poster_path'],
        season=match_res['season'],
        # ... (后续保持不变)
        start_episode=1,
        end_episode=match_res['total_episodes'],
        bangumi_id=str(subject_id),
        enabled=True,
        # --- 以下来自模板或默认值 ---
        target_client_id=target_tmpl.target_client_id if target_tmpl else default_client_id,
        save_path=target_tmpl.save_path if target_tmpl else None,
        category=target_tmpl.category if target_tmpl else "Anime",
        auto_fill=target_tmpl.auto_fill if target_tmpl else True,
        filter_res=target_tmpl.filter_res if target_tmpl else None,
        filter_team=target_tmpl.filter_team if target_tmpl else None,
        filter_source=target_tmpl.filter_source if target_tmpl else None,
        filter_codec=target_tmpl.filter_codec if target_tmpl else None,
        filter_audio=target_tmpl.filter_audio if target_tmpl else None,
        filter_sub=target_tmpl.filter_sub if target_tmpl else None,
        filter_effect=target_tmpl.filter_effect if target_tmpl else None,
        filter_platform=target_tmpl.filter_platform if target_tmpl else None,
        include_keywords=target_tmpl.include_keywords if target_tmpl else None,
        exclude_keywords=target_tmpl.exclude_keywords if target_tmpl else None
    )

    # 4. 保存订阅
    await SubscriptionManager.save_subscription(sub)
    await NotificationManager.push_sub_add_notification(sub)
    
    logger.info(f"✅ 一键订阅成功: {sub.title} (使用模板: {target_tmpl.name if target_tmpl else '系统默认'})")
    log_audit("订阅", "一键订阅", f"已自动为 Bangumi:{subject_id} 创建订阅: {sub.title} S{sub.season}")

    return {"success": True, "message": f"已成功订阅 {sub.title}"}

class BatchSubRequest(BaseModel):
    subject_ids: List[int]
    template_id: Optional[int] = None

@router.post("/batch_subscribe", summary="批量订阅每日放送")
async def batch_subscribe(req: BatchSubRequest):
    """
    批量执行 Bangumi 订阅任务。
    """
    results = {"success": 0, "failed": 0, "details": []}
    for sid in req.subject_ids:
        try:
            res = await one_click_subscribe(sid, template_id=req.template_id)
            if res.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append({"id": sid, "success": res.get("success"), "message": res.get("message")})
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"id": sid, "success": False, "message": str(e)})
    
    return results
