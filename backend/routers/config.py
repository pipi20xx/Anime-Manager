from fastapi import APIRouter, HTTPException
from config_manager import ConfigManager
from monitor import MonitorManager
from logger import log_audit
from pydantic import BaseModel
from typing import Optional
import os
import re
import datetime

router = APIRouter(tags=["系统配置"])

@router.get("/api/config", summary="获取全局配置")
async def get_config(): 
    """
    返回系统当前的全部配置项，包括路径、API 密钥、整理任务、重命名规则等。
    """
    return ConfigManager.get_config()

@router.post("/api/config", summary="更新全局配置")
async def update_config(config: dict):
    """
    更新并保存全局配置，同时触发后台监控器的动态重载。
    """
    ConfigManager.update_config(config)
    await MonitorManager.reload()
    log_audit("系统", "配置", "更新系统配置")
    return {"status": "success"}

@router.post("/api/refresh_remote_rules", summary="同步远程规则库")
async def refresh_remote_rules():
    """
    从云端仓库同步最新的自定义识别词、自定义制作组、自定义渲染词等社区规则。
    """
    try:
        cache = await ConfigManager.refresh_remote_rules()
        total = sum(len(v) for v in cache.values())
        log_audit("系统", "同步", f"远程规则同步成功，共 {total} 条")
        return {"success": True, "message": f"同步成功，共拉取 {total} 条规则"}
    except Exception as e:
        log_audit("系统", "错误", f"远程规则同步失败: {str(e)}", level="ERROR")
        raise HTTPException(status_code=500, detail=str(e))
