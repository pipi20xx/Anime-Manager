from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import select
from datetime import datetime
from database import get_session, db
from models import HealthCheckConfig
from notification import notification_manager
from logger import log_audit
from clients.manager import ClientManager
import logging
import os
import asyncio
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

def _resolve_cd2_client(file_path: str):
    """
    按 CD2 挂载点前缀匹配 CD2 客户端实例。
    复用 organizer_core 的同款逻辑：mount_path 前缀匹配 > 单实例兜底。
    """
    all_clients = ClientManager.get_all_clients()
    cd2_configs = [c for c in all_clients if c.get('type') == 'cd2']

    for c_conf in cd2_configs:
        m_path = (c_conf.get('mount_path') or '').strip()
        if m_path and file_path and os.path.abspath(file_path).startswith(os.path.abspath(m_path)):
            return ClientManager.get_client(c_conf.get('id'))

    # 单实例兜底
    if len(cd2_configs) == 1:
        return ClientManager.get_client(cd2_configs[0].get('id'))
    return None


def _check_cd2_path(file_path: str, cd2_client) -> tuple:
    """
    用 CD2 gRPC 检查云端文件是否存在。
    file_path 可以是 CD2 内部路径（如 /115open/check.txt）或本地挂载路径。
    返回 (ok: bool, error_detail: str)
    """
    if not cd2_client.logged_in:
        if not cd2_client.login():
            return False, "CD2 登录失败"

    browser = cd2_client._file_browser
    # 判断是否为本地挂载路径：如果以 mount_path 开头则需要转换，否则直接当 CD2 内部路径用
    mount_path = (cd2_client.config or {}).get('mount_path', '').strip()
    if mount_path and os.path.abspath(file_path).startswith(os.path.abspath(mount_path)):
        cloud_path = cd2_client._to_cd2_path(file_path)
    else:
        cloud_path = file_path
    cloud_exists = browser.path_exists(cloud_path, True)
    if not cloud_exists:
        return False, f"CD2 云端文件不存在: {cloud_path}"
    return True, ""


async def run_single_check(config_id: int):
    async with db.session_scope(force_new=True):
        config = await db.get(HealthCheckConfig, config_id)
        if not config or not config.enabled:
            return

        status = "Failed"
        error_detail = ""
        via = config.path_via or "local"
        path_label = f" ({'CD2' if via == 'cd2' else '本地'})"
        log_audit("健康检查", "执行", f"正在检查项目: {config.name}{path_label}", level="DEBUG")

        try:
            # ---- 按路径归属分流检测 ----
            if via == "cd2":
                # ============ CD2 挂载路径检测 ============
                cd2_client = _resolve_cd2_client(config.file_path)
                if not cd2_client:
                    error_detail = "未找到匹配的 CD2 客户端 (挂载点未配置或无 CD2 实例)"
                else:
                    ok, err = await asyncio.to_thread(_check_cd2_path, config.file_path, cd2_client)
                    if ok:
                        # 文件存在，检查 URL（如有）
                        if config.file_url and config.file_url.strip():
                            try:
                                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                                    response = await client.get(config.file_url, headers={"Range": "bytes=0-1024"})
                                    if response.status_code in [200, 206]:
                                        status = "OK"
                                    else:
                                        error_detail = f"下载源访问失败 (HTTP {response.status_code})，Cookie 可能已失效"
                            except Exception as e:
                                error_detail = f"网络请求异常: {type(e).__name__}"
                        else:
                            status = "OK"
                    else:
                        error_detail = err
            else:
                # ============ 本地路径检测 ============
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
                        # 检查 URL (如果提供了 URL)
                        if config.file_url and config.file_url.strip():
                            try:
                                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
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
                log_audit("健康检查", "正常", f"项目 [{config.name}] 检测通过{path_label}", level="INFO")
            else:
                status = f"Failed ({error_detail})"
                log_audit("健康检查", "异常", f"项目 [{config.name}] 检测到异常: {error_detail}{path_label}", level="ERROR", details=config.file_path)

        except Exception as e:
            status = f"Failed ({type(e).__name__})"
            log_audit("健康检查", "错误", f"检测逻辑执行崩溃: {str(e)}", level="ERROR")

        config.last_status = status
        config.last_check = datetime.now()
        await db.save(config)

        # 如果检测失败，发送通知
        if status != "OK":
            await notification_manager.notify_health_check(
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
