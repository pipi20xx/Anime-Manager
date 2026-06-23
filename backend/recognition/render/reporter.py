from ..context import RecognitionContext

class RenderReporter:
    """
    负责最终结论的汇报、日志打印及审计写入。
    """
    @staticmethod
    def report(ctx: RecognitionContext, data_packet: dict):
        # 1. 性能统计
        ctx.log(f"⏱️ [性能审计]: 全链路耗时 {int(ctx.duration * 1000)}ms ({' | '.join(ctx.perf_stats)})")

        f = data_packet["final_result"]

        # 2. 控制台结论汇报
        ctx.log("📢 [最终结论汇报 (标准化元数据)]")

        sec_cat = f.get('secondary_category')
        if str(sec_cat) == '123':
            sec_cat = "未分类 (待修正)"

        lines = [
            f"🎬 标题 {{title}}: {f['title']}",
            f"📆 年份 {{year}}: {f.get('year') or 'null'}",
            f"🆔 TMDB ID {{tmdb_id}}: {f['tmdb_id']}",
            f"🎦 类型 {{category}}: {f.get('category') or 'null'}",
            f"📅 季号 {{season}}: {f.get('season', 1)} | 集号 {{episode}}: {f.get('episode', '')}",
            f"🏷️ 二级分类 {{secondary_category}}: {sec_cat or 'null'}",
            f"🌍 原产地 {{origin_country}}: {f.get('origin_country') or 'null'}",
            f"👥 制作组 {{team}}: {f.get('team') or 'null'}",
            f"📺 分辨率 {{resolution}}: {f.get('resolution') or 'null'}",
            f"🎞️ 视频编码 {{video_encode}}: {f.get('video_encode') or 'null'}",
            f"🔊 音频编码 {{audio_encode}}: {f.get('audio_encode') or 'null'}",
            f"💬 字幕语言 {{subtitle}}: {f.get('subtitle') or 'null'}",
            f"💿 介质来源 {{source}}: {f.get('source') or 'null'}",
            f"📡 发布平台 {{platform}}: {f.get('platform') or 'null'}",
            f"📄 渲染后名 {{processed_name}}: {f['processed_name']}",
        ]

        for i, line in enumerate(lines):
            prefix = "┗" if i == len(lines) - 1 else "┣"
            ctx.log(f"{prefix} {line}")

        data_packet["logs"] = ctx.logs
        return data_packet