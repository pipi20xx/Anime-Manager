import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlmodel import select, and_
from models import Subscription, Rule, FeedItem, DownloadHistory, Feed, FilterRule, QualityProfile, SubscribedEpisode
from recognition.recognizer import MovieRecognizer
from rss_core.field_match import check_conditions
from config_manager import ConfigManager
from rss_core.subscription_manager import SubscriptionManager
from rss_core.manager import RssManager
from rss_core.matcher import Matcher
from logger import log_audit
from database import db
from notification import notification_manager
from task_history import log_task
import re

logger = logging.getLogger("SubscriptionMatcher")

class SubscriptionMatcher:
    @staticmethod
    def _check_rule_match(item: Dict, rule: FilterRule) -> bool:
        """
        检查条目是否符合某个 FilterRule。
        媒体规格字段走 recognition_engine.field_match 的统一策略匹配,
        这里只处理规则特有的 must_contain / must_not_contain 正则。
        """
        c = rule.conditions
        if not c: return True

        if not check_conditions(c, item): return False

        # 优先使用原始标题进行正则匹配，如果不存在则回退到 tmdb_title
        match_title = item.get("rss_title") or item.get("title", "")
        
        # 2. 正则/关键词 (模糊匹配)
        if c.get("must_contain"):
            try:
                if not re.search(c["must_contain"], match_title, re.I):
                    return False
            except: pass
            
        if c.get("must_not_contain"):
            try:
                if re.search(c["must_not_contain"], match_title, re.I):
                    return False
            except: pass
                
        return True

    @staticmethod
    def _calculate_score(item_data: Dict, profile: QualityProfile, rules_map: Dict[int, FilterRule]) -> int:
        """根据策略计算分数 (返回匹配到的最高洗版分数)"""
        if not profile or not profile.rules_config:
            return 0
        
        # rules_config 是有序列表，靠前的优先级高
        for rule_config in profile.rules_config:
            rule_id = rule_config.get("rule_id")
            score = rule_config.get("score", 0)
            
            rule = rules_map.get(rule_id)
            if not rule: continue
            
            if SubscriptionMatcher._check_rule_match(item_data, rule):
                return score
                
        return 0

    @staticmethod
    async def load_tmdb_block_map() -> Tuple[Dict[Tuple[str, str], Dict[str, Any]], List[Dict[str, Any]]]:
        """
        一次性载入 TMDB 屏蔽列表，供单轮任务内逐条目查表，避免每条目一次数据库查询。
        返回 (精确表, 全局条件表)：
        - 精确表键为 (tmdb_id, media_type)，锚定具体作品；
        - tmdb_id 留空的条目进入全局条件表，对所有作品按规格条件匹配（如屏蔽某制作组全部发布）。
        均为普通 dict/list，不受会话生命周期影响。
        """
        from models import TmdbBlocklist
        block_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        global_blocks: List[Dict[str, Any]] = []
        async with db.session_scope():
            entries = await db.all(TmdbBlocklist, select(TmdbBlocklist))
        for e in entries:
            payload = {
                "tmdb_id": str(e.tmdb_id or "").strip(),
                "media_type": e.media_type or "tv",
                "conditions": e.conditions or {},
            }
            if payload["tmdb_id"]:
                block_map[(payload["tmdb_id"], payload["media_type"])] = payload
            else:
                global_blocks.append(payload)
        return block_map, global_blocks

    @staticmethod
    def match_tmdb_block(block_map: Dict[Tuple[str, str], Dict[str, Any]],
                         global_blocks: List[Dict[str, Any]],
                         tmdb_id: Optional[str], media_type: str, meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        查找命中的屏蔽条目。优先查精确表（锚定作品）；未命中再过全局条件表
        （tmdb_id 留空的条目，media_type=all 时对剧集/电影都生效）。
        带 conditions 的条目走 field_match 统一匹配，条件不满足视为未命中。
        """
        if tmdb_id:
            entry = block_map.get((str(tmdb_id), media_type))
            if entry:
                conditions = entry.get("conditions") or {}
                if not conditions or check_conditions(conditions, meta or {}):
                    return entry
        for entry in global_blocks or []:
            if entry.get("media_type") not in (None, "", "all", media_type):
                continue
            conditions = entry.get("conditions") or {}
            if conditions and check_conditions(conditions, meta or {}):
                return entry
        return None

    @staticmethod
    def describe_block_conditions(entry: Dict[str, Any]) -> str:
        conditions = entry.get("conditions") or {}
        cond = ", ".join(f"{k}={v}" for k, v in conditions.items() if str(v or "").strip())
        if not cond:
            return ""
        prefix = "全局条件" if not entry.get("tmdb_id") else "条件"
        return f"{prefix}: {cond}"

    @staticmethod
    async def apply_tmdb_block(entry: Dict[str, Any], meta: Dict[str, Any], guid: str, title: str,
                               feed_id: Optional[int] = None, description: Optional[str] = None):
        """
        屏蔽命中后的统一动作（幂等，已有 TmdbBlocked 记录则跳过）：
        - 无规格条件（整部作品级）：同步把启用订阅的对应集标记已下载，订阅不再追；
        - 带规格条件（资源级）：只拦本条资源，同作品其他组的资源照常匹配；
        最后写 state=TmdbBlocked 的下载历史（rule_id 为空 = 全局），
        使后续订阅匹配与规则匹配两个阶段都按"已下载"跳过。
        """
        from models import DownloadHistory
        async with db.session_scope():
            dup_stmt = select(DownloadHistory).where(
                DownloadHistory.guid == guid,
                DownloadHistory.state == "TmdbBlocked"
            )
            if await db.first(DownloadHistory, dup_stmt) is not None:
                return

        if not (entry.get("conditions") or {}) and entry.get("tmdb_id"):
            # 仅整部作品级屏蔽（锚定具体作品且无规格条件）才标记订阅；
            # 全局条件条目与带条件的条目都是资源级，不动订阅状态。
            _tmdb = entry["tmdb_id"]
            _mtype = entry["media_type"]
            _season = meta.get("season")
            _episode = meta.get("episode")
            async with db.session_scope():
                _sub_stmt = select(Subscription).where(
                    Subscription.tmdb_id == _tmdb,
                    Subscription.media_type == _mtype,
                    Subscription.enabled == True
                )
                _subs = await db.all(Subscription, _sub_stmt)
                for _sub in _subs:
                    if _mtype == "tv":
                        try:
                            _ep_num = int(_episode)
                            if _sub.season != 0 and _sub.season != _season:
                                continue
                            if _sub.start_episode > 0 and _ep_num < _sub.start_episode:
                                continue
                            if _sub.end_episode > 0 and _ep_num > _sub.end_episode:
                                continue
                        except:
                            continue
                        await SubscriptionManager.add_subscribed_episode(
                            _sub.tmdb_id, _sub.media_type, _season, _ep_num,
                            title=f"TMDB屏蔽列表: {title}"
                        )
                        if _sub.end_episode > 0:
                            await SubscriptionManager.check_and_complete_subscription(_sub.id)
                    else:
                        await SubscriptionManager.add_subscribed_episode(
                            _sub.tmdb_id, _sub.media_type, 0, 0,
                            title=f"TMDB屏蔽列表: {title}"
                        )

        async with db.session_scope():
            hist = DownloadHistory(
                guid=guid,
                title=title,
                description=description,
                feed_id=feed_id,
                download_client_id=None,
                info_hash=None,
                state="TmdbBlocked"
            )
            await RssManager.add_history(hist)

    @staticmethod
    async def recognize_items(entries: List[Dict], retry_failed: bool = False, task_id: str = None) -> int:
        """
        对条目进行识别。
        返回本次成功新识别的条目数量。
        """
        config = ConfigManager.get_config()
        if not config.get("tmdb_api_key"): return 0

        global_anime_prio = config.get("anime_priority", True)
        bgm_prio = config.get("bangumi_priority", False)
        bgm_failover = config.get("bangumi_failover", True)

        # 缓存 feeds 配置，减少数据库查询
        feeds_cache = {}
        # 屏蔽列表整轮载入一次（全局，不受订阅源开关控制）
        block_map, global_blocks = await SubscriptionMatcher.load_tmdb_block_map()
        recognized_count = 0

        for entry in entries:
            guid = entry['guid']
            title = entry['title']
            
            # [Fix] 1. 查询阶段：使用短事务
            db_item = None
            feed_anime_prio = global_anime_prio
            feed_check_emby = False
            feed_batch_enhance = False
            
            async with db.session_scope():
                stmt = select(FeedItem).where(FeedItem.guid == guid)
                db_item = await db.first(FeedItem, stmt)
                
                if db_item:
                    if db_item.feed_id:
                        if db_item.feed_id not in feeds_cache:
                            feed = await db.get(Feed, db_item.feed_id)
                            feeds_cache[db_item.feed_id] = {
                                'anime_priority': feed.anime_priority if feed else global_anime_prio,
                                'check_emby_exists': feed.check_emby_exists if feed else False,
                                'batch_enhance': feed.batch_enhance if feed else False
                            }
                        feed_anime_prio = feeds_cache[db_item.feed_id]['anime_priority']
                        feed_check_emby = feeds_cache[db_item.feed_id]['check_emby_exists']
                        feed_batch_enhance = feeds_cache[db_item.feed_id]['batch_enhance']

            if not db_item: continue

            # 逻辑拆分
            is_failed = db_item.recognition_done and (not db_item.tmdb_id or db_item.tmdb_id.lower() == "none")
            
            should_process = False
            if retry_failed:
                if is_failed: should_process = True
            else:
                if not db_item.recognition_done: should_process = True
            
            if not should_process: continue

            try:
                result, recog_logs = await MovieRecognizer.recognize_full(
                    title, force_filename=True,
                    anime_priority=feed_anime_prio, bangumi_priority=bgm_prio,
                    bangumi_failover=bgm_failover,
                    batch_enhancement=True,
                    description=db_item.description if feed_batch_enhance else None
                )
                
                recog_task_id = None
                try:
                    from task_history import start_task as _start_task, log_task as _log_task, finish_task as _finish_task
                    import uuid as _uuid
                    recog_task_id = f"recog_{_uuid.uuid4().hex[:12]}"
                    await _start_task(recog_task_id, "识别", f"[识别] {title}")
                    for log_msg in recog_logs:
                        level = "ERROR" if "❌" in log_msg or "[ERROR]" in log_msg else "WARN" if "⚠️" in log_msg else "INFO"
                        await _log_task(recog_task_id, log_msg, level)
                except Exception:
                    recog_task_id = None
                
                if result.get("success") and result.get("final_result"):
                    final_result = result["final_result"]
                    await RssManager.update_item_recognition(db_item.id, final_result)
                    recognized_count += 1
                    
                    _title = final_result.get('title', '')
                    _season = final_result.get('season', '')
                    _episode = final_result.get('episode', '')
                    _tmdb = final_result.get('tmdb_id', '')
                    ep_info = f"S{_season}E{_episode}" if _season and _episode else ""
                    
                    if task_id:
                        from task_history import log_task as _log_task
                        await _log_task(task_id, f"🧠 识别: {title}")
                        await _log_task(task_id, f"   → {_title} {ep_info} (TMDB: {_tmdb})")
                    
                    if recog_task_id:
                        try:
                            stats = {"success": 1, "title": _title, "tmdb_id": _tmdb, "category": final_result.get("category"), "season": _season, "episode": _episode}
                            await _finish_task(recog_task_id, "completed", stats=stats)
                        except Exception:
                            pass

                    # TMDB 主动屏蔽检查（全局，不受订阅源开关控制）：
                    # 用户手动填入 tmdb_id + 类型（可选规格条件如制作组），识别命中后直接标记已下载，
                    # 阻止后续追剧订阅与下载规则处理；标记 state=TmdbBlocked 以区别于 Emby。
                    # 带规格条件的条目为资源级屏蔽：只拦满足条件的资源，不标记订阅；
                    # 无条件为整部作品级屏蔽：同时标记订阅对应集已下载。
                    _tmdb_blocked = False
                    if final_result.get("tmdb_id"):
                        _block_type = final_result.get("category")
                        _block_media = "tv" if _block_type == "剧集" else "movie"
                        _block_entry = SubscriptionMatcher.match_tmdb_block(
                            block_map, global_blocks, final_result.get("tmdb_id"), _block_media, final_result
                        )
                        if _block_entry:
                            _tmdb_blocked = True
                            _block_cond = SubscriptionMatcher.describe_block_conditions(_block_entry)
                            logger.debug(f"TMDB屏蔽列表命中: {final_result.get('title')} (tmdb_id={final_result.get('tmdb_id')})")
                            if task_id:
                                from task_history import log_task as _log_task
                                _cond_suffix = f"（{_block_cond}）" if _block_cond else ""
                                await _log_task(task_id, f"🚫 TMDB屏蔽列表命中{_cond_suffix}，标记已下载: {final_result.get('title')} S{final_result.get('season')}E{final_result.get('episode')}")
                            await SubscriptionMatcher.apply_tmdb_block(
                                _block_entry, final_result, guid, title,
                                feed_id=db_item.feed_id, description=entry.get('description')
                            )

                    # Emby 库存在检查（受订阅源开关控制）：开启时若 Emby 已有则标记已下载，
                    # 阻止后续追剧订阅与下载规则重复处理；未命中或开关关闭则放行。
                    if not _tmdb_blocked and feed_check_emby and final_result.get("tmdb_id"):
                        from emby_client import get_emby_client, EmbyAPIError
                        from emby_index_service import wrap_emby_with_index
                        from task_history import log_task as _log_task
                        _emby_client = get_emby_client()
                        if _emby_client:
                            try:
                                _emby_tmdb = final_result.get("tmdb_id")
                                _emby_type = final_result.get("category")
                                _emby_season = final_result.get("season")
                                _emby_episode = final_result.get("episode")

                                _cleanup = await wrap_emby_with_index(_emby_client, _emby_tmdb, _emby_type)
                                _emby_exists = False
                                try:
                                    if _emby_type == "剧集":
                                        if _emby_season is not None and _emby_episode:
                                            _emby_exists = await asyncio.to_thread(_emby_client.check_episode_exists, _emby_tmdb, _emby_season, _emby_episode)
                                    elif _emby_type == "电影":
                                        _emby_exists = await asyncio.to_thread(_emby_client.check_movie_exists, _emby_tmdb)
                                except EmbyAPIError as e:
                                    logger.warning(f"Emby API 不可用，无法确认库状态，按未入库继续处理: {e}")
                                finally:
                                    await _cleanup()

                                if _emby_exists:
                                    logger.debug(f"Emby 已存在，标记已下载: {final_result.get('title')} S{_emby_season}E{_emby_episode}")
                                    if task_id:
                                        await _log_task(task_id, f"✅ Emby已存在，标记已下载: {final_result.get('title')} S{_emby_season}E{_emby_episode}")

                                    # 标记订阅已下载 + 写下载历史，阻止追剧订阅与下载规则重复处理
                                    async with db.session_scope():
                                        from models import Subscription
                                        _sub_stmt = select(Subscription).where(
                                            Subscription.tmdb_id == str(_emby_tmdb),
                                            Subscription.media_type == ("tv" if _emby_type == "剧集" else "movie"),
                                            Subscription.enabled == True
                                        )
                                        _emby_subs = await db.all(Subscription, _sub_stmt)
                                        for _emby_sub in _emby_subs:
                                            if _emby_type == "剧集":
                                                try:
                                                    _ep_num = int(_emby_episode)
                                                    if _emby_sub.season != 0 and _emby_sub.season != _emby_season:
                                                        continue
                                                    if _emby_sub.start_episode > 0 and _ep_num < _emby_sub.start_episode:
                                                        continue
                                                    if _emby_sub.end_episode > 0 and _ep_num > _emby_sub.end_episode:
                                                        continue
                                                except:
                                                    continue
                                                await SubscriptionManager.add_subscribed_episode(
                                                    _emby_sub.tmdb_id, _emby_sub.media_type, _emby_season, _ep_num,
                                                    title=f"Emby库已存在: {title}"
                                                )
                                                if _emby_sub.end_episode > 0:
                                                    await SubscriptionManager.check_and_complete_subscription(_emby_sub.id)
                                            elif _emby_type == "电影":
                                                await SubscriptionManager.add_subscribed_episode(
                                                    _emby_sub.tmdb_id, _emby_sub.media_type, 0, 0,
                                                    title=f"Emby库已存在: {title}"
                                                )

                                    from models import DownloadHistory
                                    async with db.session_scope():
                                        _emby_hist = DownloadHistory(
                                            guid=guid,
                                            title=title,
                                            description=entry.get('description'),
                                            feed_id=db_item.feed_id,
                                            download_client_id=None,
                                            info_hash=None,
                                            state="EmbyExists"
                                        )
                                        await RssManager.add_history(_emby_hist)
                                else:
                                    logger.debug(f"Emby 未找到: {final_result.get('title')} S{_emby_season}E{_emby_episode}")
                                    if task_id:
                                        await _log_task(task_id, f"❌ Emby未找到，继续后续流程: {final_result.get('title')} S{_emby_season}E{_emby_episode}")
                            except Exception as e:
                                logger.error(f"Emby 检查异常: {e}")
                                import traceback
                                logger.error(traceback.format_exc())
                                if task_id:
                                    await _log_task(task_id, f"⚠️ Emby检查异常: {final_result.get('title')} - {str(e)}", "WARN")
                        else:
                            logger.warning("⚠️ Emby 客户端未初始化，跳过检查")
                            if task_id:
                                await _log_task(task_id, "⚠️ Emby 客户端未初始化，跳过检查", "WARN")
                else:
                    if recog_task_id:
                        try:
                            await _finish_task(recog_task_id, "error", stats={"errors": 1})
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"识别条目 '{title}' 失败: {e}")
                if task_id:
                    from task_history import log_task as _log_task
                    await _log_task(task_id, f"⚠️ 识别失败: {title}", "WARN")
                if recog_task_id:
                    try:
                        await _log_task(recog_task_id, f"❌ 识别异常: {str(e)}", "ERROR")
                        await _finish_task(recog_task_id, "error", stats={"errors": 1, "message": str(e)})
                    except Exception:
                        pass
        
        return recognized_count

    @staticmethod
    async def match_and_download(entries: List[Dict], subscriptions: List[Subscription], task_id: str = None) -> int:
        """
        基于识别结果进行订阅匹配 (支持优先级与洗版)
        """
        if not subscriptions: return 0

        # 屏蔽列表整轮载入一次，用于回溯拦截"识别之后才加入屏蔽"的条目
        block_map, global_blocks = await SubscriptionMatcher.load_tmdb_block_map()

        rules_map = {}
        profiles_map = {}
        async with db.session_scope():
            all_rules = await db.all(FilterRule)
            rules_map = {r.id: r for r in all_rules}
            
            all_profiles = await db.all(QualityProfile)
            profiles_map = {p.id: p for p in all_profiles}

        matched_count = 0
        skipped_count = 0
        feeds_cache = {}
        
        for entry in entries:
            guid = entry['guid']
            title = entry['title']
            
            if await RssManager.is_blacklisted(guid, title=title):
                logger.debug(f"订阅模块：跳过黑名单条目: {title}")
                skipped_count += 1
                continue

            # 已下载（含 TMDB 屏蔽/Emby 标记，state!=Failed）也跳过，避免追剧订阅重复处理；
            # 失败记录不计入（is_downloaded 已排除 Failed），不影响失败重试
            if await RssManager.is_downloaded(guid, title=title):
                logger.debug(f"订阅模块：跳过已下载条目: {title}")
                skipped_count += 1
                continue
            
            # [Fix] 2. 获取条目数据 (使用短事务)
            db_item = None
            async with db.session_scope():
                stmt = select(FeedItem).where(FeedItem.guid == guid)
                db_item = await db.first(FeedItem, stmt)
                
                if db_item and db_item.tmdb_id:
                    item_data = {
                        "tmdb_id": db_item.tmdb_id,
                        "tmdb_title": db_item.tmdb_title,
                        "title": db_item.title,
                        "media_type": db_item.media_type,
                        "season": db_item.season,
                        "episode": db_item.episode,
                        "resolution": db_item.resolution,
                        "team": db_item.team,
                        "source": db_item.source,
                        "video_encode": db_item.video_encode,
                        "audio_encode": db_item.audio_encode,
                        "video_effect": db_item.video_effect,
                        "subtitle": db_item.subtitle,
                        "platform": db_item.platform,
                        "feed_id": db_item.feed_id,
                        "id": db_item.id
                    }
                    db_item = type('obj', (object,), item_data)
                else:
                    db_item = None

            if not db_item or not db_item.tmdb_id:
                continue

            # TMDB 屏蔽回溯检查：识别阶段后才加入屏蔽的条目在这里补拦。
            # 新识别条目已在 recognize_items 阶段写过 TmdbBlocked 历史，
            # 会被上方 is_downloaded 拦下，通常不会走到这里。
            _block_entry = SubscriptionMatcher.match_tmdb_block(
                block_map, global_blocks, str(db_item.tmdb_id), db_item.media_type, item_data
            )
            if _block_entry:
                _block_cond = SubscriptionMatcher.describe_block_conditions(_block_entry)
                logger.debug(f"TMDB屏蔽列表命中(回溯): {title} (tmdb_id={db_item.tmdb_id})")
                if task_id:
                    _cond_suffix = f"（{_block_cond}）" if _block_cond else ""
                    await log_task(task_id, f"🚫 TMDB屏蔽列表命中{_cond_suffix}，标记已下载: {title}")
                await SubscriptionMatcher.apply_tmdb_block(
                    _block_entry, item_data, guid, title,
                    feed_id=db_item.feed_id, description=entry.get('description')
                )
                skipped_count += 1
                continue

            current_feed_id = str(db_item.feed_id)

            # 查询该条目所属订阅源是否开启 Emby 检查
            feed_check_emby = False
            if db_item.feed_id:
                if db_item.feed_id not in feeds_cache:
                    async with db.session_scope():
                        _feed = await db.get(Feed, db_item.feed_id)
                        feeds_cache[db_item.feed_id] = _feed.check_emby_exists if _feed else False
                feed_check_emby = feeds_cache[db_item.feed_id]

            recognition_data = {
                "tmdb_id": db_item.tmdb_id, "title": db_item.tmdb_title,
                "rss_title": title,
                "category": "电影" if db_item.media_type == "movie" else "剧集",
                "season": db_item.season, "episode": db_item.episode,
                "resolution": db_item.resolution, "team": db_item.team,
                "source": db_item.source, "video_encode": db_item.video_encode,
                "audio_encode": db_item.audio_encode, "video_effect": db_item.video_effect,
                "subtitle": db_item.subtitle, "platform": db_item.platform
            }

            tmdb_id = str(db_item.tmdb_id)
            m_type = db_item.media_type
            
            try:
                season = db_item.season if db_item.season is not None else 1
                ep_raw = str(db_item.episode or "")
                if "-" in ep_raw:
                    episode, is_batch, end_ep = int(ep_raw.split("-")[0]), True, int(ep_raw.split("-")[1])
                else:
                    episode, is_batch, end_ep = (int(ep_raw) if ep_raw else None), False, None
            except: continue

            for sub in subscriptions:
                if sub.target_feeds and sub.target_feeds.strip():
                    target_ids = [fid.strip() for fid in sub.target_feeds.split(',') if fid.strip()]
                    if current_feed_id not in target_ids:
                        continue

                if str(sub.tmdb_id) == tmdb_id and sub.media_type == m_type:
                    err = ""
                    if sub.media_type == "tv":
                        if episode is None: 
                            err = "未识别到集号"
                        elif sub.season != 0 and sub.season != season: 
                            err = f"季号 S{season} 不匹配(订阅 S{sub.season})"
                        elif sub.start_episode > 0 and episode < sub.start_episode and not is_batch: 
                            err = f"集号 {episode} 低于订阅范围(起: {sub.start_episode})"
                        elif sub.end_episode > 0 and episode > sub.end_episode: 
                            err = f"集号 {episode} 超过订阅范围(止: {sub.end_episode})"
                    
                    if err:
                        continue
                        
                    should_download = False
                    current_score = 0
                    is_upgrade = False
                    
                    profile = profiles_map.get(sub.quality_profile_id)
                    if profile:
                        current_score = SubscriptionMatcher._calculate_score(recognition_data, profile, rules_map)
                    
                    if sub.media_type == "tv":
                        prev_record = await SubscriptionManager.get_episode_record(sub.tmdb_id, sub.media_type, season, episode)
                    else:
                        prev_record = await SubscriptionManager.get_episode_record(sub.tmdb_id, sub.media_type, 0, 0)
                        
                    if prev_record:
                        if profile and profile.upgrade_allowed:
                            prev_score = prev_record.quality_score or 0
                            cutoff = profile.cutoff_score or 999999
                            
                            if prev_score >= cutoff:
                                logger.info(f"[{sub.title}] 旧资源得分 {prev_score} 已达标(cutoff={cutoff})，跳过洗版: {title}")
                                continue
                            
                            if current_score > prev_score:
                                is_upgrade = True
                                should_download = True
                                logger.info(f"[{sub.title}] 触发洗版! 新分({current_score}) > 旧分({prev_score}) - {title}")
                            else:
                                logger.info(f"[{sub.title}] 新资源得分 {current_score} 不高于旧资源 {prev_score}，不洗版: {title}")
                                skipped_count += 1
                                continue
                        else:
                            skipped_count += 1
                            continue
                    else:
                        should_download = True

                    if not should_download:
                        continue

                    filter_ok, filter_err = SubscriptionManager.check_subscription_filter(sub, recognition_data, title)
                    if not filter_ok:
                        logger.info(f"订阅 '{sub.title}' 过滤未命中: {title} (原因: {filter_err})")
                        continue

                    # Emby 库存在检查（受订阅源开关控制）
                    if feed_check_emby:
                        from emby_client import get_emby_client, EmbyAPIError
                        from emby_index_service import wrap_emby_with_index
                        emby_client = get_emby_client()
                        if emby_client:
                            try:
                                cleanup = await wrap_emby_with_index(emby_client, tmdb_id, m_type)
                                try:
                                    exists_in_emby = False
                                    if m_type == "tv":
                                        exists_in_emby = await asyncio.to_thread(emby_client.check_episode_exists, tmdb_id, season, episode)
                                    elif m_type == "movie":
                                        exists_in_emby = await asyncio.to_thread(emby_client.check_movie_exists, tmdb_id)
                                except EmbyAPIError as e:
                                    logger.warning(f"Emby API 不可用，无法确认库状态，按未入库继续处理: {e}")
                                finally:
                                    await cleanup()
                                if exists_in_emby:
                                    logger.info(f"订阅 '{sub.title}' Emby已存在，跳过下载: {title} S{season}E{episode}")
                                    await SubscriptionManager.add_subscribed_episode(
                                        sub.tmdb_id, sub.media_type, season, episode,
                                        title=f"Emby库已存在: {title}"
                                    )
                                    # 记录历史防止后续重复处理
                                    async with db.session_scope():
                                        history = DownloadHistory(
                                            guid=guid, title=title,
                                            description=entry.get('description'),
                                            feed_id=db_item.feed_id,
                                            download_client_id=None, info_hash=None,
                                            state="EmbyExists"
                                        )
                                        await RssManager.add_history(history)

                                    if sub.media_type == "tv" and sub.end_episode > 0:
                                        await SubscriptionManager.check_and_complete_subscription(sub.id)

                                    continue
                            except Exception as e:
                                logger.warning(f"订阅 '{sub.title}' Emby检查异常，继续下载: {e}")

                    temp_rule = Rule(
                        name=f"Sub:{sub.title}", target_client_id=sub.target_client_id,
                        save_path=sub.save_path, category=sub.category, enabled=True
                    )
                    
                    action_log = "洗版" if is_upgrade else "命中"
                    logger.info(f"订阅{action_log}: [{sub.title}] (Score: {current_score}) -> {title}")
                    
                    success, info_hash, error_msg = await Matcher.download({'title': title, 'link': entry['link'], 'guid': guid, 'fallback_link': entry.get('fallback_link')}, temp_rule)
                    
                    if success:
                        matched_count += 1
                        if sub.media_type == "tv":
                            if is_batch and end_ep:
                                for ep_num in range(episode, end_ep + 1):
                                    await SubscriptionManager.add_subscribed_episode(
                                        sub.tmdb_id, sub.media_type, season, ep_num, 
                                        title=title, info_hash=info_hash, 
                                        quality_score=current_score, profile_id=sub.quality_profile_id
                                    )
                            else:
                                await SubscriptionManager.add_subscribed_episode(
                                    sub.tmdb_id, sub.media_type, season, episode, 
                                    title=title, info_hash=info_hash,
                                    quality_score=current_score, profile_id=sub.quality_profile_id
                                )
                        else:
                            await SubscriptionManager.add_subscribed_episode(
                                sub.tmdb_id, sub.media_type, 0, 0, 
                                title=title, info_hash=info_hash,
                                quality_score=current_score, profile_id=sub.quality_profile_id
                            )
                        
                        log_audit("订阅", action_log, f"订阅 '{sub.title}' 匹配并推送成功: {title} (Score: {current_score})")
                        
                        if task_id:
                            action_icon = "🔄" if is_upgrade else "📺"
                            await log_task(task_id, f"    {action_icon} [{sub.title}] → {title}")
                        
                        await notification_manager.notify_sub_matched(
                            sub=sub,
                            item=db_item 
                        )
                        
                        if sub.media_type == "tv" and sub.end_episode > 0:
                            await SubscriptionManager.check_and_complete_subscription(sub.id)

                        break
                    else:
                        logger.error(f"订阅匹配成功但推送失败: {title} - {error_msg}")
                        log_audit("订阅", "推送失败", f"订阅 '{sub.title}' 推送至客户端失败: {title}", level="ERROR")
                        if task_id:
                            await log_task(task_id, f"    ❌ [{sub.title}] 推送失败: {title} - {error_msg}", "ERROR")
                        
                        from datetime import datetime
                        config = ConfigManager.get_config()
                        max_fail_count = config.get("download_max_fail_count", 3)
                        
                        existing = await RssManager.get_fail_history(guid, None)
                        if existing:
                            existing.fail_count += 1
                            existing.fail_reason = error_msg
                            existing.updated_at = datetime.now()
                            await db.save(existing)
                            
                            if existing.fail_count >= max_fail_count:
                                from models import Blacklist
                                bl_entry = Blacklist(
                                    guid=guid,
                                    title=title,
                                    reason=f"download_failed_{existing.fail_count}_times: {error_msg}"
                                )
                                await db.save(bl_entry)
                                logger.info(f"🚫 资源 {title} 失败 {existing.fail_count} 次，已加入黑名单")
                                if task_id:
                                    await log_task(task_id, f"    🚫 [{sub.title}] 失败 {existing.fail_count} 次，已拉黑: {title} - {error_msg}")
                        else:
                            fail_history = DownloadHistory(
                                guid=guid,
                                title=title,
                                feed_id=db_item.feed_id if db_item else None,
                                state="Failed",
                                fail_count=1,
                                fail_reason=error_msg
                            )
                            await RssManager.add_history(fail_history)
                            logger.info(f"❌ 下载失败 (1/{max_fail_count}): {title} - {error_msg}")
                            if task_id:
                                await log_task(task_id, f"    ❌ [{sub.title}] 下载失败 (1/{max_fail_count}): {title} - {error_msg}")
        
        if task_id and skipped_count > 0:
            await log_task(task_id, f"    ⏩ 跳过 {skipped_count} 个已下载/黑名单订阅资源")
            
        return matched_count
