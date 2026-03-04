from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Dict, Any
from tmdbmatefull.manager import TmdbMateFullManager
from tmdbmatefull.database import TmdbFullDB
from tmdbmatefull.models import TmdbDeepMeta, RefGenre, RefCompany, RefKeyword
from sqlmodel import or_, col, select
from logger import log_audit

router = APIRouter(prefix="/api/tmdb_full", tags=["TMDB满血元数据"])

async def task_refresh_all_metadata():
    """后台执行全量刷新逻辑"""
    log_audit("离线库", "全量刷新", "开始执行全量元数据同步任务...")
    async with await TmdbFullDB.get_session() as session:
        # 获取库中所有 ID 和类型
        stmt = select(TmdbDeepMeta.tmdb_id, TmdbDeepMeta.media_type)
        items = (await session.execute(stmt)).all()
        
    count = 0
    for tid, mtype in items:
        try:
            # 调用 fetch_and_ingest 且 force=True (强制云端同步)
            await TmdbMateFullManager.fetch_and_ingest(tid, mtype, force=True)
            count += 1
        except Exception as e:
            print(f"[离线刷新] ID {tid} 失败: {e}")
            
    log_audit("离线库", "刷新完成", f"已成功强制更新 {count} 条元数据")

@router.get("/rules/export", summary="导出二级分类规则")
async def export_secondary_rules():
    """导出当前所有二级分类规则"""
    return await TmdbMateFullManager.load_secondary_rules()

@router.post("/rules/import", summary="导入二级分类规则")
async def import_secondary_rules(rules: List[Dict[str, Any]], mode: str = Query("append", enum=["append", "replace"])):
    """
    导入二级分类规则
    - mode=append: 追加模式（默认）
    - mode=replace: 覆盖模式（先清空现有规则）
    """
    count = await TmdbMateFullManager.import_secondary_rules(rules, mode)
    return {"status": "success", "count": count}

@router.get("/rules", summary="获取二级分类规则")
async def get_secondary_rules():
    """
    获取系统中定义的二级分拣逻辑规则（从数据库加载）。
    """
    return await TmdbMateFullManager.load_secondary_rules()

@router.post("/rules", summary="保存二级分类规则列表")
async def save_secondary_rules(rules: List[Dict[str, Any]]):
    """
    批量更新所有规则（支持排序更新）。
    """
    for r in rules:
        # 保存每一条规则（如果是新增，Manager 会自动生成 ID）
        await TmdbMateFullManager.save_secondary_rule(r)
    
    # 重新加载一遍数据库里的规则（它们现在已经有了正确的 ID）
    latest_rules = await TmdbMateFullManager.load_secondary_rules()
    
    # 获取最新的 ID 列表（保持前端传来的顺序）
    # 我们根据名称来匹配前端传来的顺序，或者直接按前端传来的顺序重新计算优先级
    ordered_rule_ids = []
    # 建立一个查找映射 (name -> id)
    db_mapping = {r["name"]: r["id"] for r in latest_rules}
    
    for r in rules:
        rid = r.get("id") or db_mapping.get(r["name"])
        if rid:
            ordered_rule_ids.append(rid)
    
    # 执行物理重排
    if ordered_rule_ids:
        await TmdbMateFullManager.reorder_rules(ordered_rule_ids)
        
    return {"status": "success"}

@router.delete("/rules/{rule_id}", summary="删除规则")
async def delete_secondary_rule(rule_id: int):
    success = await TmdbMateFullManager.delete_secondary_rule(rule_id)
    if success: return {"status": "success"}
    raise HTTPException(404, "规则未找到")

@router.post("/refresh_all", summary="全量强制刷新离线库")
async def refresh_all_metadata(background_tasks: BackgroundTasks):
    """
    触发后台异步任务，对库中所有条目强制与 TMDB 云端同步。
    """
    background_tasks.add_task(task_refresh_all_metadata)
    return {"status": "success", "message": "全量刷新任务已在后台启动，请关注系统日志"}

@router.get("/list", summary="浏览离线库元数据")
async def list_full_meta(
    page: int = Query(1),
    page_size: int = Query(20),
    search: str = Query(None)
):
    """
    分页并支持搜索地查看本地 FullDB 中的详细元数据。
    """
    return await TmdbMateFullManager.browse_deep_meta(page, page_size, search)

@router.get("/export_dict", summary="导出映射字典")
async def export_reference_dictionary():
    """
    导出所有流派、公司、关键字的 ID 映射表，用于规则编写参考。
    """
    return await TmdbMateFullManager.browse_deep_meta_export()

@router.get("/search_ref", summary="离线字典快速搜索")
async def search_reference(q: str = Query(..., min_length=1), type: str = Query("all")):
    """
    在本地 FullDB 的参考表中搜索名称，获取其对应的 ID（支持流派、制作公司、关键字）。
    """
    results = []

    async with await TmdbFullDB.get_session() as session:

        # 1. 搜流派

        if type in ["all", "genre"]:

            stmt = select(RefGenre).where(or_(

                col(RefGenre.name_zh).contains(q),

                col(RefGenre.name_en).contains(q)

            ))

            res = await session.execute(stmt)

            for item in res.scalars().all():

                results.append({"id": str(item.id), "name": item.name_zh or item.name_en, "type": "流派"})



        # 2. 搜公司

        if type in ["all", "company"]:

            stmt = select(RefCompany).where(col(RefCompany.name).contains(q))

            res = await session.execute(stmt)

            for item in res.scalars().all():

                results.append({"id": str(item.id), "name": item.name, "type": "公司"})



        # 3. 搜关键词

        if type in ["all", "keyword"]:

            stmt = select(RefKeyword).where(col(RefKeyword.name_en).contains(q))

            res = await session.execute(stmt)

            for item in res.scalars().all():

                results.append({"id": str(item.id), "name": item.name_en, "type": "关键词"})



    return results
