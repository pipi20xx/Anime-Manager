import os
import contextvars
import contextlib
import logging
from typing import Type, TypeVar, List, Optional, Any, Generic, Union, Sequence, Dict
from sqlmodel import SQLModel, text, select, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=SQLModel)

def get_database_url() -> str:
    from config_manager import ConfigManager
    config = ConfigManager.get_config().get("database", {})
    
    user = config.get("user", "postgres")
    password = config.get("password", "")
    host = config.get("host", "localhost")
    port = config.get("port", 5432)
    database = config.get("database", "anime_pro_matcher")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"

# 全局变量，将在 get_engine 中初始化
_engine = None
_async_session_maker = None

def get_engine():
    global _engine, _async_session_maker
    if _engine is None:
        url = get_database_url()
        
        # 调试信息：打印除密码外的连接参数
        try:
            from config_manager import ConfigManager
            c = ConfigManager.get_config().get("database", {})
            print(f"[DB Debug] 尝试连接数据库: {c.get('host')}:{c.get('port')} | 用户: {c.get('user')} | 库名: {c.get('database')}")
        except:
            pass

        engine_kwargs = {
            "echo": False,
            "pool_pre_ping": True,
            "pool_size": 20,            # 适度连接池，避免超过 PG max_connections
            "max_overflow": 10,         # 溢出连接上限 (总共最多 30)
            "pool_recycle": 1800,       # 30 分钟回收，避免长连接泄漏
            "pool_timeout": 30,          # 等待连接超时
            "connect_args": {
                "command_timeout": 60,
                "timeout": 60,
                "server_settings": {
                    "jit": "off",      # 对于简单查询，关闭 JIT 可以提速
                    "application_name": "AnimeProMatcher"
                }
            }
        }
        
        _engine = create_async_engine(url, **engine_kwargs)

        _async_session_maker = sessionmaker(
            _engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    return _engine

def get_session_maker():
    get_engine()
    return _async_session_maker

def init_engine():
    """Manual re-initialization of the engine (e.g. after config change)"""
    global _engine, _async_session_maker
    _engine = None
    _async_session_maker = None
    return get_engine()

# 使用 ContextVar 存储当前上下文的 Session
_session_ctx = contextvars.ContextVar("_session_ctx", default=None)

class DBService:
    @property
    def session(self) -> AsyncSession:
        """获取当前上下文的 session，如果没有则抛出异常"""
        s = _session_ctx.get()
        if s is None:
            raise RuntimeError("No DB session in current context. Use 'async with db.session_scope():'")
        return s

    @contextlib.asynccontextmanager
    async def session_scope(self, force_new: bool = False):
        """Session 生命周期管理器 (用于 FastAPI 依赖或后台任务)"""
        token = None
        s = _session_ctx.get()
        if s is None or force_new:
            maker = get_session_maker()
            async with maker() as new_session:
                token = _session_ctx.set(new_session)
                try:
                    yield new_session
                    if new_session.in_transaction():
                        await new_session.commit()
                except Exception:
                    await new_session.rollback()
                    raise
                finally:
                    _session_ctx.reset(token)
        else:
            # 如果已经存在 Session (嵌套调用)，直接复用
            yield s

    async def get(self, model: Type[T], ident: Any) -> Optional[T]:
        """根据 ID 获取记录"""
        return await self.session.get(model, ident)

    async def all(self, model: Type[T], statement: Any = None) -> List[T]:
        """获取所有记录"""
        if statement is None:
            statement = select(model)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def first(self, model: Type[T], statement: Any) -> Optional[T]:
        """获取第一条记录"""
        result = await self.session.execute(statement)
        return result.scalars().first()

    async def save(self, instance: T, audit: bool = True) -> T:
        """保存或更新记录 (Upsert 逻辑)"""
        self.session.add(instance)
        await self.session.commit()
        try:
            await self.session.refresh(instance)
        except:
            pass
        
        if audit:
            model_name = getattr(instance, "__admin_name__", instance.__class__.__name__)
            display_name = getattr(instance, "name", getattr(instance, "title", "ID:" + str(getattr(instance, "id", ""))))
            logger.debug(f"已保存{model_name}: {display_name}")
            
        return instance

    async def delete(self, instance: T, audit: bool = True):
        """删除记录"""
        from logger import log_audit
        model_name = getattr(instance, "__admin_name__", instance.__class__.__name__)
        display_name = getattr(instance, "name", getattr(instance, "title", "ID:" + str(getattr(instance, "id", ""))))
        
        await self.session.delete(instance)
        await self.session.commit()
        
        if audit:
            log_audit("数据库", "删除", f"已删除{model_name}: {display_name}")

    async def execute(self, statement: Any):
        """执行原始 SQL 或语句"""
        return await self.session.execute(statement)

    async def upsert_all(self, model: Type[T], values: List[Dict[str, Any]], index_elements: List[str]):
        """
        PostgreSQL 专用：高性能批量 Upsert。
        :param model: SQLModel 模型
        :param values: 数据字典列表
        :param index_elements: 用于判断冲突的列名列表 (如 ['guid'])
        """
        if not values: return
        from sqlalchemy.dialects.postgresql import insert
        
        # 转换 SQLModel 模型为原始 SQLAlchemy table 对象
        stmt = insert(model.__table__).values(values)
        
        # 定义冲突后的行为：不做任何事 (Do Nothing) 或 更新 (Do Update)
        # 这里默认使用 Do Nothing，因为 RSS 条目通常一旦抓取就不再改变 guid
        stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)
        
        await self.session.execute(stmt)
        await self.session.commit()

# 单例模式导出
db = DBService()

async def init_db():
    engine = get_engine()
    async with engine.begin() as conn:
        # 创建必要扩展和 Schema
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS metadata;"))
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public;"))
        
        # 1. 导入所有模型以确保它们在 SQLModel.metadata 中注册
        import models
        from tmdbmatefull import models as tmdb_models
        
        # 2. 创建所有表 (如果不存在)
        def create_all_sync(sync_conn):
            SQLModel.metadata.create_all(sync_conn, checkfirst=True)
        await conn.run_sync(create_all_sync)

    # 3. [核心增强] 自动补全缺失的列 (Auto Migration) - 每个列使用独立事务
    async def migrate_columns():
        from sqlalchemy import inspect
        
        # 先收集所有需要添加的列
        columns_to_add = []
        
        async with engine.connect() as inspect_conn:
            def collect_columns(sync_conn):
                inspector = inspect(sync_conn)
                for table_full_name, table in SQLModel.metadata.tables.items():
                    schema = table.schema or 'public'
                    actual_table_name = table.name
                    
                    try:
                        existing_columns = [c['name'] for c in inspector.get_columns(actual_table_name, schema=schema)]
                    except Exception as e:
                        print(f"[AutoMigrate] 跳过表 {schema}.{actual_table_name}: {e}")
                        continue
                    
                    for column in table.columns:
                        if column.name not in existing_columns:
                            default_clause = ""
                            if column.default is not None:
                                try:
                                    arg = column.default.arg
                                    if str(arg).lower() == 'true': default_clause = " DEFAULT TRUE"
                                    elif str(arg).lower() == 'false': default_clause = " DEFAULT FALSE"
                                    elif isinstance(arg, (int, float)): default_clause = f" DEFAULT {arg}"
                                except: pass
                            
                            col_type = str(column.type)
                            if col_type.upper() == "DATETIME":
                                col_type = "TIMESTAMP"
                            
                            columns_to_add.append({
                                'schema': schema,
                                'table': actual_table_name,
                                'column': column.name,
                                'type': col_type,
                                'default': default_clause
                            })
            
            await inspect_conn.run_sync(collect_columns)
        
        # 为每个列使用独立事务执行迁移
        for col_info in columns_to_add:
            try:
                print(f"[AutoMigrate] 检测到缺失列: {col_info['schema']}.{col_info['table']}.{col_info['column']}, 正在补全...")
                sql = f'ALTER TABLE "{col_info["schema"]}"."{col_info["table"]}" ADD COLUMN "{col_info["column"]}" {col_info["type"]}{col_info["default"]};'
                async with engine.begin() as alter_conn:
                    await alter_conn.execute(text(sql))
                print(f"[AutoMigrate] 成功添加列: {col_info['schema']}.{col_info['table']}.{col_info['column']}")
            except Exception as e:
                print(f"[AutoMigrate] 添加列失败 {col_info['schema']}.{col_info['table']}.{col_info['column']}: {e}")
    
    await migrate_columns()

    # [类型迁移] file_hashes.file_size: INTEGER -> BIGINT (支持 >2GB 文件)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE public.file_hashes ALTER COLUMN file_size TYPE BIGINT USING file_size::BIGINT;"
            ))
        print("[AutoMigrate] file_hashes.file_size 已迁移为 BIGINT")
    except Exception as e:
        print(f"[AutoMigrate] file_hashes.file_size 类型迁移跳过: {e}")

    # [类型迁移] 纯 PG 原生化：逗号字符串列 -> 原生数组/JSONB 列
    # 通过 udt_name 判断目标类型，已迁移则跳过（避免每次启动重写大表）
    async def migrate_column_types():
        # (schema, table, column, 目标类型, USING 表达式, 迁移完成后的 udt_name)
        targets = [
            ("metadata", "tmdb_deep_meta", "genre_ids", "integer[]", "string_to_array(NULLIF(genre_ids,''), ',')::int[]", "_int4"),
            ("metadata", "tmdb_deep_meta", "company_ids", "integer[]", "string_to_array(NULLIF(company_ids,''), ',')::int[]", "_int4"),
            ("metadata", "tmdb_deep_meta", "keyword_ids", "integer[]", "string_to_array(NULLIF(keyword_ids,''), ',')::int[]", "_int4"),
            ("metadata", "tmdb_deep_meta", "origin_country", "text[]", "string_to_array(NULLIF(origin_country,''), ',')::text[]", "_text"),
            ("public", "remote_rules", "content", "jsonb", "content::jsonb", "jsonb"),
        ]
        for schema, table, column, target_type, using_expr, done_udt in targets:
            try:
                async with engine.connect() as check_conn:
                    res = await check_conn.execute(text(
                        "SELECT udt_name FROM information_schema.columns "
                        "WHERE table_schema = :s AND table_name = :t AND column_name = :c"
                    ), {"s": schema, "t": table, "c": column})
                    udt = res.scalar()
                if udt is None or udt == done_udt:
                    continue  # 新库由建表直接生成目标类型，或已迁移
                sql = f'ALTER TABLE "{schema}"."{table}" ALTER COLUMN "{column}" TYPE {target_type} USING {using_expr};'
                async with engine.begin() as alter_conn:
                    await alter_conn.execute(text(sql))
                print(f"[AutoMigrate] {schema}.{table}.{column} 已迁移为 {target_type}")
            except Exception as e:
                print(f"[AutoMigrate] {schema}.{table}.{column} 类型迁移跳过: {e}")

    await migrate_column_types()

    async with engine.begin() as conn:

        # 4. 清理已废弃的表
        await conn.execute(text("DROP TABLE IF EXISTS public.task_logs;"))
        await conn.execute(text("DROP TABLE IF EXISTS public.bgm_tmdb_mapping;"))
        
        # 5. 执行索引创建和高级优化
        # [性能增强] 建立三元组索引以加速 ILIKE 模糊搜索
        # 增加对全文搜索的支持，使用 GIN 索引
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subs_title_trgm ON public.subscriptions USING gin (title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_title_trgm ON metadata.tmdb_deep_meta USING gin (title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_orig_title_trgm ON metadata.tmdb_deep_meta USING gin (original_title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_custom_title_trgm ON metadata.tmdb_deep_meta USING gin (custom_title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_full_data_gin ON metadata.tmdb_deep_meta USING GIN (full_data);"))

        # [性能增强] ID 数组列 GIN 索引，加速 @> 包含查询 (需在类型迁移为原生数组后执行)
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_genre_gin ON metadata.tmdb_deep_meta USING gin (genre_ids);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_company_gin ON metadata.tmdb_deep_meta USING gin (company_ids);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_keyword_gin ON metadata.tmdb_deep_meta USING gin (keyword_ids);"))

        # [性能增强] 文件哈希表多字段模糊搜索 (routers/file_hashes.py 的 ILIKE 查询)
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_file_hash_filename_trgm ON public.file_hashes USING gin (original_filename gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_file_hash_title_trgm ON public.file_hashes USING gin (title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_file_hash_ed2k_trgm ON public.file_hashes USING gin (ed2k gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_file_hash_sha1_trgm ON public.file_hashes USING gin (sha1 gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_file_hash_source_path_trgm ON public.file_hashes USING gin (source_path gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_file_hash_target_path_trgm ON public.file_hashes USING gin (target_path gin_trgm_ops);"))

        # [性能增强] RSS 条目标题模糊搜索
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feed_items_title_trgm ON public.feed_items USING gin (title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_feed_items_tmdb_title_trgm ON public.feed_items USING gin (tmdb_title gin_trgm_ops);"))

        # [性能增强] 元数据参考字典表名称搜索
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ref_genre_zh_trgm ON metadata.ref_genres USING gin (name_zh gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ref_genre_en_trgm ON metadata.ref_genres USING gin (name_en gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ref_company_name_trgm ON metadata.ref_companies USING gin (name gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ref_keyword_name_trgm ON metadata.ref_keywords USING gin (name_en gin_trgm_ops);"))
        
        # [BangumiDataItem] raw_data JSONB 字段建立 GIN 索引以加速 JSON 查询
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bangumi_data_item_raw_data_gin ON public.bangumi_data_item USING GIN (raw_data);"))
        
        # [BangumiDataItem] updated_at 字段由触发器自动维护
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION public.set_updated_at()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        await conn.execute(text("DROP TRIGGER IF EXISTS trg_bangumi_data_item_updated_at ON public.bangumi_data_item;"))
        await conn.execute(text("""
            CREATE TRIGGER trg_bangumi_data_item_updated_at
                BEFORE INSERT OR UPDATE ON public.bangumi_data_item
                FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
        """))
        
        # [新增加速] 针对 MediaTitleIndex 的模糊搜索索引
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_media_index_title_trgm ON metadata.media_title_index USING gin (title gin_trgm_ops);"))

        # [性能增强] 为历史表增加模糊搜索索引
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_history_title_trgm ON public.download_history USING gin (title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_org_history_title_trgm ON public.organize_history USING gin (title gin_trgm_ops);"))

        # [高级优化] 增加一个相似度自定义函数，方便后续进行语义接近度排序
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION public.smart_match_score(target text, search text) 
            RETURNS float8 AS $$
            BEGIN
                RETURN similarity(target, search);
            END;
            $$ LANGUAGE plpgsql IMMUTABLE;
        """))

        # 6. 特殊索引 (唯一约束等)
        # 为 FeedItem 增加唯一索引以支持批量 Upsert
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_feed_items_guid ON public.feed_items (guid);"))
        # 为 Emby 索引表增加唯一索引以支持批量回写 (INSERT OR IGNORE)
        await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_emby_media_index_item ON public.emby_media_index (tmdb_id, media_type, emby_item_id);"))
        
    from logger import log_audit
    log_audit("数据库", "初始化", "PostgreSQL 数据库已连接并初始化 (含自动迁移检查)")



async def get_session():
    """FastAPI 依赖项"""
    async with db.session_scope() as session:
        yield session