import os
import re
from typing import Dict, Any, Optional

class Renamer:
    @staticmethod
    def format_path(result_data: Dict[str, Any], pattern: str, original_filename: str) -> str:
        """
        根据元数据和模板生成新路径。
        """
        if not pattern:
            return original_filename
            
        final = result_data.get("final_result", {})
        raw = result_data.get("raw_meta", {})
        tmdb = result_data.get("tmdb_match", {})
        
        # 核心：提取后缀名
        _, ext_with_dot = os.path.splitext(original_filename)
        ext = ext_with_dot.lstrip(".")
        
        def strip_ext(name: Any) -> str:
            if not name: return ""
            s = str(name)
            if s.lower().endswith(ext_with_dot.lower()):
                return s[: -len(ext_with_dot)]
            return s

        # 3. 构建全量变量映射表
        replacements = {}

        # === Group 1: Final Result ===
        for key, value in final.items():
            # 特殊处理：processed_name 和 filename 剥离后缀后放入变量
            if key in ["processed_name", "filename"]:
                replacements[f"{{{key}}}"] = Renamer.sanitize(strip_ext(value))
            else:
                replacements[f"{{{key}}}"] = str(value) if value is not None else ""
        
        # 快捷方式：{title} 肯定不含后缀
        # 格式化补零
        season_val = final.get('season')
        episode_val = final.get('episode')
        
        season_02 = ""
        try:
            if isinstance(season_val, (int, float)):
                season_02 = f"{int(season_val):02d}"
            elif season_val and str(season_val).isdigit():
                 season_02 = f"{int(season_val):02d}"
            else:
                season_02 = str(season_val or "")
        except:
            season_02 = str(season_val or "")
            
        episode_02 = ""
        try:
            if isinstance(episode_val, (int, float)):
                episode_02 = f"{int(episode_val):02d}"
            elif episode_val and str(episode_val).isdigit():
                 episode_02 = f"{int(episode_val):02d}"
            else:
                episode_02 = str(episode_val or "")
        except:
            episode_02 = str(episode_val or "")

        replacements["{season_02}"] = season_02
        replacements["{episode_02}"] = episode_02

        # === Group 2: Raw Meta ===
        for key, value in raw.items():
            if key == "processed_name":
                replacements["{raw_processed_name}"] = Renamer.sanitize(strip_ext(value))
            else:
                replacements[f"{{raw_{key}}}"] = str(value) if value is not None else ""

        # === Group 4: 强制变量 ===
        replacements["{ext}"] = ext
        # 严格遵循用户要求：原始文件名也不含后缀
        replacements["{original_filename}"] = Renamer.sanitize(strip_ext(original_filename))
        replacements["{name}"] = Renamer.sanitize(strip_ext(original_filename))
        replacements["{path}"] = Renamer.sanitize(path_val) if (path_val := final.get("path")) else ""

        # 别名一致性
        sec_cat = replacements.get("{secondary_category}", "")
        replacements["{main_category}"] = sec_cat.split("/")[0] if sec_cat else ""
        
        replacements["{group}"] = replacements.get("{team}", "")
        replacements["{date}"] = replacements.get("{release_date}", "")

        # 3. 执行替换
        result = pattern
        for key, value in replacements.items():
            result = result.replace(key, str(value))

        # 4. 路径清洗
        result = result.replace("()", "").replace("[]", "")
        result = re.sub(r'\s+-\s+-', ' - ', result)
        result = re.sub(r'\[\s+\]', '', result) 
        result = re.sub(r'\(\s+\)', '', result)
        result = re.sub(r'\s+', ' ', result).strip()
        
        parts = result.split("/")
        clean_parts = [Renamer.sanitize(p) for p in parts if p.strip()] 
        
        final_path = os.path.join(*clean_parts)
        
        return final_path

    @staticmethod
    def sanitize(name: Any) -> str:
        if name is None: return ""
        s = str(name)
        s = re.sub(r'[\\/:*?"<>|]', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def get_default_rules():
        return [
            {
                "id": "secondary_category_rule",
                "name": "智能二级分类 (推荐)",
                "movie_pattern": "{secondary_category}/{title}({year})/{title}.{ext}",
                "tv_pattern": "{secondary_category}/{title}({year})/Season {season}/S{season_02}E{episode_02}.{ext}"
            },
            {
                "id": "default_emby",
                "name": "默认 (Emby标准)",
                "movie_pattern": "{title}({year})[tmdbid={tmdb_id}]/{original_filename}.{ext}",
                "tv_pattern": "{title}({year})[tmdbid={tmdb_id}]/Season {season}/S{season_02}E{episode_02}.{ext}"
            },
            {
                "id": "raw_processed_name",
                "name": "渲染后原名",
                "movie_pattern": "({year}){title}[tmdbid={tmdb_id}]/{processed_name}.{ext}",
                "tv_pattern": "({year}){title}[tmdbid={tmdb_id}]/Season {season}/S{season_02}E{episode_02} - {processed_name}.{ext}"
            }
        ]