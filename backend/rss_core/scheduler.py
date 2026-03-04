import asyncio
import feedparser
import logging
import requests
import httpx
import time
import uuid
from typing import List, Dict
from sqlmodel import select, delete
from database import db
from models import Feed, FeedItem, Rule, DownloadHistory, Blacklist, SubscribedEpisode
from rss_core.manager import RssManager
from rss_core.subscription_manager import SubscriptionManager
from rss_core.subscription_matcher import SubscriptionMatcher
from .matcher import Matcher
from logger import log_audit
from notification import NotificationManager
from task_history import start_task, log_task, finish_task

logger = logging.getLogger("RssScheduler")

_last_auto_clear_time = 0

def normalize_guid(guid: str) -> str:
    """如果 GUID 过长（超过 500 字符），则使用 MD5 摘要以避免数据库索引溢出"""
    if not guid:
        return ""
    if len(guid) > 500:
        import hashlib
        return hashlib.md5(guid.encode()).hexdigest()
    return guid

async def refresh_all_feeds():
    global _last_auto_clear_time
    from config_manager import ConfigManager
    config = ConfigManager.get_config()
    
    # [Fix] 1. 自动清理：使用独立的短事务
    auto_clear = config.get("auto_clear_recognition", False)
    clear_interval_hours = config.get("auto_clear_interval", 24)
    
    if auto_clear:
        current_now = time.time()
        elapsed_seconds = current_now - _last_auto_clear_time
        interval_seconds = clear_interval_hours * 3600
        if _last_auto_clear_time == 0 or elapsed_seconds >= interval_seconds:
            async with db.session_scope() as session:
                logger.info(f"Scheduler: 触发定时自动清空缓存 ({clear_interval_hours}h)...")
                await session.execute(delete(FeedItem))
                await session.commit()
            _last_auto_clear_time = current_now

    logger.info("Scheduler: 开始 RSS 刷新任务...")
    
    task_id = f"rss_{uuid.uuid4().hex[:8]}"
    await start_task(task_id, "RSS", "RSS 全量刷新")
    await log_task(task_id, "🚀 开始执行 RSS 全量刷新")
    
    feeds = await RssManager.get_feeds()
    active_feeds = [f for f in feeds if f.enabled]
    if not active_feeds:
        logger.info("Scheduler: 没有启用的订阅源。")
        await log_task(task_id, "⚠️ 没有启用的订阅源")
        await finish_task(task_id, "completed", 0)
        return

    await log_task(task_id, f"📋 共 {len(active_feeds)} 个活跃订阅源")

    subscriptions = await SubscriptionManager.get_subscriptions(enabled_only=True)
    log_audit("RSS", "刷新", f"开始执行 RSS 自动刷新任务，共 {len(active_feeds)} 个源")

    total_new_items = 0
    total_matched = 0
    # [Fix] 3. 循环处理：每一步操作（保存、识别、匹配）内部均有独立事务管理，不再包裹大 session
    for feed in active_feeds:
        try:
            feed_name = feed.title or feed.url
            logger.info(f"正在刷新: {feed_name}")
            
            proxy = ConfigManager.get_proxy("rss")
            proxy_log = f" (使用代理: {proxy})" if proxy else ""
            await log_task(task_id, f"🔄 刷新: {feed_name}{proxy_log}")
            
            async with httpx.AsyncClient(proxy=proxy, timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(feed.url)
                resp.raise_for_status()
                content = resp.content

            parsed_feed = feedparser.parse(content)
            
            entries = []
            filtered_count = 0
            raw_count = len(parsed_feed.entries)
            
            for entry in parsed_feed.entries:
                item_title = entry.get('title', 'No Title')
                
                if not Matcher.check_match(
                    item_title, 
                    feed.include_keywords, 
                    feed.exclude_keywords, 
                    False
                ):
                    filtered_count += 1
                    continue

                link = entry.get('link', '')
                for enc in entry.get('enclosures', []):
                    if enc.get('href'):
                        link = enc.get('href')
                        break
                
                raw_guid = entry.get('id', link)
                fallback_link = None
                if raw_guid and raw_guid.startswith('http') and '.torrent' in raw_guid:
                    fallback_link = raw_guid
                
                entries.append({
                    'title': item_title,
                    'link': link,
                    'fallback_link': fallback_link,
                    'description': entry.get('summary', entry.get('description', '')),
                    'guid': normalize_guid(raw_guid),
                    'pub_date': entry.get('published', entry.get('updated', ''))
                })
            
            await RssManager.save_feed_items(feed.id, entries)
            total_new_items += len(entries)
            
            info_msg = f"  📥 发现 {len(entries)} 条可用资源"
            if filtered_count > 0:
                info_msg += f" (过滤了 {filtered_count} 条)"
            await log_task(task_id, info_msg)
            
            recog_count = await SubscriptionMatcher.recognize_items(entries)
            if recog_count > 0:
                await log_task(task_id, f"  🧠 智能识别: 成功识别 {recog_count} 个新项目")
            
            sub_count = 0
            if subscriptions and getattr(feed, 'for_subscription', True):
                sub_count = await SubscriptionMatcher.match_and_download(entries, subscriptions, task_id)
                if sub_count > 0:
                    await log_task(task_id, f"  📬 订阅匹配: 推送 {sub_count} 条")
            elif not getattr(feed, 'for_subscription', True):
                logger.debug(f"源 {feed_name} 已禁用订阅匹配，跳过。")
            
            rule_count = 0
            if getattr(feed, 'for_rules', True):
                rule_count = await run_auto_match_for_feed(feed.id, entries, task_id)
                if rule_count > 0:
                    await log_task(task_id, f"  📋 规则匹配: 推送 {rule_count} 条")
            else:
                logger.debug(f"源 {feed_name} 已禁用规则匹配，跳过。")
            
        except Exception as e:
            logger.error(f"刷新源 {feed.url} 失败: {e}")
            log_audit("RSS", "刷新失败", f"源 '{feed.title or feed.url}' 刷新出错", level="ERROR", details=str(e))
            await log_task(task_id, f"❌ 刷新失败: {feed.title or feed.url}", "ERROR")

    await log_task(task_id, f"🏁 完成，共处理 {total_new_items} 个条目")
    
    # 构建统计信息
    stats = {
        "total_feeds": len(active_feeds),
        "total_items": total_new_items,
        "total_matched": total_matched
    }
    
    await finish_task(task_id, "completed", total_new_items, stats)
    log_audit("RSS", "完成", f"RSS 刷新任务结束，本次共处理 {total_new_items} 个条目")
    logger.info("Scheduler: RSS 刷新任务结束。")

async def run_auto_match_for_feed(feed_id: int, entries: List[Dict], task_id: str = None):
    """对单个 Feed 的当前新鲜条目运行所有规则"""
    if not entries:
        return 0

    async with db.session_scope():
        rules = await RssManager.get_rules()
        enabled_rules = [r for r in rules if r.enabled]
        if not enabled_rules:
            return 0

        check_list = entries
        matched_count = 0
        skipped_count = 0

        for entry in check_list:
            guid = entry['guid']
            entry_title = entry.get('title')
            
            is_new_for_any_rule = False
            for rule in enabled_rules:
                if await RssManager.is_downloaded(guid, title=entry_title, rule_id=rule.id):
                    continue

                is_new_for_any_rule = True
                
                if rule.target_feeds:
                    target_ids = rule.target_feeds.split(',')
                    if str(feed_id) not in target_ids:
                        continue
                
                if Matcher.check_match(entry_title, rule.must_contain, rule.must_not_contain, rule.use_regex):
                    logger.info(f"匹配成功: [{rule.name}] -> {entry_title}")
                    success, info_hash = await Matcher.download(entry, rule)
                    if success:
                        matched_count += 1
                        from clients.manager import ClientManager
                        client = ClientManager.get_client(rule.target_client_id)
                        client_name = client.name if client else "未知下载器"
                        
                        log_audit("RSS", "规则匹配", f"规则 [{rule.name}] 命中并推送: {entry_title}", details={"client": client_name})
                        
                        if task_id:
                            from task_history import log_task
                            await log_task(task_id, f"    📌 [{rule.name}] → {entry_title}")

                        await NotificationManager.push_rule_push_notification(
                            title=entry_title,
                            rule_name=rule.name,
                            client_name=client_name
                        )

                        history = DownloadHistory(
                            guid=guid,
                            title=entry_title,
                            description=entry.get('description'),
                            feed_id=feed_id,
                            rule_id=rule.id,
                            download_client_id=rule.target_client_id,
                            info_hash=info_hash
                        )
                        await RssManager.add_history(history)
                        break
            
            if not is_new_for_any_rule:
                skipped_count += 1
        
        if task_id and skipped_count > 0:
            await log_task(task_id, f"    ⏩ 跳过 {skipped_count} 个已下载项目")
            
        return matched_count

async def check_stalled_downloads():
    """定期检查下载器中的死种任务，并在超时后自动清理并拉黑"""
    from config_manager import ConfigManager
    from clients.manager import ClientManager
    from rss_core.subscription_manager import SubscriptionManager
    from recognition.recognizer import MovieRecognizer
    
    config = ConfigManager.get_config()
    timeout_minutes = float(config.get("stalled_timeout_minutes", 0))
    if timeout_minutes <= 0:
        return

    task_id = f"stalled_{uuid.uuid4().hex[:8]}"
    await start_task(task_id, "死种清理", "死种超时检查")
    await log_task(task_id, f"🚀 开始检查死种下载 (超时阈值: {timeout_minutes}m)")

    logger.info(f"Scheduler: 开始检查死种下载 (超时阈值: {timeout_minutes}m)...")
    client_configs = ClientManager.get_all_clients()
    now = time.time()
    total_stalled = 0
    
    for conf in client_configs:
        try:
            client = ClientManager.get_client(conf.get('id'))
            if not client: continue
            
            from clients.qbittorrent import QBClient
            if not isinstance(client, QBClient):
                continue
            
            torrents = client.get_torrents() 
            if not torrents:
                await log_task(task_id, f"📁 {client.name}: 无任务")
                continue
            
            await log_task(task_id, f"📁 检查 {client.name}: {len(torrents)} 个任务")
            stalled_count = 0
            for t in torrents:
                name = t.get('name')
                state = t.get('state', '')
                progress = t.get('progress', 0)
                added_on = t.get('added_on', now)
                elapsed_minutes = (now - added_on) / 60
                
                logger.info(f"  → 任务: {name} | 进度: {progress*100:.1f}% | 状态: {state} | 已运行: {elapsed_minutes:.2f}m")
                
                if progress >= 1.0: continue
                
                if elapsed_minutes > timeout_minutes:
                    hash_str = str(t.get('hash', '')).lower()
                    await log_task(task_id, f"💀 发现死种: {name} (已运行 {elapsed_minutes:.0f}m, 进度 {progress*100:.0f}%)")
                    log_audit("监控", "死种清理", f"发现超时死种任务: {name}", details=f"已挂机 {elapsed_minutes:.1f} 分钟, 进度 {progress*100:.1f}%, 状态 {state}")
                    
                    async with db.session_scope() as session:
                        stmt_sub_find = select(SubscribedEpisode).where(SubscribedEpisode.info_hash == hash_str)
                        sub_item = await db.first(SubscribedEpisode, stmt_sub_find)
                        
                        final_guid = None
                        final_title = sub_item.title if sub_item else name

                        bl_entry = Blacklist(
                            info_hash=hash_str,
                            guid=final_guid,
                            title=final_title, 
                            reason=f"stalled_at_{elapsed_minutes:.1f}m"
                        )
                        await db.save(bl_entry, audit=False)
                        
                        await session.execute(delete(SubscribedEpisode).where(SubscribedEpisode.info_hash == hash_str))
                        
                        logger.info(f"已将死种 '{final_title}' 移至黑名单并重置订阅状态 (Hash: {hash_str})")
                        await session.commit()

                    try:
                        client.delete_torrent(hash_str, delete_files=True)
                        stalled_count += 1
                        total_stalled += 1
                    except Exception as e:
                        logger.error(f"删除死种失败: {e}")
                        await log_task(task_id, f"❌ 删除失败: {name}", "ERROR")
                    
                    await NotificationManager.push_client_error_notification(name, client.name, f"该资源被判定为死种 (超时 {elapsed_minutes:.1f}m 未完成)，已自动清理并重置订阅。")

            if stalled_count == 0:
                logger.info(f"客户端 {client.name} 巡检完毕，未发现死种。")
            else:
                logger.info(f"客户端 {client.name} 巡检完毕，共清理 {stalled_count} 个死种任务。")

        except Exception as e:
            logger.error(f"检查客户端 {client.name} 失败: {e}")
            await log_task(task_id, f"❌ 检查 {client.name} 失败: {str(e)}", "ERROR")

    await log_task(task_id, f"🏁 完成，共清理 {total_stalled} 个死种")
    
    # 构建统计信息
    stats = {
        "total_stalled": total_stalled,
        "total_clients": len(client_configs)
    }
    
    await finish_task(task_id, "completed", total_stalled, stats)
