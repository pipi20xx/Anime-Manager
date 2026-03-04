from typing import Optional, List, Any, Dict
from datetime import datetime
from sqlmodel import Field, SQLModel, Relationship, Column
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

def get_public_schema():
    return "public"

def get_json_type():
    return JSONB

class SeriesFingerprint(SQLModel, table=True):
    __tablename__ = "series_fingerprint"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "智能记忆"
    fingerprint: str = Field(primary_key=True)
    tmdb_id: str
    type: str
    title: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.now)

class FilterRule(SQLModel, table=True):
    __tablename__ = "filter_rules"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "基础规则"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    description: Optional[str] = None
    # 存储具体的过滤条件
    # 例如: {"resolution": "2160p", "team": "MTeam", "must_contain": "HDR", "source": "BluRay"}
    conditions: Dict[str, Any] = Field(sa_column=Column(get_json_type()), default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

class QualityProfile(SQLModel, table=True):
    __tablename__ = "quality_profiles"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "优先级策略"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    description: Optional[str] = None
    
    # 存储规则的组合与排序
    # 结构: [{"rule_id": 1, "name": "4K", "score": 1000}, ...]
    rules_config: List[Dict] = Field(sa_column=Column(get_json_type()), default_factory=list)
    
    upgrade_allowed: bool = Field(default=False) # 是否允许洗版
    cutoff_score: int = Field(default=0) # 截止分数
    created_at: datetime = Field(default_factory=datetime.now)

class SystemLog(SQLModel, table=True):
    __tablename__ = "system_logs"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "系统日志"
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.now, index=True)
    level: str
    module: str = Field(index=True)
    action: str
    message: str
    details: Optional[str] = None

class Feed(SQLModel, table=True):
    __tablename__ = "feeds"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "订阅源"
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str
    title: Optional[str] = None
    enabled: bool = Field(default=True)
    for_subscription: bool = Field(default=True) # 是否用于订阅匹配
    for_rules: bool = Field(default=True)        # 是否用于规则匹配
    anime_priority: bool = Field(default=True)   # 是否动漫优先
    include_keywords: Optional[str] = None # 前置包含词
    exclude_keywords: Optional[str] = None # 前置排除词
    last_update: Optional[datetime] = None

class Rule(SQLModel, table=True):
    __tablename__ = "rules"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "下载规则"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    enabled: bool = Field(default=True)
    must_contain: Optional[str] = None
    must_not_contain: Optional[str] = None
    use_regex: bool = Field(default=False)
    target_feeds: Optional[str] = None 
    target_client_id: Optional[str] = None
    save_path: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    paused: bool = Field(default=False)
    upload_limit: Optional[int] = 0
    download_limit: Optional[int] = 0

class FeedItem(SQLModel, table=True):
    __tablename__ = "feed_items"
    __table_args__ = {"schema": get_public_schema()}
    id: Optional[int] = Field(default=None, primary_key=True)
    feed_id: int = Field(foreign_key="public.feeds.id", index=True)
    guid: str = Field(index=True, unique=True)
    title: str
    link: str
    description: Optional[str] = None
    pub_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    tmdb_id: Optional[str] = Field(default=None, index=True)
    tmdb_title: Optional[str] = Field(default=None)
    media_type: Optional[str] = Field(default=None)
    season: Optional[int] = Field(default=None)
    episode: Optional[str] = Field(default=None)
    resolution: Optional[str] = Field(default=None)
    team: Optional[str] = Field(default=None)
    source: Optional[str] = Field(default=None)
    video_encode: Optional[str] = Field(default=None)
    audio_encode: Optional[str] = Field(default=None)
    video_effect: Optional[str] = Field(default=None)
    subtitle: Optional[str] = Field(default=None)
    platform: Optional[str] = Field(default=None)
    recognition_done: bool = Field(default=False)

class DownloadHistory(SQLModel, table=True):
    __tablename__ = "download_history"
    __table_args__ = {"schema": get_public_schema()}
    id: Optional[int] = Field(default=None, primary_key=True)
    guid: str = Field(index=True)
    title: str
    description: Optional[str] = None
    feed_id: Optional[int] = None
    rule_id: Optional[int] = Field(default=None, index=True)
    download_client_id: Optional[str] = None
    info_hash: Optional[str] = Field(default=None, index=True)
    state: str = Field(default="Success")
    created_at: datetime = Field(default_factory=datetime.now)

class Blacklist(SQLModel, table=True):
    __tablename__ = "blacklist"
    __table_args__ = {"schema": get_public_schema()}
    id: Optional[int] = Field(default=None, primary_key=True)
    info_hash: Optional[str] = Field(default=None, index=True)
    guid: Optional[str] = Field(default=None, index=True)
    title: Optional[str] = None
    reason: Optional[str] = Field(default="stalled")
    created_at: datetime = Field(default_factory=datetime.now)

class Subscription(SQLModel, table=True):
    __tablename__ = "subscriptions"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "媒体订阅"
    id: Optional[int] = Field(default=None, primary_key=True)
    tmdb_id: str = Field(index=True)
    media_type: str = Field(default="tv")
    title: str
    year: Optional[str] = None
    poster_path: Optional[str] = None
    filter_res: Optional[str] = None
    filter_team: Optional[str] = None
    filter_source: Optional[str] = None
    filter_codec: Optional[str] = None
    filter_audio: Optional[str] = None
    filter_sub: Optional[str] = None
    filter_effect: Optional[str] = None
    filter_platform: Optional[str] = None
    include_keywords: Optional[str] = None 
    exclude_keywords: Optional[str] = None 
    target_feeds: Optional[str] = None # 目标订阅源 (ID列表)
    target_client_id: Optional[str] = None
    save_path: Optional[str] = None
    category: Optional[str] = None
    season: int = Field(default=1)
    start_episode: int = Field(default=1)
    end_episode: int = Field(default=0)
    enabled: bool = Field(default=True)
    auto_fill: bool = Field(default=True)
    bangumi_id: Optional[str] = Field(default=None, index=True) # 关联 Bangumi ID
    quality_profile_id: Optional[int] = Field(foreign_key="public.quality_profiles.id", default=None) # 关联优先级策略
    last_check: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)

class RemoteRule(SQLModel, table=True):
    __tablename__ = "remote_rules"
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(index=True) # noise, groups, render
    content: List[str] = Field(sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=datetime.now)

class SubscriptionTemplate(SQLModel, table=True):
    __tablename__ = "subscription_templates"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "订阅模板"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    is_default: bool = Field(default=False)
    
    # 过滤与下载配置
    filter_res: Optional[str] = None
    filter_team: Optional[str] = None
    filter_source: Optional[str] = None
    filter_codec: Optional[str] = None
    filter_audio: Optional[str] = None
    filter_sub: Optional[str] = None
    filter_effect: Optional[str] = None
    filter_platform: Optional[str] = None
    include_keywords: Optional[str] = None 
    exclude_keywords: Optional[str] = None 
    target_feeds: Optional[str] = None # 目标订阅源 (ID列表)
    target_client_id: Optional[str] = None
    save_path: Optional[str] = None
    category: Optional[str] = Field(default="Anime")
    auto_fill: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.now)

class SubscribedEpisode(SQLModel, table=True):
    __tablename__ = "subscribed_episodes"
    __table_args__ = {"schema": get_public_schema()}
    id: Optional[int] = Field(default=None, primary_key=True)
    tmdb_id: str = Field(index=True)
    media_type: str = Field(default="tv", index=True)
    season: int
    episode: int
    title: Optional[str] = None
    info_hash: Optional[str] = Field(default=None, index=True)
    quality_score: int = Field(default=0) # 记录下载时的质量分数
    download_at: datetime = Field(default_factory=datetime.now, nullable=True)

class OrganizeHistory(SQLModel, table=True):
    __tablename__ = "organize_history"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "整理历史"
    id: Optional[int] = Field(default=None, primary_key=True)
    source_path: str = Field(index=True)
    target_path: Optional[str] = None
    filename: str
    tmdb_id: Optional[str] = None
    title: Optional[str] = None
    season: Optional[int] = None
    episode: Optional[str] = None
    media_type: Optional[str] = None
    action_type: Optional[str] = None
    file_size: Optional[str] = None
    processed_at: datetime = Field(default_factory=datetime.now)
    resolution: Optional[str] = None
    team: Optional[str] = None
    video_encode: Optional[str] = None
    year: Optional[str] = None
    status: str = Field(default="success") # success, failed, skipped
    message: Optional[str] = None

class DiscoverCache(SQLModel, table=True):
    __tablename__ = "discover_cache"
    __table_args__ = {"schema": get_public_schema()}
    key: str = Field(primary_key=True)
    content: Any = Field(sa_column=Column(get_json_type()))
    updated_at: datetime = Field(default_factory=datetime.now)
    expire_at: datetime

class CalendarSubject(SQLModel, table=True):
    __tablename__ = "calendar_subjects"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "日历追踪"
    id: Optional[int] = Field(default=None, primary_key=True)
    tmdb_id: str = Field(index=True)
    media_type: str = Field(default="tv")
    title: str
    season: int = Field(default=1)       # 新增：季号
    poster_path: Optional[str] = None
    first_air_date: Optional[str] = None # 格式: 2024-01-08
    air_weekday: Optional[int] = None    # 1-7
    # 存储剧集信息: [{"episode": 1, "air_date": "2024-01-01"}, ...]
    episodes_cache: List[Dict] = Field(sa_column=Column(get_json_type()), default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)



class SecondaryRule(SQLModel, table=True):



    __tablename__ = "secondary_rules"



    __table_args__ = {"schema": get_public_schema()}



    __admin_name__ = "二级分类规则"



    id: Optional[int] = Field(default=None, primary_key=True)



    name: str



    target: str = Field(default="all")



    enabled: bool = Field(default=True)



    priority: int = Field(default=0)



    criteria: Dict[str, Any] = Field(sa_column=Column(get_json_type()), default_factory=dict)



    updated_at: datetime = Field(default_factory=datetime.now)







class HealthCheckConfig(SQLModel, table=True):



    __tablename__ = "health_check_configs"



    __table_args__ = {"schema": get_public_schema()}



    __admin_name__ = "健康检查配置"



    id: Optional[int] = Field(default=None, primary_key=True)



    name: str



    file_path: str



    file_url: str



    enabled: bool = Field(default=True)



    last_status: Optional[str] = Field(default="Unknown") # OK, Failed, Unknown



    last_check: Optional[datetime] = Field(default=None)



    created_at: datetime = Field(default_factory=datetime.now)







class User(SQLModel, table=True):



    __tablename__ = "users"



    __table_args__ = {"schema": get_public_schema()}



    __admin_name__ = "用户管理"



    id: Optional[int] = Field(default=None, primary_key=True)



    username: str = Field(unique=True, index=True)



    hashed_password: str

    is_active: bool = Field(default=True)

    otp_secret: Optional[str] = Field(default=None)

    is_otp_enabled: bool = Field(default=False)

    last_login: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.now)

class TaskRecord(SQLModel, table=True):
    __tablename__ = "task_records"
    __table_args__ = {"schema": get_public_schema()}
    __admin_name__ = "任务记录"
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(unique=True, index=True)
    module: str = Field(index=True)
    name: Optional[str] = None
    status: str = Field(default="running")
    started_at: datetime = Field(default_factory=datetime.now, index=True)
    finished_at: Optional[datetime] = Field(default=None)
    processed: int = Field(default=0)
    logs: List[Dict[str, Any]] = Field(sa_column=Column(get_json_type()), default_factory=list)
    # 扩展统计字段
    stats: Dict[str, Any] = Field(sa_column=Column(get_json_type()), default_factory=dict)


