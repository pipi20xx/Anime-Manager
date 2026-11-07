# -*- coding: utf-8 -*-
"""番剧分季拆分 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from season_split import service, store

router = APIRouter(prefix="/season-split", tags=["番剧分季"])


# ---------------------------------------------------------------------------
# 请求体
# ---------------------------------------------------------------------------

class PreviewRequest(BaseModel):
    tmdb_id: int
    priority: Optional[str] = Field(default=None, description="tvdb, bangumi / bangumi, tvdb / 仅 tvdb / 仅 bangumi")
    use_source: Optional[bool] = Field(default=None, description="启用 CureTMDb 外部分季规则表（空则用系统设置）")
    source: Optional[str] = Field(default=None, description="规则表地址（空则用系统设置）")
    force_reference: Optional[bool] = Field(default=None, description="忽略「仅日本动画 / 季数 1~2」的自动参照门槛（空则用系统设置）")
    skip_references: Optional[bool] = Field(default=None, description="编辑已有规则时跳过参照源获取与候选生成")


class CompileRequest(BaseModel):
    tmdb_id: int
    groups: List[Dict[str, Any]] = Field(default_factory=list)
    overrides: Dict[str, Any] = Field(default_factory=dict)
    excluded: List[Any] = Field(default_factory=list)
    names: Dict[str, Any] = Field(default_factory=dict)
    reference: Optional[str] = None


class SaveRequest(CompileRequest):
    status: str = Field(default="draft", description="draft / active / disabled")
    render_words: Optional[str] = Field(default=None, description="手动渲染词覆盖（留空则按分组重新编译）")
    origin: Optional[str] = Field(
        default=None, description="创建来源：manual / sytmdb / auto（留空 = 保留库里原值，新建时按 manual）")


class SytmdbImportRequest(BaseModel):
    tmdb_ids: Optional[List[int]] = Field(
        default=None, description="要导入的 TMDB ID；留空 = 导入 SYTMDB 全部需要拆分的条目")
    status: str = Field(default="active", description="导入后的规则状态：active / draft / disabled")
    overwrite: bool = Field(default=False, description="规则库里已存在时是否覆盖")


class SettingsRequest(BaseModel):
    season_split_mode: Optional[str] = None
    season_split_scope: Optional[Dict[str, Any]] = None
    season_split_blacklist: Optional[List[Any]] = None
    season_split_exclude_patterns: Optional[List[str]] = None
    season_split_priority: Optional[str] = None
    season_split_source: Optional[str] = None
    season_split_use_source: Optional[bool] = None
    season_split_force_reference: Optional[bool] = None
    season_split_auto_generate: Optional[bool] = None
    season_split_auto_push_sytmdb: Optional[bool] = None
    season_split_gap_days: Optional[int] = None
    season_split_ref_genre_ids: Optional[List[int]] = None
    season_split_ref_countries: Optional[List[str]] = None
    season_split_ref_season_min: Optional[int] = None
    season_split_ref_season_max: Optional[int] = None
    season_split_fixed_sizes: Optional[List[int]] = None
    season_split_gap_mark_days: Optional[int] = None
    season_split_use_includes_rules: Optional[bool] = None
    tvdb_api_key: Optional[str] = None


# ---------------------------------------------------------------------------
# 规则库
# ---------------------------------------------------------------------------

@router.get("/rules", summary="分季规则列表")
async def list_rules(status: Optional[str] = None, q: str = "", origin: Optional[str] = None):
    """`origin` 过滤：manual / sytmdb / auto / legacy（历史未知，升级前没有来源列的老数据）。"""
    return {
        "items": await store.list_rules(status=status, q=q, origin=origin),
        "cache": store.cache_stats(),
    }


@router.get("/rules/{tmdb_id}", summary="单条规则详情")
async def get_rule(tmdb_id: int):
    rule = await store.get_rule(tmdb_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    return rule


@router.put("/rules", summary="保存规则（会自动重新编译渲染词）")
async def save_rule(req: SaveRequest):
    try:
        return await service.save(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {e}")


@router.delete("/rules/{tmdb_id}", summary="删除规则")
async def delete_rule(tmdb_id: int):
    ok = await store.delete_rule(tmdb_id)
    if not ok:
        raise HTTPException(status_code=404, detail="规则不存在")
    return {"ok": True, "tmdb_id": tmdb_id}


# ---------------------------------------------------------------------------
# 预览 / 编译
# ---------------------------------------------------------------------------

@router.post("/preview", summary="拉取 TMDB 结构 + 参照源，出候选分组与默认方案")
async def preview(req: PreviewRequest):
    try:
        return await service.preview(req.tmdb_id, req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {e}")


@router.post("/compile", summary="按提交的分组重新编译（不落库）")
async def compile_rules(req: CompileRequest):
    try:
        return await service.compile_only(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 落地动作
# ---------------------------------------------------------------------------

@router.post("/push-episodegroup/{tmdb_id}", summary="把剧集组写入 SYTMDB")
async def push_episode_group(tmdb_id: int):
    try:
        return await service.push_episode_group(tmdb_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"SYTMDB 写入失败: {e}")


@router.post("/reload", summary="强制重载规则缓存")
async def reload_cache():
    count = await store.reload()
    return {"ok": True, "count": count, "cache": store.cache_stats()}


# ---------------------------------------------------------------------------
# SYTMDB 一键导入（直接使用 SYTMDB 的剧集组，不重新生成）
# ---------------------------------------------------------------------------

@router.get("/sytmdb/candidates", summary="列出 SYTMDB 里所有带剧集组的番")
async def sytmdb_candidates():
    try:
        return await service.sytmdb_candidates()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"读取 SYTMDB 失败: {e}")


@router.post("/sytmdb/import", summary="把 SYTMDB 的剧集组一键导入成规则")
async def sytmdb_import(req: SytmdbImportRequest):
    try:
        return await service.sytmdb_import(
            tmdb_ids=req.tmdb_ids,
            status=req.status,
            overwrite=req.overwrite,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"导入失败: {e}")


@router.get("/debug", summary="映射调试器：回放某集的规则")
async def debug(tmdb_id: int, season: int, episode: int, filename: str = ""):
    try:
        return await service.debug_episode(tmdb_id, season, episode, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# 设置
# ---------------------------------------------------------------------------

@router.get("/settings", summary="读取开关 / 黑名单 / 默认参数")
async def get_settings():
    return service.settings_snapshot()


@router.put("/settings", summary="更新开关 / 黑名单 / 默认参数")
async def update_settings(req: SettingsRequest):
    try:
        data = service.settings_update(req.model_dump(exclude_none=True))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await store.reload()
    return data


@router.get("/blacklist/meta", summary="黑名单条目元数据（永久缓存 / 数据中心）")
async def blacklist_meta():
    return await service.blacklist_meta()
