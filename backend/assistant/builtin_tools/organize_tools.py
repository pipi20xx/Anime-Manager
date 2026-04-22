from ..tools import tool, ToolResult
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@tool(
    name="list_organize_tasks",
    description="获取所有整理任务配置列表。",
    category="整理管理",
    parameters=[]
)
async def list_organize_tasks() -> ToolResult:
    try:
        from config_manager import ConfigManager
        
        config = ConfigManager.get_config()
        tasks = config.get("organize_tasks", [])
        
        simplified = []
        for task in tasks:
            simplified.append({
                "id": task.get("id"),
                "name": task.get("name"),
                "source_dir": task.get("source_dir"),
                "target_dir": task.get("target_dir"),
                "rule_id": task.get("rule_id"),
                "enabled": task.get("enabled", True)
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"共有 {len(simplified)} 个整理任务"
        )
    except Exception as e:
        logger.error(f"[Tool] list_organize_tasks 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="list_directory",
    description="列出指定目录下的文件和文件夹。",
    category="整理管理",
    parameters=[
        {"name": "path", "type": "string", "description": "目录路径", "required": True}
    ]
)
async def list_directory(path: str) -> ToolResult:
    try:
        from organizer_core.file_explorer import FileExplorer
        
        data = FileExplorer.list_directory(path)
        
        return ToolResult(
            success=True,
            data=data,
            message=f"找到 {len(data.get('files', []))} 个文件, {len(data.get('directories', []))} 个文件夹"
        )
    except FileNotFoundError:
        return ToolResult(success=False, error="路径不存在")
    except PermissionError:
        return ToolResult(success=False, error="权限不足")
    except Exception as e:
        logger.error(f"[Tool] list_directory 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_file_info",
    description="获取文件的详细信息。",
    category="整理管理",
    parameters=[
        {"name": "path", "type": "string", "description": "文件路径", "required": True}
    ]
)
async def get_file_info(path: str) -> ToolResult:
    try:
        from organizer_core.file_explorer import FileExplorer
        
        data = FileExplorer.get_file_info(path)
        
        return ToolResult(success=True, data=data)
    except Exception as e:
        logger.error(f"[Tool] get_file_info 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_rename_rules",
    description="获取所有重命名规则配置。",
    category="整理管理",
    parameters=[]
)
async def get_rename_rules() -> ToolResult:
    try:
        from config_manager import ConfigManager
        from organizer_core.renamer import Renamer
        
        config = ConfigManager.get_config()
        rules = config.get("rename_rules", Renamer.get_default_rules())
        
        simplified = []
        for rule in rules:
            simplified.append({
                "id": rule.get("id"),
                "name": rule.get("name"),
                "movie_pattern": rule.get("movie_pattern"),
                "tv_pattern": rule.get("tv_pattern"),
                "is_default": rule.get("is_default", False)
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"共有 {len(simplified)} 个重命名规则"
        )
    except Exception as e:
        logger.error(f"[Tool] get_rename_rules 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="preview_rename",
    description="预览文件重命名结果，根据识别结果计算目标路径。",
    category="整理管理",
    parameters=[
        {"name": "filename", "type": "string", "description": "文件名", "required": True},
        {"name": "rule_id", "type": "string", "description": "重命名规则 ID", "required": True},
        {"name": "target_dir", "type": "string", "description": "目标目录", "required": False}
    ]
)
async def preview_rename(filename: str, rule_id: str, target_dir: str = "") -> ToolResult:
    try:
        from recognition.recognizer import MovieRecognizer
        from organizer_core.renamer import Renamer
        from config_manager import ConfigManager
        
        config = ConfigManager.get_config()
        anime_prio = config.get("anime_priority", True)
        
        result_data, _ = await MovieRecognizer.recognize_full(
            filename,
            force_filename=True,
            anime_priority=anime_prio
        )
        
        if not result_data.get("success"):
            return ToolResult(success=False, error="识别失败", data=result_data)
        
        rules = config.get("rename_rules", Renamer.get_default_rules())
        rule = next((r for r in rules if r["id"] == rule_id), None)
        
        if not rule:
            return ToolResult(success=False, error=f"规则 {rule_id} 不存在")
        
        final = result_data.get("final_result", {})
        is_movie = final.get("category") == "电影"
        pattern = rule.get("movie_pattern" if is_movie else "tv_pattern")
        
        new_path = Renamer.format_path(result_data, pattern, final.get("filename", filename))
        
        if target_dir:
            full_path = target_dir.rstrip("/") + "/" + new_path
        else:
            full_path = new_path
        
        return ToolResult(
            success=True,
            data={
                "original_filename": filename,
                "new_path": new_path,
                "full_path": full_path,
                "title": final.get("title"),
                "season": final.get("season"),
                "episode": final.get("episode"),
                "resolution": final.get("resolution")
            },
            message=f"预览: {filename} → {new_path}"
        )
    except Exception as e:
        logger.error(f"[Tool] preview_rename 失败: {e}")
        return ToolResult(success=False, error=str(e))


@tool(
    name="get_background_tasks",
    description="获取后台整理任务的状态列表。",
    category="整理管理",
    parameters=[]
)
async def get_background_tasks() -> ToolResult:
    try:
        from routers.organizer import _background_tasks
        
        tasks = list(_background_tasks.values())
        
        simplified = []
        for task in tasks:
            simplified.append({
                "task_id": task.get("task_id"),
                "name": task.get("name"),
                "status": task.get("status"),
                "processed": task.get("processed", 0),
                "started_at": task.get("started_at"),
                "finished_at": task.get("finished_at"),
                "error": task.get("error")
            })
        
        return ToolResult(
            success=True,
            data=simplified,
            message=f"共有 {len(simplified)} 个后台任务"
        )
    except Exception as e:
        logger.error(f"[Tool] get_background_tasks 失败: {e}")
        return ToolResult(success=False, error=str(e))
