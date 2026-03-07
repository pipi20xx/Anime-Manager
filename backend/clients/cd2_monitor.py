import time
import os
import logging
import threading
import requests
import grpc
from typing import Dict, Any, Optional

from config_manager import ConfigManager
from .cd2 import CD2Client
from .cd2_helper import ensure_cd2_module
from logger import log_audit

logger = logging.getLogger("CD2Monitor")

class CD2TransferMonitor:
    """
    后台监控 CD2 的传输任务（上传、下载、云端复制等）。
    当任务完成时，自动触发本地 Webhook 以进行 STRM 生成。
    """
    _instance = None
    _thread: Optional[threading.Thread] = None
    _stop_event = threading.Event()
    _watchdog_thread: Optional[threading.Thread] = None

    def __init__(self):
        self.pb2, self.pb2_grpc = ensure_cd2_module()
        self.last_scan_cache = {}
        self.channel = None
        self.stub = None
        self.token = None
        self._refresh_config()

    def _refresh_config(self):
        """重新加载配置"""
        self.client_config = self._get_cd2_config()
        self.monitor_interval = self.client_config.get("monitor_interval", 5) if self.client_config else 5

    @classmethod
    def start(cls):
        if cls._instance is None:
            cls._instance = cls()
        else:
            cls._instance._refresh_config()

        if not cls._instance.client_config:
            logger.warning("未找到有效的 CD2 客户端配置，传输监控无法启动。")
            return

        monitor_enabled = cls._instance.client_config.get("monitor_enabled", None)
        if monitor_enabled is None:
            config = ConfigManager.get_config()
            monitor_enabled = config.get("enable_cd2_monitor", True)

        if not monitor_enabled:
            logger.info("CD2 传输监控未开启 (monitor_enabled=False)")
            return

        cls._stop_event.clear()

        if cls._instance._thread and cls._instance._thread.is_alive():
            logger.debug("CD2 监控线程已在运行中，仅重启看门狗")
        else:
            cls._thread = threading.Thread(target=cls._instance._run_loop, name="CD2MonitorThread", daemon=True)
            cls._thread.start()
            log_audit("CD2监控", "启动", "CD2 传输监控服务已启动 🚀")

        if cls._watchdog_thread is None or not cls._watchdog_thread.is_alive():
            cls._watchdog_thread = threading.Thread(target=cls._watchdog, name="CD2WatchdogThread", daemon=True)
            cls._watchdog_thread.start()

    @classmethod
    def stop(cls):
        cls._stop_event.set()
        if cls._instance and cls._instance._thread:
            cls._instance._thread.join(timeout=2)
        log_audit("CD2监控", "停止", "CD2 传输监控服务已停止")

    @classmethod
    def _watchdog(cls):
        """看门狗线程：监控主线程状态，异常退出时自动重启"""
        while not cls._stop_event.wait(timeout=30):
            if cls._instance and cls._instance._thread:
                if not cls._instance._thread.is_alive():
                    if not cls._stop_event.is_set():
                        logger.warning("CD2 监控线程异常退出，尝试自动重启...")
                        try:
                            cls._instance._refresh_config()
                            monitor_enabled = cls._instance.client_config.get("monitor_enabled", None)
                            if monitor_enabled is None:
                                config = ConfigManager.get_config()
                                monitor_enabled = config.get("enable_cd2_monitor", True)
                            
                            if monitor_enabled and cls._instance.client_config:
                                cls._thread = threading.Thread(
                                    target=cls._instance._run_loop, 
                                    name="CD2MonitorThread", 
                                    daemon=True
                                )
                                cls._thread.start()
                                log_audit("CD2监控", "自动重启", "CD2 监控已自动恢复 🔄")
                        except Exception as e:
                            logger.error(f"CD2 监控自动重启失败: {e}")

    def _get_cd2_config(self) -> Optional[Dict[str, Any]]:
        """从全局配置中提取第一个 CD2 客户端的配置"""
        config = ConfigManager.get_config()
        clients = config.get("download_clients", [])
        for c in clients:
            if c.get("type") == "cd2":
                return c
        return None

    def _connect_and_login(self) -> bool:
        if not self.client_config: return False
        
        try:
            host = self.client_config.get("url", "").replace("http://", "").replace("https://", "").rstrip("/")
            api_token = self.client_config.get("api_token", "")
            user = self.client_config.get("username", "")
            password = self.client_config.get("password", "")

            if self.channel: self.channel.close()
            
            self.channel = grpc.insecure_channel(host)
            self.stub = self.pb2_grpc.CloudDriveFileSrvStub(self.channel)

            if api_token:
                self.token = api_token
                logger.info("CD2 监控使用 API Token 登录成功")
                return True

            req = self.pb2.GetTokenRequest(userName=user, password=password)
            resp = self.stub.GetToken(req, timeout=10)
            
            if resp.success:
                self.token = resp.token
                return True
            else:
                logger.error(f"CD2 监控登录失败: {resp.errorMessage}")
                return False
        except Exception as e:
            logger.error(f"CD2 监控连接异常: {e}")
            return False

    def _run_loop(self):
        # 初始连接
        if not self._connect_and_login():
            logger.error("CD2 监控无法连接，将在 60 秒后重试...")
            time.sleep(60)
            # 如果第一次就失败，尝试递归或循环重试，这里简单点直接进入循环
        
        retry_count = 0

        while not self._stop_event.is_set():
            try:
                if not self.token or not self.stub:
                    if not self._connect_and_login():
                        time.sleep(30)
                        continue

                meta = [('authorization', f'Bearer {self.token}')]
                req = self.pb2.GetUploadFileListRequest(itemsPerPage=100, pageNumber=0, filter="")
                
                # 获取任务列表
                result = self.stub.GetUploadFileList(req, metadata=meta, timeout=10)
                retry_count = 0 # 重置重试计数

                current_scan_paths = set()

                for f in result.uploadFiles:
                    f_path = f.destPath
                    if not f_path: continue
                    
                    # 记录当前存在的任务
                    current_scan_paths.add(f_path)
                    
                    # 更新缓存状态
                    f_name = os.path.basename(f_path) if f_path else "Unknown"
                    self.last_scan_cache[f_path] = {
                        "name": f_name,
                        "status": f.status,
                        "type": getattr(f, 'operatorType', 0)
                    }

                # 检查已完成的任务 (消失的任务)
                cached_paths = set(self.last_scan_cache.keys())
                vanished_paths = cached_paths - current_scan_paths

                for path in vanished_paths:
                    info = self.last_scan_cache[path]
                    last_status = info['status']
                    
                    # 只有非错误状态的消失才算成功完成
                    if "Error" not in last_status and "Fatal" not in last_status and "Cancelled" not in last_status:
                        log_audit("CD2监控", "任务完成", f"检测到 CD2 任务完成: {info['name']}", details=f"路径: {path}")
                        self._send_webhook(path)
                    
                    del self.last_scan_cache[path]

                time.sleep(self.monitor_interval)

            except grpc.RpcError as e:
                # 忽略一些常规超时或断连，尝试重连
                logger.debug(f"CD2 监控 RPC 波动: {e.code()}")
                self.token = None # 触发重连
                time.sleep(5)
            except Exception as e:
                log_audit("CD2监控", "异常", f"监控循环异常: {e}", level="ERROR")
                self.token = None
                time.sleep(10)

        if self.channel:
            self.channel.close()

    def _send_webhook(self, cd2_path: str):
        """发送内部 Webhook 通知 (延迟 5 秒)"""
        async def _do_send_async():
            import asyncio
            from routers.webhook import process_cd2_notification
            from logger import log_audit

            log_audit("CD2监控", "准备联动", f"文件传输已完成，5秒后触发 STRM 同步...", details=f"目标: {os.path.basename(cd2_path)}")

            await asyncio.sleep(5)
            
            payload_data = [
                {
                    "action": "create",
                    "source_file": cd2_path,
                    "is_dir": "false"
                }
            ]
            
            try:
                triggered = await process_cd2_notification(payload_data, "CD2监控")
                if triggered == 0:
                    log_audit("CD2监控", "提示", "联动触发完成，但未命中任何 STRM 任务 (请检查路径映射)", level="WARN", details=f"路径: {cd2_path}")
            except Exception as e:
                log_audit("CD2监控", "异常", f"执行内部联动失败: {e}", level="ERROR")

        def _run_in_loop():
            from monitor import MonitorManager
            import asyncio
            if MonitorManager._loop:
                asyncio.run_coroutine_threadsafe(_do_send_async(), MonitorManager._loop)
            else:
                asyncio.run(_do_send_async())

        threading.Thread(target=_run_in_loop, daemon=True).start()
