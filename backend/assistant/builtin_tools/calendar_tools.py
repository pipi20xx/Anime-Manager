from ..tools import tool, ToolResult
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@tool(
    name="list_calendar_subjects",
    description="获取日历追踪列表，显示正在追番的作品及其更新时间。",
    category="日历追踪",
    parameters=[]
)
async def list_calendar_subjects() -> ToolResult:
    try:
        from database import db
        from models import CalendarSubject
        from sqlmodel import select
        
        async with db.session_scope():
            stmt = select(CalendarSubject)
            subjects = await db.all(CalendarSubject, stmt)
        
        result = []
        for sub in subjects:
            result.append({
                "id": sub.id,
                "subject_id": sub.subject_id,
                "title": sub.title,
                "weekday": sub.weekday,
                "air_date": sub.air_date,
                "episode_count": sub.episode_count,
                "enabled": sub.enabled,
                "notify": sub.notify
            })
        
        return ToolResult(
            success=True,
            data=result,
            message=f"正在追踪 {len(result)} 部番剧"
        )
    except Exception as e:
        logger.error(f"[Tool] list_calendar_subjects 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="add_calendar_subject",
    description="添加番剧到日历追踪列表，系统会在更新时提醒。",
    category="日历追踪",
    parameters=[
        {"name": "bangumi_id", "type": "integer", "description": "Bangumi 条目 ID", "required": True},
        {"name": "notify", "type": "boolean", "description": "是否开启更新通知", "required": False}
    ]
)
async def add_calendar_subject(bangumi_id: int, notify: bool = True) -> ToolResult:
    try:
        from recognition.data_provider.bangumi.client import BangumiProvider
        from database import db
        from models import CalendarSubject
        from sqlmodel import select
        
        bgm_item = await BangumiProvider.get_subject_details(bangumi_id)
        if not bgm_item:
            return ToolResult(success=False, error=f"Bangumi 条目 {bangumi_id} 未找到")
        
        async with db.session_scope():
            existing_stmt = select(CalendarSubject).where(
                CalendarSubject.subject_id == str(bangumi_id)
            )
            existing = await db.first(CalendarSubject, existing_stmt)
            if existing:
                return ToolResult(
                    success=False,
                    error=f"已在追踪列表中: {existing.title}",
                    data={"existing_id": existing.id}
                )
            
            subject = CalendarSubject(
                subject_id=str(bangumi_id),
                title=bgm_item.get("title"),
                image=bgm_item.get("images", {}).get("large") if bgm_item.get("images") else None,
                notify=notify,
                enabled=True
            )
            
            await db.save(subject)
        
        return ToolResult(
            success=True,
            data={
                "id": subject.id,
                "title": subject.title,
                "notify": subject.notify
            },
            message=f"已添加追踪: {subject.title}"
        )
    except Exception as e:
        logger.error(f"[Tool] add_calendar_subject 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="remove_calendar_subject",
    description="从日历追踪列表中移除番剧。",
    category="日历追踪",
    parameters=[
        {"name": "subject_id", "type": "integer", "description": "追踪条目 ID（非 Bangumi ID）", "required": True}
    ]
)
async def remove_calendar_subject(subject_id: int) -> ToolResult:
    try:
        from database import db
        from models import CalendarSubject
        
        async with db.session_scope():
            subject = await db.get(CalendarSubject, subject_id)
            if not subject:
                return ToolResult(success=False, error=f"追踪条目 {subject_id} 不存在")
            
            title = subject.title
            await db.delete(subject)
        
        return ToolResult(success=True, message=f"已移除追踪: {title}")
    except Exception as e:
        logger.error(f"[Tool] remove_calendar_subject 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="refresh_calendar_subject",
    description="刷新指定番剧的放送日期信息。",
    category="日历追踪",
    parameters=[
        {"name": "subject_id", "type": "integer", "description": "追踪条目 ID", "required": True}
    ]
)
async def refresh_calendar_subject(subject_id: int) -> ToolResult:
    try:
        from database import db
        from models import CalendarSubject
        from recognition.data_provider.bangumi.client import BangumiProvider
        
        async with db.session_scope():
            subject = await db.get(CalendarSubject, subject_id)
            if not subject:
                return ToolResult(success=False, error=f"追踪条目 {subject_id} 不存在")
            
            bgm_id = int(subject.subject_id)
            bgm_item = await BangumiProvider.get_subject_details(bgm_id)
            
            if bgm_item:
                subject.title = bgm_item.get("title", subject.title)
                subject.episode_count = bgm_item.get("eps")
                await db.save(subject)
        
        return ToolResult(success=True, message=f"已刷新: {subject.title}")
    except Exception as e:
        logger.error(f"[Tool] refresh_calendar_subject 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_today_anime",
    description="获取今天更新的番剧列表。",
    category="日历追踪",
    parameters=[]
)
async def get_today_anime() -> ToolResult:
    try:
        from datetime import datetime
        from database import db
        from models import CalendarSubject
        from sqlmodel import select
        
        today_weekday = datetime.now().weekday()
        weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
        
        async with db.session_scope():
            stmt = select(CalendarSubject).where(
                CalendarSubject.weekday == today_weekday,
                CalendarSubject.enabled == True
            )
            subjects = await db.all(CalendarSubject, stmt)
        
        result = []
        for sub in subjects:
            result.append({
                "id": sub.id,
                "title": sub.title,
                "episode_count": sub.episode_count,
                "notify": sub.notify
            })
        
        weekday_name = weekday_map[today_weekday]
        if not result:
            formatted = f"📅 今天（{weekday_name}）没有追番更新"
        else:
            lines = [f"📅 **今日更新（{weekday_name}）**\n"]
            for idx, sub in enumerate(result, 1):
                notify_icon = "🔔" if sub.get("notify") else "🔇"
                lines.append(f"{idx}. {notify_icon} {sub['title']}")
            formatted = "\n".join(lines)
        
        return ToolResult(
            success=True,
            data={
                "weekday": weekday_name,
                "anime_list": result
            },
            message=f"今天（{weekday_name}）更新 {len(result)} 部番剧",
            formatted_message=formatted
        )
    except Exception as e:
        logger.error(f"[Tool] get_today_anime 失败: {e}")
        return ToolResult(success=False, error=str(e))
