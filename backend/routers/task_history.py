from fastapi import APIRouter, Query, HTTPException

from task_history import get_task_list, get_task_detail, delete_task, cleanup_old_tasks

router = APIRouter(prefix="/api/task_history", tags=["任务中心"])

@router.get("", summary="获取任务历史列表")
async def list_tasks(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), module: str = Query(None)):
    """
    获取任务历史记录列表。
    - limit: 返回数量限制
    - offset: 偏移量（用于分页）
    - module: 按模块筛选 (整理/STRM/RSS/元数据)
    """
    return await get_task_list(limit=limit, offset=offset, module=module)

@router.get("/{task_id}", summary="获取任务详情")
async def task_detail(task_id: str):
    """
    获取单个任务的完整执行日志。
    """
    detail = await get_task_detail(task_id)
    if not detail:
        raise HTTPException(status_code=404, detail="任务记录不存在")
    return detail

@router.delete("/{task_id}", summary="删除任务记录")
async def remove_task(task_id: str):
    """
    删除单个任务记录及其日志。
    """
    success = await delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务记录不存在")
    return {"status": "success", "message": "任务记录已删除"}

@router.delete("", summary="清理旧任务记录")
async def cleanup_tasks(max_records: int = Query(500), max_days: int = Query(30)):
    """
    清理旧任务记录。
    - max_records: 保留最近 N 条记录
    - max_days: 保留最近 N 天的记录
    """
    await cleanup_old_tasks(max_records=max_records, max_days=max_days)
    return {"status": "success", "message": f"已清理超过 {max_days} 天或超过 {max_records} 条的记录"}
