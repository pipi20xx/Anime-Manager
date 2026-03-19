import logging
from typing import List, Dict, Any, Optional, Tuple
from sqlmodel import select, and_
from models import Subscription, Rule, FeedItem, DownloadHistory, Feed, FilterRule, QualityProfile, SubscribedEpisode
from recognition.recognizer import MovieRecognizer
from config_manager import ConfigManager
from rss_core.subscription_manager import SubscriptionManager
from rss_core.manager import RssManager
from rss_core.matcher import Matcher
from logger import log_audit
from database import db
from notification import NotificationManager
import re

logger = logging.getLogger("SubscriptionMatcher")

class SubscriptionMatcher:
    @staticmethod
    def _check_rule_match(item: Dict, rule: FilterRule) -> bool:
        """检查条目是否符合某个 FilterRule (精确匹配)"""
        c = rule.conditions
        if not c: return True
        
        def match_exact(rule_key, item_key):
            """
            辅助函数：精确匹配，支持逗号分隔。
            例如 rule="WebDL, WebRip" vs item="WebDL" -> True
            """
            rule_val = c.get(rule_key)
            if not rule_val: return True # 规则未定义该字段限制 -> Pass
            
            item_val = item.get(item_key)
            if not item_val: return False # 规则有要求，但条目为空 -> Fail
            
            # 统一转小写比较
            targets = [t.strip().lower() for t in rule_val.split(',') if t.strip()]
            return str(item_val).strip().lower() in targets

        # 1. 核心字段精确匹配
        if not match_exact("resolution", "resolution"): return False
        if not match_exact("source", "source"): return False
        if not match_exact("team", "team"): return False
        if not match_exact("video_encode", "video_encode"): return False
        if not match_exact("audio_encode", "audio_encode"): return False
        if not match_exact("video_effect", "video_effect"): return False
        if not match_exact("subtitle", "subtitle"): return False
        if not match_exact("platform", "platform"): return False
        
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
        """根据策略计算分数 (返回匹配到的最高优先级分数)"""
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
    async def recognize_items(entries: List[Dict], retry_failed: bool = False) -> int:
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
        recognized_count = 0

        for entry in entries:
            guid = entry['guid']
            title = entry['title']
            
            # [Fix] 1. 查询阶段：使用短事务
            db_item = None
            feed_anime_prio = global_anime_prio
            feed_check_emby = False
            
            async with db.session_scope():
                stmt = select(FeedItem).where(FeedItem.guid == guid)
                db_item = await db.first(FeedItem, stmt)
                
                if db_item:
                    # 获取该条目所属订阅源的独立配置
                    if db_item.feed_id:
                        if db_item.feed_id not in feeds_cache:
                            feed = await db.get(Feed, db_item.feed_id)
                            feeds_cache[db_item.feed_id] = {
                                'anime_priority': feed.anime_priority if feed else global_anime_prio,
                                'check_emby_exists': feed.check_emby_exists if feed else False
                            }
                        feed_anime_prio = feeds_cache[db_item.feed_id]['anime_priority']
                        feed_check_emby = feeds_cache[db_item.feed_id]['check_emby_exists']

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
                # [Fix] 2. 识别阶段：无数据库事务，允许耗时操作
                result, _ = await MovieRecognizer.recognize_full(
                    title, force_filename=True,
                    anime_priority=feed_anime_prio, bangumi_priority=bgm_prio,
                    bangumi_failover=bgm_failover,
                    batch_enhancement=True, # RSS 识别场景默认开启合集增强
                    description=db_item.description
                )
                
                # [Fix] 3. 更新阶段：内部自带事务
                if result.get("success") and result.get("final_result"):
                    final_result = result["final_result"]
                    await RssManager.update_item_recognition(db_item.id, final_result)
                    recognized_count += 1
                    
                    # [New] Emby 检查 - 识别成功后立即检查 Emby 库
                    log_audit("RSS", "Emby检查", f"Emby检查状态: {'已启用' if feed_check_emby else '未启用'}")
                    
                    if feed_check_emby and final_result.get("tmdb_id"):
                        from emby_client import get_emby_client
                        emby_client = get_emby_client()
                        
                        log_audit("RSS", "Emby检查", f"开始检查 Emby 库 - 标题: {title}")
                        
                        if emby_client:
                            try:
                                tmdb_id = final_result.get("tmdb_id")
                                media_type = final_result.get("category")
                                season = final_result.get("season")
                                episode = final_result.get("episode")
                                
                                log_audit("RSS", "Emby检查", f"检查参数 - TMDB ID: {tmdb_id}, 类型: {media_type}, 季: {season}, 集: {episode}")
                                
                                exists_in_emby = False
                                if media_type == "剧集":
                                    if season is not None and episode:
                                        log_audit("RSS", "Emby检查", f"检查剧集是否存在: TMDB ID {tmdb_id}, S{season}E{episode}")
                                        exists_in_emby = emby_client.check_episode_exists(tmdb_id, season, episode)
                                    else:
                                        log_audit("RSS", "Emby检查", f"跳过剧集检查 - 缺少季集信息: 季={season}, 集={episode}")
                                elif media_type == "电影":
                                    log_audit("RSS", "Emby检查", f"检查电影是否存在: TMDB ID {tmdb_id}")
                                    exists_in_emby = emby_client.check_movie_exists(tmdb_id)
                                else:
                                    log_audit("RSS", "Emby检查", f"跳过检查 - 不支持的媒体类型: {media_type}")
                                
                                if exists_in_emby:
                                    log_audit("RSS", "Emby检查", f"✅ Emby库中已存在: {final_result.get('title')} - S{season}E{episode} (TMDB: {tmdb_id})")
                                    # 标记为已下载，添加到下载历史
                                    from models import DownloadHistory
                                    async with db.session_scope():
                                        history = DownloadHistory(
                                            guid=guid,
                                            title=title,
                                            description=entry.get('description'),
                                            feed_id=db_item.feed_id,
                                            download_client_id=None,
                                            info_hash=None
                                        )
                                        await RssManager.add_history(history)
                                else:
                                    log_audit("RSS", "Emby检查", f"❌ Emby库中未找到: {final_result.get('title')} - S{season}E{episode} (TMDB: {tmdb_id})")
                                    
                                    # 查找匹配的订阅并标记为已下载
                                    async with db.session_scope():
                                        from models import Subscription
                                        stmt = select(Subscription).where(
                                            Subscription.tmdb_id == str(tmdb_id),
                                            Subscription.media_type == ("tv" if media_type == "剧集" else "movie"),
                                            Subscription.enabled == True
                                        )
                                        subs = await db.all(Subscription, stmt)
                                        
                                        for sub in subs:
                                            # 检查是否在订阅范围内
                                            if media_type == "剧集":
                                                if sub.season != 0 and sub.season != season:
                                                    continue
                                                try:
                                                    ep_num = int(episode)
                                                    if sub.start_episode > 0 and ep_num < sub.start_episode:
                                                        continue
                                                    if sub.end_episode > 0 and ep_num > sub.end_episode:
                                                        continue
                                                except:
                                                    continue
                                                
                                                # 标记为已下载
                                                await SubscriptionManager.add_subscribed_episode(
                                                    sub.tmdb_id, sub.media_type, season, ep_num,
                                                    title=f"Emby库已存在: {title}"
                                                )
                                                log_audit("订阅", "Emby检查", f"订阅 '{sub.title}' Emby库中已存在，自动标记为已下载: {title}")
                                            elif media_type == "电影":
                                                await SubscriptionManager.add_subscribed_episode(
                                                    sub.tmdb_id, sub.media_type, 0, 0,
                                                    title=f"Emby库已存在: {title}"
                                                )
                                                log_audit("订阅", "Emby检查", f"订阅 '{sub.title}' Emby库中电影已存在，自动标记为已下载: {title}")
                            except Exception as e:
                                logger.error(f"Emby 检查异常: {e}")
                                import traceback
                                logger.error(traceback.format_exc())
                                log_audit("RSS", "Emby检查失败", f"Emby检查异常: {str(e)}", level="WARN")
                        else:
                            log_audit("RSS", "Emby检查", f"⚠️ 跳过 Emby 检查 - Emby 客户端未初始化（请检查 Emby 配置）")
                    else:
                        if not feed_check_emby:
                            log_audit("RSS", "Emby检查", f"⚠️ Emby 检查未启用，跳过检查")
                        if not final_result.get("tmdb_id"):
                            log_audit("RSS", "Emby检查", f"⚠️ 跳过 Emby 检查 - 识别结果缺少 TMDB ID")
            except Exception as e:
                logger.error(f"识别条目 '{title}' 失败: {e}")
        
        return recognized_count

    @staticmethod
    async def match_and_download(entries: List[Dict], subscriptions: List[Subscription], task_id: str = None) -> int:
        """
        基于识别结果进行订阅匹配 (支持优先级与洗版)
        """
        if not subscriptions: return 0

        rules_map = {}
        profiles_map = {}
        async with db.session_scope():
            all_rules = await db.all(FilterRule)
            rules_map = {r.id: r for r in all_rules}
            
            all_profiles = await db.all(QualityProfile)
            profiles_map = {p.id: p for p in all_profiles}

        matched_count = 0
        skipped_count = 0
        
        for entry in entries:
            guid = entry['guid']
            title = entry['title']
            
            if await RssManager.is_blacklisted(guid, title=title):
                logger.debug(f"订阅模块：跳过黑名单条目: {title}")
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
            
            current_feed_id = str(db_item.feed_id)
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

                    temp_rule = Rule(
                        name=f"Sub:{sub.title}", target_client_id=sub.target_client_id,
                        save_path=sub.save_path, category=sub.category, enabled=True
                    )
                    
                    action_log = "洗版" if is_upgrade else "命中"
                    logger.info(f"订阅{action_log}: [{sub.title}] (Score: {current_score}) -> {title}")
                    
                    success, info_hash = await Matcher.download({'title': title, 'link': entry['link'], 'guid': guid, 'fallback_link': entry.get('fallback_link')}, temp_rule)
                    
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
                            from task_history import log_task
                            action_icon = "🔄" if is_upgrade else "📺"
                            await log_task(task_id, f"    {action_icon} [{sub.title}] → {title}")
                        
                        await NotificationManager.push_sub_push_notification(
                            sub=sub,
                            item=db_item 
                        )
                        
                        if sub.media_type == "tv" and sub.end_episode > 0:
                            await SubscriptionManager.check_and_complete_subscription(sub.id)

                        break
                    else:
                        logger.error(f"订阅匹配成功但推送失败: {title}")
                        log_audit("订阅", "推送失败", f"订阅 '{sub.title}' 推送至客户端失败: {title}", level="ERROR")
        
        if task_id and skipped_count > 0:
            from task_history import log_task
            await log_task(task_id, f"    ⏩ 跳过 {skipped_count} 个已下载/黑名单订阅资源")
            
        return matched_count
