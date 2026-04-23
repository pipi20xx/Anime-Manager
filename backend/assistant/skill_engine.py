import os
import re
import yaml
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
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
    
    def __post_init__(self):
        if self.triggers is None:
            self.triggers = []
        if self.tools_needed is None:
            self.tools_needed = []


class SkillEngine:
    _instance = None
    _skills: Dict[str, SkillDefinition] = {}
    _loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def load_skills(cls, skills_dir: str = SKILLS_DIR):
        if cls._loaded:
            return
        
        if not os.path.exists(skills_dir):
            logger.warning(f"[SkillEngine] 技能目录不存在: {skills_dir}")
            return
        
        for skill_name in os.listdir(skills_dir):
            skill_path = os.path.join(skills_dir, skill_name)
            if os.path.isdir(skill_path):
                skill_md = os.path.join(skill_path, "SKILL.md")
                if os.path.exists(skill_md):
                    try:
                        skill_def = cls._parse_skill_md(skill_md, skill_name, skill_path)
                        if skill_def:
                            cls._skills[skill_name] = skill_def
                            logger.info(f"[SkillEngine] 加载技能: {skill_def.name} ({skill_name})")
                    except Exception as e:
                        logger.error(f"[SkillEngine] 解析技能 {skill_name} 失败: {e}")
        
        cls._loaded = True
        logger.info(f"[SkillEngine] 共加载 {len(cls._skills)} 个技能")
    
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
                except:
                    pass
        
        name = frontmatter.get("name", skill_id)
        version = str(frontmatter.get("version", "1"))
        description = frontmatter.get("description", "")
        
        triggers = cls._extract_triggers(content)
        tools_needed = cls._extract_tools(content)
        
        return SkillDefinition(
            id=skill_id,
            name=name,
            version=version,
            description=description,
            content=content,
            path=skill_path,
            triggers=triggers,
            tools_needed=tools_needed
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
        
        return list(set(triggers))
    
    @classmethod
    def _extract_tools(cls, content: str) -> List[str]:
        tools = []
        
        tool_patterns = [
            r"`([a-z_]+)`",
            r"工具[：:]?\s*`?([a-z_]+)`?",
            r"调用\s*`?([a-z_]+)`?",
        ]
        
        for pattern in tool_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            tools.extend(matches)
        
        return list(set(tools))
    
    @classmethod
    def get_skill(cls, skill_id: str) -> Optional[SkillDefinition]:
        if not cls._loaded:
            cls.load_skills()
        return cls._skills.get(skill_id)
    
    @classmethod
    def list_skills(cls) -> List[SkillDefinition]:
        if not cls._loaded:
            cls.load_skills()
        return list(cls._skills.values())
    
    @classmethod
    def match_skill(cls, user_message: str) -> Optional[SkillDefinition]:
        if not cls._loaded:
            cls.load_skills()
        
        message_lower = user_message.lower()
        
        for skill in cls._skills.values():
            for trigger in skill.triggers:
                if trigger.lower() in message_lower:
                    return skill
            
            if skill.id.replace("-", " ") in message_lower:
                return skill
            
            if skill.name.lower() in message_lower:
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
            lines.append(f"\n## {skill.name} (`{skill.id}`)\n")
            lines.append(f"{skill.description}\n")
            if skill.triggers:
                lines.append(f"触发词: {', '.join(skill.triggers)}\n")
        
        return "\n".join(lines)
