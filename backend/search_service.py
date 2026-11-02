"""统一搜索服务 — 所有基于 Jackett 的搜索的唯一入口。

为什么要有这一层：
    原本「资源搜索页」「订阅补全」「AI 助手资源搜索」各自写了一套搜索调用，
    参数、返回字段、错误处理都不一样，改一处容易漏另一处。现在统一收敛到：

    SearchService.search()                 纯搜索（资源搜索页 / AI 助手）
    SearchService.recognize_title()        单条标题识别（与补全共用同一套参数）
    SearchService.search_with_recognition() 搜索 + 逐条识别（「带识别」的搜索场景）
    run_subscription_fill()                搜索 → 识别 → 过滤 → 去重 → 推送 → 通知

    底层仍只有一份 Jackett 客户端实现（clients/jackett.py 的 JackettClient），
    本模块只负责「搜索之上」的编排，避免重复实现。

不在此模块范围内：
    RSS 订阅匹配走的是已落库的 feed_items（订阅源抓取 + 识别缓存），
    不经过 Jackett 搜索，因此不受本模块影响。
"""

import asyncio
import logging
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from clients.jackett import JackettClient
from clients.manager import ClientManager
from config_manager import ConfigManager
from database import db
from logger import log_audit
from models import Subscription
from notification import notification_manager
from recognition.recognizer import MovieRecognizer
from rss_core.subscription_manager import SubscriptionManager
from task_history import finish_task, log_task, start_task

logger = logging.getLogger("SearchService")

# 进度回调：接收与前端 NDJSON 一致的 dict（{"type": ..., "message": ...}）
ProgressLogger = Callable[[Dict[str, Any]], Awaitable[None]]


def _recognize_config() -> Dict[str, Any]:
    """识别参数统一取值，避免各处自己读 config 导致行为不一致。"""
    config = ConfigManager.get_config()
    return {
        "anime_priority": config.get("anime_priority", True),
        "bangumi_priority": config.get("bangumi_priority", False),
        "bangumi_failover": config.get("bangumi_failover", True),
    }


class SearchService:
    """Jackett 搜索的统一入口。"""

    @staticmethod
    async def search(keyword: str, indexer: str = "all") -> List[Dict[str, str]]:
        """纯搜索，返回原始结果列表（title/link/guid/size/description/indexer）。"""
        return await JackettClient.search(keyword, indexer=indexer or "all")

    @staticmethod
    async def get_indexers() -> List[Dict[str, str]]:
        """可选站点列表（与搜索共享同一套 Jackett 配置）。"""
        return await JackettClient.get_indexers()

    @classmethod
    async def recognize_title(
        cls,
        title: str,
        description: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """识别单个标题，返回 (final_result | None, 识别日志)。"""
        result, recog_logs = await MovieRecognizer.recognize_full(
            title,
            force_filename=True,
            batch_enhancement=True,
            description=description,
            **_recognize_config(),
        )
        if not result.get("success") or not result.get("final_result"):
            return None, recog_logs
        return result["final_result"], recog_logs

    @classmethod
    async def search_with_recognition(
        cls,
        keyword: str,
        indexer: str = "all",
        limit: Optional[int] = None,
        on_progress: Optional[ProgressLogger] = None,
    ) -> List[Dict[str, Any]]:
        """搜索 + 逐条识别（识别成本高，limit 用于截断识别条数）。

        返回结果在原始字段基础上追加：
            recognized / tmdb_id / tmdb_title / media_type / season / episode
        """
        results = await cls.search(keyword, indexer)
        if limit is not None and limit > 0:
            results = results[:limit]

        total = len(results)
        enriched: List[Dict[str, Any]] = []
        for idx, item in enumerate(results):
            title = item.get("title", "")
            if on_progress:
                await on_progress({
                    "type": "process",
                    "message": f"正在分析: {title}",
                    "index": idx,
                    "total": total,
                    "title": title,
                })

            final: Optional[Dict[str, Any]] = None
            try:
                final, _logs = await cls.recognize_title(title, item.get("description"))
            except Exception as e:  # 识别失败不应中断整批搜索
                logger.warning(f"[Search] 识别失败: {title[:60]} - {e}")

            enriched.append({
                **item,
                "recognized": bool(final),
                "tmdb_id": final.get("tmdb_id") if final else None,
                "tmdb_title": final.get("title") if final else None,
                "media_type": (
                    "movie" if final and final.get("category") == "电影" else "tv"
                ) if final else None,
                "season": final.get("season") if final else None,
                "episode": str(final.get("episode")) if final and final.get("episode") is not None else None,
            })

        if on_progress:
            await on_progress({"type": "finish", "message": f"识别完成，共 {total} 条", "pushed": 0})
        return enriched


async def run_subscription_fill(
    sub: Subscription,
    logger_func: Optional[ProgressLogger] = None,
    indexer: str = "all",
    task_id: Optional[str] = None,
) -> int:
    """按订阅搜索并补全缺失集数（手动补全 / 自动补全共用）。

    流程：Jackett 搜索 → 逐条识别 → TMDB/季度/集数校验 → 已下载去重 →
    匹配条件过滤 → 推送下载 → 写 SubscribedEpisode → 通知。
    返回本次推送的条目数。
    """

    async def _log(msg: str, l_type: str = "info", extra: Optional[Dict[str, Any]] = None):
        if logger_func:
            await logger_func({"type": l_type, "message": msg, **(extra or {})})
        if task_id:
            try:
                level = "ERROR" if l_type == "error" else "WARN" if l_type == "warn" else "INFO"
                await log_task(task_id, msg, level)
            except Exception:
                pass

    # [优化] 不在整个函数外层包裹 session_scope，避免长时网络 IO 占用 DB 连接
    await _log(f"开始搜寻补全: {sub.title} (范围: {indexer})", l_type="start")

    search_results = await SearchService.search(sub.title, indexer=indexer)
    if not search_results:
        await _log("未发现搜索结果", l_type="error")
        return 0

    pushed_count = 0
    total = len(search_results)

    async def check_is_completed():
        """订阅内所有集数是否都已下载（内部按需开短 session）。"""
        async with db.session_scope():
            if sub.media_type == "movie":
                return await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, 0, 0)
            if sub.end_episode > 0:
                for ep in range(sub.start_episode, sub.end_episode + 1):
                    if not await SubscriptionManager.is_episode_downloaded(
                        sub.tmdb_id, sub.media_type, sub.season or 1, ep
                    ):
                        return False
                return True
            return False

    for idx, item in enumerate(search_results):
        if await check_is_completed():
            await _log("检测到订阅已全部补全，跳过后续搜索条目。", l_type="info")
            break

        title = item["title"]
        await _log(title, l_type="process", extra={"index": idx, "total": total, "title": title})

        try:
            result, recog_logs = await MovieRecognizer.recognize_full(
                title, force_filename=True,
                batch_enhancement=True,
                description=item.get("description"),
                **_recognize_config(),
            )

            recog_task_id = None
            try:
                recog_task_id = f"recog_{uuid.uuid4().hex[:12]}"
                await start_task(recog_task_id, "识别", f"[识别] {title}")
                for log_msg in recog_logs:
                    level = "ERROR" if "❌" in log_msg or "[ERROR]" in log_msg else "WARN" if "⚠️" in log_msg else "INFO"
                    await log_task(recog_task_id, log_msg, level)
            except Exception:
                recog_task_id = None

            if not result.get("success") or not result.get("final_result"):
                await _log(f"识别失败，跳过: {title}", l_type="info")
                if recog_task_id:
                    try:
                        await log_task(recog_task_id, "❌ 识别失败", "ERROR")
                        await finish_task(recog_task_id, "error")
                    except Exception:
                        pass
                continue

            final = result["final_result"]
            if recog_task_id:
                try:
                    stats = {
                        "title": final.get("title"),
                        "tmdb_id": final.get("tmdb_id"),
                        "category": final.get("category"),
                        "season": final.get("season"),
                        "episode": final.get("episode"),
                    }
                    await finish_task(recog_task_id, "completed", stats=stats)
                except Exception:
                    pass

            if str(final.get("tmdb_id")) != str(sub.tmdb_id):
                # 仅记录同名但 ID 不匹配的情况，或者完全不匹配
                await _log(f"ID 不匹配 ({final.get('tmdb_id') or '未知'}), 跳过: {title}", l_type="info")
                continue

            try:
                season = int(final.get("season")) if final.get("season") is not None else 1
                episode_raw = str(final.get("episode") or "")
                if "-" in episode_raw:
                    episode = int(episode_raw.split("-")[0])
                    is_batch, end_ep = True, int(episode_raw.split("-")[1])
                else:
                    episode = int(episode_raw) if episode_raw else None
                    is_batch, end_ep = False, episode
            except (ValueError, TypeError):
                await _log(f"集数解析失败, 跳过: {title}", l_type="warn")
                continue

            if sub.media_type == "tv":
                if episode is None:
                    await _log(f"未识别到集数, 跳过: {title}", l_type="info")
                    continue
                if sub.season != 0 and sub.season != season:
                    await _log(f"季度不匹配 (S{season}), 跳过: {title}", l_type="info")
                    continue

                if is_batch and end_ep:
                    if sub.start_episode > 0 and end_ep < sub.start_episode:
                        await _log(f"合集范围 [{episode}-{end_ep}] 早于订阅起始集数, 跳过: {title}", l_type="info")
                        continue
                    if sub.end_episode > 0 and episode > sub.end_episode:
                        await _log(f"合集范围 [{episode}-{end_ep}] 晚于订阅结束集数, 跳过: {title}", l_type="info")
                        continue
                else:
                    if sub.start_episode > 0 and episode < sub.start_episode:
                        await _log(f"早于起始集数 (E{episode}), 跳过: {title}", l_type="info")
                        continue
                    if sub.end_episode > 0 and episode > sub.end_episode:
                        await _log(f"晚于结束集数 (E{episode}), 跳过: {title}", l_type="info")
                        continue

                if is_batch and end_ep:
                    all_exist = True
                    for ep_num in range(episode, end_ep + 1):
                        if not await SubscriptionManager.is_episode_downloaded(
                            sub.tmdb_id, sub.media_type, season, ep_num
                        ):
                            all_exist = False
                    if all_exist:
                        await _log(f"合集集数已全部存在 (S{season}E{episode}-{end_ep}), 跳过: {title}", l_type="info")
                        continue
                else:
                    if await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, season, episode):
                        await _log(f"集数已存在 (S{season}E{episode}), 跳过: {title}", l_type="info")
                        continue
            else:
                if await SubscriptionManager.is_episode_downloaded(sub.tmdb_id, sub.media_type, 0, 0):
                    await _log(f"电影已存在, 跳过: {title}", l_type="info")
                    continue

            if hasattr(SubscriptionManager, "check_subscription_filter"):
                filter_ok, filter_err = SubscriptionManager.check_subscription_filter(sub, final, title)
                if not filter_ok:
                    await _log(f"过滤: {title} ({filter_err})", l_type="warn")
                    continue

            success, _msg = await ClientManager.add_task(
                sub.target_client_id, item["link"], save_path=sub.save_path, category=sub.category
            )

            if success:
                # 写入操作依然开启短 session
                async with db.session_scope():
                    if sub.media_type == "tv":
                        if is_batch and end_ep:
                            for ep_num in range(episode, end_ep + 1):
                                await SubscriptionManager.add_subscribed_episode(
                                    sub.tmdb_id, sub.media_type, season or 1, ep_num, title=title
                                )
                        else:
                            await SubscriptionManager.add_subscribed_episode(
                                sub.tmdb_id, sub.media_type, season or 1, episode, title=title
                            )
                    else:
                        await SubscriptionManager.add_subscribed_episode(
                            sub.tmdb_id, sub.media_type, 0, 0, title=title
                        )

                    # [彻底解耦] 补全操作不写入全局 DownloadHistory，只维护 SubscribedEpisode

                pushed_count += 1
                await _log(f"成功补全推送: {title}", l_type="hit")

                # [Notify]
                await notification_manager.notify_sub_matched(sub=sub, item=final)

                if await check_is_completed():
                    await _log("补全圆满结束。", l_type="finish")
                    break

        except Exception as e:
            await _log(f"处理错误: {str(e)}", l_type="warn")

        await asyncio.sleep(0.05)

    await _log(f"任务完成，共推送 {pushed_count} 个集数", l_type="finish", extra={"pushed": pushed_count})

    if await check_is_completed():
        log_audit("订阅", "自动完结", f"检测到订阅 '{sub.title}' 已全部完成，自动清理任务")
        await notification_manager.notify_sub_completed(sub)
        async with db.session_scope():
            await db.delete(sub)

    return pushed_count


async def run_subscription_fill_in_background(sub: Subscription, indexer: str = "all") -> str:
    """后台执行补全（非流式场景：AI 助手等），返回任务历史 ID。

    手动补全走 HTTP 流式接口，能实时看进度；AI 工具这种一次性调用不适合等待
    几分钟，所以这里落一条任务历史后异步跑，调用方只需把 task_id 告诉用户。
    """
    task_id = f"fill_{uuid.uuid4().hex[:12]}"
    await start_task(task_id, "订阅补全", f"[后台] {sub.title}")

    async def _run():
        try:
            pushed = await run_subscription_fill(
                sub, logger_func=None, indexer=indexer, task_id=task_id
            )
            await log_task(task_id, f"🏁 补全完成，共推送 {pushed} 个集数")
            await finish_task(task_id, "completed", pushed)
        except Exception as e:
            logger.error(f"[Search] 后台补全失败 ({sub.title}): {e}")
            try:
                await log_task(task_id, f"❌ 补全失败: {e}", "ERROR")
                await finish_task(task_id, "failed", 0)
            except Exception:
                pass

    asyncio.create_task(_run())
    return task_id
