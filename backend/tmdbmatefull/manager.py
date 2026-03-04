import json
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from logger import log_audit
from .models import TmdbDeepMeta
from .database import TmdbFullDB
from .ingestor import TmdbFullIngestor
from .browser import TmdbFullBrowser
from .classifier import TmdbFullClassifier
from .matcher import TmdbFullMatcher

from database import db
from sqlmodel import select, delete
from models import SecondaryRule

logger = logging.getLogger(__name__)

class TmdbMateFullManager:
    """
    离线元数据中心 - 统一调度层 (Dispatcher)
    """
    
    @staticmethod
    async def load_secondary_rules() -> List[Dict[str, Any]]:
        """从数据库加载二级分类规则"""
        async with db.session_scope():
            # 自动迁移逻辑：如果数据库为空但 JSON 文件存在，执行一次性迁移
            path = "data/secondary_rules.json"
            stmt = select(SecondaryRule).order_by(SecondaryRule.priority.asc(), SecondaryRule.id.asc())
            rules = await db.all(SecondaryRule, stmt)
            
            if not rules and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                        for i, r in enumerate(old_data):
                            new_rule = SecondaryRule(
                                name=r.get("name"), target=r.get("target", "all"),
                                enabled=r.get("enabled", True), priority=i,
                                criteria=r.get("criteria", {})
                            )
                            await db.save(new_rule, audit=False)
                        # 迁移成功后改名，防止下次又搬
                        os.rename(path, path + ".bak")
                        # 重新读取
                        rules = await db.all(SecondaryRule, stmt)
                except Exception as e:
                    logger.error(f"从 JSON 迁移分类规则失败: {e}")

            return [r.model_dump() for r in rules]

    @staticmethod
    async def save_secondary_rule(rule_data: Dict[str, Any]):
        """保存单条规则 (新增或更新)"""
        async with db.session_scope():
            rule_id = rule_data.get("id")
            if rule_id:
                existing = await db.get(SecondaryRule, rule_id)
                if existing:
                    for k, v in rule_data.items():
                        if hasattr(existing, k) and k != "id":
                            setattr(existing, k, v)
                    existing.updated_at = datetime.now()
                    await db.save(existing)
                    return True
            
            # 新增
            new_rule = SecondaryRule(**rule_data)
            await db.save(new_rule)
            return True

    @staticmethod
    async def delete_secondary_rule(rule_id: int):
        """删除规则"""
        async with db.session_scope():
            existing = await db.get(SecondaryRule, rule_id)
            if existing:
                await db.delete(existing)
                return True
        return False

    @staticmethod
    async def reorder_rules(rule_ids: List[int]):
        """批量重新排序"""
        async with db.session_scope():
            for i, rid in enumerate(rule_ids):
                rule = await db.get(SecondaryRule, rid)
                if rule:
                    rule.priority = i
                    await db.save(rule, audit=False)
        return True

    @staticmethod
    async def import_secondary_rules(rules_data: List[Dict[str, Any]], mode: str = "append") -> int:
        """导入规则"""
        count = 0
        async with db.session_scope():
            if mode == "replace":
                # 删除所有现有规则
                stmt = delete(SecondaryRule)
                await db.exec(stmt)
            
            for r in rules_data:
                # 清洗数据，移除 ID，确保作为新记录插入
                clean_data = {
                    "name": r.get("name"),
                    "target": r.get("target", "all"),
                    "enabled": r.get("enabled", True),
                    "priority": r.get("priority", 0),
                    "criteria": r.get("criteria", {})
                }
                new_rule = SecondaryRule(**clean_data)
                await db.save(new_rule, audit=False)
                count += 1
        return count

    @staticmethod
    async def fetch_and_ingest(tmdb_id: str, media_type: str, force: bool = False) -> bool:
        """[进项] 调度 Ingestor 抓取并入库"""
        if not force:
            existing = await TmdbMateFullManager.get_deep_meta(tmdb_id, media_type)
            # 关键改进：只有当记录存在且流派信息不为空时，才认为是“已完整存在”而跳过
            if existing and existing.genre_ids: 
                logger.info(f"{media_type}/{tmdb_id} 的元数据已完整存在，跳过。")
                return True
            if existing:
                logger.info(f"{media_type}/{tmdb_id} 探测到空壳记录，正在激活全量同步...")
        
        logger.info(f"正在调度 {media_type}/{tmdb_id} 的入库任务...")
        from config_manager import ConfigManager
        config = ConfigManager.get_config()
        
        success = await TmdbFullIngestor.process(
            tmdb_id=str(tmdb_id), media_type=media_type,
            api_key=config.get("tmdb_api_key"),
            proxy=ConfigManager.get_proxy("tmdb")
        )

        if success:
            log_audit("MetaFull", "Ingest", f"已成功存入本地数据中心: {media_type}/{tmdb_id}")
        else:
            logger.warning(f"{media_type}/{tmdb_id} 入库任务失败。")
            
        return success

    @staticmethod
    async def browse_deep_meta(page: int = 1, page_size: int = 20, search: str = None) -> Dict[str, Any]:
        """[检索] 调度 Browser 分页浏览数据"""
        return await TmdbFullBrowser.browse(page, page_size, search)

    @staticmethod
    async def browse_deep_meta_export() -> Dict[str, Any]:
        """[调度] 导出全量字典"""
        return await TmdbFullBrowser.export_dictionary()

    @staticmethod
    async def resolve_recognition(title: str, year: Optional[str] = None, 
                                  media_type: Optional[str] = None, 
                                  anime_priority: bool = True) -> Optional[Dict[str, Any]]:
        """[识别] 调度 Matcher 执行本地极速匹配"""
        logger.debug(f"正在进行离线识别: {title} (年份: {year}, 类型: {media_type})")
        result = await TmdbFullMatcher.resolve(title, year, media_type, anime_priority)
        if result:
            logger.info(f"离线匹配成功: {title} -> {result['id']} ({result['title']})")
        return result

    @staticmethod
    async def calculate_secondary_categories(tmdb_id: str, media_type: str, secondary_rules: List[Dict[str, Any]]) -> str:
        """[分拣] 调度 Classifier 计算二级路径"""
        deep = await TmdbMateFullManager.get_deep_meta(tmdb_id, media_type)
        return await TmdbFullClassifier.calculate(tmdb_id, media_type, secondary_rules, deep)

    @staticmethod
    async def calculate_secondary_categories_with_data(tmdb_id: str, media_type: str, secondary_rules: List[Dict[str, Any]], data: Dict[str, Any]) -> str:
        """[分拣] 直接基于传入的数据计算"""
        return await TmdbFullClassifier.calculate_with_data(tmdb_id, media_type, secondary_rules, data)

    @staticmethod
    async def get_deep_meta(tmdb_id: str, media_type: str) -> Optional[TmdbDeepMeta]:
        """[直连] 获取数据库主记录对象"""
        async with await TmdbFullDB.get_session() as session:
            return await session.get(TmdbDeepMeta, (str(tmdb_id), media_type))
