from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import select
from datetime import datetime
from database import get_session, db
from models import HealthCheckConfig
from notification import NotificationManager
from logger import log_audit
import logging
import os
import httpx
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])

@router.get("/configs", response_model=List[HealthCheckConfig])
async def get_health_configs(session=Depends(get_session)):
    return await db.all(HealthCheckConfig)

@router.post("/configs", response_model=HealthCheckConfig)
async def create_health_config(config: HealthCheckConfig, session=Depends(get_session)):
    return await db.save(config)

@router.put("/configs/{config_id}", response_model=HealthCheckConfig)
async def update_health_config(config_id: int, config_data: HealthCheckConfig, session=Depends(get_session)):
    db_config = await db.get(HealthCheckConfig, config_id)
    if not db_config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # 修复 DataError: 排除自增和时间字段，防止字符串覆盖 datetime 对象
    update_data = config_data.dict(exclude={"id", "created_at", "last_check"})
    for key, value in update_data.items():
        setattr(db_config, key, value)
    
    return await db.save(db_config)

@router.delete("/configs/{config_id}")
async def delete_health_config(config_id: int, session=Depends(get_session)):
    db_config = await db.get(HealthCheckConfig, config_id)
    if not db_config:
        raise HTTPException(status_code=404, detail="Config not found")
    await db.delete(db_config)
    return {"status": "ok"}

async def run_single_check(config_id: int):
    async with db.session_scope(force_new=True):
        config = await db.get(HealthCheckConfig, config_id)
        if not config or not config.enabled:
            return

        status = "Failed"
        error_detail = ""
        log_audit("健康检查", "执行", f"正在检查项目: {config.name}", level="DEBUG")

        try:
            # 1. 检查本地文件
            if not os.path.exists(config.file_path):
                error_detail = "本地文件不存在或路径错误"
            elif not os.path.isfile(config.file_path):
                error_detail = "指定路径是一个目录而非文件"
            else:
                # 尝试读取 1 字节，确保磁盘 IO 真正通畅
                try:
                    with open(config.file_path, "rb") as f:
                        f.read(1)
                    local_ok = True
                except Exception as e:
                    error_detail = f"文件读取失败 (磁盘可能已掉线): {str(e)}"
                    local_ok = False

                if local_ok:
                    # 2. 检查 URL (如果提供了 URL)
                    if config.file_url and config.file_url.strip():
                        try:
                            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                                # 仅获取头部或前 1KB
                                response = await client.get(config.file_url, headers={"Range": "bytes=0-1024"})
                                if response.status_code in [200, 206]:
                                    status = "OK"
                                else:
                                    error_detail = f"下载源访问失败 (HTTP {response.status_code})，Cookie 可能已失效"
                        except Exception as e:
                            error_detail = f"网络请求异常: {type(e).__name__}"
                    else:
                        # 仅有本地且通过
                        status = "OK"

            if status == "OK":
                log_audit("健康检查", "正常", f"项目 [{config.name}] 检测通过", level="INFO")
            else:
                status = f"Failed ({error_detail})"
                log_audit("健康检查", "异常", f"项目 [{config.name}] 检测到异常: {error_detail}", level="ERROR", details=config.file_path)

        except Exception as e:
            status = f"Failed ({type(e).__name__})"
            log_audit("健康检查", "错误", f"检测逻辑执行崩溃: {str(e)}", level="ERROR")

        config.last_status = status
        config.last_check = datetime.now()
        await db.save(config)

        # 4. 如果检测失败，发送通知
        if status != "OK":
            await NotificationManager.push_health_check_notification(
                config.name, status, config.file_path
            )

@router.post("/check/{config_id}")
async def trigger_health_check(config_id: int, background_tasks: BackgroundTasks, session=Depends(get_session)):
    background_tasks.add_task(run_single_check, config_id)
    return {"status": "triggered"}

@router.post("/check_all")
async def trigger_all_health_checks(background_tasks: BackgroundTasks, session=Depends(get_session)):
    configs = await db.all(HealthCheckConfig, select(HealthCheckConfig).where(HealthCheckConfig.enabled == True))
    for config in configs:
        background_tasks.add_task(run_single_check, config.id)
    return {"status": "triggered_all", "count": len(configs)}
