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
        # 索引上下文 (由调用方在异步侧设置，同步侧读取)
        self._index_titles: Optional[List[str]] = None
        self._index_writeback: List[Dict] = []

    def set_index_context(self, titles: List[str]):
        """设置索引上下文，search_by_tmdb_id 将优先用这些标题搜索。"""
        self._index_titles = titles
        self._index_writeback = []

    def clear_index_context(self) -> List[Dict]:
        """清除索引上下文并返回兜底遍历发现的需要回写的条目。"""
        self._index_titles = None
        result = list(self._index_writeback)
        self._index_writeback = []
        return result

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

    def search_by_tmdb_id(self, tmdb_id: str, media_type: str = 'all',
                          index_titles: Optional[List[str]] = None,
                          on_items_matched: Optional[callable] = None) -> Optional[Dict]:
        """
        通过 TMDB ID 搜索 Emby 库。
        - index_titles: 显式传入的索引标题 (优先级最高)
        - 同时检查实例上下文 self._index_titles
        - on_items_matched: 兜底遍历找到新条目时的立即回调
        - 兜底发现也会收集到 self._index_writeback 中
        """
        # 合并参数和实例上下文的标题
        titles = index_titles or []
        if self._index_titles:
            titles = list(set(titles + self._index_titles))

        new_items_for_index = []  # 兜底遍历时发现的新条目

        # 1. 优先走索引: 用标题搜索 → 比对 TMDB ID
        if titles:
            for title in titles:
                search_result = self.search_by_title(title, media_type)
                if not search_result or not search_result.get('Items'):
                    continue

                matched = []
                for item in search_result['Items']:
                    item_tmdb_id = (item.get('ProviderIds', {}) or {}).get('Tmdb')
                    if item_tmdb_id and str(item_tmdb_id) == str(tmdb_id):
                        if media_type == 'all' or item.get('Type', '').lower() == media_type.lower():
                            matched.append(item)

                if matched:
                    logger.info(f"索引命中: tmdb_id={tmdb_id} 标题='{title}' 匹配 {len(matched)} 项")
                    return {
                        'tmdb_id': tmdb_id,
                        'matched_items': matched,
                        'total': len(matched)
                    }

        # 2. 兜底: 遍历整个 Emby 库
        logger.info(f"执行兜底遍历: tmdb_id={tmdb_id}")
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
            item_tmdb_id = (item.get('ProviderIds', {}) or {}).get('Tmdb')
            if item_tmdb_id and str(item_tmdb_id) == str(tmdb_id):
                if media_type == 'all' or item.get('Type', '').lower() == media_type.lower():
                    matched_items.append(item)
                    entry = {
                        'tmdb_id': str(tmdb_id),
                        'media_type': item.get('Type', ''),
                        'emby_item_id': item.get('Id', ''),
                        'title': item.get('Name', ''),
                    }
                    new_items_for_index.append(entry)

        # 3. 回写索引
        if new_items_for_index:
            # 收集到实例上下文
            self._index_writeback.extend(new_items_for_index)
            # 同时调用显式回调
            if on_items_matched:
                try:
                    on_items_matched(new_items_for_index)
                except Exception as e:
                    logger.warning(f"回写索引回调失败: {e}")

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
            logger.info(f"Emby 检查: 正在检查剧集 '{series_name}' (ID: {series_id})")
            
            seasons = self.get_seasons(series_id)
            if not seasons:
                logger.info(f"Emby 检查: 剧集 '{series_name}' 没有找到季信息")
                continue
            
            target_season = None
            for season in seasons:
                if season.get('IndexNumber') == season_number:
                    target_season = season
                    break
            
            if not target_season:
                logger.info(f"Emby 检查: 剧集 '{series_name}' 没有找到第 {season_number} 季")
                continue
            
            episodes = self.get_episodes(series_id, target_season['Id'])
            if not episodes:
                logger.info(f"Emby 检查: 剧集 '{series_name}' 第 {season_number} 季没有找到集数")
                continue
            
            for episode in episodes:
                if episode.get('IndexNumber') == episode_number:
                    logger.info(f"Emby 检查: ✅ 在剧集 '{series_name}' 中找到 S{season_number}E{episode_number}")
                    return True
        
        logger.info(f"Emby 检查: ❌ 在所有匹配的 {len(matched_items)} 个剧集中都未找到 S{season_number}E{episode_number}")
        return False

    def get_episode_info(self, tmdb_id: str, season_number: int, episode_number: int) -> Optional[Dict]:
        series_result = self.search_series_by_tmdb_id(tmdb_id)
        if not series_result or not series_result.get('matched_items'):
            logger.info(f"Emby 查询集信息: TMDB ID {tmdb_id} 未找到匹配的剧集")
            return None
        
        logger.info(f"Emby 查询集信息: TMDB ID {tmdb_id} 正在查询 S{season_number}E{episode_number}")
        
        for series_item in series_result['matched_items']:
            series_id = series_item.get('Id')
            series_name = series_item.get('Name', 'Unknown')
            
            seasons = self.get_seasons(series_id)
            if not seasons:
                continue
            
            target_season = None
            for season in seasons:
                if season.get('IndexNumber') == season_number:
                    target_season = season
                    break
            
            if not target_season:
                continue
            
            episodes = self.get_episodes(series_id, target_season['Id'])
            if not episodes:
                continue
            
            for episode in episodes:
                if episode.get('IndexNumber') == episode_number:
                    media_sources = episode.get('MediaSources', [])
                    files = []
                    
                    for source in media_sources:
                        files.append({
                            'path': source.get('Path', ''),
                            'name': source.get('Name', ''),
                            'size': source.get('Size', 0),
                            'container': source.get('Container', ''),
                        })
                    
                    logger.info(f"Emby 查询集信息: ✅ 在剧集 '{series_name}' 中找到 S{season_number}E{episode_number}，共 {len(files)} 个文件")
                    return {
                        'exists': True,
                        'episode_id': episode.get('Id'),
                        'series_name': series_name,
                        'files': files
                    }
        
        logger.info(f"Emby 查询集信息: ❌ 未找到 S{season_number}E{episode_number}")
        return {'exists': False}

    def get_season_episodes_info(self, tmdb_id: str, season_number: int) -> Dict[int, Dict]:
        series_result = self.search_series_by_tmdb_id(tmdb_id)
        if not series_result or not series_result.get('matched_items'):
            logger.info(f"Emby 查询季度集信息: TMDB ID {tmdb_id} 未找到匹配的剧集")
            return {}
        
        matched_items = series_result['matched_items']
        logger.info(f"Emby 查询季度集信息: TMDB ID {tmdb_id} 找到 {len(matched_items)} 个匹配项，正在查询第 {season_number} 季")
        
        episodes_info = {}
        
        for series_item in matched_items:
            series_id = series_item.get('Id')
            series_name = series_item.get('Name', 'Unknown')
            logger.info(f"Emby 查询季度集信息: 正在查询剧集 '{series_name}' (ID: {series_id})")
            
            seasons = self.get_seasons(series_id)
            if not seasons:
                logger.info(f"Emby 查询季度集信息: 剧集 '{series_name}' 没有找到季信息")
                continue
            
            target_season = None
            for season in seasons:
                if season.get('IndexNumber') == season_number:
                    target_season = season
                    break
            
            if not target_season:
                logger.info(f"Emby 查询季度集信息: 剧集 '{series_name}' 没有找到第 {season_number} 季")
                continue
            
            episodes = self.get_episodes(series_id, target_season['Id'])
            if not episodes:
                logger.info(f"Emby 查询季度集信息: 剧集 '{series_name}' 第 {season_number} 季没有找到集数")
                continue
            
            logger.info(f"Emby 查询季度集信息: 剧集 '{series_name}' 第 {season_number} 季找到 {len(episodes)} 集")
            
            for episode in episodes:
                ep_num = episode.get('IndexNumber')
                if ep_num is None:
                    continue
                
                media_sources = episode.get('MediaSources', [])
                
                if ep_num not in episodes_info:
                    episodes_info[ep_num] = {
                        'exists': True,
                        'episode_id': episode.get('Id'),
                        'series_name': series_name,
                        'files': []
                    }
                
                for source in media_sources:
                    file_path = source.get('Path', '')
                    file_name = source.get('Name', '')
                    
                    existing_paths = {f.get('path') for f in episodes_info[ep_num]['files']}
                    if file_path and file_path not in existing_paths:
                        episodes_info[ep_num]['files'].append({
                            'path': file_path,
                            'name': file_name,
                            'size': source.get('Size', 0),
                            'container': source.get('Container', ''),
                        })
        
        total_episodes = len(episodes_info)
        total_files = sum(len(ep['files']) for ep in episodes_info.values())
        logger.info(f"Emby 查询季度集信息: 完成，共 {total_episodes} 集，{total_files} 个文件")
        
        return episodes_info

    def check_movie_exists(self, tmdb_id: str) -> bool:
        movie_result = self.search_movie_by_tmdb_id(tmdb_id)
        if movie_result and movie_result.get('matched_items'):
            matched_count = len(movie_result['matched_items'])
            logger.info(f"Emby 检查: TMDB ID {tmdb_id} 找到 {matched_count} 个匹配的电影")
            return True
        else:
            logger.info(f"Emby 检查: TMDB ID {tmdb_id} 未找到匹配的电影")
            return False

    def get_movie_info(self, tmdb_id: str) -> Optional[Dict]:
        movie_result = self.search_movie_by_tmdb_id(tmdb_id)
        if not movie_result or not movie_result.get('matched_items'):
            logger.info(f"Emby 查询电影信息: TMDB ID {tmdb_id} 未找到匹配的电影")
            return {'exists': False}
        
        movie_item = movie_result['matched_items'][0]
        movie_name = movie_item.get('Name', 'Unknown')
        logger.info(f"Emby 查询电影信息: ✅ 找到电影 '{movie_name}'")
        
        media_sources = movie_item.get('MediaSources', [])
        files = []
        
        for source in media_sources:
            files.append({
                'path': source.get('Path', ''),
                'name': source.get('Name', ''),
                'size': source.get('Size', 0),
                'container': source.get('Container', ''),
            })
        
        logger.info(f"Emby 查询电影信息: 电影 '{movie_name}' 共 {len(files)} 个文件")
        
        return {
            'exists': True,
            'item_id': movie_item.get('Id'),
            'name': movie_name,
            'files': files
        }

    def get_series_library_status(self, tmdb_id: str, seasons_info: List[Dict] = None) -> Dict:
        series_result = self.search_series_by_tmdb_id(tmdb_id)
        if not series_result or not series_result.get('matched_items'):
            logger.info(f"Emby 查询剧集状态: TMDB ID {tmdb_id} 未找到匹配的剧集")
            return {'exists': False, 'seasons': {}}
        
        matched_items = series_result['matched_items']
        logger.info(f"Emby 查询剧集状态: TMDB ID {tmdb_id} 找到 {len(matched_items)} 个匹配项")
        
        seasons_status = {}
        
        for series_item in matched_items:
            series_id = series_item.get('Id')
            series_name = series_item.get('Name', '')
            logger.info(f"Emby 查询剧集状态: 正在查询剧集 '{series_name}' (ID: {series_id})")
            
            seasons = self.get_seasons(series_id)
            if not seasons:
                logger.info(f"Emby 查询剧集状态: 剧集 '{series_name}' 没有找到季信息")
                continue
            
            for season in seasons:
                season_number = season.get('IndexNumber')
                if season_number is None:
                    continue
                
                episodes = self.get_episodes(series_id, season['Id'])
                if not episodes:
                    continue
                
                if season_number not in seasons_status:
                    seasons_status[season_number] = {
                        'exists': True,
                        'total_episodes': len(episodes),
                        'series_name': series_name
                    }
                    logger.info(f"Emby 查询剧集状态: 剧集 '{series_name}' 第 {season_number} 季有 {len(episodes)} 集")
        
        result = {
            'exists': True,
            'series_name': series_result['matched_items'][0].get('Name', '') if series_result['matched_items'] else '',
            'seasons': seasons_status
        }
        
        logger.info(f"Emby 查询剧集状态: 完成，共 {len(seasons_status)} 季")
        return result

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

    def fetch_all_items_brief(self) -> List[Dict]:
        """
        获取 Emby 库中所有媒体项的简要信息 (ID, TMDB ID, 类型, 标题)。
        用于构建索引。
        """
        result = self._make_request('GET', '/Items', params={
            'IncludeItemTypes': 'Movie,Series',
            'Recursive': 'true',
            'Fields': 'ProviderIds',
            'EnableUserData': 'false'
        })
        if not result or 'Items' not in result:
            logger.warning("Emby fetch_all_items_brief: 未获取到任何条目")
            return []

        brief_items = []
        for item in result['Items']:
            provider_ids = item.get('ProviderIds', {})
            tmdb_id = provider_ids.get('Tmdb')
            if tmdb_id:
                brief_items.append({
                    'emby_item_id': item.get('Id', ''),
                    'tmdb_id': str(tmdb_id),
                    'media_type': item.get('Type', ''),  # "Movie" 或 "Series"
                    'title': item.get('Name', ''),
                })
        logger.info(f"Emby fetch_all_items_brief: 共获取 {len(brief_items)} 个带 TMDB ID 的条目")
        return brief_items

    def search_by_title(self, title: str, media_type: str = 'all') -> Optional[Dict]:
        """
        通过标题搜索 Emby 库，返回匹配的媒体项。
        """
        include_types = 'Movie,Series' if media_type == 'all' else media_type
        result = self._make_request('GET', '/Items', params={
            'IncludeItemTypes': include_types,
            'Recursive': 'true',
            'Fields': 'ProviderIds,Path,MediaSources',
            'SearchTerm': title,
            'EnableUserData': 'false'
        })
        if not result or 'Items' not in result:
            return None
        return {'Items': result['Items'], 'TotalRecordCount': result.get('TotalRecordCount', 0)}

    def test_connection(self) -> bool:
        result = self._make_request('GET', '/System/Info')
        return result is not None


_emby_client_instance = None


def get_emby_client() -> EmbyClient:
    global _emby_client_instance
    if _emby_client_instance is None:
        _emby_client_instance = EmbyClient()
    return _emby_client_instance
