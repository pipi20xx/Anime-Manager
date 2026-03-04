from fastapi import APIRouter, HTTPException
from typing import List, Optional
from sqlmodel import select
from database import db
from models import CalendarSubject
from recognition.data_provider.tmdb.client import TMDBProvider
from datetime import datetime
import json

router = APIRouter(prefix="/api/calendar", tags=["Watch Calendar"])

@router.get("/subjects", summary="获取日历追踪列表")
async def get_subjects():
    async with db.session_scope():
        stmt = select(CalendarSubject)
        return await db.all(CalendarSubject, stmt)

@router.post("/subjects", summary="添加日历追踪项")
async def add_subject(subject: CalendarSubject):
    async with db.session_scope():
        # 1. 检查是否已存在 (按 tmdb_id 和 season 唯一)
        stmt = select(CalendarSubject).where(
            CalendarSubject.tmdb_id == subject.tmdb_id,
            CalendarSubject.season == subject.season
        )
        exists = await db.first(CalendarSubject, stmt)
        if exists:
            return {"success": False, "message": "该季度已在日历中"}
        
        # 2. 如果是 TV 且没有剧集缓存，抓取 TMDB 日期
        if subject.media_type == "tv" and not subject.episodes_cache:
            tmdb = TMDBProvider()
            eps = await tmdb.get_season_episodes(subject.tmdb_id, subject.season)
            if eps:
                subject.episodes_cache = eps
                # 顺便更新首播日期
                subject.first_air_date = eps[0]["air_date"]
        
        await db.save(subject)
    return {"success": True, "message": "已成功加入日历并同步放送日期"}

@router.post("/subjects/{subject_id}/refresh", summary="刷新条目的放送日期")
async def refresh_subject(subject_id: int):
    async with db.session_scope():
        subject = await db.get(CalendarSubject, subject_id)
        if not subject or subject.media_type != "tv":
            return {"success": False, "message": "条目不存在或非电视剧"}
        
        tmdb = TMDBProvider()
        eps = await tmdb.get_season_episodes(subject.tmdb_id, subject.season)
        if eps:
            subject.episodes_cache = eps
            subject.first_air_date = eps[0]["air_date"]
            await db.save(subject)
            return {"success": True, "message": "已同步最新放送计划"}
    return {"success": False, "message": "无法从 TMDB 获取数据"}

@router.delete("/subjects/{subject_id}", summary="删除日历追踪项")

async def delete_subject(subject_id: int):

    async with db.session_scope():

        subject = await db.get(CalendarSubject, subject_id)

        if subject:

            await db.delete(subject)

    return {"success": True}



@router.put("/subjects/{subject_id}", summary="修改日历追踪项")

async def update_subject(subject_id: int, updated_data: dict):

    async with db.session_scope():

        subject = await db.get(CalendarSubject, subject_id)

        if not subject:

            return {"success": False, "message": "未找到条目"}

        

        # 更新标题或季号

        subject.title = updated_data.get("title", subject.title)

        

        # 如果季号变了，需要重新同步日期

        new_season = updated_data.get("season", subject.season)

        if new_season != subject.season:

            subject.season = new_season

            tmdb = TMDBProvider()

            eps = await tmdb.get_season_episodes(subject.tmdb_id, subject.season)

            if eps:

                subject.episodes_cache = eps

                subject.first_air_date = eps[0]["air_date"]

        

        await db.save(subject)

    return {"success": True}



@router.post("/import_bangumi/{bgm_id}", summary="从 Bangumi 一键导入")

async def import_bangumi(bgm_id: int):

    from routers.bangumi import match_tmdb

    

    # 1. 自动匹配 TMDB

    match_res = await match_tmdb(bgm_id)

    if not match_res.get("success"):

        return match_res

    

    tmdb_id = match_res["tmdb_id"]

    season = match_res.get("season") or 1

    title = match_res["title"]

    poster = match_res.get("poster_path")



    async with db.session_scope():

        # 2. 检查是否已在追踪

        stmt = select(CalendarSubject).where(CalendarSubject.tmdb_id == tmdb_id, CalendarSubject.season == season)

        exists = await db.first(CalendarSubject, stmt)

        if exists:

            return {"success": False, "message": f"《{title}》已在日历中"}



        # 3. 抓取放送日期

        tmdb = TMDBProvider()

        eps = await tmdb.get_season_episodes(tmdb_id, season)

        

        new_sub = CalendarSubject(

            tmdb_id=tmdb_id,

            media_type=match_res["media_type"],

            title=title,

            season=season,

            poster_path=poster,

            episodes_cache=eps,

            first_air_date=eps[0]["air_date"] if eps else None

        )

        await db.save(new_sub)

        

    return {"success": True, "message": f"已成功将《{title}》加入日历"}

@router.post("/batch_import_bangumi", summary="从 Bangumi 批量导入")
async def batch_import_bangumi(bgm_ids: List[int]):
    results = {"success": 0, "failed": 0, "details": []}
    for bid in bgm_ids:
        try:
            res = await import_bangumi(bid)
            if res.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1
            results["details"].append({"id": bid, "success": res.get("success"), "message": res.get("message")})
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"id": bid, "success": False, "message": str(e)})
    
    return results

@router.post("/test_push", summary="测试发送今日播出总结")
async def test_push():
    """
    手动触发一次当天的每日播出总结推送。
    """
    from monitor import MonitorManager
    try:
        await MonitorManager._calendar_daily_push()
        return {"success": True, "message": "测试推送已发送，请检查您的 Telegram。"}
    except Exception as e:
        return {"success": False, "message": f"发送失败: {str(e)}"}
