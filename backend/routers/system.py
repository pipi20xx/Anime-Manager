from fastapi import APIRouter, Query, HTTPException, Body, Response, Request
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from typing import Optional, List, Any, Dict
from metadata.meta_cache import MetaCacheManager
from config_manager import ConfigManager
from monitor import MonitorManager
import os
import asyncio
import re
import httpx
import datetime
from database import db
from sqlmodel import text

from logger import log_audit
from notification import NotificationManager
from rss_core.scheduler import check_stalled_downloads

router = APIRouter(prefix="/api/system", tags=["系统管理"])

@router.get("/services", summary="获取后台服务状态")
async def get_services_status():
    """
    获取所有后台服务和监控任务的运行状态。
    包括：RSS刷新、规则同步、订阅补全、健康检查、CD2监控、文件监控任务等。
    """
    try:
        status = MonitorManager.get_services_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取服务状态失败: {str(e)}")

@router.get("/docs", include_in_schema=False)
async def get_documentation(request: Request, theme: str = "cyan", token: str = None):
    referer = request.headers.get("referer")
    host = request.headers.get("host")
    
    # 安全校验：建议从系统内部加载
    if not referer or host not in referer:
         # 允许直接访问以便调试，但在生产环境建议开启
         # raise HTTPException(status_code=403, detail="禁止直接访问 API 文档。请通过系统仪表盘进入。")
         pass
    
    # 根据主题定义配色 (默认青蓝色)
    primary_color = "#2080f0" if theme == "cyan" else "#705df2"
    bg_color = "#101014"
    card_bg = "#18181c"
    text_color = "#e0e0e0"

    # 自动授权脚本
    auth_js = ""
    if token:
        auth_js = f"""
        setTimeout(function() {{
            if (window.ui) {{
                window.ui.authActions.authorize({{
                    "BearerAuth": {{
                        name: "BearerAuth",
                        schema: {{
                            type: "http",
                            scheme: "bearer",
                            bearerFormat: "JWT"
                        }},
                        value: "{token}"
                    }}
                }});
                console.log("番剧管家：API Token 已自动注入");
            }}
        }}, 1000);
        """

    custom_css = f"""
    /* 基础背景与文字 */
    body {{ background-color: {bg_color} !important; margin: 0; padding: 0; }}
    .swagger-ui {{ background-color: {bg_color} !important; color: {text_color} !important; }}
    
    /* 滚动条美化 */
    ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: rgba(255, 255, 255, 0.1); border-radius: 10px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: {primary_color}; }}
    
    .swagger-ui .topbar {{ display: none; }}
    .swagger-ui .info .title, .swagger-ui .info li, .swagger-ui .info p, .swagger-ui .info table, .swagger-ui .info h1, .swagger-ui .info h2, .swagger-ui .info h3 {{ color: {text_color} !important; }}
    
    /* 接口区块与标签 */
    .swagger-ui .opblock-tag {{ color: {text_color} !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important; }}
    .swagger-ui .opblock-tag:hover {{ background: rgba(255,255,255,0.05) !important; }}
    .swagger-ui .opblock {{ background: {card_bg} !important; border: 1px solid rgba(255,255,255,0.05) !important; box-shadow: none !important; }}
    .swagger-ui .opblock .opblock-summary-path {{ color: {text_color} !important; font-family: 'JetBrains Mono', monospace; }}
    .swagger-ui .opblock .opblock-summary-description {{ color: rgba(255,255,255,0.6) !important; }}
    
    /* 参数与请求配置区 */
    .swagger-ui .scheme-container {{ background: {card_bg} !important; box-shadow: none !important; border-top: 1px solid rgba(255,255,255,0.05) !important; }}
    .swagger-ui select {{ background: {bg_color} !important; color: {text_color} !important; border-color: rgba(255,255,255,0.2) !important; }}
    .swagger-ui input {{ background: {card_bg} !important; color: {text_color} !important; border: 1px solid rgba(255,255,255,0.1) !important; }}
    .swagger-ui .btn {{ color: {text_color} !important; border-color: rgba(255,255,255,0.2) !important; background: transparent !important; }}
    .swagger-ui .btn.execute {{ background-color: {primary_color} !important; border-color: {primary_color} !important; color: #fff !important; font-weight: bold !important; }}
    
    /* 模型 (Models / Schemas) 区块 */
    .swagger-ui .models {{ background: {card_bg} !important; border: 1px solid rgba(255,255,255,0.05) !important; margin: 20px !important; border-radius: 8px !important; }}
    .swagger-ui .models .model-container {{ background: transparent !important; margin: 0 !important; padding: 10px !important; }}
    .swagger-ui .models h4 {{ color: {text_color} !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important; padding-bottom: 10px !important; }}
    .swagger-ui .model-box {{ background: transparent !important; color: {text_color} !important; }}
    .swagger-ui .model-box-control {{ background: transparent !important; color: {text_color} !important; border: none !important; }}
    .swagger-ui .model-box-control:focus {{ outline: none !important; }}
    .swagger-ui .model-wrapper {{ background: transparent !important; }}
    .swagger-ui .model {{ color: {text_color} !important; background: transparent !important; }}
    .swagger-ui .model-title {{ color: {text_color} !important; }}
    .swagger-ui .prop-type {{ color: {primary_color} !important; }}
    .swagger-ui .prop-format {{ color: rgba(255,255,255,0.4) !important; }}
    .swagger-ui .prop-name {{ color: {text_color} !important; font-weight: bold !important; }}
    
    /* 核心修复：Schemas 内部嵌套表格和列表的白底 */
    .swagger-ui section.models .model-container {{ background-color: transparent !important; }}
    .swagger-ui section.models .model-box {{ background-color: rgba(255,255,255,0.02) !important; }}
    .swagger-ui .model-toggle:after {{ filter: invert(1) brightness(2); }}

    /* 适配新版 JSON Schema 2020-12 渲染器 (彻底修复白底) */
    .json-schema-2020-12-accordion {{ background: transparent !important; border: none !important; color: {text_color} !important; }}
    .json-schema-2020-12-accordion__children {{ color: {text_color} !important; }}
    .json-schema-2020-12__title {{ color: {text_color} !important; font-weight: bold !important; }}
    .json-schema-2020-12-accordion__icon svg {{ fill: {text_color} !important; }}
    .json-schema-2020-12-accordion:hover {{ background: rgba(255,255,255,0.05) !important; }}
    .json-schema-2020-12-expand-deep-button {{ 
      color: {primary_color} !important; 
      background: transparent !important; 
      border: 1px solid {primary_color} !important; 
      border-radius: 4px !important;
      padding: 2px 8px !important;
      font-size: 12px !important;
    }}
    
    /* 响应与表格 */
    .swagger-ui table thead tr td, .swagger-ui table thead tr th {{ color: {text_color} !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important; }}
    .swagger-ui .response-col_status {{ color: {text_color} !important; }}
    .swagger-ui section.models h4 {{ color: {text_color} !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important; }}
    .swagger-ui .parameter__name, .swagger-ui .parameter__type, .swagger-ui .parameter__deprecated, .swagger-ui .parameter__in {{ color: {text_color} !important; font-family: monospace !important; }}
    .swagger-ui .parameter__extension, .swagger-ui .parameter__in {{ font-style: italic !important; color: rgba(255,255,255,0.5) !important; }}
    
    /* Parameters 专属修复 */
    .swagger-ui .opblock-section-header {{ background: rgba(255,255,255,0.05) !important; border-top: 1px solid rgba(255,255,255,0.1) !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important; }}
    .swagger-ui .opblock-section-header h4 {{ color: {text_color} !important; }}
    .swagger-ui .parameters-container, .swagger-ui .responses-container {{ background: transparent !important; }}
    .swagger-ui table.parameters, .swagger-ui table.responses-table {{ background: transparent !important; }}
    .swagger-ui .parameter__name {{ color: {primary_color} !important; font-weight: bold !important; }}
    .swagger-ui .parameter__type {{ color: #f2a3ff !important; }}
    
    /* Markdown 描述 */
    .swagger-ui .renderedMarkdown p, .swagger-ui .renderedMarkdown li {{ color: rgba(255,255,255,0.8) !important; }}
    
    /* 修复白底嵌套 */
    .swagger-ui .opblock-body pre {{ background: #111 !important; color: #70ff70 !important; border: 1px solid rgba(255,255,255,0.1) !important; }}

    /* 接口行右侧图标 (锁与箭头) 适配 */
    .swagger-ui .authorization__btn svg {{ fill: {primary_color} !important; }}
    .swagger-ui .opblock-summary-control svg {{ fill: {text_color} !important; opacity: 0.7; }}
    .swagger-ui .opblock-summary-control:hover svg {{ opacity: 1; }}
    .swagger-ui .view-line-link.copy-to-clipboard svg {{ fill: {text_color} !important; }}

    /* 强制调整弹窗位置：使其紧贴顶部工具栏，模仿下拉效果 */
    .swagger-ui .scheme-container {{ position: relative !important; }}
    .swagger-ui .dialog-ux {{ 
      position: absolute !important; 
      top: 100% !important; 
      left: 50% !important; 
      transform: translateX(-50%) !important; 
      z-index: 9999 !important;
      width: 600px !important;
    }}
    .swagger-ui .modal-ux-mask {{ 
      position: absolute !important; 
      top: 0 !important; 
      left: 0 !important; 
      width: 100% !important; 
      height: 10000px !important; 
      z-index: 9998 !important; 
      background: rgba(0, 0, 0, 0.1) !important; 
    }}
    .swagger-ui .modal-ux {{ 
      background-color: {card_bg} !important; 
      border: 1px solid rgba(255,255,255,0.1) !important;
      border-radius: 8px !important;
      max-height: 700px !important; 
      overflow-y: auto !important; 
      box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
    }}
    .swagger-ui .modal-ux-header {{ 
      border-bottom: 1px solid rgba(255,255,255,0.1) !important; 
      padding: 10px 15px !important;
    }}
    .swagger-ui .modal-ux-header h3 {{ color: {text_color} !important; font-size: 16px !important; }}
    .swagger-ui .modal-ux-content {{ 
      background-color: {bg_color} !important; 
      padding: 15px !important; 
    }}
    .swagger-ui .modal-ux-content h4 {{ color: {text_color} !important; font-size: 14px !important; }}
    .swagger-ui .auth-container {{ 
      color: {text_color} !important; 
      padding: 10px 0 !important;
      border-bottom: 1px solid rgba(255,255,255,0.05) !important; 
    }}
    .swagger-ui .auth-container:last-of-type {{ border-bottom: none !important; }}
    .swagger-ui .auth-container label {{ color: {text_color} !important; margin-bottom: 5px !important; }}
    .swagger-ui .auth-btn-wrapper {{ justify-content: center !important; gap: 10px !important; padding-top: 15px !important; }}
    .swagger-ui .modal-ux-content p {{ color: rgba(255,255,255,0.5) !important; font-size: 12px !important; }}

    /* 按钮美化 */
    .swagger-ui .btn.modal-btn {{ border-radius: 4px !important; padding: 6px 16px !important; }}
    """
    
    from fastapi.openapi.docs import get_swagger_ui_html
    response = get_swagger_ui_html(
        openapi_url="/api/system/openapi.json", 
        title="番剧管家 API 文档",
        swagger_js_url="https://cdn.staticfile.net/swagger-ui/5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.staticfile.net/swagger-ui/5.9.0/swagger-ui.css",
    )
    
    # 手动注入自定义 CSS 和 JS
    html_content = response.body.decode("utf-8")
    custom_injection = f"<style>{custom_css}</style><script>{auth_js}</script>"
    new_content = html_content.replace("</head>", f"{custom_injection}</head>")
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=new_content)

@router.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(request: Request):
    referer = request.headers.get("referer")
    host = request.headers.get("host")
    if not referer or host not in referer:
         # raise HTTPException(status_code=403, detail="Forbidden")
         pass
         
    from fastapi.openapi.utils import get_openapi
    
    # 获取原始 schema
    schema = get_openapi(title=request.app.title, version=request.app.version, routes=request.app.routes)
    
    # 1. 注入全局安全定义
    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }
    
    # 2. 强制统一所有接口的安全要求
    if "paths" in schema:
        for path in schema["paths"].values():
            for operation in path.values():
                operation["security"] = [{"BearerAuth": []}]
                
    # 3. 设置全局默认安全校验
    schema["security"] = [{"BearerAuth": []}]
    
    return schema

@router.post("/stalled_check", summary="手动触发死种超时清理")
async def trigger_stalled_check():
    """立即执行一次下载器死种巡检"""
    try:
        # 直接等待执行完成，并返回结果
        await check_stalled_downloads()
        return {"status": "success", "message": "已完成下载器死种超时清理巡检"}
    except Exception as e:
        raise HTTPException(500, detail=str(e))

@router.get("/img", summary="TMDB 图片本地代理")
async def get_tmdb_image(path: str = Query(..., description="TMDB 图片路径 (例如 /abc.jpg)")):
    """
    代理下载 TMDB 图片，并缓存至本地 data/tmp/tmdbimg。
    """
    # 鲁棒性处理：防止套娃 (Nested Proxy Calls)
    # 如果 path 已经是一个完整的代理 URL 或包含 Bangumi 域名，说明传参错了
    if "/api/system/" in path or "http" in path or "lain.bgm.tv" in path:
        # 如果是套娃请求，尝试提取最深层的原始路径，或者干脆报错防止文件系统混乱
        if "path=" in path:
             path = path.split("path=")[-1]
        elif "url=" in path:
             # 如果误传了 BGM 的代理链接进来，直接报错拒绝，以免在 tmdbimg 目录下创建乱七八糟的文件夹
             raise HTTPException(status_code=400, detail="Invalid TMDB path (BGM link detected)")
        else:
             # 这种可能是非法的或者格式错误的路径
             raise HTTPException(status_code=400, detail=f"Invalid TMDB path format: {path}")

    # 清洗路径：去掉可能存在的尺寸前缀
    clean_path = path
    size_match = re.match(r"^/(w\d+|original)(/.*)$", path)
    if size_match:
        clean_path = size_match.group(2)
    
    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path
    
    # 防止路径穿越
    if ".." in clean_path:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    # 定义本地存储路径
    cache_dir = "data/tmp/tmdbimg"
    local_file = os.path.join(cache_dir, clean_path.lstrip("/"))
    
    # 1. 命中缓存直接返回
    if os.path.exists(local_file):
        return FileResponse(local_file)
    
    # 2. 未命中缓存，从 TMDB 下载原图
    os.makedirs(os.path.dirname(local_file), exist_ok=True)
    tmdb_url = f"https://image.tmdb.org/t/p/original{clean_path}"
    
    proxy = ConfigManager.get_proxy("tmdb")
    
    async with httpx.AsyncClient(timeout=30, proxy=proxy) as client:
        try:
            resp = await client.get(tmdb_url)
            if resp.status_code == 200:
                with open(local_file, "wb") as f:
                    f.write(resp.content)
                return Response(content=resp.content, media_type="image/jpeg")
            else:
                # 记录错误但不崩溃
                print(f"[IMG PROXY ERROR] Failed to download {tmdb_url}: {resp.status_code}")
                raise HTTPException(status_code=404, detail="TMDB 图片未找到")
        except Exception as e:
            print(f"[IMG PROXY ERROR] Exception: {str(e)}")
            raise HTTPException(status_code=500, detail=f"图片代理错误: {str(e)}")

@router.get("/bgm_img", summary="Bangumi 图片本地代理")
async def get_bgm_image(url: str = Query(..., description="Bangumi 图片完整 URL")):
    """
    代理下载 Bangumi 图片，并缓存至本地 data/tmp/bgmimg。
    """
    if not url:
        return Response(status_code=400)
    
    # 生成本地文件名
    import hashlib
    url_hash = hashlib.md5(url.encode()).hexdigest()
    ext = ".jpg"
    for e in [".png", ".gif", ".webp"]:
        if e in url.lower():
            ext = e
            break
    
    cache_dir = "data/tmp/bgmimg"
    local_file = os.path.join(cache_dir, f"{url_hash}{ext}")
    
    # 1. 命中缓存直接返回
    if os.path.exists(local_file):
        return FileResponse(local_file)
    
    # 2. 未命中缓存，尝试下载 (带重试机制)
    os.makedirs(cache_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    proxy = ConfigManager.get_proxy("bangumi")
    
    # 透明 1x1 像素 GIF 占位符，用于失败回退
    TRANSPARENT_GIF = b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b"

    async with httpx.AsyncClient(timeout=10, proxy=proxy, follow_redirects=True) as client:
        for attempt in range(3):
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    with open(local_file, "wb") as f:
                        f.write(resp.content)
                    return Response(content=resp.content, media_type=resp.headers.get("content-type", "image/jpeg"))
                elif resp.status_code == 404:
                    break # 没必要重试
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
                if attempt == 2:
                    print(f"[BGM IMG] 最终同步失败: {url} | 原因: {str(e)}")
                await asyncio.sleep(1) # 等待 1 秒重试
            except Exception as e:
                print(f"[BGM IMG] 未知异常: {str(e)}")
                break

    # 如果所有尝试都失败，返回透明占位图，避免 500 错误
    return Response(content=TRANSPARENT_GIF, media_type="image/gif")

@router.post("/telegram/test", summary="测试 Telegram 通知")
async def test_telegram_notification():
    """
    发送一条测试消息到配置的 Telegram 机器人。
    """
    msg = "<b>🔔 测试通知</b>\n\n您的 Telegram 机器人配置成功！"
    success, error = await NotificationManager.send_telegram_message(msg)
    if success:
        return {"status": "success", "message": "测试消息已发送"}
    else:
        raise HTTPException(status_code=400, detail=f"发送失败: {error}")

@router.get("/db/tables", summary="列出数据库表")
async def get_db_tables():
    """
    获取当前 PostgreSQL 数据库中所有的表名及行数。
    """
    try:
        async with db.session_scope():
            # 针对 PostgreSQL 优化：获取 public 和 metadata 下的真实用户表
            sql = """
                SELECT n.nspname || '.' || c.relname as full_name
                FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname IN ('public', 'metadata')
                AND c.relkind = 'r'
                AND c.relname NOT LIKE 'pg_%'
                AND c.relname NOT LIKE 'sql_%';
            """
            tables_res = await db.execute(text(sql))
            tables = [r[0] for r in tables_res.all()]
            
            result = []
            for t in tables:
                try:
                    # 统计行数，使用双引号包裹 schema.table
                    safe_table_name = f'"{t.split(".")[0]}"."{t.split(".")[1]}"'
                    count_res = await db.execute(text(f"SELECT COUNT(*) FROM {safe_table_name}"))
                    count = count_res.scalar()
                    result.append({"name": t, "count": count})
                except Exception as e:
                    print(f"统计表 {t} 失败: {e}")
                    continue
            return {"status": "success", "tables": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库查询失败: {e}")

@router.post("/db/query", summary="执行 SQL 查询")
async def query_db(payload: Dict[str, str] = Body(...)):
    """
    执行自定义 SELECT 语句，仅用于管理界面查看数据。禁止修改操作。
    """
    sql = payload.get("sql", "").strip()
    if not sql:
        raise HTTPException(400, "SQL 语句不能为空")
        
    # 安全检查：只允许 SELECT
    if not re.match(r"^\s*SELECT", sql, re.IGNORECASE):
        raise HTTPException(403, "仅允许执行 SELECT 查询语句")
        
    # 禁止明显的高危操作（放宽对 . 的限制以支持 schema）
    if re.search(r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE)", sql, re.IGNORECASE):
        raise HTTPException(403, "检测到潜在的危险操作，已拦截")

    try:
        async with db.session_scope():
            result = await db.execute(text(sql))
            
            # 统一结果解析逻辑
            if result.returns_rows:
                keys = list(result.keys())
                rows = []
                for row in result.all():
                    # 处理 Row 对象转字典，确保兼容不同数据库驱动
                    row_dict = {}
                    for i, key in enumerate(keys):
                        val = row[i]
                        # 转换非 JSON 兼容对象
                        if isinstance(val, (datetime.datetime, datetime.date)):
                            val = val.isoformat()
                        row_dict[key] = val
                    rows.append(row_dict)
                return {"status": "success", "data": rows, "columns": keys}
            else:
                return {"status": "success", "data": [], "columns": [], "message": "执行成功，无返回行"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/db/table_info/{table_name}", summary="获取表结构信息")
async def get_table_info(table_name: str):
    """
    获取指定表的列信息。
    """
    try:
        async with db.session_scope():
             # PostgreSQL 获取主键 (标准方式)
             schema = 'public'
             t_name = table_name
             if '.' in table_name:
                 schema, t_name = table_name.split('.', 1)
             
             sql = """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_name = :t_name
                AND tc.table_schema = :schema;
             """
             res = await db.execute(text(sql).bindparams(t_name=t_name, schema=schema))
             pk = res.scalar()
             return {"status": "success", "pk": pk}
    except Exception as e:
        raise HTTPException(500, f"获取表信息失败: {e}")

@router.post("/db/delete_row", summary="删除数据库行")
async def delete_db_row(payload: Dict[str, Any] = Body(...)):
    """
    根据主键删除指定表中的单行数据。
    """
    table = payload.get("table")
    pk_col = payload.get("pk_col")
    pk_val = payload.get("pk_val")
    
    if not all([table, pk_col, pk_val is not None]):
        raise HTTPException(400, "缺少必要参数")

    # 基本校验防止注入：允许字母、数字、下划线和点号
    if not re.match(r"^[a-zA-Z0-9_\.]+$", table) or not re.match(r"^[a-zA-Z0-9_]+$", pk_col):
         raise HTTPException(400, f"无效的标识符: table={table}, pk_col={pk_col}")

    # 处理表名：如果是 schema.table 格式，需要分别用双引号包裹
    if "." in table:
        s, t = table.split(".", 1)
        safe_table = f'"{s}"."{t}"'
    else:
        safe_table = f'"{table}"'

    sql = f"DELETE FROM {safe_table} WHERE {pk_col} = :pk_val"
    
    try:
        async with db.session_scope() as session:
            # 使用 bindparams 安全传参
            await session.execute(text(sql).bindparams(pk_val=pk_val))
            await session.commit()
            log_audit("系统", "删除数据", f"手动删除数据: {table} (PK: {pk_val})", level="WARN")
            return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/db/truncate", summary="清空数据库表")
async def truncate_db_table(payload: Dict[str, Any] = Body(...)):
    """
    清空指定的数据库表。出于安全考虑，仅允许清理特定的业务表。
    """
    table = payload.get("table")
    if not table:
        raise HTTPException(400, "未指定表名")

    # 安全检查：仅允许清理 public 或 metadata schema 下的表
    is_safe = table.startswith("public.") or table.startswith("metadata.")
    
    if not is_safe:
        raise HTTPException(403, f"禁止操作系统级或受保护的表: {table}")

    # 处理表名转义
    if "." in table:
        s, t = table.split(".", 1)
        safe_table = f'"{s}"."{t}"'
    else:
        safe_table = f'"{table}"'

    try:
        async with db.session_scope() as session:
            # PostgreSQL TRUNCATE 比 DELETE 更快
            await session.execute(text(f"TRUNCATE TABLE {safe_table} RESTART IDENTITY"))
            await session.commit()
            log_audit("系统", "维护", f"执行表清空: {table}", level="WARN")
            return {"status": "success", "message": f"表 {table} 已清空"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/db/update_cell", summary="更新数据库单元格")
async def update_db_cell(payload: Dict[str, Any] = Body(...)):
    """
    更新指定行和列的单个值。
    """
    table = payload.get("table")
    pk_col = payload.get("pk_col")
    pk_val = payload.get("pk_val")
    col = payload.get("col")
    val = payload.get("val")

    # 允许 val 为空字符串或 None (视为 NULL)
    if not all([table, pk_col, col, pk_val is not None]):
        raise HTTPException(400, "缺少必要参数")

    # 标识符安全校验：允许 table 包含点号
    if not re.match(r"^[a-zA-Z0-9_\.]+$", table) or not all(re.match(r"^[a-zA-Z0-9_]+$", s) for s in [pk_col, col]):
         raise HTTPException(400, "无效的标识符")

    # 处理表名
    if "." in table:
        s, t = table.split(".", 1)
        safe_table = f'"{s}"."{t}"'
    else:
        safe_table = f'"{table}"'

    sql = f"UPDATE {safe_table} SET {col} = :val WHERE {pk_col} = :pk_val"

    try:
        async with db.session_scope() as session:
            await session.execute(text(sql).bindparams(val=val, pk_val=pk_val))
            await session.commit()
            log_audit("系统", "修改数据", f"手动修改数据: {table}.{col} = {val} (PK: {pk_val})", level="WARN")
            return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/db/test_connect", summary="测试数据库连接")
async def test_db_connect(payload: Dict[str, Any] = Body(...)):
    """
    测试给定的数据库连接参数是否有效。
    """
    user = payload.get("user")
    password = payload.get("password")
    host = payload.get("host")
    port = payload.get("port")
    database = payload.get("database")
    
    url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    from sqlalchemy.ext.asyncio import create_async_engine
    test_engine = create_async_engine(url)
    try:
        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "success", "message": "连接成功！"}
    except Exception as e:
        return {"status": "error", "message": f"连接失败: {str(e)}"}
    finally:
        await test_engine.dispose()

@router.post("/db/save_connect", summary="保存数据库配置并应用")
async def save_db_connect(payload: Dict[str, Any] = Body(...)):
    """
    更新数据库配置，并尝试重新初始化数据库引擎。
    """
    try:
        # 1. 更新配置
        current_config = ConfigManager.get_config()
        if "database" not in current_config:
            current_config["database"] = {}
        
        current_config["database"].update(payload)
        ConfigManager.update_config(current_config)
        
        # 2. 重新初始化主引擎
        from database import init_engine, init_db
        init_engine()
        await init_db()
        
        # 3. 重新初始化数据中心引擎 (如果存在)
        try:
            from tmdbmatefull.database import TmdbFullDB
            await TmdbFullDB.init_db()
        except Exception as e:
            log_audit("系统", "错误", f"重新初始化数据中心失败: {e}", level="ERROR")
            
        log_audit("系统", "数据库", f"数据库配置已更新并重新连接 ({payload.get('type')})")
        return {"status": "success", "message": "配置已保存，数据库已重新连接"}
    except Exception as e:
        log_audit("系统", "错误", f"保存数据库配置失败: {e}", level="ERROR")
        return {"status": "error", "message": str(e)}

@router.get("/logs/stream", summary="流式获取日志 (SSE)")
async def stream_logs():
    """
    通过 Server-Sent Events (SSE) 持续推送 monitor.log 文件的新内容。
    """
    log_path = "data/monitor.log"
    
    async def log_generator():
        if not os.path.exists(log_path):
            yield "data: [SYSTEM] 等待日志文件...\n\n"
            while not os.path.exists(log_path):
                await asyncio.sleep(2)
        
        # Start by sending the last 20 lines for context
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-20:]:
                    yield f"data: {line.strip()}\n\n"
        except Exception:
            pass

        last_ino = os.stat(log_path).st_ino
        f = open(log_path, "r", encoding="utf-8")
        f.seek(0, os.SEEK_END)

        try:
            while True:
                line = f.readline()
                if not line:
                    # Check if file was rotated
                    if os.path.exists(log_path):
                        curr_ino = os.stat(log_path).st_ino
                        if curr_ino != last_ino:
                            f.close()
                            f = open(log_path, "r", encoding="utf-8")
                            last_ino = curr_ino
                            yield "data: [SYSTEM] 日志文件已轮转.\n\n"
                    
                    await asyncio.sleep(0.5)
                    continue
                
                if line.strip():
                    yield f"data: {line.strip()}\n\n"
        except asyncio.CancelledError:
            f.close()
            raise
        except Exception as e:
            yield f"data: [ERROR] 日志流错误: {str(e)}\n\n"
        finally:
            f.close()

    return StreamingResponse(log_generator(), media_type="text/event-stream")

def reverse_line_generator(file_path: str, buffer_size: int = 65536):
    """
    高效从后往前读取文件的行。
    适用于大文件的倒序流式传输。
    """
    if not os.path.exists(file_path):
        return
        
    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        pointer = file_size
        buffer = b""
        
        while pointer > 0:
            read_size = min(pointer, buffer_size)
            pointer -= read_size
            f.seek(pointer)
            chunk = f.read(read_size)
            
            # 将新读入的块拼接到缓冲区前端
            buffer = chunk + buffer
            
            # 分割行
            lines = buffer.split(b"\n")
            
            # lines[0] 可能是跨块的残缺行，保留到下一次循环
            # 从最后一个（最新的）开始 yield
            for i in range(len(lines) - 1, 0, -1):
                yield lines[i].decode("utf-8", "replace") + "\n"
            
            buffer = lines[0]
            
        # yield 最后剩下的第一行
        if buffer:
            yield buffer.decode("utf-8", "replace") + "\n"

@router.get("/logs/raw", summary="查看原始日志文本")
async def get_raw_log(
    type: str = "monitor", 
    download: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(1000, ge=1)
):
    """
    在浏览器中查看或下载原始日志文本。
    - 查看模式：仅返回最近的分页日志，倒序排列。
    - 导出模式 (download=True)：返回完整的原始文件 (倒序排列)。
    """
    log_path = "data/monitor.log" if type == "monitor" else "data/audit.log"

    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="日志文件未找到")

    if download:
        return StreamingResponse(
            reverse_line_generator(log_path),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"inline; filename={os.path.basename(log_path)}"}
        )

    try:
        from itertools import islice
        gen = reverse_line_generator(log_path)
        start = (page - 1) * limit
        end = start + limit
        selected_lines = list(islice(gen, start, end))
        
        if not selected_lines and page > 1:
            return Response(content="--- [结束] 已无更多历史日志 ---", media_type="text/plain; charset=utf-8")
            
        content = "".join(selected_lines)
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志失败: {str(e)}")

@router.get("/logs/dates", summary="获取日志日期列表")
async def get_log_dates():
    """
    返回 data/logs 目录下所有可用的日志日期。
    """
    log_dir = "data/logs"
    if not os.path.exists(log_dir):
        return []
    
    files = os.listdir(log_dir)
    # 过滤出 YYYY-MM-DD.log 格式的文件
    dates = []
    for f in files:
        if f.endswith(".log") and len(f) == 14: # 2023-10-27.log
            dates.append(f.replace(".log", ""))
    
    dates.sort(reverse=True) # 最近的排在前面
    return dates

@router.get("/logs/date/{date_str}", summary="获取特定日期的完整日志")
async def get_log_by_date(
    date_str: str, 
    download: bool = False,
    page: int = Query(1, ge=1),
    limit: int = Query(1000, ge=1)
):
    """
    读取并返回指定日期的完整日志内容。
    - 查看模式：支持分页，倒序排列。
    - 下载模式：返回完整的原始文件 (倒序排列)。
    """
    # 简单校验格式防止路径穿越
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        raise HTTPException(400, "无效的日期格式")
        
    path = os.path.join("data/logs", f"{date_str}.log")
    if not os.path.exists(path):
        raise HTTPException(404, "该日期的日志文件不存在")
        
    if download:
        return StreamingResponse(
            reverse_line_generator(path),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"inline; filename={date_str}.log"}
        )

    try:
        from itertools import islice
        gen = reverse_line_generator(path)
        start = (page - 1) * limit
        end = start + limit
        selected_lines = list(islice(gen, start, end))
        
        if not selected_lines and page > 1:
            return Response(content="--- [结束] 已无更多历史日志 ---", media_type="text/plain; charset=utf-8")
            
        content = "".join(selected_lines)
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except Exception as e:
        raise HTTPException(500, f"读取日志失败: {str(e)}")

@router.get("/logs/export", summary="导出日志文件")
async def export_log_file(type: str = "monitor"):
    """
    流式下载日志文件。采用倒序（最新在前）以对齐查看体验。
    """
    log_path = "data/monitor.log" if type == "monitor" else "data/audit.log"
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="日志文件未找到")
    
    return StreamingResponse(
        reverse_line_generator(log_path),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(log_path)}"}
    )

@router.post("/login", summary="管理员登录")
async def admin_login(payload: Dict[str, str] = Body(...)):
    """
    校验 Web 管理密码。
    """
    password = payload.get("password")
    config = ConfigManager.get_config()
    saved_password = config.get("web_password", "")
    
    # 如果没设密码，直接允许登录
    if not saved_password:
        return {"status": "success", "token": "no-password-set"}
        
    if password == saved_password:
        # 这里为了简单直接返回密码作为 token，实际项目中建议生成 JWT
        return {"status": "success", "token": password}
    else:
        raise HTTPException(status_code=401, detail="密码错误")

@router.get("/logs", summary="分页查询系统日志")
async def get_system_logs(
    module: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    从数据库分页获取审计日志，支持按模块和级别过滤。
    """
    from models import SystemLog
    from sqlalchemy import select
    
    async with db.session_scope():
        stmt = select(SystemLog)
        if module:
            stmt = stmt.where(SystemLog.module == module)
        if level:
            stmt = stmt.where(SystemLog.level == level.upper())
            
        stmt = stmt.order_by(SystemLog.timestamp.desc()).offset(offset).limit(limit)
        return await db.all(SystemLog, stmt)

_version_cache = {
    "version": None,
    "timestamp": None,
    "cache_duration": 7200  # 2小时缓存
}

@router.get("/version/check", summary="检查版本更新")
async def check_version():
    """
    检查Docker Hub上的最新版本号。
    使用2小时缓存机制，避免频繁请求Docker Hub API。
    """
    import time
    from main import __version__
    
    current_time = time.time()
    
    if _version_cache["version"] and _version_cache["timestamp"]:
        cache_age = current_time - _version_cache["timestamp"]
        if cache_age < _version_cache["cache_duration"]:
            latest = _version_cache["version"]
            if latest and latest != __version__:
                log_audit("系统", "版本检查", f"发现新版本: {latest} (当前: {__version__})", level="INFO")
            return {
                "current_version": __version__,
                "latest_version": _version_cache["version"],
                "cached": True,
                "cache_age_seconds": int(cache_age)
            }
    
    try:
        proxy = ConfigManager.get_proxy("docker_hub")
        async with httpx.AsyncClient(timeout=10, proxy=proxy) as client:
            resp = await client.get("https://hub.docker.com/v2/repositories/pipi20xx/anime-manager/tags/")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("results") and len(data["results"]) > 0:
                    for tag_info in data["results"]:
                        tag_name = tag_info["name"]
                        if tag_name != "latest":
                            latest_tag = tag_name
                            _version_cache["version"] = latest_tag
                            _version_cache["timestamp"] = current_time
                            
                            if latest_tag != __version__:
                                log_audit("系统", "版本检查", f"发现新版本: {latest_tag} (当前: {__version__})")
                            else:
                                log_audit("系统", "版本检查", f"已是最新版本: {__version__}")
                            
                            return {
                                "current_version": __version__,
                                "latest_version": latest_tag,
                                "cached": False
                            }
    except Exception as e:
        log_audit("系统", "版本检查", f"检查失败: {e}", level="WARN")
    
    return {
        "current_version": __version__,
        "latest_version": _version_cache["version"] or "",
        "cached": True,
        "error": "无法获取最新版本信息"
    }




