import time
from logger import log_audit
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
        ctx.log(f"┣ 🎬 标题 {{title}}: {f['title']} ({f.get('year', '')})")
        ctx.log(f"┣ 🆔 TMDB ID {{tmdb_id}}: {f['tmdb_id']} [{f.get('category', '未知')}]")
        ctx.log(f"┣ 📅 季号 {{season}}: {f.get('season', 1)} | 集号 {{episode}}: {f.get('episode', '')}")
        
        sec_cat = f.get('secondary_category')
        if str(sec_cat) == '123': sec_cat = "未分类 (待修正)"
        ctx.log(f"┣ 🏷️ 二级分类: {sec_cat or '未命中'}")
        
        if f.get('origin_country'): 
            ctx.log(f"┣ 🌍 原产地 {{origin_country}}: {f['origin_country']}")
            
        specs = []
        if f.get('team'): specs.append(f"👥 制作组 {{team}}: {f['team']}")
        if f.get('resolution'): specs.append(f"📺 分辨率 {{resolution}}: {f['resolution']}")
        if f.get('video_encode'): specs.append(f"🎞️ 视频编码: {f['video_encode']}")
        if f.get('audio_encode'): specs.append(f"🔊 音频编码: {f['audio_encode']}")
        if f.get('subtitle'): specs.append(f"💬 字幕语言 {{subtitle}}: {f['subtitle']}")
        if f.get('source'): specs.append(f"CD 来源: {f['source']}")
        if specs: ctx.log(f"┣ 🛠️ 规格: {' | '.join(specs)}")
        
        ctx.log(f"┗ 📝 渲染后名: {f['processed_name']}")
        
        # 3. 写入系统审计日志
        log_audit("识别", "识别成功", f"{f['title']} (ID: {f['tmdb_id']}) S{f.get('season')}E{f.get('episode')}", details=f)
        
        # 4. 补充 logs 字段供前端显示
        data_packet["logs"] = ctx.logs
        return data_packet
