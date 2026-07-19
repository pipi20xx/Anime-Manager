import httpx
import logging
import re
import os
from typing import Any
from config_manager import ConfigManager
from logger import log_audit

logger = logging.getLogger("Notification")

class NotificationManager:
    @staticmethod
    def _get_tmdb_image_url(poster_path: str) -> str:
        """
        将图片路径转换为公网可访问的完整 URL（用于 Telegram 等外部服务）。
        处理以下格式：
        - 完整 URL (http/https) → 直接返回
        - TMDB 本地代理路径 /api/system/img?path=/w500/abc.jpg → 解码并拼成 TMDB 公网 URL
        - Bangumi 本地代理路径 /api/system/bgm_img?url=https%3A%2F%2F... → 解码出原始 URL
        - TMDB 原始路径 /abc.jpg 或 /w500/abc.jpg → 拼成 TMDB 公网 URL
        :return: 公网可访问的图片 URL；无法识别时返回 None（只发文本通知）
        """
        if not poster_path:
            return None

        from urllib.parse import parse_qs, urlparse, unquote

        # 完整 URL，直接返回
        if poster_path.startswith("http"):
            return poster_path

        # TMDB 本地代理路径：/api/system/img?path=%2Fw500%2Fabc.jpg
        # 解码出 path 参数，还原成 TMDB 原始路径，再拼公网 URL
        if "/api/system/img" in poster_path:
            parsed = urlparse(poster_path)
            qs = parse_qs(parsed.query)
            raw_path = qs.get("path", [None])[0]
            if raw_path:
                # 去掉尺寸前缀 /w500/xxx → /xxx
                size_match = re.match(r"^/(w\d+|original)(/.*)$", raw_path)
                clean_path = size_match.group(2) if size_match else raw_path
                if not clean_path.startswith("/"):
                    clean_path = "/" + clean_path
                image_domain = ConfigManager.get_tmdb_image_domain()
                return f"https://{image_domain}/t/p/original{clean_path}"
            return None

        # Bangumi 本地代理路径：/api/system/bgm_img?url=https%3A%2F%2F...
        # 解码出原始 Bangumi 图片 URL，供 Telegram 直接下载
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
    
    @staticmethod
    async def send_telegram_message(text: str, photo_url: str = None, pin: bool = False):
        """
        发送 Telegram 消息，支持图片和置顶。
        :param text: 消息文本 (支持 MarkdownV2 或 HTML，这里暂用纯文本或简单Markdown)
        :param photo_url: 图片的 URL（可选）
        :param pin: 是否置顶消息（可选）
        :return: (success: bool, message: str, message_id: int|None)
        """
        config = ConfigManager.get_config()
        tg_conf = config.get("telegram", {})
        
        if not tg_conf.get("enabled"):
            return False, "Telegram notification is disabled", None

        bot_token = tg_conf.get("bot_token")
        chat_id = tg_conf.get("chat_id")

        if not bot_token or not chat_id:
            return False, "Missing Bot Token or Chat ID", None

        proxy = ConfigManager.get_proxy("telegram")
        
        base_url = f"https://api.telegram.org/bot{bot_token}"
        
        try:
            async with httpx.AsyncClient(proxy=proxy, timeout=10.0) as client:
                if photo_url:
                    url = f"{base_url}/sendPhoto"
                    payload = {
                        "chat_id": chat_id,
                        "photo": photo_url,
                        "caption": text,
                        "parse_mode": "HTML"
                    }
                    resp = await client.post(url, json=payload)
                else:
                    url = f"{base_url}/sendMessage"
                    payload = {
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": "HTML"
                    }
                    resp = await client.post(url, json=payload)

                if resp.status_code == 200:
                    result = resp.json()
                    message_id = result.get("result", {}).get("message_id")
                    
                    if pin and message_id:
                        await NotificationManager.pin_chat_message(chat_id, message_id, bot_token, client)
                    
                    log_audit("通知", "发送成功", "Telegram 消息发送成功", level="DEBUG")
                    return True, "Success", message_id
                else:
                    err_msg = f"Telegram API Error: {resp.status_code} - {resp.text}"
                    logger.error(err_msg)
                    log_audit("通知", "发送失败", f"Telegram 发送失败: {resp.status_code}", level="ERROR")
                    return False, err_msg, None

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            log_audit("通知", "发送异常", f"Telegram 发送异常: {str(e)}", level="ERROR")
            return False, str(e), None

    @staticmethod
    async def pin_chat_message(chat_id: str, message_id: int, bot_token: str = None, client: httpx.AsyncClient = None):
        """
        置顶 Telegram 消息
        :param chat_id: 聊天 ID
        :param message_id: 消息 ID
        :param bot_token: Bot Token（可选，不传则从配置读取）
        :param client: httpx 客户端（可选，不传则创建新的）
        """
        config = ConfigManager.get_config()
        tg_conf = config.get("telegram", {})
        
        if not bot_token:
            bot_token = tg_conf.get("bot_token")
        
        if not bot_token:
            logger.warning("无法置顶消息：缺少 Bot Token")
            return False
        
        base_url = f"https://api.telegram.org/bot{bot_token}"
        proxy = ConfigManager.get_proxy("telegram")
        
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(proxy=proxy, timeout=10.0)
        
        try:
            url = f"{base_url}/pinChatMessage"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "disable_notification": True
            }
            resp = await client.post(url, json=payload)
            
            if resp.status_code == 200:
                logger.info(f"消息 {message_id} 已置顶")
                return True
            else:
                logger.warning(f"置顶消息失败: {resp.status_code} - {resp.text}")
                return False
        except Exception as e:
            logger.error(f"置顶消息异常: {e}")
            return False
        finally:
            if own_client:
                await client.aclose()

    @staticmethod
    async def push_sub_add_notification(sub: Any):
        """新增订阅通知 (美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_sub_add", True): return

        def get_val(obj, key, default=None):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        title = get_val(sub, "title")
        year = get_val(sub, "year", "")
        poster_path = get_val(sub, "poster_path")
        media_type = get_val(sub, "media_type", "tv")
        season = get_val(sub, "season", 1)
        start_ep = get_val(sub, "start_episode", 1)
        end_ep = get_val(sub, "end_episode", 0)
        category = "电影" if media_type == "movie" else "剧集"

        # 构造范围信息
        range_info = ""
        if media_type == "tv":
            s_str = f"S{season:02d}" if isinstance(season, int) else f"S{season}"
            e_str = f"E{start_ep}"
            if end_ep > 0:
                e_str += f"-{end_ep}"
            else:
                e_str += "+"
            range_info = f"🔢 <b>范围：</b>{s_str} {e_str}\n"

        msg = (
            f"📺 <b>新增订阅：{title} ({year})</b>\n\n"
            f"📚 <b>类型：</b>{category}\n"
            f"{range_info}"
            f"🆔 <b>影号：</b>{get_val(sub, 'tmdb_id')}\n"
        )

        photo_url = NotificationManager._get_tmdb_image_url(poster_path)

        await NotificationManager.send_telegram_message(msg, photo_url=photo_url)

    @staticmethod
    async def push_health_check_notification(name: str, status: str, file_path: str):
        """健康检查失败通知"""
        msg = (
            f"🚨 <b>系统健康告警</b>\n\n"
            f"📌 <b>项目：</b>{name}\n"
            f"❌ <b>状态：</b>{status}\n"
            f"📁 <b>路径：</b><code>{file_path}</code>\n\n"
            f"请检查硬盘挂载状态或下载器 Cookie 是否有效。"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_sub_del_notification(sub: Any):
        """删除订阅通知 (美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_sub_del", True): return

        def get_val(obj, key, default=None):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        title = get_val(sub, "title")
        year = get_val(sub, "year", "")
        poster_path = get_val(sub, "poster_path")
        media_type = get_val(sub, "media_type", "tv")
        season = get_val(sub, "season", 1)
        start_ep = get_val(sub, "start_episode", 1)
        end_ep = get_val(sub, "end_episode", 0)
        category = "电影" if media_type == "movie" else "剧集"

        # 构造范围信息
        range_info = ""
        if media_type == "tv":
            s_str = f"S{season:02d}" if isinstance(season, int) else f"S{season}"
            e_str = f"E{start_ep}"
            if end_ep > 0:
                e_str += f"-{end_ep}"
            else:
                e_str += "+"
            range_info = f"🔢 <b>范围：</b>{s_str} {e_str}\n"

        msg = (
            f"🗑️ <b>已删除订阅：{title} ({year})</b>\n\n"
            f"📚 <b>类型：</b>{category}\n"
            f"{range_info}"
            f"🆔 <b>影号：</b>{get_val(sub, 'tmdb_id')}\n"
        )

        photo_url = NotificationManager._get_tmdb_image_url(poster_path)

        await NotificationManager.send_telegram_message(msg, photo_url=photo_url)

    @staticmethod
    async def push_sub_complete_notification(sub: Any):
        """订阅完结通知 (美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_sub_complete", True): return

        def get_val(obj, key, default=None):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        title = get_val(sub, "title")
        poster_path = get_val(sub, "poster_path")
        season = get_val(sub, "season", 1)
        media_type = get_val(sub, "media_type", "tv")

        s_info = f" (S{season:02d})" if media_type == "tv" else ""

        msg = (
            f"🎊 <b>订阅作品已完结</b>\n\n"
            f"🎬 <b>名称：</b>{title}{s_info}\n"
            f"✅ <b>状态：</b>所有指定集数已补全，任务已自动清理。\n"
        )

        photo_url = NotificationManager._get_tmdb_image_url(poster_path)

        await NotificationManager.send_telegram_message(msg, photo_url=photo_url)

    @staticmethod
    async def push_sub_push_notification(sub: Any, item: Any):
        """订阅命中推送通知 (美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_sub_push", True): return

        def get_val(obj, key, default=None):
            if isinstance(obj, dict): return obj.get(key, default)
            return getattr(obj, key, default)

        tmdb_title = get_val(item, "tmdb_title") or get_val(item, "title") or get_val(sub, "title")
        season = get_val(item, "season")
        episode = get_val(item, "episode")
        category = get_val(item, "media_type") or get_val(item, "category")
        category = "电影" if category == "movie" or category == "电影" else "剧集"
        
        year = get_val(sub, "year") or ""
        resolution = get_val(item, "resolution") or ""
        team = get_val(item, "team") or ""
        poster_path = get_val(sub, "poster_path")
        tmdb_id = get_val(sub, "tmdb_id")
        raw_title = get_val(item, "title") or "Unknown"

        se_info = f"S{season:02d} E{episode}" if isinstance(season, int) else f"S{season} E{episode}"
        if category == "电影": se_info = ""

        msg = (
            f"🎯 <b>发现订阅更新：{tmdb_title}</b>\n\n"
            f"🎬 <b>名称：</b>{tmdb_title} ({year})\n"
            f"🔢 <b>季集：</b>{se_info}\n"
            f"📊 <b>质量：</b>{resolution or '未知'}\n"
            f"👥 <b>组名：</b>{team or '未知'}\n"
            f"🆔 <b>影号：</b>{tmdb_id}\n"
            f"📋 <b>来源：</b>{get_val(sub, 'title')}\n\n"
            f"📦 <b>资源：</b><code>{raw_title}</code>\n"
        )

        photo_url = NotificationManager._get_tmdb_image_url(poster_path)

        await NotificationManager.send_telegram_message(msg, photo_url=photo_url)

    @staticmethod
    async def push_rule_push_notification(title: str, rule_name: str, client_name: str = "默认客户端"):
        """规则命中推送通知 (极简美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_rule_push", True): return

        msg = (
            f"⚡️ <b>规则命中下载</b>\n\n"
            f"📋 <b>规则：</b>{rule_name}\n"
            f"📥 <b>下载：</b>{client_name}\n\n"
            f"📦 <b>资源：</b><code>{title}</code>\n"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_strm_finish_notification(task_name: str, stats: dict):
        """STRM 任务完成通知 (深度明细版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_strm_finish", True): return

        duration = stats.get("duration", "未知")
        
        # 提取细分统计
        strm_c = stats.get('strm_created', 0)
        strm_s = stats.get('strm_skipped', 0)
        meta_c = stats.get('meta_copied', 0)
        meta_s = stats.get('meta_skipped', 0)
        deleted = stats.get('deleted', 0)

        msg = (
            f"🎬 <b>STRM 任务处理完成</b>\n\n"
            f"📌 <b>任务名称：</b>{task_name}\n"
            f"──────────────────\n"
            f"📄 <b>STRM 文件：</b>\n"
            f"   ├ ✅ 新增：{strm_c}\n"
            f"   └ ⏭️ 跳过：{strm_s}\n\n"
            f"🖼️ <b>元数据文件：</b>\n"
            f"   ├ ✅ 同步：{meta_c}\n"
            f"   └ ⏭️ 跳过：{meta_s}\n\n"
            f"🧹 <b>清理冗余：</b>{deleted}\n"
            f"⏱️ <b>总计耗时：</b>{duration}\n"
            f"──────────────────\n"
            f"📁 <b>源径：</b><code>{stats.get('source', '未知')}</code>"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_strm_link_notification(file_name: str, task_name: str):
        """STRM 整理联动生成通知"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_strm_link", True): return

        msg = (
            f"🔗 <b>整理联动生成成功</b>\n\n"
            f"📌 <b>任务：</b>{task_name}\n"
            f"📄 <b>文件：</b>{file_name}\n"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_webhook_strm_notification(results: list):
        """Webhook 实时监控通知 (支持多文件分组显示)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_strm_link", True): 
            return

        success_results = [r for r in results if r and r.get("status") == "success"]
        if not success_results:
            return

        strm_files = {}
        meta_files = {}
        task_names = set()

        for res in success_results:
            rel_path = res.get("rel_path")
            target_root = res.get("target_root", "")
            task_name = res.get("task_name")
            
            if task_name:
                task_names.add(task_name)
            if not rel_path: continue
            
            full_path = os.path.join(target_root, rel_path) if target_root else rel_path
            folder = os.path.dirname(full_path) or "/"
            filename = os.path.basename(full_path)
            
            msg_type = res.get("message", "")
            if "STRM" in msg_type:
                if folder not in strm_files: strm_files[folder] = []
                strm_files[folder].append(filename)
            elif "Meta" in msg_type:
                if folder not in meta_files: meta_files[folder] = []
                meta_files[folder].append(filename)

        if not strm_files and not meta_files:
            return

        sections = ["<b>Webhook 联动:</b>\n"]
        
        if task_names:
            task_str = ", ".join(task_names)
            sections.append(f"📌 <b>涉及任务:</b> {task_str}\n")

        if strm_files:
            sections.append("🔗 <b>成功创建Strm文件</b>\n")
            for folder, files in strm_files.items():
                sections.append(f"--- 📁 <code>{folder}</code>")
                for i, f in enumerate(files):
                    char = "└──" if i == len(files) - 1 else "├──"
                    sections.append(f"     {char} {f}")
            sections.append("")

        if meta_files:
            sections.append("📋 <b>成功复制元数据</b>\n")
            for folder, files in meta_files.items():
                sections.append(f"--- 📁 <code>{folder}</code>")
                for i, f in enumerate(files):
                    char = "└──" if i == len(files) - 1 else "├──"
                    sections.append(f"     {char} {f}")
            sections.append("")

        final_msg = "\n".join(sections)
        await NotificationManager.send_telegram_message(final_msg)

    @staticmethod
    async def push_organize_notification(final_res: dict):
        """整理完成通知 (全能美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_organize", True): return

        file_name = final_res.get("filename", "Unknown")
        tmdb_title = final_res.get("title", "Unknown")
        season = final_res.get("season", 1)
        episode = final_res.get("episode", 1)
        tmdb_id = final_res.get("tmdb_id")
        category = final_res.get("category", "未知")
        year = final_res.get("year", "")
        resolution = final_res.get("resolution", "")
        team = final_res.get("team", "")
        poster_path = final_res.get("poster_path")
        rating = final_res.get("vote_average")
        duration = final_res.get("duration", "未知")
        file_size = final_res.get("file_size", "未知")
        file_count = final_res.get("file_count", 1)

        # 构造集数
        se_info = f"S{season:02d} E{episode}" if isinstance(season, int) else f"S{season} E{episode}"
        if category == "电影": se_info = ""

        # 评分转换
        rating_str = f"{rating:.1f}/10" if rating else "暂无评分"

        msg = (
            f"🎬 <b>{tmdb_title} ({year}) {se_info} 已入库</b>\n"
            f"📚 <b>类型：</b>{category}\n"
            f"📊 <b>质量：</b>{resolution or '未知'}\n"
            f"📂 <b>文件：</b>{file_count}个\n"
            f"💾 <b>大小：</b>{file_size}\n"
            f"🆔 <b>影号：</b>{tmdb_id}\n"
            f"👥 <b>组名：</b>{team or '未知'}\n"
            f"⏱️ <b>用时：</b>{duration}\n\n"
            f"📄 <b>原始：</b><code>{file_name}</code>\n"
        )

        photo_url = NotificationManager._get_tmdb_image_url(poster_path)

        await NotificationManager.send_telegram_message(msg, photo_url=photo_url)

    @staticmethod
    async def push_library_new_notification(payload: dict):
        """Emby 新入库通知 (精简美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("enabled"): return
        if not config.get("telegram", {}).get("notify_on_library_new", True): return

        item = payload.get("Item", {})
        media_type = item.get("Type")
        
        is_tv = media_type in ["Series", "Episode"]
        category = "剧集" if is_tv else "电影"
        
        # 提取标题
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
        
        # 构造季集信息
        se_info = ""
        if media_type == "Episode":
            s_num = item.get("ParentIndexNumber")
            e_num = item.get("IndexNumber")
            if s_num is not None and e_num is not None:
                se_info = f"S{s_num:02d} E{e_num:02d}"
                if episode_name:
                    se_info += f" {episode_name}"

        # 格式化时间
        from datetime import datetime, timedelta
        date_str = payload.get("Date", "")
        formatted_date = "未知"
        try:
            clean_date = date_str.split('.')[0].replace('Z', '')
            dt = datetime.fromisoformat(clean_date)
            dt = dt + timedelta(hours=8)
            formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            formatted_date = date_str[:19].replace('T', ' ')

        # 剧情简介截断
        if overview and len(overview) > 150:
            overview = overview[:150] + "..."

        msg = (
            f"📺 <b>新入库 {category} {display_title} {se_info}</b>\n"
            f"⭐️ <b>评分：</b>{rating or '暂无'}/10\n"
            f"📚 <b>类型：</b>{category}\n"
            f"🕒 <b>时间：</b>{formatted_date}\n\n"
            f"📝 <b>剧情：</b>{overview or '暂无简介'}\n"
            f"─── 来自 Emby Webhook ───"
        )

        # 图片处理：优先寻找本地 fanart.jpg
        photo_url = None
        if path:
            try:
                # 寻找策略：文件同级目录，或者往上找两级（Season 目录或剧集根目录）
                current_dir = os.path.dirname(path)
                search_dirs = [current_dir]
                # 往上走两级
                p1 = os.path.dirname(current_dir)
                if p1: search_dirs.append(p1)
                p2 = os.path.dirname(p1)
                if p2: search_dirs.append(p2)

                for d in search_dirs:
                    if not os.path.isdir(d): continue
                    # 按照优先级寻找图片
                    for img_name in ["fanart.jpg", "backdrop.jpg", "poster.jpg", "folder.jpg"]:
                        img_path = os.path.join(d, img_name)
                        if os.path.exists(img_path):
                            from urllib.parse import quote
                            photo_url = f"/api/system/img?path={quote(img_path)}"
                            break
                    if photo_url: break
            except: pass

        # 如果本地没找到，且有 TMDB ID (虽然不显示但可以用来拿图)，作为备选
        if not photo_url:
            tmdb_id = item.get("ProviderIds", {}).get("Tmdb")
            # 尝试从路径解析 (仅作为拿图辅助)
            if not tmdb_id and path:
                import re
                match = re.search(r"\[tmdbid=(\d+)\]", path)
                if match: tmdb_id = match.group(1)
            
            if tmdb_id:
                try:
                    from recognition.data_provider.tmdb.client import TMDBProvider
                    provider = TMDBProvider()
                    m_type = "tv" if is_tv else "movie"
                    details = await provider.get_subject_details(str(tmdb_id), m_type)
                    if details and details.get("backdrop_path"):
                        photo_url = details.get("backdrop_path")
                        if "path=" in photo_url:
                            from urllib.parse import parse_qs, urlparse
                            qs = parse_qs(urlparse(photo_url).query)
                            if "path" in qs: photo_url = qs["path"][0]
                        photo_url = NotificationManager._get_tmdb_image_url(photo_url)
                except: pass

        await NotificationManager.send_telegram_message(msg, photo_url=photo_url)

    @staticmethod
    async def push_emby_delete_notification(payload):
        """Emby 删除事件通知"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("enabled"): return

        file_list = []

        # 处理 deep.delete 事件格式
        if isinstance(payload, dict) and payload.get("Event") == "deep.delete":
            description = payload.get("Description", "")
            # 从Description中提取Mount Paths部分的文件
            if "Mount Paths:" in description:
                mount_paths_section = description.split("Mount Paths:")[1].strip()
                # 按行分割，提取文件名
                for line in mount_paths_section.split('\n'):
                    line = line.strip()
                    if line:
                        filename = os.path.basename(line)
                        if filename and filename != line:  # 确保是文件路径而不是目录
                            file_list.append(filename)
        # 处理旧格式：list of dicts
        elif isinstance(payload, list):
            for item in payload:
                is_dir = str(item.get("is_dir", "false")).lower()
                if is_dir != "true":
                    source_file = item.get("source_file", "")
                    if source_file:
                        filename = os.path.basename(source_file)
                        file_list.append(filename)

        if not file_list:
            return

        # 构造消息
        msg = f"Emby深度删除\n\n"
        for filename in file_list:
            msg += f"{filename}\n"
        msg += "\n─── 来自 Emby Webhook ───"

        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_client_error_notification(resource_name: str, client_name: str, error_message: str):
        """客户端报错通知"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_client_error", True): return

        # 简单错误信息中文化映射
        error_map = {
            "login failed": "登录失败，请检查账号密码",
            "connection timed out": "连接超时，请检查网络或IP端口",
            "max retries exceeded": "连接失败，目标主机不可达",
            "rpc error": "RPC 远程调用错误",
            "timed out": "请求超时"
        }
        
        final_error = error_message
        for k, v in error_map.items():
            if k in error_message.lower():
                final_error = f"{v}\n<pre>{error_message}</pre>"
                break

        msg = (
            f"⚠️ <b>下载任务执行异常</b>\n\n"
            f"📦 <b>资源：</b><code>{resource_name}</code>\n"
            f"📡 <b>客户端：</b>{client_name}\n"
            f"❌ <b>错误信息：</b>{final_error}"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_torrent_download_error(title: str, link: str, error_message: str, is_fallback: bool = False):
        """种子文件下载失败通知"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_client_error", True): return

        prefix = "🔄 " if is_fallback else ""
        msg = (
            f"{prefix}❌ <b>种子下载失败</b>\n\n"
            f"📦 <b>资源：</b><code>{title}</code>\n"
            f"🔗 <b>链接：</b><code>{link[:80]}{'...' if len(link) > 80 else ''}</code>\n"
            f"❌ <b>错误：</b>{error_message}"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_client_push_error(title: str, client_name: str, error_message: str):
        """推送客户端失败通知"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_client_error", True): return

        msg = (
            f"⚠️ <b>推送客户端失败</b>\n\n"
            f"📦 <b>资源：</b><code>{title}</code>\n"
            f"📡 <b>客户端：</b>{client_name}\n"
            f"❌ <b>错误：</b>{error_message}"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_organize_error_notification(file_path: str, error_message: str):
        """整理执行异常通知"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_organize_error", True): return

        file_name = os.path.basename(file_path)
        msg = (
            f"🚨 <b>整理执行异常</b>\n\n"
            f"📄 <b>文件：</b><code>{file_name}</code>\n"
            f"❌ <b>错误：</b>{error_message}\n"
            f"📂 <b>路径：</b><code>{file_path}</code>\n\n"
            f"请检查识别结果或目标磁盘挂载状态。"
        )
        await NotificationManager.send_telegram_message(msg)

    @staticmethod
    async def push_daily_calendar_summary(subjects: list):
        """每日播出概览通知 (聚合美化版)"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("enabled"): return
        
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        weekday_cn = ["一", "二", "三", "四", "五", "六", "日"][datetime.now().weekday()]

        sections = [f"📅 <b>今日播出概览 ({today_str} 周{weekday_cn})</b>\n"]
        
        if not subjects:
            sections.append("今天暂无订阅剧集播出。")
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
                sections.append(f"{char} <b>{title}</b> (S{season:02d}){ep_info}")

        sections.append("\n记得及时检查下载器状态哦~")
        final_msg = "\n".join(sections)
        
        photo_url = None
        if len(subjects) == 1 and subjects[0].get("poster_path"):
            path = subjects[0]["poster_path"]
            if path and path.strip():
                photo_url = NotificationManager._get_tmdb_image_url(path)

        pin_message = config.get("calendar_pin_message", False)
        success, msg, _ = await NotificationManager.send_telegram_message(final_msg, photo_url=photo_url, pin=pin_message)
        
        if not success and photo_url:
            logger.warning(f"带图片发送失败，尝试仅发送文本: {msg}")
            success, msg, _ = await NotificationManager.send_telegram_message(final_msg, photo_url=None, pin=pin_message)
        
        return success, msg

    @staticmethod
    async def push_startup_notification(status_info: dict):
        """系统启动通知 - 汇报各功能模块状态（HTML 格式美化版）"""
        config = ConfigManager.get_config()
        if not config.get("telegram", {}).get("notify_on_startup", True): return

        from datetime import datetime
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ── 收集模块状态 ──
        modules = []

        # CD2 监控
        cd2_status = status_info.get("cd2_monitor", {})
        if cd2_status.get("enabled"):
            running = cd2_status.get("running", False)
            icon = "🟢" if running else "🔴"
            label = "运行中" if running else "未启动"
            detail = ""
            if cd2_status.get("client"):
                detail = f' <code>{cd2_status["client"]}</code>'
            modules.append((icon, "CD2 监控", label, detail))

        # 整理任务
        organize_tasks = status_info.get("organize_tasks", 0)
        if organize_tasks > 0:
            modules.append(("🟢", "整理任务", f"{organize_tasks} 个", ""))

        # STRM 任务
        strm_tasks = status_info.get("strm_tasks", 0)
        if strm_tasks > 0:
            modules.append(("🟢", "STRM 任务", f"{strm_tasks} 个", ""))

        # RSS 订阅
        rss_feeds = status_info.get("rss_feeds", 0)
        if rss_feeds > 0:
            modules.append(("🟢", "RSS 订阅", f"{rss_feeds} 个", ""))

        # 定时任务
        scheduler_jobs = status_info.get("scheduler_jobs", 0)
        if scheduler_jobs > 0:
            modules.append(("🟢", "定时任务", f"{scheduler_jobs} 个", ""))

        # ── 构建 HTML 消息 ──
        lines = []

        # 标题区 - 使用引用块风格
        lines.append(f"<b>🚀 番剧管家 启动完成</b>")
        lines.append(f"<blockquote>🕓 {start_time}</blockquote>")

        # 模块状态列表
        if modules:
            lines.append("")
            lines.append("<b>📋 服务状态</b>")
            for icon, name, value, detail in modules:
                lines.append(f"▪️ <b>{name}</b> — {value}{detail}")

        # 错误/警告
        errors = status_info.get("errors", [])
        if errors:
            lines.append("")
            lines.append("<b>⚠️ 启动警告</b>")
            for err in errors[:3]:
                lines.append(f"• {err}")

        # 底部
        lines.append("")
        lines.append("<i>💡 系统已就绪，等待任务调度...</i>")

        await NotificationManager.send_telegram_message("\n".join(lines))
