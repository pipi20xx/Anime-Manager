"""联动记录中心 API：Webhook 事件台账的查询、详情、手动重放与清理。

注意：路由前缀刻意避开 /api/webhook* —— 该前缀在 main.py 的鉴权中间件中被
免登录放行（供 CD2/Emby 回调使用），台账管理端点必须走登录鉴权。
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException

import webhook_ledger as ledger
from routers.webhook import process_cd2_notification

router = APIRouter(prefix="/api/linkage_events", tags=["联动记录"])
logger = logging.getLogger("WebhookLedger")


def _parse_dt(value: str = None) -> datetime:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"时间格式无效: {value}")


@router.get("", summary="获取联动记录列表")
async def list_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str = Query(None, description="按状态筛选: pending/processing/success/failed/unmatched"),
    source: str = Query(None, description="按来源筛选（如: 原生 Webhook）"),
    search: str = Query(None, description="按路径关键词搜索"),
    start_time: str = Query(None, description="起始时间 ISO 格式"),
    end_time: str = Query(None, description="结束时间 ISO 格式"),
    parent_id: int = Query(None, description="按父目录事件 id 筛选（查看目录展开的子事件）"),
):
    start = _parse_dt(start_time)
    end = _parse_dt(end_time)
    items = await ledger.list_events(limit=limit, offset=offset, status=status, source=source,
                                     search=search, start_time=start, end_time=end, parent_id=parent_id)
    total = await ledger.count_events(status=status, source=source, search=search,
                                      start_time=start, end_time=end)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/stats", summary="获取联动记录统计")
async def event_stats():
    """状态分布 + 今日总数/今日失败数。"""
    return await ledger.get_stats()


@router.get("/{event_id}", summary="获取联动记录详情")
async def event_detail(event_id: int):
    detail = await ledger.get_event(event_id)
    if not detail:
        raise HTTPException(status_code=404, detail="联动记录不存在")
    return detail


@router.get("/{event_id}/logs", summary="获取事件全链路执行日志")
async def event_logs(event_id: int):
    """
    聚合事件完整链路的任务日志：webhook 接收任务 + 队列 STRM 处理任务 / 目录展开任务，
    按时间顺序返回，详情页无需跳转任务中心即可看完整日志。
    """
    logs = await ledger.get_event_logs(event_id)
    if logs is None:
        raise HTTPException(status_code=404, detail="联动记录不存在")
    return {"tasks": logs}


@router.post("/{event_id}/replay", summary="手动重放联动事件")
async def replay_event(event_id: int):
    """
    将台账中保存的原始 payload 原样重新执行一遍（成功/失败的事件均可重放）。
    复用同一条台账记录：attempts +1，状态回到 processing 后按本次执行结果更新。
    """
    record = await ledger.mark_replaying(event_id)
    if not record:
        raise HTTPException(status_code=404, detail="联动记录不存在")

    payload = record.payload or {}
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        await ledger.update_event(event_id, status="failed", error_message="重放失败: 台账中无可执行的 payload")
        raise HTTPException(status_code=400, detail="台账中无可执行的 payload")

    result = await process_cd2_notification(
        data, source="手动重放", raw_payload=payload,
        replay_event_id=event_id, skip_dedup=True,
        parent_event_id=record.parent_event_id,
    )
    return {"status": "success", "event_id": event_id, "result": result}


@router.post("/replay_all", summary="批量重放当前筛选结果")
async def replay_all_events(
    status: str = Query(None, description="按状态筛选"),
    source: str = Query(None, description="按来源筛选"),
    search: str = Query(None, description="按路径关键词筛选"),
    start_time: str = Query(None, description="起始时间 ISO 格式"),
    end_time: str = Query(None, description="结束时间 ISO 格式"),
    limit: int = Query(500, ge=1, le=1000, description="单次最多重放条数（按时间倒序）"),
):
    """
    对当前筛选结果内的全部事件按顺序逐条重放（与列表页筛选条件一致）。
    串行执行避免并发请求触发网盘风控；单次上限 limit 条，超出请缩小筛选范围。
    """
    start = _parse_dt(start_time)
    end = _parse_dt(end_time)
    matched = await ledger.count_events(status=status, source=source, search=search,
                                        start_time=start, end_time=end)
    ids = await ledger.get_event_ids(status=status, source=source, search=search,
                                     start_time=start, end_time=end, limit=limit)
    ok, failed = 0, 0
    for eid in ids:
        try:
            record = await ledger.mark_replaying(eid)
            if not record:
                failed += 1
                continue
            payload = record.payload or {}
            data = payload.get("data")
            if not isinstance(data, list) or not data:
                await ledger.update_event(eid, status="failed", error_message="重放失败: 台账中无可执行的 payload")
                failed += 1
                continue
            await process_cd2_notification(
                data, source="手动重放", raw_payload=payload,
                replay_event_id=eid, skip_dedup=True,
                parent_event_id=record.parent_event_id,
            )
            ok += 1
        except Exception as e:
            logger.warning(f"[联动记录] 批量重放单条失败 (id={eid}): {e}")
            await ledger.update_event(eid, status="failed", error_message=f"重放异常: {e}")
            failed += 1
    return {
        "status": "success", "matched": matched, "replayed": ok, "failed": failed,
        "message": f"批量重放完成：成功触发 {ok} 个{('，失败 ' + str(failed) + ' 个') if failed else ''}"
                   + (f"（筛选共 {matched} 条，本次超出上限未重放 {matched - ok - failed} 条，请缩小范围后继续）" if matched > ok + failed else ""),
    }


@router.delete("/{event_id}", summary="删除单条联动记录")
async def remove_event(event_id: int):
    success = await ledger.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="联动记录不存在")
    return {"status": "success", "message": "联动记录已删除"}


@router.post("/clear", summary="批量清理联动记录")
async def clear_events(
    status: str = Query(None, description="按状态筛选"),
    source: str = Query(None, description="按来源筛选"),
    search: str = Query(None, description="按路径关键词筛选"),
    start_time: str = Query(None, description="起始时间 ISO 格式"),
    end_time: str = Query(None, description="结束时间 ISO 格式"),
    before_days: int = Query(None, description="只清理 N 天前的记录"),
):
    """清理范围与列表筛选条件完全一致（重放/清理共用同一套筛选）。"""
    count = await ledger.clear_events(status=status, source=source, search=search,
                                      start_time=_parse_dt(start_time), end_time=_parse_dt(end_time),
                                      before_days=before_days)
    return {"status": "success", "message": f"已清理 {count} 条联动记录", "count": count}
