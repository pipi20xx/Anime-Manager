import os
import time
from ..context import RecognitionContext
from recognition_engine.kernel import core_recognize
from recognition_engine.batch_helper import BatchHelper
from recognition_engine.constants import MediaType

class ParserStage:
    @staticmethod
    async def run(ctx: RecognitionContext):
        start = time.time()
        
        # --- [NEW] 锚点溯源与智能懒加载 (Lazy Path Context) ---
        import re
        
        is_force_file = ctx.kwargs.get("force_filename", False)
        if is_force_file:
            # [FIX] 强制单文件模式：不使用 os.path.basename 截断，保留完整输入
            # 后续 TitleCleaner 会负责在单文件模式下对路径进行扁平化处理
            raw_filename = ctx.filename
            path_parts = [ctx.filename]
        else:
            raw_filename = os.path.basename(ctx.filename)
            path_parts = ctx.filename.replace('\\', '/').split('/')

        name_no_ext = os.path.splitext(raw_filename)[0]
        
        # 1. 判定文件名置信度
        low_info_patterns = [
            r"^\d+$", r"^[sS]\d+[eE]\d+$", r"^\d+[xX]\d+$", 
            r"^[eE][pP]?\d+$", r"^第?\s*\d+\s*[集话回]$", r"^\d+v\d+$"
        ]
        is_low_info = any(re.match(p, name_no_ext.strip()) for p in low_info_patterns) or len(name_no_ext.strip()) <= 6
        
        id_regex = re.compile(r"tmdb(?:id)?[:=\-](\d+)", re.IGNORECASE)
        season_regex = re.compile(r"^(?:Season|S|第)\s*(\d+)\s*(季)?$", re.IGNORECASE)
        
        useful_segments = []
        has_id_lock = False
        
        if not is_force_file and len(path_parts) > 1:
            # 2. 深度扫描最近两层目录 (Level -2 and -3)
            found_season = None
            found_id = None
            
            # 倒序检查父级目录
            for i in range(2, min(len(path_parts) + 1, 4)):
                folder = path_parts[-i]
                
                # 检查 ID 锁
                id_match = id_regex.search(folder)
                if id_match and not found_id:
                    found_id = id_match.group(1)
                
                # 检查季文件夹
                s_match = season_regex.search(folder)
                if s_match and not found_season:
                    found_season = s_match.group(1)
                
                # 只要不是太短或有特征，就加入路径列表
                if id_match or s_match or len(folder.strip()) > 4:
                    if folder not in useful_segments:
                        useful_segments.insert(0, folder)

            # 3. 应用探测结果
            if found_id:
                ctx.kwargs["forced_tmdb_id"] = found_id
                ctx.log(f"┣ [路径锁定] 🔐 锁定 ID: {found_id}")
                has_id_lock = True
                
            if found_season:
                if ctx.kwargs.get("forced_season") is None:
                    ctx.kwargs["forced_season"] = found_season
                ctx.kwargs["forced_type"] = "tv" # 探测到季文件夹，铁定是剧集
                ctx.log(f"┣ [路径锁定] 📂 识别到季层: S{found_season} (强制类型: TV)")

            # 4. 组装路径：低信息量或有 ID 锁时使用溯源路径
            if has_id_lock:
                # [Optimization] 如果已经锁定了 ID，识别内核只需要处理文件名来提取集数和规格
                ctx.filename = raw_filename
                ctx.log(f"┣ [路径精准] 🎯 已锁定 ID，开启精准模式：仅解析文件名提取集数")
            elif is_low_info:
                if is_low_info: ctx.log(f"┣ [路径溯源] ⚠️ 文件名信息不足，使用溯源路径: {'/'.join(useful_segments)}")
                ctx.filename = "/".join(useful_segments + [raw_filename])
            else:
                ctx.filename = raw_filename
        else:
            # 强制单文件或只有一层，直接使用 raw_filename (如果是强制单文件，则已经是扁平化的了)
            ctx.filename = raw_filename

        # 状态展示
        p_anime = "ON" if ctx.anime_priority else "OFF"
        p_batch = "ON" if ctx.batch_enhance else "OFF"
        p_fp = "ON" if ctx.use_fingerprint else "OFF"
        p_off = "Local-First" if ctx.offline_priority else "Cloud-First"
        p_bgm = "ON" if ctx.bangumi_priority else "OFF"
        p_failover = "ON" if ctx.bangumi_failover else "OFF"
        p_force_file = "ON" if is_force_file else "OFF"

        ctx.log(f"🚀 --- [ANIME 深度审计流水线启动] ---")
        ctx.log(f"┃ [待处理条目]: {ctx.filename}")
        ctx.log(f"┃ [配置] 策略状态: 动漫优化[{p_anime}] | 合集增强[{p_batch}] | 记忆[{p_fp}] | 搜索顺序[{p_off}] | BGM优先[{p_bgm}] | BGM故障转移[{p_failover}] | 强制单文件[{p_force_file}]")

        # 1. 检查系列指纹 (Pre-match Acceleration)
        # 只有在启用指纹且当前还未获取到数据时执行
        if ctx.use_fingerprint and not ctx.tmdb_data:
            fp_match = await ctx.cache_dao.get_fingerprint_match(ctx.filename, ctx.logs)
            if fp_match:
                ctx.tmdb_data = {
                    "id": fp_match["id"],
                    "type": fp_match["type"],
                    "source": "fingerprint_match"
                }
                ctx.add_perf("记忆命中", start)
                # [Short-circuit] 记忆命中后，仅执行极简解析(提取集数等必备信息)，跳过昂贵的标题拆分与匹配
                ctx.log(f"┃ [智能记忆] ⚡ 记忆加速启动，将跳过冗余内核解析步骤")

        # 2. 调用新内核进行解析 (Layer 1 Core)
        # 如果指纹命中了，我们会告诉内核使用指纹数据，内核会自动简化流程
        kernel_logs = []
        ctx.meta = core_recognize(
            input_name=ctx.filename, 
            custom_words=ctx.all_noise, 
            custom_groups=ctx.all_groups,
            original_input=ctx.filename,
            current_logs=kernel_logs,
            batch_enhancement=ctx.batch_enhance,
            fingerprint_data=ctx.tmdb_data,
            force_filename=is_force_file
        )
        
        # 统一同步内核日志
        for l in kernel_logs: ctx.log(l)

        # 2. [Enhance][STEP 2.6] 副标题描述注入
        description = ctx.kwargs.get("description")
        ctx.log("┃")
        ctx.log("┃ [DEBUG][STEP 2.6: 副标题描述注入]: 启动检测")
        if description and ctx.meta:
            d_logs = []
            BatchHelper.enhance_from_description(ctx.meta, description, d_logs)
            if not d_logs:
                ctx.log("┣ ⏩ 描述信息已传入，但未发现有效合集/规格特征")
            else:
                for dl in d_logs: ctx.log(f"┣ {dl}")
        else:
            ctx.log("┣ ⏩ 环境上下文未探测到副标题 (Description) 数据流")
        ctx.log("┗ ✅ 注入检测结束")
        
        # 3. 处理参数覆盖
        ParserStage._apply_forced_params(ctx)

        ctx.add_perf("本地解析", start)

    @staticmethod
    def _apply_forced_params(ctx: RecognitionContext):
        k, meta = ctx.kwargs, ctx.meta
        if k.get("forced_tmdb_id"):
            meta.forced_tmdbid = str(k["forced_tmdb_id"])
            ctx.log(f"┣ [强制参数] 🔧 强制 TMDB ID: {meta.forced_tmdbid}")
        if k.get("forced_type"):
            ft = k["forced_type"].lower()
            meta.type = MediaType.MOVIE if ft == "movie" else MediaType.TV
            ctx.log(f"┣ [强制参数] 🔧 强制类型: {ft}")
        if k.get("forced_season") is not None and k.get("forced_season") != "":
            try: meta.begin_season = int(k["forced_season"]); ctx.log(f"┣ [强制参数] 🔧 强制季号: S{meta.begin_season}")
            except: pass
        if k.get("forced_episode") is not None and k.get("forced_episode") != "":
            try: meta.begin_episode = int(k["forced_episode"]); ctx.log(f"┣ [强制参数] 🔧 强制集号: E{meta.begin_episode}")
            except: pass
