import os
import re
import yaml
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

def _get_skills_dir() -> str:
    possible_paths = [
        "/app/skills",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "skills"),
        os.path.join(os.getcwd(), "skills"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return "/app/skills"

SKILLS_DIR = _get_skills_dir()

# 技能启用状态持久化文件
SKILLS_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills_state.json")


@dataclass
class SkillDefinition:
    id: str
    name: str
    version: str
    description: str
    content: str
    path: str
    triggers: List[str] = None
    tools_needed: List[str] = None
    enabled: bool = True

    def __post_init__(self):
        if self.triggers is None:
            self.triggers = []
        if self.tools_needed is None:
            self.tools_needed = []

    def to_dict(self, include_content: bool = False) -> Dict:
        result = {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "triggers": self.triggers,
            "tools_needed": self.tools_needed,
            "enabled": self.enabled,
            "path": self.path,
        }
        if include_content:
            result["content"] = self.content
        return result


class SkillEngine:
    _instance = None
    _skills: Dict[str, SkillDefinition] = {}
    _loaded = False
    # 运行时启用状态（独立于文件，可从前端修改）
    _enabled_state: Dict[str, bool] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def _load_enabled_state(cls):
        """从持久化文件加载技能启用状态"""
        try:
            if os.path.exists(SKILLS_STATE_FILE):
                with open(SKILLS_STATE_FILE, "r", encoding="utf-8") as f:
                    cls._enabled_state = json.load(f)
        except Exception as e:
            logger.warning(f"[SkillEngine] 加载技能状态失败: {e}")
            cls._enabled_state = {}

    @classmethod
    def _save_enabled_state(cls):
        """持久化技能启用状态"""
        try:
            with open(SKILLS_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._enabled_state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[SkillEngine] 保存技能状态失败: {e}")

    @classmethod
    def load_skills(cls, skills_dir: str = SKILLS_DIR, force: bool = False):
        if cls._loaded and not force:
            return

        cls._load_enabled_state()

        if not os.path.exists(skills_dir):
            logger.warning(f"[SkillEngine] 技能目录不存在: {skills_dir}")
            cls._loaded = True
            return

        cls._skills = {}
        for skill_name in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, skill_name)
            if os.path.isdir(skill_path):
                skill_md = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(skill_md):
                    try:
                        skill_def = cls._parse_skill_md(skill_md, skill_name, skill_path)
                        if skill_def:
                            # 应用持久化的启用状态
                            if skill_name in cls._enabled_state:
                                skill_def.enabled = cls._enabled_state[skill_name]
                            cls._skills[skill_name] = skill_def
                            logger.info(f"[SkillEngine] 加载技能: {skill_def.name} ({skill_name}) [{'启用' if skill_def.enabled else '禁用'}]")
                    except Exception as e:
                        logger.error(f"[SkillEngine] 解析技能 {skill_name} 失败: {e}")

        cls._loaded = True
        enabled_count = sum(1 for s in cls._skills.values() if s.enabled)
        logger.info(f"[SkillEngine] 共加载 {len(cls._skills)} 个技能（{enabled_count} 个启用）")

    @classmethod
    def reload(cls, skills_dir: str = SKILLS_DIR):
        """重新加载所有技能"""
        cls._loaded = False
        cls.load_skills(skills_dir, force=True)

    @classmethod
    def _parse_skill_md(cls, file_path: str, skill_id: str, skill_path: str) -> Optional[SkillDefinition]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        frontmatter = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass

        name = frontmatter.get("name", skill_id)
        version = str(frontmatter.get("version", "1"))
        description = frontmatter.get("description", "")
        enabled = bool(frontmatter.get("enabled", True))

        # 优先从 frontmatter 的 tools 字段读取（推荐方式）
        tools_needed = frontmatter.get("tools", [])
        if isinstance(tools_needed, str):
            tools_needed = [t.strip() for t in tools_needed.split(",") if t.strip()]
        if not tools_needed:
            # 退化为从正文提取（兼容旧技能）
            tools_needed = cls._extract_tools(content)

        triggers = cls._extract_triggers(content)

        return SkillDefinition(
            id=skill_id,
            name=name,
            version=version,
            description=description,
            content=content,
            path=skill_path,
            triggers=triggers,
            tools_needed=tools_needed,
            enabled=enabled
        )

    @classmethod
    def _extract_triggers(cls, content: str) -> List[str]:
        triggers = []

        trigger_patterns = [
            r"当用户[询问说]+[\"「]([^\"」]+)[\"」]",
            r"用户问[\"「]([^\"」]+)[\"」]",
            r"触发词[：:]?\s*[\"「]([^\"」]+)[\"」]",
            r"触发[：:]\s*[\"「]([^\"」]+)[\"」]",
        ]

        for pattern in trigger_patterns:
            matches = re.findall(pattern, content)
            triggers.extend(matches)

        return list(dict.fromkeys(triggers))  # 去重保持顺序

    @classmethod
    def _extract_tools(cls, content: str) -> List[str]:
        """
        从技能内容中提取工具名（兼容旧技能）。
        只提取被反引号包裹、且符合工具命名规则的标识符。
        """
        # 匹配 `tool_name` 格式，工具名只含小写字母、数字、下划线
        raw_matches = re.findall(r"`([a-z][a-z0-9_]{2,40})`", content)
        # 去重保持顺序
        return list(dict.fromkeys(raw_matches))

    @classmethod
    def get_skill(cls, skill_id: str) -> Optional[SkillDefinition]:
        if not cls._loaded:
            cls.load_skills()
        return cls._skills.get(skill_id)

    @classmethod
    def list_skills(cls, include_disabled: bool = True) -> List[SkillDefinition]:
        if not cls._loaded:
            cls.load_skills()
        if include_disabled:
            return list(cls._skills.values())
        return [s for s in cls._skills.values() if s.enabled]

    @classmethod
    def set_skill_enabled(cls, skill_id: str, enabled: bool) -> bool:
        """设置技能启用/禁用状态，持久化保存"""
        if not cls._loaded:
            cls.load_skills()
        skill = cls._skills.get(skill_id)
        if not skill:
            return False
        skill.enabled = enabled
        cls._enabled_state[skill_id] = enabled
        cls._save_enabled_state()
        logger.info(f"[SkillEngine] 技能 {skill.name} 已{'启用' if enabled else '禁用'}")
        return True

    @classmethod
    def match_skill(cls, user_message: str) -> Optional[SkillDefinition]:
        if not cls._loaded:
            cls.load_skills()

        message_lower = user_message.lower().strip()

        # 按优先级匹配：显式触发词 > 技能 ID > 技能名称
        # 1. 触发词匹配（最精确）
        for skill in cls._skills.values():
            if not skill.enabled:
                continue
            for trigger in skill.triggers:
                if trigger.lower() in message_lower:
                    return skill

        # 2. 技能 ID 匹配（支持中划线/空格两种形式）
        for skill in cls._skills.values():
            if not skill.enabled:
                continue
            id_variants = [
                skill.id.lower(),
                skill.id.lower().replace("-", " "),
                skill.id.lower().replace("-", ""),
            ]
            if any(v in message_lower for v in id_variants if v):
                return skill

        # 3. 技能名称匹配
        for skill in cls._skills.values():
            if not skill.enabled:
                continue
            if skill.name and skill.name.lower() in message_lower:
                return skill

        return None

    @classmethod
    def get_skill_prompt(cls, skill_id: str) -> str:
        skill = cls.get_skill(skill_id)
        if not skill:
            return ""

        return f"""## 当前技能: {skill.name}

{skill.description}

### 技能详情
{skill.content}

请按照技能描述的流程执行操作。
"""

    @classmethod
    def get_all_skills_description(cls) -> str:
        if not cls._loaded:
            cls.load_skills()

        lines = ["# 可用技能\n"]
        for skill in cls._skills.values():
            if not skill.enabled:
                continue
            lines.append(f"\n## {skill.name} (`{skill.id}`)\n")
            lines.append(f"{skill.description}\n")
            if skill.triggers:
                lines.append(f"触发词: {', '.join(skill.triggers)}\n")

        return "\n".join(lines)
