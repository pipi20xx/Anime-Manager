import asyncio
import os
import logging
import json
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from config_manager import ConfigManager
from monitor import MonitorManager
from logger import init_logging, LogBroadcaster
from metadata.meta_cache import MetaCacheManager
from auth_utils import decode_access_token

logger = logging.getLogger(__name__)

def _get_version():
    paths = [
        "/app/VERSION",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION"),
    ]
    for version_file in paths:
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            continue
    return "unknown"

__version__ = _get_version()

# Import Routers
from routers import (
    recognition, organizer, cache, strm, config, 
    system, clients, rss, subscriptions, tmdb, bangumi, webhook, tmdb_full, explore, priority, calendar, auth, health, user_mapping, task_history
)

app = FastAPI(
    title="番剧管家 (Anime Manager) API",
    description="""
番剧管家后端管理接口。
提供高性能动画识别、全自动整理重命名、RSS 订阅管理以及 PostgreSQL 超级元数据中心。
    """,
    version=__version__,
    docs_url=None,
    redoc_url=None
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 1. Mount API Routers
app.include_router(recognition.router)
app.include_router(organizer.router)
app.include_router(cache.router, prefix="/api/cache")
app.include_router(strm.router)
app.include_router(config.router)
app.include_router(system.router)
app.include_router(tmdb.router)
app.include_router(explore.router)
app.include_router(bangumi.router)
app.include_router(clients.router, prefix="/api")
app.include_router(rss.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")
app.include_router(priority.router, prefix="/api")
app.include_router(calendar.router)
app.include_router(webhook.router)
app.include_router(tmdb_full.router)
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(user_mapping.router)
app.include_router(task_history.router)

# --- API Audit & Security Middleware ---
@app.middleware("http")
async def api_audit_middleware(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api"):
        return await call_next(request)
    
    skip_paths = []
    if any(p in path for p in skip_paths):
        return await call_next(request)

    config = ConfigManager.get_config()
    
    if not config.get("enable_api", True):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"detail": "API access is disabled in settings."})

    expected_api_token = config.get("external_token")
    
    auth_header = request.headers.get("Authorization")
    provided_token = auth_header.replace("Bearer ", "").strip() if auth_header and auth_header.startswith("Bearer ") else None
    if not provided_token:
        provided_token = request.query_params.get("token") or request.query_params.get("apikey")

    is_authenticated = False
    
    if path == "/api/system/login" or path.startswith("/api/webhook") or path.startswith("/api/auth"):
        is_authenticated = True
    
    elif "/api/system/img" in path or "/api/system/bgm_img" in path:
        referer = request.headers.get("referer", "")
        host = request.headers.get("host", "")
        if host and host in referer:
            is_authenticated = True

    elif provided_token:
        payload = decode_access_token(provided_token)
        if payload and payload.get("sub") and payload.get("type") != "2fa_pending":
            from database import db
            from models import User, Session
            from sqlmodel import select
            try:
                jwt_never_expire = config.get("jwt_never_expire", False)
                
                async with db.session_scope() as session:
                    result = await session.execute(select(User).where(User.username == payload.get("sub")))
                    user = result.scalars().first()
                    if user:
                        validated = decode_access_token(provided_token, user.hashed_password)
                        if validated:
                            token_id = payload.get("jti")
                            if token_id:
                                if jwt_never_expire:
                                    session_result = await session.execute(
                                        select(Session).where(
                                            Session.user_id == user.id,
                                            Session.token_id == token_id
                                        )
                                    )
                                else:
                                    session_result = await session.execute(
                                        select(Session).where(
                                            Session.user_id == user.id,
                                            Session.token_id == token_id,
                                            Session.expires_at > datetime.utcnow()
                                        )
                                    )
                                db_session = session_result.scalars().first()
                                if db_session:
                                    db_session.last_activity = datetime.utcnow()
                                    session.add(db_session)
                                    await session.commit()
                                    is_authenticated = True
                                else:
                                    from logger import log_audit
                                    log_audit("AUTH", "会话失效", f"用户: {user.username}, Token ID: {token_id}", level="WARN")
            except:
                pass
        elif expected_api_token and provided_token == expected_api_token:
            is_authenticated = True

    if not is_authenticated:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})

    query_params = dict(request.query_params)
    request_body = None
    
    content_type = request.headers.get("Content-Type", "")
    if "application/json" in content_type and request.method != "GET":
        try:
            body_bytes = await request.body()
            if body_bytes:
                request_body = json.loads(body_bytes)
            
            receive_ = request.receive
            body_sent = False
            async def receive():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {"type": "http.request", "body": body_bytes}
                return await receive_()
            request._receive = receive
        except:
            pass

    response = await call_next(request)

    if config.get("api_logging") is not False:
        from logger import log_audit
        status_code = response.status_code
        level = "INFO" if status_code < 400 else "ERROR"
        
        audit_details = {
            "ip": request.client.host if request.client else "unknown",
            "params": query_params,
        }
        if request_body:
            if isinstance(request_body, dict):
                safe_body = {k: (v if "password" not in k.lower() and "token" not in k.lower() else "******") 
                             for k, v in request_body.items()}
            elif isinstance(request_body, list):
                safe_body = []
                for item in request_body:
                    if isinstance(item, dict):
                        safe_body.append({k: (v if "password" not in k.lower() and "token" not in k.lower() else "******") for k, v in item.items()})
                    else:
                        safe_body.append(item)
            else:
                safe_body = request_body
                
            audit_details["body"] = safe_body

        log_audit(
            module="API", 
            action=request.method, 
            message=f"{request.method} {path} ({status_code})",
            level=level,
            details=json.dumps(audit_details, ensure_ascii=False),
            to_root=(request.method != "GET" or level == "ERROR")
        )
        
    return response

# --- WebSocket for Real-time Logs ---
@app.websocket("/ws/system/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    await LogBroadcaster.register(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        await LogBroadcaster.unregister(websocket)

# 2. Static Files & SPA Routing
DIST_DIR = os.path.join(os.path.dirname(__file__), "dist")

@app.on_event("startup")
async def startup_event():
    import time
    if hasattr(time, 'tzset'):
        time.tzset()
    init_logging()
    
    asyncio.create_task(LogBroadcaster.broadcast_loop())
    
    try:
        from database import init_db
        await init_db()
        logger.info("主数据库已连接并完成初始化。")
    except Exception as e:
        logger.error(f"主数据库初始化失败: {e}")

    await MetaCacheManager.init_db()
    
    try:
        from tmdbmatefull.database import TmdbFullDB
        await TmdbFullDB.init_db()
        logger.info("本地数据中心已就绪。")
    except Exception as e:
        logger.error(f"初始化本地数据中心失败: {e}")

    ConfigManager.init_config()
    
    try:
        from recognition_engine.builtin_group_loader import BuiltinGroupLoader
        BuiltinGroupLoader.load()
    except Exception as e:
        logger.warning(f"加载内置制作组失败: {e}")
    
    from auth_utils import ensure_default_user
    await ensure_default_user()

    from logger import log_audit
    log_audit("系统", "启动", "番剧管家 (Anime Manager) 服务正在启动...")
    
    async def async_init_tasks():
        startup_errors = []
        
        try:
            from clients.cd2_helper import ensure_cd2_module
            await MonitorManager._loop.run_in_executor(None, ensure_cd2_module)
        except Exception as e:
            logger.warning(f"CD2 预热跳过: {e}")
            startup_errors.append(f"CD2 模块预热失败")

        try:
            rules = await ConfigManager.get_cached_rules_async()
            ConfigManager._rule_memory_cache = rules
            logger.info(f"系统规则缓存预热完成 (干扰词: {len(rules['noise'])})")
        except Exception as e:
            logger.error(f"预热规则缓存失败: {e}")
            startup_errors.append(f"规则缓存预热失败")

        try:
            ConfigManager.load_privileged_rules()
        except Exception as e:
            logger.warning(f"加载特权规则失败: {e}")

        MonitorManager.start_all()
        
        log_audit("系统", "启动完成", "所有后台服务已启动。")

        try:
            from notification import NotificationManager
            from clients.cd2_monitor import CD2TransferMonitor
            
            config = ConfigManager.get_config()
            cd2_clients = [c for c in config.get("download_clients", []) if c.get("type") == "cd2"]
            
            cd2_monitor_status = {
                "enabled": len(cd2_clients) > 0,
                "running": CD2TransferMonitor._thread is not None and CD2TransferMonitor._thread.is_alive(),
                "client": cd2_clients[0].get("name", "未命名") if cd2_clients else None
            }
            
            scheduler_jobs = 0
            if MonitorManager._scheduler:
                scheduler_jobs = len(MonitorManager._scheduler.get_jobs())
            
            status_info = {
                "cd2_monitor": cd2_monitor_status,
                "organize_tasks": len(config.get("organize_tasks", [])),
                "strm_tasks": len(config.get("strm_tasks", [])),
                "rss_feeds": len(config.get("rss_feeds", [])),
                "scheduler_jobs": scheduler_jobs,
                "errors": startup_errors
            }
            
            await NotificationManager.push_startup_notification(status_info)
        except Exception as e:
            logger.warning(f"发送启动通知失败: {e}")

    MonitorManager.init(asyncio.get_running_loop())
    asyncio.create_task(async_init_tasks())

    async def warm_up_meta():
        try:
            from recognition.data_provider.bangumi.client import BangumiProvider
            from recognition.data_provider.tmdb.client import TMDBProvider
            from routers.system import get_tmdb_image
            logger.info("[系统] 正在预热元数据发现中心...")
            
            await BangumiProvider.get_calendar()
            
            config = ConfigManager.get_config()
            tmdb_key = config.get("tmdb_api_key")
            if tmdb_key:
                tmdb = TMDBProvider(tmdb_key)
                trending = await tmdb.get_trending()
                
                poster_tasks = []
                results = trending.get("results", [])
                for item in results[:10]:
                    p_path = item.get("poster_path")
                    if p_path and "path=" in p_path:
                        try:
                            from urllib.parse import unquote, urlparse, parse_qs
                            parsed = urlparse(p_path)
                            actual_path = parse_qs(parsed.query).get('path', [None])[0]
                            if actual_path:
                                poster_tasks.append(get_tmdb_image(actual_path))
                        except: pass
                
                if poster_tasks:
                    logger.info(f"[系统] 正在后台预下载 {len(poster_tasks)} 张热点海报...")
                    await asyncio.gather(*poster_tasks, return_exceptions=True)
            
            logger.info("[系统] 元数据发现中心预热完成")
        except Exception as e:
            logger.warning(f"元数据预热异常: {e}")
    
    asyncio.create_task(warm_up_meta())

    log_audit("系统", "启动完成", "所有后台服务已启动。")

@app.on_event("shutdown")
async def shutdown_event():
    from logger import log_audit
    log_audit("系统", "停止", "正在关闭服务...")
    MonitorManager.stop_all()
    log_audit("系统", "停止", "服务已安全关闭。")

if os.path.exists(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="static")

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        if not request.url.path.startswith("/api"):
            return FileResponse(os.path.join(DIST_DIR, "index.html"))
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

if __name__ == "__main__":
    import uvicorn
    ConfigManager.init_config()
    uvicorn.run(app, host="0.0.0.0", port=8000)
