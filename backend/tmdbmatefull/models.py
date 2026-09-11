from typing import Optional, List, Any
from datetime import datetime
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from config_manager import ConfigManager

def get_metadata_schema():
    return "metadata"

def get_json_type():
    return JSONB

class TmdbDeepMeta(SQLModel, table=True):
    """
    TMDB 统一元数据中心 (超级表)
    """
    __tablename__ = "tmdb_deep_meta"
    __table_args__ = {"schema": get_metadata_schema()}
    
    tmdb_id: str = Field(primary_key=True)
    media_type: str = Field(primary_key=True) # movie / tv
    
    # --- 标题逻辑 ---
    title: str                                            # 官方最新标题
    custom_title: Optional[str] = Field(default=None, index=True) # [NEW] 永久固定标题
    
    original_title: Optional[str] = Field(default="")     
    origin_country: Optional[List[str]] = Field(default_factory=list, sa_column=Column(ARRAY(String)))
    original_language: Optional[str] = Field(default="")  
    
    first_air_date: Optional[str] = Field(default="")     
    last_air_date: Optional[str] = None                   
    
    # --- [NEW] 核心展示字段 ---
    poster_path: Optional[str] = Field(default=None)      # 海报路径
    overview: Optional[str] = Field(default=None)         # 剧情简介
    
    genre_ids: Optional[List[int]] = Field(default_factory=list, sa_column=Column(ARRAY(Integer)))
    company_ids: Optional[List[int]] = Field(default_factory=list, sa_column=Column(ARRAY(Integer)))
    keyword_ids: Optional[List[int]] = Field(default_factory=list, sa_column=Column(ARRAY(Integer)))
    
    alias_pool: List[Any] = Field(sa_column=Column(get_json_type()), default_factory=list)
    title_pool: List[Any] = Field(sa_column=Column(get_json_type()), default_factory=list)
    
    full_data: Optional[Any] = Field(sa_column=Column(get_json_type()), default=None)      
    is_custom: bool = Field(default=False, index=True)                                    
    
    updated_at: datetime = Field(default_factory=datetime.now)

# ... (MediaTitleIndex 等其他类保持不变)
class MediaTitleIndex(SQLModel, table=True):
    __tablename__ = "media_title_index"
    __table_args__ = {"schema": get_metadata_schema()}
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True) 
    year: Optional[str] = Field(index=True)
    tmdb_id: str = Field(index=True)
    media_type: str = Field(index=True)
    source: str 

class RefGenre(SQLModel, table=True):
    __tablename__ = "ref_genres"
    __table_args__ = {"schema": get_metadata_schema()}
    id: int = Field(primary_key=True)
    name_zh: str
    name_en: str

class RefCompany(SQLModel, table=True):
    __tablename__ = "ref_companies"
    __table_args__ = {"schema": get_metadata_schema()}
    id: int = Field(primary_key=True)
    name: str
    country: str

class RefKeyword(SQLModel, table=True):
    __tablename__ = "ref_keywords"
    __table_args__ = {"schema": get_metadata_schema()}
    id: int = Field(primary_key=True)
    name_en: str

class UserGenreMapping(SQLModel, table=True):
    __tablename__ = "user_genre_mapping"
    __table_args__ = {"schema": get_metadata_schema()}
    id: int = Field(primary_key=True)
    name_zh: str = Field(default="")
    name_en: str = Field(default="")
    updated_at: datetime = Field(default_factory=datetime.now)

class UserCompanyMapping(SQLModel, table=True):
    __tablename__ = "user_company_mapping"
    __table_args__ = {"schema": get_metadata_schema()}
    id: int = Field(primary_key=True)
    name: str = Field(default="")
    country: str = Field(default="")
    updated_at: datetime = Field(default_factory=datetime.now)

class UserKeywordMapping(SQLModel, table=True):
    __tablename__ = "user_keyword_mapping"
    __table_args__ = {"schema": get_metadata_schema()}
    id: int = Field(primary_key=True)
    name_zh: str = Field(default="")
    name_en: str = Field(default="")
    updated_at: datetime = Field(default_factory=datetime.now)

class UserLanguageMapping(SQLModel, table=True):
    __tablename__ = "user_language_mapping"
    __table_args__ = {"schema": get_metadata_schema()}
    code: str = Field(primary_key=True)
    name_zh: str = Field(default="")
    name_en: str = Field(default="")
    updated_at: datetime = Field(default_factory=datetime.now)

class UserCountryMapping(SQLModel, table=True):
    __tablename__ = "user_country_mapping"
    __table_args__ = {"schema": get_metadata_schema()}
    code: str = Field(primary_key=True)
    name_zh: str = Field(default="")
    name_en: str = Field(default="")
    updated_at: datetime = Field(default_factory=datetime.now)
