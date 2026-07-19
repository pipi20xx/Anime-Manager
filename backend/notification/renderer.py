"""通知渲染层 —— 所有图标、排版、HTML 格式集中在此。

改样式只改本文件，不影响业务代码。
渲染器从 ``Notification.data`` 读取扩展字段，按事件类型分发到对应的排版方法；
未提供专属排版的事件回退到通用 minimal/default/detailed 样式。
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Notification

from .models import NotificationEvent


class NotificationRenderer:
    """通知渲染器：``Notification`` → Telegram HTML 文本。"""

    # 事件图标映射（改图标只改这里）
    ICONS = {
        NotificationEvent.DOWNLOAD_COMPLETE: "✅",
        NotificationEvent.DOWNLOAD_FAILED: "❌",
        NotificationEvent.TORRENT_DOWNLOAD_FAILED: "❌",
        NotificationEvent.ORGANIZE_COMPLETE: "🎬",
        NotificationEvent.ORGANIZE_FAILED: "🚨",
        NotificationEvent.SUB_ADDED: "📺",
        NotificationEvent.SUB_DELETED: "🗑️",
        NotificationEvent.SUB_COMPLETED: "🎊",
        NotificationEvent.SUB_MATCHED: "🎯",
        NotificationEvent.EPISODE_AIRED: "🎬",
        NotificationEvent.RULE_MATCHED: "⚡️",
        NotificationEvent.STRM_TASK_FINISHED: "🎬",
        NotificationEvent.STRM_LINK_CREATED: "🔗",
        NotificationEvent.STRM_WEBHOOK: "🔗",
        NotificationEvent.LIBRARY_NEW: "📺",
        NotificationEvent.LIBRARY_DELETED: "🧹",
        NotificationEvent.CLIENT_ERROR: "⚠️",
        NotificationEvent.CLIENT_PUSH_FAILED: "⚠️",
        NotificationEvent.RSS_UPDATED: "📡",
        NotificationEvent.TASK_STARTED: "🚀",
        NotificationEvent.TASK_COMPLETED: "✨",
        NotificationEvent.SYSTEM_STARTUP: "🚀",
        NotificationEvent.SYSTEM_HEALTH: "🚨",
        NotificationEvent.SYSTEM_WARNING: "🔔",
        NotificationEvent.CALENDAR_DAILY: "📅",
        NotificationEvent.DAILY_SUMMARY: "📅",
        NotificationEvent.TEST: "🔔",
        NotificationEvent.RAW: "📌",
    }

    # 事件标题前缀（改前缀只改这里）
    PREFIXES = {
        NotificationEvent.DOWNLOAD_COMPLETE: "下载完成",
        NotificationEvent.DOWNLOAD_FAILED: "下载失败",
        NotificationEvent.ORGANIZE_COMPLETE: "整理完成",
        NotificationEvent.ORGANIZE_FAILED: "整理失败",
    }

    # 通用 detailed 样式里显示的扩展字段定义：(data_key, 图标, 标签, 格式化函数)
    _GENERIC_FIELDS = [
        ("size", "💾", "大小", lambda v: v),
        ("quality", "🎬", "质量", lambda v: v),
        ("site", "📍", "站点", lambda v: v),
        ("episode", "📺", "集数", lambda v: f"第{v}集"),
    ]

    def render(self, notification: "Notification", style: str = "default") -> str:
        """渲染通知为 Telegram HTML 文本。

        Args:
            notification: 标准通知对象。
            style: ``"minimal"`` | ``"default"`` | ``"detailed"``。
                   拥有专属排版的事件忽略该参数，始终输出其规范布局。
        """
        # RAW 事件：原样返回 message，不做任何包装
        if notification.event_type == NotificationEvent.RAW:
            return notification.message

        # 优先使用事件专属排版方法
        handler_name = f"_render_{notification.event_type.value}"
        handler = getattr(self, handler_name, None)
        if handler is not None:
            return handler(notification)

        # 回退到通用样式
        if style == "minimal":
            return self._render_minimal(notification)
        if style == "detailed":
            return self._render_detailed(notification)
        return self._render_default(notification)

    # ────────────────────────────────────────────────────────
    # 通用样式
    # ────────────────────────────────────────────────────────

    def _icon(self, notification: "Notification") -> str:
        return self.ICONS.get(notification.event_type, "📌")

    def _render_minimal(self, n: "Notification") -> str:
        icon = self._icon(n)
        if n.title:
            return f"{icon} {n.title}"
        return f"{icon} {n.message}".strip()

    def _render_default(self, n: "Notification") -> str:
        icon = self._icon(n)
        if n.title:
            return f"{icon} <b>{n.title}</b>\n{n.message}".rstrip()
        return f"{icon} {n.message}".rstrip()

    def _render_detailed(self, n: "Notification") -> str:
        icon = self._icon(n)
        lines = []
        if n.title:
            lines.append(f"{icon} <b>{n.title}</b>")
        else:
            lines.append(f"{icon} <b>{self.PREFIXES.get(n.event_type, '')}</b>".rstrip())
        lines.append("")
        if n.message:
            lines.append(n.message)

        fields = []
        for key, emo, label, fmt in self._GENERIC_FIELDS:
            val = n.data.get(key)
            if val:
                fields.append(f"{emo} {label}：{fmt(val)}")
        if fields:
            lines.append("")
            lines.extend(fields)
        return "\n".join(lines).rstrip()

    # ────────────────────────────────────────────────────────
    # 工具方法
    # ────────────────────────────────────────────────────────

    @staticmethod
    def _se_info(season, episode, category: str = "") -> str:
        """构造 Sxx Exx 信息；电影返回空串。"""
        if category in ("电影", "movie"):
            return ""
        if isinstance(season, int):
            s = f"S{season:02d}"
        elif season is None:
            s = ""
        else:
            s = f"S{season}"
        e = f"E{episode:02d}" if isinstance(episode, int) else f"E{episode}"
        return f"{s} {e}".strip()

    @staticmethod
    def _range_info(media_type: str, season, start_ep, end_ep) -> str:
        """订阅范围信息（新增/删除订阅用）。"""
        if media_type != "tv" and media_type != "剧集":
            return ""
        s_str = f"S{season:02d}" if isinstance(season, int) else f"S{season}"
        e_str = f"E{start_ep}"
        if end_ep and end_ep > 0:
            e_str += f"-{end_ep}"
        else:
            e_str += "+"
        return f"🔢 <b>范围：</b>{s_str} {e_str}\n"

    # ────────────────────────────────────────────────────────
    # 事件专属排版
    # ────────────────────────────────────────────────────────

    def _render_test(self, n: "Notification") -> str:
        return (
            "<b>🔔 测试通知</b>\n\n"
            "您的 Telegram 机器人配置成功！"
        )

    def _render_sub_added(self, n: "Notification") -> str:
        d = n.data
        title = d.get("title", "")
        year = d.get("year", "")
        media_type = d.get("media_type", "tv")
        category = "电影" if media_type == "movie" else "剧集"
        range_info = self._range_info(media_type, d.get("season", 1), d.get("start_episode", 1), d.get("end_episode", 0))
        tmdb_id = d.get("tmdb_id")
        return (
            f"📺 <b>新增订阅：{title} ({year})</b>\n\n"
            f"📚 <b>类型：</b>{category}\n"
            f"{range_info}"
            f"🆔 <b>影号：</b>{tmdb_id}\n"
        )

    def _render_sub_deleted(self, n: "Notification") -> str:
        d = n.data
        title = d.get("title", "")
        year = d.get("year", "")
        media_type = d.get("media_type", "tv")
        category = "电影" if media_type == "movie" else "剧集"
        range_info = self._range_info(media_type, d.get("season", 1), d.get("start_episode", 1), d.get("end_episode", 0))
        tmdb_id = d.get("tmdb_id")
        return (
            f"🗑️ <b>已删除订阅：{title} ({year})</b>\n\n"
            f"📚 <b>类型：</b>{category}\n"
            f"{range_info}"
            f"🆔 <b>影号：</b>{tmdb_id}\n"
        )

    def _render_sub_completed(self, n: "Notification") -> str:
        d = n.data
        title = d.get("title", "")
        season = d.get("season", 1)
        media_type = d.get("media_type", "tv")
        s_info = f" (S{season:02d})" if media_type == "tv" else ""
        return (
            f"🎊 <b>订阅作品已完结</b>\n\n"
            f"🎬 <b>名称：</b>{title}{s_info}\n"
            f"✅ <b>状态：</b>所有指定集数已补全，任务已自动清理。\n"
        )

    def _render_sub_matched(self, n: "Notification") -> str:
        d = n.data
        tmdb_title = d.get("tmdb_title", "")
        year = d.get("year", "")
        category = d.get("category", "剧集")
        se_info = d.get("se_info", "")
        resolution = d.get("resolution", "") or "未知"
        team = d.get("team", "") or "未知"
        tmdb_id = d.get("tmdb_id")
        source_title = d.get("source_title", "")
        raw_title = d.get("raw_title", "Unknown")
        return (
            f"🎯 <b>发现订阅更新：{tmdb_title}</b>\n\n"
            f"🎬 <b>名称：</b>{tmdb_title} ({year})\n"
            f"🔢 <b>季集：</b>{se_info}\n"
            f"📊 <b>质量：</b>{resolution}\n"
            f"👥 <b>组名：</b>{team}\n"
            f"🆔 <b>影号：</b>{tmdb_id}\n"
            f"📋 <b>来源：</b>{source_title}\n\n"
            f"📦 <b>资源：</b><code>{raw_title}</code>\n"
        )

    def _render_episode_aired(self, n: "Notification") -> str:
        d = n.data
        title = d.get("title", "")
        season_str = d.get("season_str", "")
        ep_str = d.get("ep_str", "")
        ep_title = d.get("ep_title", "")
        air_date = d.get("air_date", "")
        return (
            f"🎬 <b>新集播出提醒</b>\n\n"
            f"📺 <b>番剧：</b>{title}\n"
            f"🔢 <b>集数：</b>{season_str}{ep_str}\n"
            f"📝 <b>标题：</b>{ep_title}\n"
            f"📅 <b>日期：</b>{air_date}\n"
        )

    def _render_rule_matched(self, n: "Notification") -> str:
        d = n.data
        rule_name = d.get("rule_name", "")
        client_name = d.get("client_name", "默认客户端")
        title = d.get("title", "")
        return (
            f"⚡️ <b>规则命中下载</b>\n\n"
            f"📋 <b>规则：</b>{rule_name}\n"
            f"📥 <b>下载：</b>{client_name}\n\n"
            f"📦 <b>资源：</b><code>{title}</code>\n"
        )

    def _render_strm_task_finished(self, n: "Notification") -> str:
        d = n.data
        task_name = d.get("task_name", "")
        duration = d.get("duration", "未知")
        strm_c = d.get("strm_created", 0)
        strm_s = d.get("strm_skipped", 0)
        meta_c = d.get("meta_copied", 0)
        meta_s = d.get("meta_skipped", 0)
        deleted = d.get("deleted", 0)
        source = d.get("source", "未知")
        return (
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
            f"📁 <b>源径：</b><code>{source}</code>"
        )

    def _render_strm_link_created(self, n: "Notification") -> str:
        d = n.data
        task_name = d.get("task_name", "")
        file_name = d.get("file_name", "")
        return (
            f"🔗 <b>整理联动生成成功</b>\n\n"
            f"📌 <b>任务：</b>{task_name}\n"
            f"📄 <b>文件：</b>{file_name}\n"
        )

    def _render_strm_webhook(self, n: "Notification") -> str:
        d = n.data
        task_names = d.get("task_names", [])
        strm_files = d.get("strm_files", {})   # {folder: [files]}
        meta_files = d.get("meta_files", {})   # {folder: [files]}

        sections = ["<b>Webhook 联动:</b>\n"]
        if task_names:
            sections.append(f"📌 <b>涉及任务:</b> {', '.join(task_names)}\n")

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

        return "\n".join(sections)

    def _render_organize_complete(self, n: "Notification") -> str:
        d = n.data
        tmdb_title = d.get("title", "Unknown")
        year = d.get("year", "")
        season = d.get("season", 1)
        episode = d.get("episode", 1)
        category = d.get("category", "未知")
        tmdb_id = d.get("tmdb_id")
        origin_country = d.get("origin_country", "") or "未知"
        resolution = d.get("resolution", "") or "未知"
        source = d.get("source", "") or "未知"
        platform = d.get("platform", "") or "未知"
        team = d.get("team", "") or "未知"
        file_size = d.get("file_size", "未知")
        duration = d.get("duration", "未知")
        file_name = d.get("filename", "Unknown")

        se_info = self._se_info(season, episode, category)

        return (
            f"🎬 <b>{tmdb_title} ({year}) {se_info} 已入库</b>\n"
            f"📚 <b>类型：</b>{category}\n"
            f"🆔 <b>影号：</b>{tmdb_id}\n"
            f"🌍 <b>产地：</b>{origin_country}\n"
            f"📊 <b>质量：</b>{resolution}\n"
            f"💿 <b>介质：</b>{source}\n"
            f"📡 <b>平台：</b>{platform}\n"
            f"👥 <b>组名：</b>{team}\n"
            f"💾 <b>大小：</b>{file_size}\n"
            f"⏱️ <b>用时：</b>{duration}\n\n"
            f"📄 <b>原始：</b><code>{file_name}</code>\n"
        )

    def _render_organize_failed(self, n: "Notification") -> str:
        d = n.data
        file_name = d.get("file_name", "")
        file_path = d.get("file_path", "")
        error = d.get("error", "")
        return (
            f"🚨 <b>整理执行异常</b>\n\n"
            f"📄 <b>文件：</b><code>{file_name}</code>\n"
            f"❌ <b>错误：</b>{error}\n"
            f"📂 <b>路径：</b><code>{file_path}</code>\n\n"
            f"请检查识别结果或目标磁盘挂载状态。"
        )

    def _render_library_new(self, n: "Notification") -> str:
        d = n.data
        category = d.get("category", "")
        display_title = d.get("display_title", "")
        se_info = d.get("se_info", "")
        rating = d.get("rating")
        rating_str = rating if rating else "暂无"
        formatted_date = d.get("formatted_date", "未知")
        overview = d.get("overview", "") or "暂无简介"
        return (
            f"📺 <b>新入库 {category} {display_title} {se_info}</b>\n"
            f"⭐️ <b>评分：</b>{rating_str}/10\n"
            f"📚 <b>类型：</b>{category}\n"
            f"🕒 <b>时间：</b>{formatted_date}\n\n"
            f"📝 <b>剧情：</b>{overview}\n"
            f"─── 来自 Emby Webhook ───"
        )

    def _render_library_deleted(self, n: "Notification") -> str:
        d = n.data
        files = d.get("files", [])
        msg = "Emby深度删除\n\n"
        for filename in files:
            msg += f"{filename}\n"
        msg += "\n─── 来自 Emby Webhook ───"
        return msg

    def _render_client_error(self, n: "Notification") -> str:
        d = n.data
        resource_name = d.get("resource_name", "")
        client_name = d.get("client_name", "")
        final_error = d.get("final_error", "")
        return (
            f"⚠️ <b>下载任务执行异常</b>\n\n"
            f"📦 <b>资源：</b><code>{resource_name}</code>\n"
            f"📡 <b>客户端：</b>{client_name}\n"
            f"❌ <b>错误信息：</b>{final_error}"
        )

    def _render_torrent_download_failed(self, n: "Notification") -> str:
        d = n.data
        title = d.get("title", "")
        link = d.get("link", "")
        error = d.get("error", "")
        is_fallback = d.get("is_fallback", False)
        prefix = "🔄 " if is_fallback else ""
        link_short = f"{link[:80]}{'...' if len(link) > 80 else ''}"
        return (
            f"{prefix}❌ <b>种子下载失败</b>\n\n"
            f"📦 <b>资源：</b><code>{title}</code>\n"
            f"🔗 <b>链接：</b><code>{link_short}</code>\n"
            f"❌ <b>错误：</b>{error}"
        )

    def _render_client_push_failed(self, n: "Notification") -> str:
        d = n.data
        title = d.get("title", "")
        client_name = d.get("client_name", "")
        error = d.get("error", "")
        return (
            f"⚠️ <b>推送客户端失败</b>\n\n"
            f"📦 <b>资源：</b><code>{title}</code>\n"
            f"📡 <b>客户端：</b>{client_name}\n"
            f"❌ <b>错误：</b>{error}"
        )

    def _render_system_health(self, n: "Notification") -> str:
        d = n.data
        name = d.get("name", "")
        status = d.get("status", "")
        file_path = d.get("file_path", "")
        return (
            f"🚨 <b>系统健康告警</b>\n\n"
            f"📌 <b>项目：</b>{name}\n"
            f"❌ <b>状态：</b>{status}\n"
            f"📁 <b>路径：</b><code>{file_path}</code>\n\n"
            f"请检查硬盘挂载状态或下载器 Cookie 是否有效。"
        )

    def _render_calendar_daily(self, n: "Notification") -> str:
        d = n.data
        header = d.get("header", "")
        lines = d.get("lines", [])
        sections = [header]
        sections.extend(lines)
        sections.append("\n记得及时检查下载器状态哦~")
        return "\n".join(sections)

    def _render_daily_summary(self, n: "Notification") -> str:
        """每日番剧播出摘要。"""
        items = n.data.get("items", [])
        lines = ["📅 <b>今日番剧播出</b>\n"]
        for item in items:
            season = item.get("season")
            season_str = f"S{season:02d}" if season else ""
            ep_num = item.get("episode")
            ep_str = f"E{ep_num:02d}" if isinstance(ep_num, int) else f"E{ep_num}"
            lines.append(f"🎬 {item.get('title', '未知')} {season_str}{ep_str}")
            lines.append(f"   └ {item.get('ep_title', '')}\n")
        return "\n".join(lines)

    def _render_system_startup(self, n: "Notification") -> str:
        d = n.data
        version = d.get("version", "unknown")
        start_time = d.get("start_time", "")
        modules = d.get("modules", [])          # [(icon, name, value, detail), ...]
        errors = d.get("errors", [])

        lines = []
        lines.append("<b>🚀 番剧管家 启动完成</b>")
        lines.append("──────────────────")
        lines.append(f"🏷 <b>版本：</b><code>v{version}</code>")
        lines.append(f"🕓 <b>时间：</b>{start_time}")

        if modules:
            lines.append("")
            lines.append("<b>📋 服务状态</b>")
            for icon, name, value, detail in modules:
                lines.append(f"· {icon} <b>{name}</b> — {value}{detail}")

        if errors:
            lines.append("")
            lines.append("<b>⚠️ 启动警告</b>")
            for err in errors[:3]:
                lines.append(f"• {err}")

        lines.append("")
        lines.append("<i>💡 系统已就绪，等待任务调度...</i>")
        return "\n".join(lines)


# 全局共享渲染器实例（无状态，可安全共享）
renderer = NotificationRenderer()
