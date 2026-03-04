from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from sqlmodel import select

from models import FilterRule, QualityProfile, Subscription
from database import db
from logger import log_audit

router = APIRouter(tags=["优先级规则管理"])

# ==========================================
# 1. 基础规则 (FilterRule) 管理
# ==========================================

@router.get("/priority/rules", response_model=List[FilterRule], summary="获取所有基础规则")
async def get_filter_rules():
    async with db.session_scope():
        stmt = select(FilterRule).order_by(FilterRule.id.desc())
        return await db.all(FilterRule, stmt)

@router.post("/priority/rules", summary="保存/更新基础规则")
async def save_filter_rule(rule: FilterRule):
    async with db.session_scope():
        # 检查名字是否和其他规则冲突
        stmt = select(FilterRule).where(FilterRule.name == rule.name)
        if rule.id:
            stmt = stmt.where(FilterRule.id != rule.id)
        if await db.first(FilterRule, stmt):
            raise HTTPException(status_code=400, detail=f"规则名称 '{rule.name}' 已存在")

        if rule.id:
            # 更新
            db_rule = await db.get(FilterRule, rule.id)
            if not db_rule:
                raise HTTPException(status_code=404, detail="规则不存在")
            
            update_data = rule.model_dump(exclude={"id", "created_at"}, exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_rule, key, value)
                
            saved = await db.save(db_rule)
            log_audit("优先级规则", "更新规则", f"更新了基础规则: {rule.name}")
        else:
            # 新建
            rule.id = None
            saved = await db.save(rule)
            log_audit("优先级规则", "新建规则", f"新建了基础规则: {rule.name}")
            
        return saved

@router.delete("/priority/rules/{rule_id}", summary="删除基础规则")
async def delete_filter_rule(rule_id: int):
    async with db.session_scope():
        rule = await db.get(FilterRule, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")
            
        # 检查是否有 Profile 正在使用此规则
        # 这需要遍历所有 Profile 的 JSON 字段，略显复杂，这里做简单的全量检查
        stmt = select(QualityProfile)
        profiles = await db.all(QualityProfile, stmt)
        
        used_in = []
        for p in profiles:
            if p.rules_config:
                for r in p.rules_config:
                    if str(r.get("rule_id")) == str(rule_id):
                        used_in.append(p.name)
                        break
        
        if used_in:
            raise HTTPException(status_code=400, detail=f"无法删除：该规则正被策略 [{', '.join(used_in)}] 使用中")

        await db.delete(rule)
        log_audit("优先级规则", "删除规则", f"删除了基础规则: {rule.name}")
        return {"success": True}

# ==========================================
# 2. 策略组装 (QualityProfile) 管理
# ==========================================

@router.get("/priority/profiles", response_model=List[QualityProfile], summary="获取所有优先级策略")
async def get_quality_profiles():
    async with db.session_scope():
        stmt = select(QualityProfile).order_by(QualityProfile.id.desc())
        return await db.all(QualityProfile, stmt)

@router.post("/priority/profiles", summary="保存/更新优先级策略")
async def save_quality_profile(profile: QualityProfile):
    async with db.session_scope():
        # 检查名称重复
        stmt = select(QualityProfile).where(QualityProfile.name == profile.name)
        if profile.id:
            stmt = stmt.where(QualityProfile.id != profile.id)
        if await db.first(QualityProfile, stmt):
            raise HTTPException(status_code=400, detail=f"策略名称 '{profile.name}' 已存在")

        # 简单的校验 rules_config 格式
        if not isinstance(profile.rules_config, list):
             raise HTTPException(status_code=400, detail="规则配置必须是列表")

        if profile.id:
            # 更新
            db_profile = await db.get(QualityProfile, profile.id)
            if not db_profile:
                raise HTTPException(status_code=404, detail="策略不存在")
            
            update_data = profile.model_dump(exclude={"id", "created_at"}, exclude_unset=True)
            for key, value in update_data.items():
                setattr(db_profile, key, value)
                
            saved = await db.save(db_profile)
            log_audit("优先级规则", "更新策略", f"更新了优先级策略: {profile.name}")
        else:
            # 新建
            profile.id = None
            saved = await db.save(profile)
            log_audit("优先级规则", "新建策略", f"新建了优先级策略: {profile.name}")
        
        return saved

@router.delete("/priority/profiles/{profile_id}", summary="删除优先级策略")
async def delete_quality_profile(profile_id: int):
    async with db.session_scope():
        profile = await db.get(QualityProfile, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="策略不存在")
            
        # 检查是否有订阅正在使用
        stmt = select(Subscription).where(Subscription.quality_profile_id == profile_id)
        if await db.first(Subscription, stmt):
            raise HTTPException(status_code=400, detail="无法删除：仍有订阅正在使用此策略")

        await db.delete(profile)
        log_audit("优先级规则", "删除策略", f"删除了优先级策略: {profile.name}")
        return {"success": True}
