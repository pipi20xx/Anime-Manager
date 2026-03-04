import re
import os

class PathParser:
    """
    专门用于处理文件路径的解析器。
    负责将复杂的路径结构（包含目录、标签、ID等）转换为扁平化的、适合识别的文件名字符串。
    """

    @staticmethod
    def parse(original_path: str, strict: bool = True):
        """
        解析路径，返回处理后的文件名、从路径中提取的元数据以及处理日志。
        
        Args:
            original_path: 原始文件路径
            strict: 是否开启严格模式
        
        Returns:
            tuple: (final_name, path_info, logs)
            path_info: Dict, 包含 {'tmdb_id': str, 'season': int}
        """
        logs = []
        path_info = {}
        
        # 0. 基础清理
        filename = original_path.strip()
        
        # 1. 嗅探路径中的元数据 (如 [tmdbid=12345] 或 tmdb-12345)
        tmdb_match = re.search(r'tmdb(?:id)?\s*[=\-]\s*(\d+)', filename, re.IGNORECASE)
        if tmdb_match:
            path_info['tmdb_id'] = tmdb_match.group(1)
            logs.append(f"┣ [DEBUG][Path] 🎯 从路径中嗅探到强制 ID: {path_info['tmdb_id']}")

        # 2. 智能扁平化逻辑
        if "/" in filename or "\\" in filename:
            try:
                clean_path = filename.replace("\\", "/")
                # 过滤掉空元素
                parts = [p for p in clean_path.split("/") if p.strip()]
                
                if len(parts) >= 2:
                    f_name = parts[-1]      # 文件名
                    parent = parts[-2]      # 父目录
                    grandparent = parts[-3] if len(parts) >= 3 else ""
                    
                    # --- 策略判定 ---
                    
                    # 判定 A: 父目录是否为 "季数/特殊" 目录
                    season_match = re.match(r'^(?:Season|S)\s*(\d+)$', parent, re.IGNORECASE)
                    is_special_dir = parent.lower() in ["specials", "ova", "ncop", "nced"]
                    
                    is_season_dir = bool(season_match or is_special_dir)
                    
                    # [New] 如果是明确的季数目录，提取季数
                    if season_match:
                        try:
                            s_num = int(season_match.group(1))
                            path_info['season'] = s_num
                            logs.append(f"┣ [DEBUG][Path] 从目录结构提取到强制季数: Season {s_num}")
                        except: pass
                    elif parent.lower() == "specials":
                         path_info['season'] = 0
                         logs.append(f"┣ [DEBUG][Path] 识别到 Specials 目录，强制季数: S0")
                    
                    final_name = f_name # 默认只用文件名
                    
                    if is_season_dir:
                        # 场景: /One Piece/Season 1/01.mp4 -> One Piece Season 1 01.mp4
                        # 场景: /.../[tmdbid=...]/Season 1/[ANi]... -> [tmdbid=...] Season 1 [ANi]...
                        
                        # [Opt] 过滤掉纯 ID 标记的祖父目录 (这只是元数据容器，不是标题)
                        # 比如 grandparent 是 "[tmdbid=284442]"，这绝不应拼入文件名
                        valid_grandparent = grandparent
                        if re.search(r'tmdb(?:id)?\s*[=\-]', grandparent, re.IGNORECASE):
                            valid_grandparent = ""
                        
                        # [Opt] 检查文件名是否"自洽" (Self-contained)
                        # 如果文件名很长(>10)且不全是数字/符号，通常已经包含了片名
                        # 这种情况下，没必要再拼 "Season 1"，因为我们已经提取了强制季数 path_info['season']
                        is_self_contained = len(f_name) > 15 or (len(f_name) > 8 and not re.match(r'^[\d\s\.EepS\-]+', f_name))
                        
                        if valid_grandparent:
                            # 如果有一个有效的(非ID)祖父目录(通常是片名)，且文件名极短，那肯定要拼
                            # 如: /One Piece/Season 1/01.mp4 -> One Piece Season 1 01.mp4
                            combo = [valid_grandparent, parent, f_name]
                            final_name = " ".join(combo)
                            logs.append(f"┣ [DEBUG][Path] 拼接祖父目录(片名)以补全信息: '{final_name}'")
                        elif is_self_contained:
                            # 如果没有有效的祖父目录(可能是ID)，且文件名自己看着挺全，那就不拼了
                            # 如: /[tmdbid=...]/Season 1/[ANi] Title... -> [ANi] Title...
                            # 此时 path_info['season'] 会负责传递季数信息
                            logs.append(f"┣ [DEBUG][Path] 文件名已自洽且ID已提取，跳过目录拼接")
                        else:
                            # 只有 Season 目录和短文件名 -> 拼 Season 1 01.mp4 (虽然缺片名，但总比没有好)
                            final_name = f"{parent} {f_name}"
                            logs.append(f"┣ [DEBUG][Path] 拼接 Season 目录以增加上下文: '{final_name}'")
                    
                    else:
                        # ... (原有的非Season目录逻辑保持不变)
                        # 简单的归一化对比
                        def simple_norm(s): return re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5]", "", s).lower()
                        
                        p_norm = simple_norm(parent)
                        f_norm = simple_norm(f_name)
                        
                        is_short_name = len(f_name) < 5 or (len(f_norm) < 3)
                        
                        is_redundant = False
                        if len(p_norm) > 3 and f_norm.startswith(p_norm):
                            is_redundant = True
                        
                        if is_short_name:
                            final_name = f"{parent} {f_name}"
                            logs.append(f"┣ [DEBUG][Path] 文件名过短，强制拼接父目录: '{final_name}'")
                        elif not is_redundant:
                            if strict:
                                logs.append(f"┣ [DEBUG][Path] 严格模式: 跳过普通父目录 '{parent}' 拼接")
                            else:
                                final_name = f"{parent} {f_name}"
                                logs.append(f"┣ [DEBUG][Path] 父目录包含潜在信息，拼接为: '{final_name}'")
                        else:
                            logs.append(f"┣ [DEBUG][Path] 文件名已包含父目录信息(冗余)，保持原样")
                    
                    filename = final_name

            except Exception as e:
                logs.append(f"┣ [DEBUG][Path] 路径处理异常 (跳过): {str(e)}")
        
        return filename, path_info, logs
