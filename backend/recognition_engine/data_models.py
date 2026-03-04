from typing import List, Optional, Any
from dataclasses import dataclass, field
from .constants import MediaType

@dataclass
class MetaBase:
    cn_name: Optional[str] = None
    en_name: Optional[str] = None
    year: Optional[str] = None
    type: MediaType = MediaType.UNKNOWN
    begin_season: Optional[int] = None
    begin_episode: Optional[Any] = None
    resource_team: Optional[str] = None
    resource_pix: Optional[str] = None
    resource_type: Optional[str] = None
    video_encode: Optional[str] = None
    video_effect: Optional[str] = None # [New] 动态范围 (HDR/DV/SDR)
    audio_encode: Optional[str] = None
    resource_platform: Optional[str] = None
    subtitle_lang: Optional[str] = None
    forced_tmdbid: Optional[str] = None
    is_batch: bool = False
    end_episode: Optional[Any] = None
    tags: List[str] = field(default_factory=list)
    processed_name: Optional[str] = None
    original_cn_name: Optional[str] = None
    privileged_title: Optional[str] = None  # 特权提取的标题 (优先搜索候选)
