import regex as re
import httpx
from typing import Dict, Any, List, Optional
from config_manager import ConfigManager
from metadata.meta_cache import MetaCacheManager
from ..data_provider.tmdb import TMDBClient

class RenderEngine:
    """
    核心规则引擎：负责执行各种复杂的自定义渲染逻辑。
    """
    @staticmethod
    def evaluate_includes(expression: str, filename: str) -> bool:
        try:
            expr = expression.replace('||', '|')
            tokens = re.split(r'([&\|\(\)])', expr)
            processed_tokens = []
            for token in tokens:
                t = token.strip()
                if not t: continue
                if t in ['&', '|', '(', ')']:
                    if t == '&': processed_tokens.append(' and ')
                    elif t == '|': processed_tokens.append(' or ')
                    else: processed_tokens.append(t)
                else:
                    is_contained = t.lower() in filename.lower()
                    processed_tokens.append('True' if is_contained else 'False')
            eval_str = "".join(processed_tokens)
            return eval(eval_str, {"__builtins__": {}}, {})
        except:
            return expression.lower() in filename.lower()

    @staticmethod
    def _eval_math(expression: str, context: Dict[str, Any]) -> Any:
        try:
            expr = str(expression).upper()
            for key, val in context.items():
                if val is not None:
                    expr = expr.replace(str(key).upper(), str(val))
            if not re.match(r'^[\d\s\+\-\*\/\%\(\)\.]+$', expr):
                return expression 
            return int(eval(expr, {"__builtins__": {}}, {}))
        except:
            return expression

    @staticmethod
    async def apply_rules(data: Dict[str, Any], raw_filename: str, rules: List[str], logger_logs: List[str], api_key: str) -> Dict[str, Any]:
        meta = data["raw_meta"]
        tmdb_match = data.get("tmdb_match")
        if "tags" not in meta: meta["tags"] = []
        skip_count = 0

        def get_meta_context():
            return {
                "EP": meta.get("begin_episode", 0),
                "S": meta.get("begin_season", 1),
                "YEAR": meta.get("year", ""),
            }

        async def fetch_tmdb(new_id, new_type, title_log):
            cache_key = f"{new_type}:{new_id}"
            cached_meta = await MetaCacheManager.get(cache_key)
            if cached_meta:
                data["tmdb_match"]["id"] = cached_meta.get("id")
                data["tmdb_match"]["title"] = cached_meta.get("title")
                meta["type"] = new_type
                if data.get("final_result"):
                    data["final_result"]["tmdb_id"] = cached_meta.get("id")
                    data["final_result"]["title"] = cached_meta.get("title")
                    data["final_result"]["year"] = cached_meta.get("year")
                    data["final_result"]["poster_path"] = cached_meta.get("poster_path")
                    data["final_result"]["release_date"] = cached_meta.get("release_date")
                logger_logs.append(f"┃  => [Mod] 命中本地元数据: {cached_meta.get('title')} (ID:{new_id})")
                return

            proxy = ConfigManager.get_proxy("tmdb")
            async with httpx.AsyncClient(timeout=10, proxy=proxy) as client:
                try:
                    url = f"https://api.themoviedb.org/3/{new_type}/{new_id}"
                    params = {"api_key": api_key, "language": "zh-CN"}
                    req = client.build_request("GET", url, params=params)
                    log_url = re.sub(r"api_key=[^&]+", "api_key=****", str(req.url))
                    resp = await client.send(req)
                    if resp.status_code == 200:
                        item = resp.json()
                        normalized = TMDBClient.normalize(item, media_type_hint=new_type)
                        await MetaCacheManager.update(cache_key, normalized)
                        data["tmdb_match"]["id"] = normalized.get("id")
                        data["tmdb_match"]["title"] = normalized.get("title")
                        meta["type"] = new_type
                        if data.get("final_result"):
                            data["final_result"]["tmdb_id"] = normalized.get("id")
                            data["final_result"]["title"] = normalized.get("title")
                            data["final_result"]["year"] = normalized.get("year")
                            data["final_result"]["poster_path"] = normalized.get("poster_path")
                            data["final_result"]["release_date"] = normalized.get("release_date")
                        logger_logs.append(f"┃  => [Mod] TMDB重定向: GET {log_url} -> {normalized['title']}")
                except Exception as e:
                    logger_logs.append(f"┃  => [Error] TMDB fetch failed: {e}")

        for idx, rule in enumerate(rules):
            rule = rule.strip()
            if not rule or rule.startswith("#"): continue
            
            # 判定规则来源
            is_remote = rule.startswith("[REMOTE]")
            source_tag = "[社区]" if is_remote else "[私有]"
            actual_line = rule[8:] if is_remote else rule

            try:
                # --- Mode: Offset Locator (A <> B >> Expr) ---
                if " <> " in actual_line and " >> " in actual_line:
                    parts = actual_line.split(" >> ", 1)
                    formula, locators = parts[1].strip(), parts[0].split(" <> ")
                    if len(locators) == 2:
                        p = f"(?i){re.escape(locators[0].strip())}\s*(\d+)\s*{re.escape(locators[1].strip())}"
                        match = re.search(p, raw_filename)
                        if match:
                            captured_num = int(match.group(1))
                            new_ep = RenderEngine._eval_math(formula, {"EP": captured_num})
                            if isinstance(new_ep, int):
                                meta["begin_episode"] = new_ep
                                if data.get("final_result"): data["final_result"]["episode"] = new_ep
                                logger_logs.append(f"┣ 🏷️  [Render]{source_tag} 偏移定位: {match.group(0)} -> E{new_ep}")
                                data["render_hit"] = True
                        else: skip_count += 1
                    continue

                # --- Mode: Conditional / Expert (@?{...}) ---
                if actual_line.startswith("@?{"):
                    if " => " not in actual_line: continue
                    parts = actual_line.split(" => ", 1)
                    src_match = re.search(r"\{\[(.*?)\]\}", parts[0])
                    tgt_match = re.search(r"\{\[(.*?)\]\}", parts[1])
                    if not src_match or not tgt_match: 
                        skip_count += 1; continue

                    src_conds, tgt_mods = src_match.group(1), tgt_match.group(1)
                    cond_dict = {item.split("=")[0].strip().lower(): item.split("=")[1].strip() for item in src_conds.split(";") if "=" in item}
                    if "tmdbid" in cond_dict and not tmdb_match:
                        skip_count += 1; continue

                    tmdb_id, curr_s, curr_e = str(tmdb_match.get("id")) if tmdb_match else "", int(meta.get("begin_season") or 1), int(meta.get("begin_episode") or 0)
                    m_type_raw = meta.get("type")
                    m_type = m_type_raw.value if hasattr(m_type_raw, "value") else str(m_type_raw)
                    curr_year = str(meta.get("year") or "")

                    match_fail = None
                    if "tmdbid" in cond_dict and cond_dict["tmdbid"] != tmdb_id: match_fail = f"ID不符"
                    elif "type" in cond_dict and cond_dict["type"] != m_type: match_fail = f"类型不符"
                    elif "year" in cond_dict and cond_dict["year"] != curr_year: match_fail = f"年份不符"
                    elif "s" in cond_dict and str(curr_s) != cond_dict["s"]: match_fail = f"季号不符"
                    elif "e" in cond_dict:
                        if "-" in cond_dict["e"]:
                            try:
                                s_range, e_range = map(int, cond_dict["e"].split("-"))
                                if not (s_range <= curr_e <= e_range): match_fail = f"集数不在范围"
                            except: match_fail = f"格式错误"
                        elif str(curr_e) != cond_dict["e"]: match_fail = f"集数不符"
                    elif "includes" in cond_dict:
                        if not RenderEngine.evaluate_includes(cond_dict["includes"], raw_filename): match_fail = f"包含词不匹配"

                    if match_fail:
                        skip_count += 1; continue

                    logger_logs.append(f"┣ 🎯 [Render]{source_tag} 命中专家规则: {actual_line}")
                    mod_dict = {item.split("=")[0].strip().lower(): item.split("=")[1].strip() for item in tgt_mods.split(";") if "=" in item}
                    if "tmdbid" in mod_dict:
                        new_id, new_type = mod_dict["tmdbid"], mod_dict.get("type", m_type)
                        await fetch_tmdb(new_id, new_type, "")
                    if "year" in mod_dict:
                        old_y = meta.get("year"); meta["year"] = mod_dict["year"]
                        if data.get("final_result"): data["final_result"]["year"] = meta["year"]
                        if old_y != meta["year"]: logger_logs.append(f"┃  => [Mod] 年份: {old_y} -> {meta['year']}")
                    if "s" in mod_dict:
                        old_s = meta.get("begin_season"); meta["begin_season"] = int(mod_dict["s"])
                        if data.get("final_result"): data["final_result"]["season"] = meta["begin_season"]
                        if old_s != meta["begin_season"]: logger_logs.append(f"┃  => [Mod] 季数: S{old_s} -> S{meta['begin_season']}")
                    if "e" in mod_dict:
                        e_formula, old_e = mod_dict["e"], meta.get("begin_episode")
                        new_e = RenderEngine._eval_math(e_formula, get_meta_context())
                        if isinstance(new_e, int):
                            meta["begin_episode"] = new_e
                            log_msg = f"┃  => [Mod] 集数: E{old_e} -> E{new_e}"
                            if meta.get("is_batch") and meta.get("end_episode"):
                                old_end = meta.get("end_episode")
                                new_end = RenderEngine._eval_math(e_formula, {"EP": old_end, "S": get_meta_context()["S"], "YEAR": get_meta_context()["YEAR"]})
                                if isinstance(new_end, int):
                                    meta["end_episode"] = new_end
                                    log_msg = f"┃  => [Mod] 集数区间: E{old_e}-E{old_end} -> E{new_e}-E{new_end}"
                            if data.get("final_result"):
                                if meta.get("is_batch") and meta.get("end_episode"): data["final_result"]["episode"] = f"{meta['begin_episode']}-{meta['end_episode']}"
                                else: data["final_result"]["episode"] = meta["begin_episode"]
                            logger_logs.append(log_msg)
                    data["render_hit"] = True; continue

                # --- Mode: Regex ---
                if " => " in actual_line:
                    pattern_str, replacement = actual_line.split(" => ", 1)
                    pattern_str, replacement, chain_rules = pattern_str.strip(), replacement.strip(), None
                    if replacement.startswith("&&"): chain_rules, replacement = replacement[2:].strip(), ""
                    
                    if replacement.startswith("{[") and replacement.endswith("]}"):
                        match = re.search(pattern_str, raw_filename, flags=re.I)
                        if match:
                            logger_logs.append(f"┣ 🏷️  [Render]{source_tag} 命中提取: {pattern_str}")
                            try: expanded_content = match.expand(replacement[2:-2])
                            except: expanded_content = replacement[2:-2]
                            mods = {item.split("=")[0].strip().lower(): item.split("=")[1].strip() for item in expanded_content.split(";") if "=" in item}
                            for k, v in mods.items():
                                if k == "e":
                                    val_to_set = RenderEngine._eval_math(v, get_meta_context())
                                    if isinstance(val_to_set, int):
                                        meta["begin_episode"] = val_to_set
                                        if data.get("final_result"): data["final_result"]["episode"] = val_to_set
                                        logger_logs.append(f"┃  => [Set] 集数: {val_to_set}")
                                elif k == "s":
                                    meta["begin_season"] = int(v)
                                    if data.get("final_result"): data["final_result"]["season"] = int(v)
                                    logger_logs.append(f"┃  => [Set] 季数: {v}")
                                elif k == "tmdbid": await fetch_tmdb(v, "tv", "ForceID")
                            data["render_hit"] = True
                        else: skip_count += 1; continue

                    if re.search(pattern_str, raw_filename, flags=re.I):
                        logger_logs.append(f"┣ 🏷️  [Render]{source_tag} 命中翻译: {pattern_str} -> {replacement}")
                        for field in ["cn_name", "en_name", "processed_name"]:
                            if meta.get(field): meta[field] = re.sub(pattern_str, replacement, meta[field], flags=re.I)
                        if data.get("final_result"): data["final_result"]["processed_name"] = meta.get("processed_name")
                        if replacement and replacement not in meta["tags"]: meta["tags"].append(replacement)
                        data["render_hit"] = True
                        if chain_rules: await RenderEngine.apply_rules(data, raw_filename, [chain_rules], logger_logs, api_key)
                    else: skip_count += 1
            except Exception as e:
                logger_logs.append(f"┣ ❌ [Error]{source_tag} 规则 #{idx+1} 异常: {str(e)}")

        if skip_count > 0: logger_logs.append(f"┣ ⏩ 跳过 {skip_count} 条不匹配的自定义渲染词")
        return data
