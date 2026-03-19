import requests
from typing import Dict, List, Optional, Any
from config_manager import ConfigManager
import logging

logger = logging.getLogger(__name__)


class EmbyClient:
    def __init__(self):
        self.config = ConfigManager.get_config()
        self.base_url = self.config.get('emby_url', '').rstrip('/')
        self.api_key = self.config.get('emby_api_key', '')
        self.user_id = self.config.get('emby_user_id', '')
        self.session = requests.Session()
        self.session.headers.update({
            'X-Emby-Token': self.api_key,
            'Accept': 'application/json'
        })

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Optional[Dict]:
        if not self.base_url or not self.api_key:
            return None
        
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, params=params, json=data, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Emby API 请求失败: {e}")
            return None

    def search_by_tmdb_id(self, tmdb_id: str, media_type: str = 'all') -> Optional[Dict]:
        items = self._make_request('GET', '/Items', params={
            'IncludeItemTypes': 'Movie,Series',
            'Recursive': 'true',
            'Fields': 'ProviderIds,Path,MediaSources',
            'EnableUserData': 'false'
        })
        
        if not items or 'Items' not in items:
            return None
        
        matched_items = []
        for item in items['Items']:
            provider_ids = item.get('ProviderIds', {})
            item_tmdb_id = provider_ids.get('Tmdb')
            
            if item_tmdb_id and str(item_tmdb_id) == str(tmdb_id):
                if media_type == 'all' or item.get('Type', '').lower() == media_type.lower():
                    matched_items.append(item)
        
        return {
            'tmdb_id': tmdb_id,
            'matched_items': matched_items,
            'total': len(matched_items)
        }

    def search_series_by_tmdb_id(self, tmdb_id: str) -> Optional[Dict]:
        return self.search_by_tmdb_id(tmdb_id, 'Series')

    def search_movie_by_tmdb_id(self, tmdb_id: str) -> Optional[Dict]:
        return self.search_by_tmdb_id(tmdb_id, 'Movie')

    def get_seasons(self, series_id: str) -> Optional[List[Dict]]:
        result = self._make_request('GET', f'/Shows/{series_id}/Seasons', params={
            'Fields': 'ProviderIds,IndexNumber',
            'EnableUserData': 'false'
        })
        return result.get('Items', []) if result else None

    def get_episodes(self, series_id: str, season_id: str) -> Optional[List[Dict]]:
        result = self._make_request('GET', f'/Shows/{series_id}/Episodes', params={
            'SeasonId': season_id,
            'Fields': 'ProviderIds,IndexNumber,Path,MediaSources',
            'EnableUserData': 'false'
        })
        return result.get('Items', []) if result else None

    def check_episode_exists(self, tmdb_id: str, season_number: int, episode_number: int) -> bool:
        series_result = self.search_series_by_tmdb_id(tmdb_id)
        if not series_result or not series_result.get('matched_items'):
            logger.info(f"Emby 检查: TMDB ID {tmdb_id} 未找到匹配的剧集")
            return False
        
        matched_items = series_result['matched_items']
        logger.info(f"Emby 检查: TMDB ID {tmdb_id} 找到 {len(matched_items)} 个匹配项，正在检查 S{season_number}E{episode_number}")
        
        for series_item in matched_items:
            series_id = series_item.get('Id')
            series_name = series_item.get('Name', 'Unknown')
            logger.debug(f"Emby 检查: 正在检查剧集 '{series_name}' (ID: {series_id})")
            
            seasons = self.get_seasons(series_id)
            if not seasons:
                logger.debug(f"Emby 检查: 剧集 '{series_name}' 没有找到季信息")
                continue
            
            target_season = None
            for season in seasons:
                if season.get('IndexNumber') == season_number:
                    target_season = season
                    break
            
            if not target_season:
                logger.debug(f"Emby 检查: 剧集 '{series_name}' 没有找到第 {season_number} 季")
                continue
            
            episodes = self.get_episodes(series_id, target_season['Id'])
            if not episodes:
                logger.debug(f"Emby 检查: 剧集 '{series_name}' 第 {season_number} 季没有找到集数")
                continue
            
            for episode in episodes:
                if episode.get('IndexNumber') == episode_number:
                    logger.info(f"Emby 检查: ✅ 在剧集 '{series_name}' 中找到 S{season_number}E{episode_number}")
                    return True
        
        logger.info(f"Emby 检查: ❌ 在所有匹配的 {len(matched_items)} 个剧集中都未找到 S{season_number}E{episode_number}")
        return False

    def check_movie_exists(self, tmdb_id: str) -> bool:
        movie_result = self.search_movie_by_tmdb_id(tmdb_id)
        if movie_result and movie_result.get('matched_items'):
            matched_count = len(movie_result['matched_items'])
            logger.info(f"Emby 检查: TMDB ID {tmdb_id} 找到 {matched_count} 个匹配的电影")
            return True
        else:
            logger.info(f"Emby 检查: TMDB ID {tmdb_id} 未找到匹配的电影")
            return False

    def check_item_exists(self, tmdb_id: str, media_type: str, season_number: Optional[int] = None, episode_number: Optional[int] = None) -> bool:
        if media_type == 'movie':
            return self.check_movie_exists(tmdb_id)
        elif media_type == 'series':
            if season_number is not None and episode_number is not None:
                return self.check_episode_exists(tmdb_id, season_number, episode_number)
            else:
                series_result = self.search_series_by_tmdb_id(tmdb_id)
                return bool(series_result and series_result.get('matched_items'))
        return False

    def get_item_details(self, item_id: str) -> Optional[Dict]:
        return self._make_request('GET', f'/Items/{item_id}', params={
            'Fields': 'ProviderIds,Path,MediaSources,MediaStreams,Overview,Genres,Studios'
        })

    def test_connection(self) -> bool:
        result = self._make_request('GET', '/System/Info')
        return result is not None


_emby_client_instance = None


def get_emby_client() -> EmbyClient:
    global _emby_client_instance
    if _emby_client_instance is None:
        _emby_client_instance = EmbyClient()
    return _emby_client_instance
