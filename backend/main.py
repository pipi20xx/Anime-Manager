import asyncio
import os
import logging
import json
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
    version="2.1.0",
    docs_url=None,   # 禁用默认路径
    redoc_url=None   # 禁用默认路径
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
    # 只针对 /api 开头的请求进行审计
    path = request.url.path
    if not path.startswith("/api"):
        return await call_next(request)
    
    # 豁免列表：排除配置、日志、流式处理及 API 文档等不需要审计或认证的路径
    skip_paths = [
        "/api/config", 
        "/api/system/logs", 
        "/api/system/docs",
        "/api/system/openapi.json",
        "/api/organize/execute", 
        "/api/organize/stream",
        "/api/strm/execute"
    ]
    if any(p in path for p in skip_paths):
        return await call_next(request)

    config = ConfigManager.get_config()
    
    # 1. 安全检查
    if not config.get("enable_api", True):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403, content={"detail": "API access is disabled in settings."})

    # 2. 身份认证校验
    expected_api_token = config.get("external_token")
    web_password = config.get("web_password")
    client_host = request.client.host if request.client else ""
    
    # 获取 Token (支持 Header 和 Query Parameter)
    auth_header = request.headers.get("Authorization")
    provided_token = auth_header.replace("Bearer ", "").strip() if auth_header and auth_header.startswith("Bearer ") else None
    if not provided_token:
        provided_token = request.query_params.get("token") or request.query_params.get("apikey")

    # 认证豁免逻辑
    is_authenticated = False
    
    # 情况 A: 请求来源是服务器本地，直接放行
    if client_host in ["127.0.0.1", "::1", "localhost"]:
        is_authenticated = True
    
    # 情况 B: 访问的是登录接口或 Webhook 接口，放行
    elif path == "/api/system/login" or path.startswith("/api/webhook") or path.startswith("/api/auth/login"):
        is_authenticated = True
        
    # 情况 C: 提供了正确的 Token (Web 密码 或 API Token 或 JWT)
    elif provided_token:
        # 首先尝试解析为 JWT
        payload = decode_access_token(provided_token)
        if payload and payload.get("sub") and payload.get("type") != "2fa_pending":
            is_authenticated = True
        # 兼容旧版本的 Web 密码和 API Token
        elif (web_password and provided_token == web_password) or \
           (expected_api_token and provided_token == expected_api_token):
            is_authenticated = True
            
    # 情况 D: 核心放行逻辑 (解耦 UI 登录与 API 认证)
    if not is_authenticated:
        # 1. 判定是否为“开放模式”：
        # 如果用户主动关闭了【UI登录验证】，则对于 Web 访问默认放行
        ui_auth_enabled = config.get("ui_auth_enabled", bool(web_password))
        
        # 2. 判定是否为“强制 API 认证”：
        # 只有在开启了 api_auth_required 的情况下，才无视所有豁免，必须提供 Token
        api_auth_required = config.get("api_auth_required", False)

        if not api_auth_required:
            # 如果没有开启强制 API 认证，则在以下情况放行：
            # A: 用户关闭了登录验证
            if not ui_auth_enabled:
                is_authenticated = True
            # B: 请求来自本地 (localhost/127.0.0.1)
            elif client_host in ["127.0.0.1", "::1", "localhost"]:
                is_authenticated = True
            # C: 系统既没有设置 Web 密码，也没有开启 UI 验证 (处于未初始化状态)
            elif not web_password and not config.get("ui_auth_enabled"):
                is_authenticated = True

    # 情况 E: 特殊放行 - 图片代理接口
    if not is_authenticated and ("/api/system/img" in path or "/api/system/bgm_img" in path):
        referer = request.headers.get("referer", "")
        host = request.headers.get("host", "")
        if host and host in referer:
            is_authenticated = True

    if not is_authenticated:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})

    # --- 捕获请求参数 ---
    query_params = dict(request.query_params)
    request_body = None
    
    # 仅针对 JSON 请求尝试读取 Body
    content_type = request.headers.get("Content-Type", "")
    if "application/json" in content_type and request.method != "GET":
        try:
            # 这种方式读取后必须重新包装 request，否则后面的路由读不到 body
            body_bytes = await request.body()
            if body_bytes:
                request_body = json.loads(body_bytes)
            
            # 重新包装 request 以供后续路由使用
            # 修正：确保 receive 只在第一次调用时返回 body，后续调用返回原始 receive (处理断开连接等)
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

    # 3. 执行请求
    response = await call_next(request)

    # 4. 记录日志
    if config.get("api_logging") is not False:
        from logger import log_audit
        status_code = response.status_code
        level = "INFO" if status_code < 400 else "ERROR"
        
        # 组装详细信息
        audit_details = {
            "ip": request.client.host if request.client else "unknown",
            "params": query_params,
        }
        if request_body:
            # 脱敏处理：不记录包含 password 或 token 关键字的值
            if isinstance(request_body, dict):
                safe_body = {k: (v if "password" not in k.lower() and "token" not in k.lower() else "******") 
                             for k, v in request_body.items()}
            elif isinstance(request_body, list):
                # 简单处理列表中的字典项
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
            to_root=(request.method != "GET" or level == "ERROR") # GET 请求且成功时不显示在控制台
        )
        
    return response

# --- WebSocket for Real-time Logs ---
@app.websocket("/ws/system/logs")
async def websocket_logs(websocket: WebSocket):
    await websocket.accept()
    await LogBroadcaster.register(websocket)
    try:
        while True:
            # Keep connection open, wait for client close
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        await LogBroadcaster.unregister(websocket)

# 2. Static Files & SPA Routing
# 假设前端编译后的文件放在 backend/dist 目录下
DIST_DIR = os.path.join(os.path.dirname(__file__), "dist")

@app.on_event("startup")
async def startup_event():
    import time
    if hasattr(time, 'tzset'):
        time.tzset()
    init_logging()
    
    # Start Log Broadcast Loop
    asyncio.create_task(LogBroadcaster.broadcast_loop())
    
    # 1. 初始化主数据库 (创建表、执行自动迁移)
    try:
        from database import init_db
        await init_db()
        logger.info("主数据库已连接并完成初始化。")
    except Exception as e:
        logger.error(f"主数据库初始化失败: {e}")

    await MetaCacheManager.init_db()
    
    # 2. 初始化离线满血数据库
    try:
        from tmdbmatefull.database import TmdbFullDB
        await TmdbFullDB.init_db()
        logger.info("本地数据中心已就绪。")
    except Exception as e:
        logger.error(f"初始化本地数据中心失败: {e}")

    ConfigManager.init_config()
    
    # [NEW] 自动初始化默认用户
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

    # [NEW] 预热元数据缓存 (日历/热门)
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

# 静态文件挂载逻辑需放在 API 路由之后，以防冲突
if os.path.exists(DIST_DIR):
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="static")

    # 处理 SPA 路由回退：如果路径不是 API 且文件不存在，返回 index.html
    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        if not request.url.path.startswith("/api"):
            return FileResponse(os.path.join(DIST_DIR, "index.html"))
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

if __name__ == "__main__":
    import uvicorn
    ConfigManager.init_config()
    uvicorn.run(app, host="0.0.0.0", port=8000)
