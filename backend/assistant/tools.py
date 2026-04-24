import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
    formatted_message: Optional[str] = None

    def to_dict(self) -> Dict:
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        if self.message:
            result["message"] = self.message
        if self.formatted_message:
            result["formatted_message"] = self.formatted_message
        return result

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


@dataclass
class ToolParameter:
    name: str
    type: str
    description: str
    required: bool = True
    enum: Optional[List[str]] = None
    default: Any = None


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: List[ToolParameter]
    func: Callable
    category: str = "general"
    examples: List[str] = field(default_factory=list)

    def to_openai_schema(self) -> Dict:
        properties = {}
        required = []

        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default

            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }


class ToolRegistry:
    _instance = None
    _tools: Dict[str, ToolDefinition] = {}
    _categories: Dict[str, List[str]] = {}
    _keywords_map: Dict[str, List[str]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, tool_def: ToolDefinition):
        cls._tools[tool_def.name] = tool_def
        if tool_def.category not in cls._categories:
            cls._categories[tool_def.category] = []
        if tool_def.name not in cls._categories[tool_def.category]:
            cls._categories[tool_def.category].append(tool_def.name)
        logger.info(f"[ToolRegistry] 注册工具: {tool_def.name} ({tool_def.category})")

    @classmethod
    def get(cls, name: str) -> Optional[ToolDefinition]:
        return cls._tools.get(name)

    @classmethod
    def list_all(cls) -> List[ToolDefinition]:
        return list(cls._tools.values())

    @classmethod
    def list_by_category(cls, category: str) -> List[ToolDefinition]:
        tool_names = cls._categories.get(category, [])
        return [cls._tools[name] for name in tool_names if name in cls._tools]

    @classmethod
    def get_openai_tools(cls, categories: Optional[List[str]] = None) -> List[Dict]:
        if categories:
            tools = []
            for cat in categories:
                tools.extend(cls.list_by_category(cat))
        else:
            tools = cls.list_all()
        return [t.to_openai_schema() for t in tools]

    @classmethod
    def get_tools_description(cls) -> str:
        lines = ["# 可用工具列表\n"]
        for category, tool_names in cls._categories.items():
            lines.append(f"\n## {category}\n")
            for name in tool_names:
                tool = cls._tools.get(name)
                if tool:
                    lines.append(f"- **{tool.name}**: {tool.description}")
                    for param in tool.parameters:
                        req = "必填" if param.required else "可选"
                        lines.append(f"  - `{param.name}` ({param.type}, {req}): {param.description}")
        return "\n".join(lines)

    @classmethod
    def select_tools_by_intent(cls, user_message: str, skill_tools: Optional[List[str]] = None) -> List[ToolDefinition]:
        """
        根据用户意图动态选择相关工具，减少 token 消耗
        
        策略：
        1. 如果技能指定了需要的工具，优先使用
        2. 根据关键词匹配工具类别
        3. 始终包含基础工具
        """
        selected_names = set()
        message_lower = user_message.lower()
        
        if skill_tools:
            selected_names.update(skill_tools)
        
        intent_category_map = {
            "订阅管理": ["订阅", "订阅列表", "添加订阅", "取消订阅", "删除订阅", "禁用", "启用", "订阅任务"],
            "媒体搜索": ["搜索", "查找", "找", "tmdb", "bangumi", "热门", "新番", "日历", "发现", "推荐"],
            "下载管理": ["下载", "种子", "jackett", "资源", "搜索资源"],
            "文件整理": ["整理", "重命名", "移动", "组织", "识别", "文件名"],
            "系统管理": ["状态", "配置", "设置", "系统", "检查", "健康"],
        }
        
        for category, keywords in intent_category_map.items():
            if any(kw in message_lower for kw in keywords):
                tool_names = cls._categories.get(category, [])
                selected_names.update(tool_names)
        
        essential_tools = ["list_subscriptions", "search_tmdb", "get_bangumi_calendar"]
        selected_names.update(essential_tools)
        
        return [cls._tools[name] for name in selected_names if name in cls._tools]

    @classmethod
    def get_compact_tools_description(cls, tools: List[ToolDefinition]) -> str:
        """
        生成精简的工具描述，只包含工具名和简短描述
        """
        if not tools:
            return ""
        
        lines = ["# 可用工具\n"]
        for tool in tools:
            lines.append(f"- `{tool.name}`: {tool.description.split('。')[0]}")
        return "\n".join(lines)


def _python_type_to_json(py_type: Type) -> str:
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        List: "array",
        Dict: "object",
    }

    origin = getattr(py_type, "__origin__", None)
    if origin:
        if origin is list or origin is List:
            return "array"
        if origin is dict or origin is Dict:
            return "object"

    return type_map.get(py_type, "string")


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    category: str = "general",
    parameters: Optional[List[Dict]] = None,
    examples: Optional[List[str]] = None
):
    def decorator(func: Callable):
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or "无描述"

        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        tool_params = []

        if parameters:
            for p in parameters:
                tool_params.append(ToolParameter(
                    name=p["name"],
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", True),
                    enum=p.get("enum"),
                    default=p.get("default")
                ))
        else:
            for param_name, param in sig.parameters.items():
                if param_name in ["self", "cls", "request"]:
                    continue

                param_type = _python_type_to_json(type_hints.get(param_name, str))
                param_desc = ""
                param_required = param.default is inspect.Parameter.empty

                if isinstance(param.annotation, str):
                    param_desc = param.annotation

                tool_params.append(ToolParameter(
                    name=param_name,
                    type=param_type,
                    description=param_desc,
                    required=param_required
                ))

        tool_def = ToolDefinition(
            name=tool_name,
            description=tool_description,
            parameters=tool_params,
            func=func,
            category=category,
            examples=examples or []
        )

        ToolRegistry.register(tool_def)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                if isinstance(result, ToolResult):
                    return result
                return ToolResult(success=True, data=result)
            except Exception as e:
                logger.error(f"[Tool] {tool_name} 执行失败: {e}", exc_info=True)
                return ToolResult(success=False, error=str(e))

        wrapper._tool_definition = tool_def
        return wrapper

    return decorator


def register_builtin_tools():
    from .builtin_tools import media_tools, subscription_tools, organize_tools, system_tools

    logger.info(f"[ToolRegistry] 已注册 {len(ToolRegistry._tools)} 个工具")
