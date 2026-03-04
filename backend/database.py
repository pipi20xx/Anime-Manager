import os
import contextvars
import contextlib
from typing import Type, TypeVar, List, Optional, Any, Generic, Union, Sequence, Dict
from sqlmodel import SQLModel, text, select, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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
            "pool_size": 100,           # 显著增加连接池，防止高并发识别时挂起
            "max_overflow": 50,        # 允许更多溢出连接
            "pool_recycle": 3600,
            "pool_timeout": 60,        # 增加等待超时
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
            from logger import log_audit
            model_name = getattr(instance, "__admin_name__", instance.__class__.__name__)
            display_name = getattr(instance, "name", getattr(instance, "title", "ID:" + str(getattr(instance, "id", ""))))
            log_audit("数据库", "保存", f"已保存{model_name}: {display_name}")
            
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

        # 3. [核心增强] 自动补全缺失的列 (Auto Migration)
        def migrate_columns_sync(sync_conn):
            from sqlalchemy import inspect
            inspector = inspect(sync_conn)
            
            # 遍历 SQLModel 注册的所有表
            for table_full_name, table in SQLModel.metadata.tables.items():
                schema = table.schema or 'public'
                # 重要：使用 table.name 获取纯表名，避免与 schema 参数叠加
                actual_table_name = table.name
                
                try:
                    # 获取数据库中现有的列名
                    existing_columns = [c['name'] for c in inspector.get_columns(actual_table_name, schema=schema)]
                    
                    # 遍历模型定义中的列
                    for column in table.columns:
                        if column.name not in existing_columns:
                            print(f"[AutoMigrate] 检测到缺失列: {schema}.{actual_table_name}.{column.name}, 正在补全...")
                            
                            # 特殊处理布尔默认值
                            default_clause = ""
                            if column.default is not None:
                                try:
                                    arg = column.default.arg
                                    if str(arg).lower() == 'true': default_clause = " DEFAULT TRUE"
                                    elif str(arg).lower() == 'false': default_clause = " DEFAULT FALSE"
                                    elif isinstance(arg, (int, float)): default_clause = f" DEFAULT {arg}"
                                except: pass
                            
                            # 执行迁移
                            sql = f'ALTER TABLE "{schema}"."{actual_table_name}" ADD COLUMN "{column.name}" {column.type}{default_clause};'
                            sync_conn.execute(text(sql))
                except Exception as e:
                    # 如果表还没创建（理论上不会，因为上面执行了 create_all），或者有其他权限问题，打印并跳过
                    print(f"[AutoMigrate] 跳过表 {schema}.{actual_table_name}: {e}")
        
        await conn.run_sync(migrate_columns_sync)

        # 4. 清理已废弃的表
        await conn.execute(text("DROP TABLE IF EXISTS public.task_logs;"))
        
        # 5. 执行索引创建和高级优化
        # [性能增强] 建立三元组索引以加速 ILIKE 模糊搜索
        # 增加对全文搜索的支持，使用 GIN 索引
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subs_title_trgm ON public.subscriptions USING gin (title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_title_trgm ON metadata.tmdb_deep_meta USING gin (title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_meta_orig_title_trgm ON metadata.tmdb_deep_meta USING gin (original_title gin_trgm_ops);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tmdb_full_data_gin ON metadata.tmdb_deep_meta USING GIN (full_data);"))
        
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
        
    from logger import log_audit
    log_audit("数据库", "初始化", "PostgreSQL 数据库已连接并初始化 (含自动迁移检查)")



async def get_session():
    """FastAPI 依赖项"""
    async with db.session_scope() as session:
        yield session