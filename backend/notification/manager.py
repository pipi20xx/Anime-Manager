"""通知管理器 —— 业务代码唯一入口。

职责：
1. 读取配置、决定是否发送（业务策略/开关判断集中在此）。
2. 构造标准 ``Notification`` 对象。
3. 委托 ``TelegramNotifier`` 渲染并发送。

使用方式：
    from notification import notification_manager

    await notification_manager.notify_organize_complete(final_res)
    await notification_manager.notify_sub_added(sub)
    ...
"""
import asyncio
import logging
import os
import re
from typing import Any, Optional, Dict, List, Tuple

from config_manager import ConfigManager
from logger import log_audit

from .models import Notification, NotificationEvent, NotificationPriority
from .renderer import NotificationRenderer, renderer as _shared_renderer
from .notifier import TelegramNotifier

logger = logging.getLogger("Notification")

# ── Emby 深度删除通知聚合配置 ──
# 聚合窗口（秒）：在此时间内收到的多条删除通知将被合并为一条发送
EMBY_DELETE_AGGREGATE_WINDOW = 30
# 单条消息最大文件数，超过则分多条发送（Telegram 消息长度限制 4096 字符）
EMBY_DELETE_MAX_FILES_PER_MSG = 80
# 缓冲区达到此阈值时立即发送，不再等待聚合窗口超时
EMBY_DELETE_FLUSH_THRESHOLD = 80

# ── 整理入库通知聚合配置 ──
# 聚合窗口（秒）：在此时间内收到的多条入库通知按番剧分组合并发送
ORGANIZE_AGGREGATE_WINDOW = 60
# 缓冲区达到此文件数时立即发送，不再等待聚合窗口超时
ORGANIZE_FLUSH_THRESHOLD = 20


def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """从 dict 或对象上取值，兼容两种数据形态。"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class NotificationManager:
    """通知管理器 —— 全局单例 ``notification_manager``。

    所有业务通知通过 ``notify_xxx`` 实例方法发送；
    底层 ``send`` 方法接收标准 ``Notification`` 对象。
    """

    # 共享渲染器（无状态）
    renderer: NotificationRenderer = _shared_renderer

    # 可选：通过 init() 预置的常驻 notifier；默认 None，每次按配置动态构建，
    # 以保留「改配置即时生效」的行为。
    _notifier: Optional[TelegramNotifier] = None

    # ── Emby 深度删除通知聚合状态 ──
    # 累积的文件名缓冲区
    _delete_buffer: List[str] = []
    # 延迟刷新任务
    _delete_flush_task: Optional[asyncio.Task] = None
    # 用于保护缓冲区的异步锁
    _delete_lock: asyncio.Lock = asyncio.Lock()

    # ── 整理入库通知聚合状态 ──
    # 按番剧分组的缓冲区: {group_key: {info, episodes: [final_res, ...]}}
    _organize_buffer: Dict[str, Dict] = {}
    # 延迟刷新任务
    _organize_flush_task: Optional[asyncio.Task] = None
    # 用于保护缓冲区的异步锁
    _organize_lock: asyncio.Lock = asyncio.Lock()

    # ════════════════════════════════════════════════════════
    # 初始化与底层构建
    # ════════════════════════════════════════════════════════

    @classmethod
    def init(cls, bot_token: str, chat_id: str, enabled: bool = True,
             style: str = "default"):
        """初始化常驻通知器（可选）。

        不调用本方法时，每次发送都会按当前配置动态构建 notifier，
        从而保留「配置改动即时生效」的行为。
        """
        if enabled and bot_token and chat_id:
            proxy = ConfigManager.get_proxy("telegram")
            cls._notifier = TelegramNotifier(bot_token, chat_id, proxy=proxy, style=style)
        else:
            cls._notifier = None

    @classmethod
    def _build_notifier(cls) -> Optional[TelegramNotifier]:
        """按当前配置构建一个 TelegramNotifier；禁用或未配置时返回 None。"""
        if cls._notifier is not None:
            return cls._notifier

        config = ConfigManager.get_config()
        tg_conf = config.get("telegram", {})
        if not tg_conf.get("enabled"):
            return None
        bot_token = tg_conf.get("bot_token")
        chat_id = tg_conf.get("chat_id")
        if not bot_token or not chat_id:
            return None
        proxy = ConfigManager.get_proxy("telegram")
        style = tg_conf.get("style", "default")
        return TelegramNotifier(bot_token, chat_id, proxy=proxy, style=style)

    @staticmethod
    def _tg_conf() -> Dict:
        return ConfigManager.get_config().get("telegram", {})

    # ════════════════════════════════════════════════════════
    # 核心发送
    # ════════════════════════════════════════════════════════

    async def send(
        self,
        notification: Notification,
        style: Optional[str] = None,
        photo_url: Optional[str] = None,
        pin: bool = False,
        buttons: Optional[List[List[Dict]]] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """发送标准通知对象。

        :return: (success, message, message_id)
        """
        notifier = self._build_notifier()
        if notifier is None:
            return False, "Telegram notification is disabled or not configured", None
        return await notifier.send(notification, style=style, photo_url=photo_url,
                                   pin=pin, buttons=buttons)

    async def pin_chat_message(
        self,
        chat_id: str,
        message_id: int,
        bot_token: Optional[str] = None,
        client: Any = None,
    ) -> bool:
        """置顶消息。"""
        tg_conf = self._tg_conf()
        if not bot_token:
            bot_token = tg_conf.get("bot_token")
        if not bot_token:
            logger.warning("无法置顶消息：缺少 Bot Token")
            return False

        proxy = ConfigManager.get_proxy("telegram")
        notifier = TelegramNotifier(bot_token, chat_id, proxy=proxy)
        return await notifier.pin_chat_message(chat_id, message_id, client=client)

    # ════════════════════════════════════════════════════════
    # 图片 URL 工具
    # ════════════════════════════════════════════════════════

    @staticmethod
    def get_image_url(poster_path: Optional[str]) -> Optional[str]:
        """将图片路径转换为公网可访问的完整 URL（用于 Telegram 等外部服务）。

        处理以下格式：
        - 完整 URL (http/https) → 直接返回
        - TMDB 本地代理路径 /api/system/img?path=/w500/abc.jpg → 解码并拼成 TMDB 公网 URL
        - Bangumi 本地代理路径 /api/system/bgm_img?url=... → 解码出原始 URL
        - TMDB 原始路径 /abc.jpg 或 /w500/abc.jpg → 拼成 TMDB 公网 URL
        :return: 公网可访问的图片 URL；无法识别时返回 None（只发文本通知）
        """
        if not poster_path:
            return None

        from urllib.parse import parse_qs, urlparse

        # 完整 URL，直接返回
        if poster_path.startswith("http"):
            return poster_path

        # TMDB 本地代理路径：/api/system/img?path=%2Fw500%2Fabc.jpg
        if "/api/system/img" in poster_path:
            parsed = urlparse(poster_path)
            qs = parse_qs(parsed.query)
            raw_path = qs.get("path", [None])[0]
            if raw_path:
                size_match = re.match(r"^/(w\d+|original)(/.*)$", raw_path)
                clean_path = size_match.group(2) if size_match else raw_path
                if not clean_path.startswith("/"):
                    clean_path = "/" + clean_path
                image_domain = ConfigManager.get_tmdb_image_domain()
                return f"https://{image_domain}/t/p/original{clean_path}"
            return None

        # Bangumi 本地代理路径：/api/system/bgm_img?url=https%3A%2F%2F...
        if "/api/system/bgm_img" in poster_path:
            parsed = urlparse(poster_path)
            qs = parse_qs(parsed.query)
            raw_url = qs.get("url", [None])[0]
            if raw_url and raw_url.startswith("http"):
                return raw_url
            return None

        # TMDB 原始路径：/abc.jpg 或 /w500/abc.jpg
        if poster_path.startswith("/") and not poster_path.startswith("/api"):
            size_match = re.match(r"^/(w\d+|original)(/.*)$", poster_path)
            clean_path = size_match.group(2) if size_match else poster_path
            if not clean_path.startswith("/"):
                clean_path = "/" + clean_path
            image_domain = ConfigManager.get_tmdb_image_domain()
            return f"https://{image_domain}/t/p/original{clean_path}"

        # 无法识别的格式，跳过图片只发文本
        return None

    # ════════════════════════════════════════════════════════
    # 便捷通知 API —— 业务代码通过 notification_manager.notify_xxx() 调用
    # ════════════════════════════════════════════════════════

    # ── 订阅相关 ──

    async def notify_sub_added(self, sub: Any) -> None:
        """新增订阅通知。"""
        if not self._tg_conf().get("notify_on_sub_add", True):
            return

        photo_url = self.get_image_url(_get_val(sub, "poster_path"))
        await self.send(Notification(
            event_type=NotificationEvent.SUB_ADDED,
            data={
                "title": _get_val(sub, "title"),
                "year": _get_val(sub, "year", ""),
                "media_type": _get_val(sub, "media_type", "tv"),
                "season": _get_val(sub, "season", 1),
                "start_episode": _get_val(sub, "start_episode", 1),
                "end_episode": _get_val(sub, "end_episode", 0),
                "tmdb_id": _get_val(sub, "tmdb_id"),
            },
            image_url=photo_url,
        ))

    async def notify_sub_deleted(self, sub: Any) -> None:
        """删除订阅通知。"""
        if not self._tg_conf().get("notify_on_sub_del", True):
            return

        photo_url = self.get_image_url(_get_val(sub, "poster_path"))
        await self.send(Notification(
            event_type=NotificationEvent.SUB_DELETED,
            data={
                "title": _get_val(sub, "title"),
                "year": _get_val(sub, "year", ""),
                "media_type": _get_val(sub, "media_type", "tv"),
                "season": _get_val(sub, "season", 1),
                "start_episode": _get_val(sub, "start_episode", 1),
                "end_episode": _get_val(sub, "end_episode", 0),
                "tmdb_id": _get_val(sub, "tmdb_id"),
            },
            image_url=photo_url,
        ))

    async def notify_sub_completed(self, sub: Any) -> None:
        """订阅完结通知。"""
        if not self._tg_conf().get("notify_on_sub_complete", True):
            return

        photo_url = self.get_image_url(_get_val(sub, "poster_path"))
        await self.send(Notification(
            event_type=NotificationEvent.SUB_COMPLETED,
            data={
                "title": _get_val(sub, "title"),
                "season": _get_val(sub, "season", 1),
                "media_type": _get_val(sub, "media_type", "tv"),
            },
            image_url=photo_url,
        ))

    async def notify_sub_matched(self, sub: Any, item: Any) -> None:
        """订阅命中推送通知。"""
        if not self._tg_conf().get("notify_on_sub_push", True):
            return

        tmdb_title = _get_val(item, "tmdb_title") or _get_val(item, "title") or _get_val(sub, "title")
        season = _get_val(item, "season")
        episode = _get_val(item, "episode")
        category_raw = _get_val(item, "media_type") or _get_val(item, "category")
        category = "电影" if category_raw in ("movie", "电影") else "剧集"
        year = _get_val(sub, "year") or ""
        resolution = _get_val(item, "resolution") or ""
        team = _get_val(item, "team") or ""
        poster_path = _get_val(sub, "poster_path")
        tmdb_id = _get_val(sub, "tmdb_id")
        raw_title = _get_val(item, "title") or "Unknown"
        source_title = _get_val(sub, "title")

        se_info = ""
        if category != "电影":
            if isinstance(season, int):
                se_info = f"S{season:02d} E{episode}"
            else:
                se_info = f"S{season} E{episode}"

        photo_url = self.get_image_url(poster_path)
        await self.send(Notification(
            event_type=NotificationEvent.SUB_MATCHED,
            data={
                "tmdb_title": tmdb_title, "year": year, "category": category,
                "se_info": se_info, "resolution": resolution, "team": team,
                "tmdb_id": tmdb_id, "source_title": source_title, "raw_title": raw_title,
            },
            image_url=photo_url,
        ))

    # ── 规则 ──

    async def notify_rule_matched(self, title: str, rule_name: str,
                                  client_name: str = "默认客户端") -> None:
        """规则命中下载通知。"""
        if not self._tg_conf().get("notify_on_rule_push", True):
            return
        await self.send(Notification(
            event_type=NotificationEvent.RULE_MATCHED,
            data={"title": title, "rule_name": rule_name, "client_name": client_name},
        ))

    # ── STRM ──

    async def notify_strm_finished(self, task_name: str, stats: dict) -> None:
        """STRM 任务完成通知。"""
        if not self._tg_conf().get("notify_on_strm_finish", True):
            return

        await self.send(Notification(
            event_type=NotificationEvent.STRM_TASK_FINISHED,
            data={
                "task_name": task_name,
                "duration": stats.get("duration", "未知"),
                "strm_created": stats.get("strm_created", 0),
                "strm_skipped": stats.get("strm_skipped", 0),
                "meta_copied": stats.get("meta_copied", 0),
                "meta_skipped": stats.get("meta_skipped", 0),
                "deleted": stats.get("deleted", 0),
                "source": stats.get("source", "未知"),
            },
        ))

    async def notify_strm_link_created(self, file_name: str, task_name: str) -> None:
        """STRM 整理联动生成通知。"""
        if not self._tg_conf().get("notify_on_strm_link", True):
            return
        await self.send(Notification(
            event_type=NotificationEvent.STRM_LINK_CREATED,
            data={"file_name": file_name, "task_name": task_name},
        ))

    async def notify_strm_webhook(self, results: list) -> None:
        """Webhook 实时监控通知（支持多文件分组显示）。"""
        if not self._tg_conf().get("notify_on_strm_link", True):
            return

        success_results = [r for r in results if r and r.get("status") == "success"]
        if not success_results:
            return

        strm_files: Dict[str, List[str]] = {}
        meta_files: Dict[str, List[str]] = {}
        task_names = set()

        for res in success_results:
            rel_path = res.get("rel_path")
            target_root = res.get("target_root", "")
            task_name = res.get("task_name")
            if task_name:
                task_names.add(task_name)
            if not rel_path:
                continue

            full_path = os.path.join(target_root, rel_path) if target_root else rel_path
            folder = os.path.dirname(full_path) or "/"
            filename = os.path.basename(full_path)

            msg_type = res.get("message", "")
            if "STRM" in msg_type:
                strm_files.setdefault(folder, []).append(filename)
            elif "Meta" in msg_type:
                meta_files.setdefault(folder, []).append(filename)

        if not strm_files and not meta_files:
            return

        await self.send(Notification(
            event_type=NotificationEvent.STRM_WEBHOOK,
            data={
                "task_names": sorted(task_names),
                "strm_files": strm_files,
                "meta_files": meta_files,
            },
        ))

    # ── 整理 ──

    async def notify_organize_complete(self, final_res: dict) -> None:
        """整理完成通知（聚合版）。

        将 60 秒内收到的多条入库通知按番剧分组合并发送。
        同一番剧的多集入库合并为一条消息，展示集数范围和文件列表。
        电影不走聚合，直接独立发送。
        缓冲区达到阈值时立即发送，不继续等待。
        """
        if not self._tg_conf().get("notify_on_organize", True):
            return

        # 电影类型不聚合，直接独立发送
        category = final_res.get("category", "")
        if category in ("电影", "movie"):
            await self._send_organize_single(final_res)
            return

        async with self._organize_lock:
            # 按番剧分组：以 tmdb_id + season 为 key
            tmdb_id = final_res.get("tmdb_id") or final_res.get("title", "")
            season = final_res.get("season", 1)
            group_key = f"{tmdb_id}|S{season}"

            group = self._organize_buffer.get(group_key)
            if group is None:
                # 首次出现：提取该番剧的公共信息
                photo_url = self.get_image_url(final_res.get("poster_path"))
                group = {
                    "info": {
                        "title": final_res.get("title", "Unknown"),
                        "year": final_res.get("year", ""),
                        "season": season,
                        "tmdb_id": final_res.get("tmdb_id"),
                        "category": final_res.get("category", "未知"),
                        "origin_country": final_res.get("origin_country", ""),
                        "resolution": final_res.get("resolution", ""),
                        "source": final_res.get("source", ""),
                        "platform": final_res.get("platform", ""),
                        "team": final_res.get("team", ""),
                    },
                    "episodes": [],
                    "photo_url": photo_url,
                }
                self._organize_buffer[group_key] = group

            group["episodes"].append({
                "episode": final_res.get("episode", 1),
                "file_size": final_res.get("file_size", "未知"),
                "duration": final_res.get("duration", "未知"),
                "filename": final_res.get("filename", "Unknown"),
            })

            buf_count = sum(len(g["episodes"]) for g in self._organize_buffer.values())

            # 缓冲区达到阈值 → 立即发送
            if buf_count >= ORGANIZE_FLUSH_THRESHOLD:
                if self._organize_flush_task is not None and not self._organize_flush_task.done():
                    self._organize_flush_task.cancel()
                    try:
                        await self._organize_flush_task
                    except asyncio.CancelledError:
                        pass
                await self._flush_organize_buffer()
            else:
                # 未达阈值：重置倒计时
                if self._organize_flush_task is not None and not self._organize_flush_task.done():
                    self._organize_flush_task.cancel()
                    try:
                        await self._organize_flush_task
                    except asyncio.CancelledError:
                        pass
                self._organize_flush_task = asyncio.create_task(self._delayed_flush_organize())

    async def _send_organize_single(self, final_res: dict) -> None:
        """直接发送单条入库通知（电影等不聚合的类型）。"""
        photo_url = self.get_image_url(final_res.get("poster_path"))
        await self.send(Notification(
            event_type=NotificationEvent.ORGANIZE_COMPLETE,
            data={
                "title": final_res.get("title", "Unknown"),
                "year": final_res.get("year", ""),
                "season": final_res.get("season", 1),
                "episode": final_res.get("episode", 1),
                "tmdb_id": final_res.get("tmdb_id"),
                "category": final_res.get("category", "未知"),
                "origin_country": final_res.get("origin_country", ""),
                "resolution": final_res.get("resolution", ""),
                "source": final_res.get("source", ""),
                "platform": final_res.get("platform", ""),
                "team": final_res.get("team", ""),
                "file_size": final_res.get("file_size", "未知"),
                "duration": final_res.get("duration", "未知"),
                "filename": final_res.get("filename", "Unknown"),
            },
            image_url=photo_url,
        ))

    async def _flush_organize_buffer(self) -> None:
        """将缓冲区中按番剧分组的入库通知发送，并清空缓冲区。

        调用方须已持有 ``_organize_lock``。
        """
        if not self._organize_buffer:
            return

        groups = list(self._organize_buffer.values())
        self._organize_buffer.clear()
        self._organize_flush_task = None

        for group in groups:
            info = group["info"]
            episodes = group["episodes"]
            photo_url = group.get("photo_url")

            await self.send(Notification(
                event_type=NotificationEvent.ORGANIZE_COMPLETE,
                data={
                    **info,
                    "episodes": episodes,
                    "is_aggregated": True,
                    "episode_count": len(episodes),
                },
                image_url=photo_url,
            ))

    async def _delayed_flush_organize(self) -> None:
        """等待聚合窗口超时后发送缓冲区内容。"""
        try:
            await asyncio.sleep(ORGANIZE_AGGREGATE_WINDOW)
        except asyncio.CancelledError:
            return

        async with self._organize_lock:
            await self._flush_organize_buffer()

    async def flush_organize_buffer(self) -> None:
        """公开方法：立即发送缓冲区中的入库通知。

        供整理任务结束时主动调用，确保不漏掉最后的批次。
        """
        async with self._organize_lock:
            if self._organize_flush_task is not None and not self._organize_flush_task.done():
                self._organize_flush_task.cancel()
                try:
                    await self._organize_flush_task
                except asyncio.CancelledError:
                    pass
            await self._flush_organize_buffer()

    async def notify_organize_failed(self, file_path: str, error_message: str) -> None:
        """整理执行异常通知。"""
        if not self._tg_conf().get("notify_on_organize_error", True):
            return

        file_name = os.path.basename(file_path)
        await self.send(Notification(
            event_type=NotificationEvent.ORGANIZE_FAILED,
            data={"file_name": file_name, "file_path": file_path, "error": error_message},
        ))

    # ── 系统健康 ──

    async def notify_health_check(self, name: str, status: str, file_path: str) -> None:
        """健康检查失败通知。"""
        await self.send(Notification(
            event_type=NotificationEvent.SYSTEM_HEALTH,
            data={"name": name, "status": status, "file_path": file_path},
        ))

    # ── Emby 媒体库 ──

    async def notify_library_new(self, payload: dict) -> None:
        """Emby 新入库通知。"""
        tg = self._tg_conf()
        if not tg.get("enabled"):
            return
        if not tg.get("notify_on_library_new", True):
            return

        item = payload.get("Item", {})
        media_type = item.get("Type")
        is_tv = media_type in ["Series", "Episode"]
        category = "剧集" if is_tv else "电影"

        series_name = item.get("SeriesName")
        name = item.get("Name")
        if media_type == "Episode" and series_name:
            display_title = series_name
            episode_name = name
        else:
            display_title = name
            episode_name = ""

        rating = item.get("CommunityRating")
        path = item.get("Path", "")
        overview = item.get("Overview", "")

        se_info = ""
        if media_type == "Episode":
            s_num = item.get("ParentIndexNumber")
            e_num = item.get("IndexNumber")
            if s_num is not None and e_num is not None:
                # [Fix] 防御: Emby 返回值可能是字符串，:02d 格式化需要 int
                try: s_num, e_num = int(s_num), int(e_num)
                except (ValueError, TypeError): pass
                se_info = f"S{s_num:02d} E{e_num:02d}" if isinstance(s_num, int) and isinstance(e_num, int) else f"S{s_num} E{e_num}"
                if episode_name:
                    se_info += f" {episode_name}"

        from datetime import datetime, timedelta
        date_str = payload.get("Date", "")
        formatted_date = "未知"
        try:
            clean_date = date_str.split('.')[0].replace('Z', '')
            dt = datetime.fromisoformat(clean_date)
            dt = dt + timedelta(hours=8)
            formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            formatted_date = date_str[:19].replace('T', ' ')

        if overview and len(overview) > 150:
            overview = overview[:150] + "..."

        # 图片处理：优先寻找本地 fanart.jpg
        photo_url = None
        if path:
            try:
                current_dir = os.path.dirname(path)
                search_dirs = [current_dir]
                p1 = os.path.dirname(current_dir)
                if p1:
                    search_dirs.append(p1)
                p2 = os.path.dirname(p1)
                if p2:
                    search_dirs.append(p2)

                for d in search_dirs:
                    if not os.path.isdir(d):
                        continue
                    for img_name in ["fanart.jpg", "backdrop.jpg", "poster.jpg", "folder.jpg"]:
                        img_path = os.path.join(d, img_name)
                        if os.path.exists(img_path):
                            from urllib.parse import quote
                            photo_url = f"/api/system/img?path={quote(img_path)}"
                            break
                    if photo_url:
                        break
            except Exception:
                pass

        # 本地没找到，尝试 TMDB
        if not photo_url:
            tmdb_id = item.get("ProviderIds", {}).get("Tmdb")
            if not tmdb_id and path:
                match = re.search(r"\[tmdbid=(\d+)\]", path)
                if match:
                    tmdb_id = match.group(1)

            if tmdb_id:
                try:
                    from recognition.data_provider.tmdb.client import TMDBProvider
                    provider = TMDBProvider()
                    m_type = "tv" if is_tv else "movie"
                    details = await provider.get_subject_details(str(tmdb_id), m_type)
                    if details and details.get("backdrop_path"):
                        bp = details.get("backdrop_path")
                        if "path=" in bp:
                            from urllib.parse import parse_qs, urlparse
                            qs = parse_qs(urlparse(bp).query)
                            if "path" in qs:
                                bp = qs["path"][0]
                        photo_url = self.get_image_url(bp)
                except Exception:
                    pass

        await self.send(Notification(
            event_type=NotificationEvent.LIBRARY_NEW,
            data={
                "category": category,
                "display_title": display_title,
                "se_info": se_info,
                "rating": rating,
                "formatted_date": formatted_date,
                "overview": overview,
            },
            image_url=photo_url,
        ))

    async def notify_emby_deleted(self, payload: Any) -> None:
        """Emby 删除事件通知（聚合发送版）。

        将 30 秒内收到的多条删除通知合并为一条发送，
        减少对 Telegram Bot API 的请求次数，避免消息刷屏。
        缓冲区达到阈值时立即发送，不继续等待。
        """
        if not self._tg_conf().get("enabled"):
            return

        file_list = self._extract_deleted_files(payload)
        if not file_list:
            return

        async with self._delete_lock:
            self._delete_buffer.extend(file_list)
            buf_len = len(self._delete_buffer)

            # 缓冲区达到阈值 → 立即发送当前批次
            if buf_len >= EMBY_DELETE_FLUSH_THRESHOLD:
                # 取消正在等待的定时任务
                if self._delete_flush_task is not None and not self._delete_flush_task.done():
                    self._delete_flush_task.cancel()
                    try:
                        await self._delete_flush_task
                    except asyncio.CancelledError:
                        pass
                # 立即刷出缓冲区
                await self._flush_deleted_buffer()
            else:
                # 未达阈值：取消旧定时任务，重新计时 30 秒
                if self._delete_flush_task is not None and not self._delete_flush_task.done():
                    self._delete_flush_task.cancel()
                    try:
                        await self._delete_flush_task
                    except asyncio.CancelledError:
                        pass
                # 启动新的延迟刷新任务
                self._delete_flush_task = asyncio.create_task(self._delayed_flush_deleted())

    async def _flush_deleted_buffer(self) -> None:
        """将缓冲区中的文件列表合并发送，并清空缓冲区。

        调用方须已持有 ``_delete_lock``。
        """
        if not self._delete_buffer:
            return

        # 去重并保持顺序
        seen = set()
        unique_files: List[str] = []
        for f in self._delete_buffer:
            if f not in seen:
                seen.add(f)
                unique_files.append(f)

        total_count = len(unique_files)
        self._delete_buffer.clear()
        self._delete_flush_task = None

        # 分批发送（防止单条消息过长）
        for offset in range(0, total_count, EMBY_DELETE_MAX_FILES_PER_MSG):
            chunk = unique_files[offset:offset + EMBY_DELETE_MAX_FILES_PER_MSG]
            is_last_chunk = offset + EMBY_DELETE_MAX_FILES_PER_MSG >= total_count
            await self.send(Notification(
                event_type=NotificationEvent.LIBRARY_DELETED,
                data={
                    "files": chunk,
                    "total_count": total_count,
                    "chunk_index": offset // EMBY_DELETE_MAX_FILES_PER_MSG + 1,
                    "total_chunks": (total_count + EMBY_DELETE_MAX_FILES_PER_MSG - 1) // EMBY_DELETE_MAX_FILES_PER_MSG,
                    "is_aggregated": True,
                    "is_last_chunk": is_last_chunk,
                },
            ))

    @staticmethod
    def _extract_deleted_files(payload: Any) -> List[str]:
        """从 Emby Webhook payload 中提取被删除的文件名列表。"""
        file_list: List[str] = []
        if isinstance(payload, dict) and payload.get("Event") == "deep.delete":
            description = payload.get("Description", "")
            if "Mount Paths:" in description:
                mount_paths_section = description.split("Mount Paths:")[1].strip()
                for line in mount_paths_section.split('\n'):
                    line = line.strip()
                    if line:
                        filename = os.path.basename(line)
                        if filename and filename != line:
                            file_list.append(filename)
        elif isinstance(payload, list):
            for it in payload:
                is_dir = str(it.get("is_dir", "false")).lower()
                if is_dir != "true":
                    source_file = it.get("source_file", "")
                    if source_file:
                        file_list.append(os.path.basename(source_file))
        return file_list

    async def _delayed_flush_deleted(self) -> None:
        """等待聚合窗口超时后，将缓冲区中的文件列表合并发送。"""
        try:
            await asyncio.sleep(EMBY_DELETE_AGGREGATE_WINDOW)
        except asyncio.CancelledError:
            # 被新事件取消，不发送，等待下一次窗口
            return

        async with self._delete_lock:
            await self._flush_deleted_buffer()

    # ── 客户端错误 ──

    async def notify_client_error(self, resource_name: str, client_name: str,
                                  error_message: str) -> None:
        """客户端报错通知。"""
        if not self._tg_conf().get("notify_on_client_error", True):
            return

        error_map = {
            "login failed": "登录失败，请检查账号密码",
            "connection timed out": "连接超时，请检查网络或IP端口",
            "max retries exceeded": "连接失败，目标主机不可达",
            "rpc error": "RPC 远程调用错误",
            "timed out": "请求超时",
        }
        final_error = error_message
        for k, v in error_map.items():
            if k in error_message.lower():
                final_error = f"{v}\n<pre>{error_message}</pre>"
                break

        await self.send(Notification(
            event_type=NotificationEvent.CLIENT_ERROR,
            data={"resource_name": resource_name, "client_name": client_name,
                  "final_error": final_error},
        ))

    async def notify_torrent_download_failed(self, title: str, link: str,
                                             error_message: str,
                                             is_fallback: bool = False) -> None:
        """种子文件下载失败通知。"""
        if not self._tg_conf().get("notify_on_client_error", True):
            return
        await self.send(Notification(
            event_type=NotificationEvent.TORRENT_DOWNLOAD_FAILED,
            data={"title": title, "link": link, "error": error_message,
                  "is_fallback": is_fallback},
        ))

    async def notify_client_push_failed(self, title: str, client_name: str,
                                        error_message: str) -> None:
        """推送客户端失败通知。"""
        if not self._tg_conf().get("notify_on_client_error", True):
            return
        await self.send(Notification(
            event_type=NotificationEvent.CLIENT_PUSH_FAILED,
            data={"title": title, "client_name": client_name, "error": error_message},
        ))

    # ── 日历 / 摘要 ──

    async def notify_calendar_daily(self, subjects: list) -> Tuple[bool, str]:
        """每日播出概览通知（聚合美化版）。"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("enabled"):
            return False, "disabled"

        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][datetime.now().weekday()]

        header = f"📅 <b>今日播出概览 ({today_str} 周{weekday_cn})</b>\n"
        lines = []
        if not subjects:
            lines.append("今天暂无订阅剧集播出。")
        else:
            for i, sub in enumerate(subjects):
                title = sub.get("title", "未知")
                season = sub.get("season", 1)
                ep_info = ""
                episodes = sub.get("episodes_cache", [])
                for ep in episodes:
                    if ep.get("air_date") == today_str:
                        ep_num = ep.get("episode")
                        is_finale = ep.get("episode_type") == "finale"
                        finale_tag = " [END]" if is_finale else ""
                        ep_info = f" - 第 {ep_num} 集{finale_tag}"
                        break
                char = "└──" if i == len(subjects) - 1 else "├──"
                season_tag = f" (S{season:02d})" if isinstance(season, int) and season else (f" (S{season})" if season else "")
                lines.append(f"{char} <b>{title}</b>{season_tag}{ep_info}")

        photo_url = None
        if len(subjects) == 1 and subjects[0].get("poster_path"):
            path = subjects[0]["poster_path"]
            if path and path.strip():
                photo_url = self.get_image_url(path)

        pin_message = config.get("calendar_pin_message", False)

        success, msg, _ = await self.send(
            Notification(
                event_type=NotificationEvent.CALENDAR_DAILY,
                data={"header": header, "lines": lines},
            ),
            photo_url=photo_url,
            pin=pin_message,
        )

        if not success and photo_url:
            logger.warning(f"带图片发送失败，尝试仅发送文本: {msg}")
            success, msg, _ = await self.send(
                Notification(
                    event_type=NotificationEvent.CALENDAR_DAILY,
                    data={"header": header, "lines": lines},
                ),
                photo_url=None,
                pin=pin_message,
            )

        return success, msg

    async def notify_daily_summary(self, today_airing: list) -> None:
        """每日番剧播出摘要通知。"""
        if not today_airing:
            return

        await self.send(Notification(
            event_type=NotificationEvent.DAILY_SUMMARY,
            data={"items": today_airing},
        ))

    async def notify_episode_aired(self, sub: Any, ep_info: dict) -> bool:
        """新集播出提醒通知。"""
        ep_num = ep_info.get("episode")
        ep_title = ep_info.get("title", f"第{ep_num}集")
        air_date = ep_info.get("air_date", "")

        season = _get_val(sub, "season")
        season_str = f"S{season:02d}" if isinstance(season, int) and season else ""
        ep_str = f"E{ep_num:02d}" if isinstance(ep_num, int) else f"E{ep_num}"

        photo_url = self.get_image_url(_get_val(sub, "poster_path"))

        success, _, _ = await self.send(
            Notification(
                event_type=NotificationEvent.EPISODE_AIRED,
                data={
                    "title": _get_val(sub, "title"),
                    "season_str": season_str,
                    "ep_str": ep_str,
                    "ep_title": ep_title,
                    "air_date": air_date,
                },
                image_url=photo_url,
            ),
        )
        return success

    # ── 系统启动 ──

    async def notify_startup(self, status_info: dict) -> None:
        """系统启动通知 - 汇报各功能模块状态。"""
        if not self._tg_conf().get("notify_on_startup", True):
            return

        from datetime import datetime
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            from main import __version__
            version = __version__
        except Exception:
            version = "unknown"

        modules = []

        cd2_status = status_info.get("cd2_monitor", {})
        if cd2_status.get("enabled"):
            running = cd2_status.get("running", False)
            label = "运行中" if running else "未启动"
            detail = ""
            if cd2_status.get("client"):
                detail = f' · <code>{cd2_status["client"]}</code>'
            icon = "☁️" if running else "⚠️"
            modules.append((icon, "CD2 监控", label, detail))

        organize_tasks = status_info.get("organize_tasks", 0)
        if organize_tasks > 0:
            modules.append(("📂", "整理任务", f"{organize_tasks} 个", ""))

        strm_tasks = status_info.get("strm_tasks", 0)
        if strm_tasks > 0:
            modules.append(("🎬", "STRM 任务", f"{strm_tasks} 个", ""))

        rss_feeds = status_info.get("rss_feeds", 0)
        if rss_feeds > 0:
            modules.append(("📡", "RSS 订阅", f"{rss_feeds} 个", ""))

        scheduler_jobs = status_info.get("scheduler_jobs", 0)
        if scheduler_jobs > 0:
            modules.append(("⏰", "定时任务", f"{scheduler_jobs} 个", ""))

        errors = status_info.get("errors", [])

        await self.send(Notification(
            event_type=NotificationEvent.SYSTEM_STARTUP,
            data={
                "version": version,
                "start_time": start_time,
                "modules": modules,
                "errors": errors,
            },
        ))

    # ── 测试 ──

    async def notify_test(self) -> Tuple[bool, str]:
        """发送测试通知。"""
        success, msg, _ = await self.send(Notification(
            event_type=NotificationEvent.TEST,
        ))
        return success, msg

    # ── 通用下载通知（文档标准 API）──

    async def notify_download_complete(self, anime_name: str, episode: int, **data) -> bool:
        """下载完成通知。"""
        success, _, _ = await self.send(Notification(
            event_type=NotificationEvent.DOWNLOAD_COMPLETE,
            title=anime_name,
            message=f"第{episode}集下载完成",
            data={"anime_name": anime_name, "episode": episode, **data},
        ))
        return success

    async def notify_download_failed(self, anime_name: str, episode: int,
                                     error: str, **data) -> bool:
        """下载失败通知。"""
        success, _, _ = await self.send(Notification(
            event_type=NotificationEvent.DOWNLOAD_FAILED,
            title=anime_name,
            message=f"第{episode}集下载失败\n错误：{error}",
            priority=NotificationPriority.HIGH.value,
            data={"anime_name": anime_name, "episode": episode, "error": error, **data},
        ))
        return success

    async def notify_rss_updated(self, rss_name: str, new_count: int, **data) -> bool:
        """RSS 更新通知。"""
        success, _, _ = await self.send(Notification(
            event_type=NotificationEvent.RSS_UPDATED,
            title=rss_name,
            message=f"发现 {new_count} 个新资源",
            data={"rss_name": rss_name, "new_count": new_count, **data},
        ))
        return success


# 全局实例 —— 业务代码唯一入口
notification_manager = NotificationManager()
