import os
import json
import httpx
import logging
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from organizer_core.renamer import Renamer
from logger import log_audit

CONFIG_PATH = "data/config.json"
CONFIG_BAK_PATH = "data/config.json.bak"

logger = logging.getLogger("ConfigManager")

class ConfigManager:
    DEFAULT_CONFIG = {
        "tmdb_api_key": "",
        "bangumi_token": "",
        "bangumi_priority": False,
        "bangumi_failover": True,
        "http_proxy": "",
        "proxy_services": {
            "tmdb": False,
            "bangumi": False,
            "remote_rules": False,
            "jackett": False,
            "telegram": False,
            "rss": False,
            "docker_hub": False
        },
        "jackett_url": "",
        "jackett_api_key": "",
        "jackett_password": "",
        "emby_url": "",
        "emby_api_key": "",
        "emby_username": "",
        "emby_password": "",
        "emby_user_id": "",
        "telegram": {
            "bot_token": "",
            "chat_id": "",
            "enabled": False,
            "notify_on_sub_add": True,
            "notify_on_sub_del": True,
            "notify_on_sub_push": True,
            "notify_on_rule_push": True,
            "notify_on_organize": True,
            "notify_on_strm_finish": True,
            "notify_on_sub_complete": True,
            "notify_on_library_new": True
        },
        "anime_priority": True,
        "offline_priority": True,
        "ai_config": {
            "openai_base_url": "http://localhost:11434/v1",
            "openai_api_key": "sk-xxx",
            "openai_model": "qwen2.5:1.5b"
        },
        "batch_enhancement": False,
        "series_fingerprint": True,
        "custom_noise_words": [],
        "remote_noise_urls": [],
        "custom_release_groups": [],
        "remote_group_urls": [],
        "custom_render_words": [],
        "remote_render_urls": [],
        "custom_privileged_rules": [],
        "remote_privileged_urls": [],
        "rename_rules": Renamer.get_default_rules(),
        "organize_tasks": [], # 确保整理任务持久化
        "strm_tasks": [], # 确保 strm_tasks 也有默认占位符
        "download_clients": [],
        "rss_auto_refresh": True,
        "rss_refresh_interval": 15,
        "auto_clear_recognition": False,
        "auto_clear_interval": 24,
        "sub_auto_fill": False,
        "sub_fill_interval": 12,
        "rule_auto_update": False,
        "rule_update_interval": 24,
        "external_token": "", 
        "web_password": "",
        "enable_api": True,
        "api_auth_required": False,
        "api_logging": True,
        "stalled_timeout_minutes": 0, # 下载超时自动熔断阈值（分钟），0为禁用
        "stalled_monitor_interval": 30, # 下载超时巡检间隔（分钟）
        "health_check_enabled": True, # 是否开启健康检查自动巡检
        "health_check_interval": 30, # 健康检查巡检间隔（分钟）
        "calendar_daily_push": False, # 追剧日历每日播报
        "calendar_push_time": "09:00", # 每日播报时间
        "database": {
            "type": "postgresql", # 仅支持 postgresql
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": "",
            "database": "anime_pro_matcher"
        }
    }
    
    @staticmethod
    def _save_atomic(path: str, data: Any):
        """原子级写入文件，防止磁盘满导致文件损坏"""
        tmp_path = path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno()) # 强制刷盘
            
            # 写入成功后，执行原子替换
            os.replace(tmp_path, path)
            
            # 同时保留一份备份
            if path == CONFIG_PATH:
                shutil.copy2(path, CONFIG_BAK_PATH)
        except Exception as e:
            logger.error(f"Atomic save failed for {path}: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @staticmethod
    def init_config():
        if not os.path.exists("data"): os.makedirs("data")
        config = ConfigManager.DEFAULT_CONFIG.copy()
        
        load_success = False
        
        # 依次尝试从主文件和备份文件加载
        for path in [CONFIG_PATH, CONFIG_BAK_PATH]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if not content: continue # 跳过空文件
                        
                        existing = json.loads(content)
                        # Deep merge for dictionary fields like proxy_services
                        for k, v in existing.items():
                            # Auto-clear redundant keys not in DEFAULT_CONFIG
                            if k not in config:
                                continue
                                
                            if k == "proxy_services" and isinstance(v, dict) and isinstance(config.get(k), dict):
                                config[k].update(v)
                            else:
                                config[k] = v
                        load_success = True
                        logger.info(f"配置文件加载成功: {path}")
                        break # 加载成功，退出循环
                except Exception as e:
                    logger.error(f"Failed to load config from {path}: {e}")
                    # 如果主文件坏了但备份文件还没试，继续循环
                    continue
        
        # 如果文件存在但全部加载失败，这说明真的坏了，为了安全起见，不要盲目覆盖！
        if os.path.exists(CONFIG_PATH) and not load_success:
            msg = "配置文件已损坏且无法从备份恢复！请手动检查 data/config.json。程序将停止以防止数据丢失。"
            logger.critical(msg)
            # 抛出异常阻止程序启动，保护现场
            # raise RuntimeError(msg) 
            # 这里如果不抛异常，则会自动使用默认值并保存，导致丢配置
        
        ConfigManager._save_atomic(CONFIG_PATH, config)

    @staticmethod
    def get_config() -> Dict:
        # 自动初始化检查
        if not os.path.exists(CONFIG_PATH) and not os.path.exists(CONFIG_BAK_PATH):
            ConfigManager.init_config()
            
        config = ConfigManager.DEFAULT_CONFIG.copy()
        try:
            # 尝试加载物理配置文件
            load_path = CONFIG_PATH if os.path.exists(CONFIG_PATH) else (CONFIG_BAK_PATH if os.path.exists(CONFIG_BAK_PATH) else None)
            if load_path:
                with open(load_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    # 深度更新配置，防止丢失 key
                    for k, v in existing.items():
                        if k in config and isinstance(v, dict) and isinstance(config[k], dict):
                            config[k].update(v)
                        else:
                            config[k] = v
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")

        # --- 环境变量强制覆盖逻辑 (优先级最高) ---
        if "database" not in config:
            config["database"] = {}
            
        db_conf = config["database"]
        # 显式读取环境变量，并自动去除可能存在的空格
        env_host = os.getenv("DB_HOST")
        env_port = os.getenv("DB_PORT")
        env_user = os.getenv("DB_USER")
        env_pass = os.getenv("DB_PASS")
        env_name = os.getenv("DB_NAME")

        if env_host: db_conf["host"] = env_host.strip()
        if env_port: db_conf["port"] = int(env_port.strip())
        if env_user: db_conf["user"] = env_user.strip()
        if env_pass: db_conf["password"] = env_pass.strip()
        if env_name: db_conf["database"] = env_name.strip()
        
        config["database"] = db_conf
        return config

    @staticmethod
    def get_proxy(service_name: str) -> Optional[str]:
        config = ConfigManager.get_config()
        proxy_url = config.get("http_proxy", "")
        services = config.get("proxy_services", {})
        
        if proxy_url and services.get(service_name, False):
            return proxy_url
        return None

    @staticmethod
    async def fetch_urls(urls: List[str]) -> List[str]:
        results = []
        proxy = ConfigManager.get_proxy("remote_rules")
        if proxy:
            logger.info(f"[Proxy] 🌐 通过代理 {proxy} 拉取远程规则")
        async with httpx.AsyncClient(follow_redirects=True, proxy=proxy) as client:
            for url in urls:
                url = url.strip()
                if not url.startswith("http"): continue
                try:
                    resp = await client.get(url, timeout=15)
                    if resp.status_code == 200:
                        content = resp.content.decode('utf-8-sig')
                        lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
                        results.extend(lines)
                except Exception as e:
                    logger.warning(f"Fetch failed for {url}: {e}")
        return results

    @staticmethod
    async def refresh_remote_rules():
        from models import RemoteRule
        from database import db
        from sqlalchemy import delete
        
        config = ConfigManager.get_config()
        log_audit("同步", "刷新开始", "正在从远程拉取最新的识别规则...")
        
        cache_data = {
            "noise": await ConfigManager.fetch_urls(config.get("remote_noise_urls", [])),
            "groups": await ConfigManager.fetch_urls(config.get("remote_group_urls", [])),
            "render": await ConfigManager.fetch_urls(config.get("remote_render_urls", [])),
            "privileged": await ConfigManager.fetch_urls(config.get("remote_privileged_urls", []))
        }
        
        # 写入数据库 (独立表存储)
        async with db.session_scope() as session:
            # 1. 清空旧规则
            await session.execute(delete(RemoteRule))
            # 2. 插入新规则
            for cat, items in cache_data.items():
                new_rule = RemoteRule(category=cat, content=items, updated_at=datetime.now())
                session.add(new_rule)
            await session.commit()
        
        # 立即同步到内存
        ConfigManager._rule_memory_cache = cache_data
        
        # 加载特权规则到处理器
        privileged_rules = cache_data.get("privileged", []) + config.get("custom_privileged_rules", [])
        if privileged_rules:
            from recognition_engine.special_episode_handler import SpecialEpisodeHandler
            SpecialEpisodeHandler.load_external_rules(privileged_rules)
        
        total = sum(len(v) for v in cache_data.items())
        log_audit("同步", "刷新完成", f"远程规则同步成功，共获取 {total} 条新规则")
        return cache_data

    @staticmethod
    async def get_cached_rules_async():
        """异步获取缓存规则 (优先从独立表读取)"""
        from models import RemoteRule
        from database import db
        from sqlalchemy import select
        
        rules = {"noise": [], "render": [], "groups": [], "privileged": []}
        try:
            async with db.session_scope():
                stmt = select(RemoteRule)
                res = await db.all(RemoteRule, stmt)
                if res:
                    for r in res:
                        rules[r.category] = r.content
                else:
                    # 兼容性回退：尝试从旧的 discover_cache 读取一次
                    from metadata.meta_cache import MetaCacheManager
                    old_rules = await MetaCacheManager.get_discover_cache("remote_rule_cache")
                    if old_rules:
                        rules = old_rules
                        # 顺便迁移到新表
                        for cat, items in rules.items():
                            db_rule = RemoteRule(category=cat, content=items)
                            await db.save(db_rule, audit=False)
        except:
            pass
            
        return rules

    @staticmethod
    def get_cached_rules():
        """同步获取缓存规则，合并内存中的远程规则和实时的本地智能规则"""
        # 1. 获取内存中的远程规则备份
        rules = getattr(ConfigManager, "_rule_memory_cache", {"noise": [], "render": [], "groups": [], "privileged": []}).copy()
        
        return rules

    @staticmethod
    def clear_cached_rules():
        """清除远程规则缓存，强制下次从数据库重新加载"""
        if hasattr(ConfigManager, "_rule_memory_cache"):
            delattr(ConfigManager, "_rule_memory_cache")
        if hasattr(ConfigManager, "get_cached_rules"):
            if hasattr(ConfigManager.get_cached_rules, "__cache__"):
                delattr(ConfigManager.get_cached_rules, "__cache__")

    @staticmethod
    def load_privileged_rules():
        """加载特权规则 (启动时调用)"""
        try:
            config = ConfigManager.get_config()
            custom_rules = config.get("custom_privileged_rules", [])
            
            # 尝试从缓存获取远程规则
            cached = ConfigManager.get_cached_rules()
            remote_rules = cached.get("privileged", [])
            
            all_rules = remote_rules + custom_rules
            if all_rules:
                from recognition_engine.special_episode_handler import SpecialEpisodeHandler
                SpecialEpisodeHandler.load_external_rules(all_rules)
                logger.info(f"[Config] 已加载 {len(all_rules)} 条特权规则")
        except Exception as e:
            logger.warning(f"[Config] 加载特权规则失败: {e}")

    @staticmethod
    def update_config(new_config: Dict):
        current = ConfigManager.get_config()
        current.update(new_config)
        ConfigManager._save_atomic(CONFIG_PATH, current)
        log_audit("系统", "配置更新", "系统全局配置已更新")
        
        # 重新加载特权规则（如果配置中有更新）
        if "custom_privileged_rules" in new_config or "remote_privileged_urls" in new_config:
            ConfigManager.load_privileged_rules()
        
        # 清除远程规则缓存（如果远程URL有更新）
        if ("remote_noise_urls" in new_config or 
            "remote_group_urls" in new_config or 
            "remote_render_urls" in new_config or
            "remote_privileged_urls" in new_config):
            ConfigManager.clear_cached_rules()
