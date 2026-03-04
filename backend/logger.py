import logging
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import asyncio

# 日志根目录
LOG_DIR = "data/logs"
os.makedirs(LOG_DIR, exist_ok=True)

class LogFormatter(logging.Formatter):
    """带颜色的格式化 (对齐 cs123)"""
    blue = "\x1b[34;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    reset = "\x1b[0m"
    
    # 统一格式: 时间 | 级别 | 消息
    fmt_str = "%(asctime)s | %(levelname)-5s | %(message)s"
    
    FORMATS = {
        logging.DEBUG: fmt_str,
        logging.INFO: blue + fmt_str + reset,
        logging.WARNING: yellow + fmt_str + reset,
        logging.ERROR: red + fmt_str + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno, self.fmt_str)
        # 如果是 log_audit 产生的消息，它们已经带了 Emoji，这里就不再重复加了
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)

# 实时广播管理器 (支持多订阅者，对齐 cs123 结构)
class LogBroadcaster:
    _subscribers = set()
    _history = [] # 内存回填缓冲区

    @classmethod
    def subscribe(cls):
        queue = asyncio.Queue()
        cls._subscribers.add(queue)
        return queue

    @classmethod
    def unsubscribe(cls, queue):
        cls._subscribers.discard(queue)

    @classmethod
    async def broadcast(cls, message):
        # 维护内存回填 (最后 100 条)
        cls._history.append(message)
        if len(cls._history) > 100:
            cls._history = cls._history[-100:]

        for queue in list(cls._subscribers):
            try:
                queue.put_nowait(message)
            except:
                pass
    
    @classmethod
    async def register(cls, websocket):
        """兼容原有 main.py 调用方式"""
        queue = cls.subscribe()
        try:
            # 发送历史回填
            for log in cls._history:
                await websocket.send_text(log)
            
            while True:
                msg = await queue.get()
                await websocket.send_text(msg)
        except:
            pass
        finally:
            cls.unsubscribe(queue)

    @classmethod
    async def unregister(cls, websocket):
        """兼容原有 main.py，实际逻辑已在 register 闭环"""
        pass

    @classmethod
    async def broadcast_loop(cls):
        """兼容原有 main.py 调用方式，由于现在是主动推，此循环可空转或作为心跳"""
        while True:
            await asyncio.sleep(3600)

class QueueHandler(logging.Handler):
    """WebSocket 广播处理器 (对齐 cs123)"""
    def emit(self, record):
        try:
            msg = self.format(record).strip()
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(LogBroadcaster.broadcast(msg))
            except RuntimeError:
                pass
        except:
            pass

class DailyFileHandler(logging.FileHandler):
    """自定义处理程序：始终以 YYYY-MM-DD.log 命名，并在跨天时自动切换 (对齐 cs123)"""
    def __init__(self, dirname, backupCount=7, encoding='utf-8'):
        self.dirname = dirname
        self.backupCount = backupCount
        self.encoding = encoding
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.dirname, f"{self.current_date}.log")
        super().__init__(log_file, encoding=encoding)

    def emit(self, record):
        new_date = datetime.now().strftime("%Y-%m-%d")
        if new_date != self.current_date:
            self.current_date = new_date
            self.stream.close()
            self.baseFilename = os.path.abspath(os.path.join(self.dirname, f"{self.current_date}.log"))
            self.stream = self._open()
            self._cleanup_old_logs()
        super().emit(record)

    def _cleanup_old_logs(self):
        try:
            files = [f for f in os.listdir(self.dirname) if f.endswith(".log")]
            files.sort(reverse=True)
            if len(files) > self.backupCount:
                for old_file in files[self.backupCount:]:
                    os.remove(os.path.join(self.dirname, old_file))
        except Exception:
            pass

def init_logging(log_file: str = "data/monitor.log", level=logging.INFO):
    """
    初始化日志系统，使其行为与 cs123 完全一致：
    1. 按天切割文件 (YYYY-MM-DD.log)
    2. WebSocket 实时广播
    3. 控制台带颜色输出
    """
    root = logging.getLogger()
    root.setLevel(level)
    
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)
    
    # 1. 控制台输出 (对齐 cs123 样式)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(LogFormatter())
    root.addHandler(stdout_handler)
    
    # 2. WebSocket 广播处理器 (实时流)
    q_handler = QueueHandler()
    # 实时流不需要颜色代码，但需要结构化
    q_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s", datefmt="%H:%M:%S"))
    root.addHandler(q_handler)
    
    # 3. 按天分割的文件记录 (对齐 cs123)
    file_handler = DailyFileHandler(LOG_DIR, backupCount=7, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    root.addHandler(file_handler)

    # 4. 同时也保留一个 monitor.log 作为最新运行日志的副本 (增加自动轮转防止无限大)
    try:
        from logging.handlers import TimedRotatingFileHandler
        # 每1天轮转一次，保留最近7天的备份
        monitor_handler = TimedRotatingFileHandler(
            log_file, when='D', interval=1, backupCount=7, encoding='utf-8'
        )
        monitor_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        root.addHandler(monitor_handler)
    except:
        pass

    # 重定向 stdout/stderr
    class StreamToLogger:
        def __init__(self, logger, level):
            self.logger = logger
            self.level = level
        def write(self, buf):
            for line in buf.rstrip().splitlines():
                self.logger.log(self.level, line.rstrip())
        def flush(self): pass

    sys.stdout = StreamToLogger(root, logging.INFO)
    sys.stderr = StreamToLogger(root, logging.ERROR)

def log_audit(module: str, action: str, message: str, level: str = "INFO", details: Any = None, to_root: bool = True):
    """
    审计日志输出 (对齐 cs123 的性能审计风格)
    """
    lvl = getattr(logging, level.upper(), logging.INFO)
    logger = logging.getLogger("System")
    
    # 映射 Emoji
    emoji_map = {
        "INFO": "✨",
        "WARN": "⚠️",
        "ERROR": "❌",
        "SUCCESS": "✅",
        "START": "🚀",
        "DONE": "🏁",
        "CLEAN": "🗑️",
        "DB": "🗄️",
        "AUTH": "🔒"
    }
    
    # 根据 Action 或 Module 自动选择 Emoji
    emoji = emoji_map.get(level.upper(), "✨")
    if action in emoji_map: emoji = emoji_map[action]
    elif module in emoji_map: emoji = emoji_map[module]
    
    # 核心日志行
    msg = f"{emoji} [{module}] {action}: {message}"
    logger.log(lvl, msg)
    
    # 细节行 (使用 ┗ 符号)
    if details:
        detail_msg = f"┗ {details}"
        logger.log(lvl, detail_msg)

    # 数据库审计逻辑已停用，以节省空间并防止数据库膨胀。
    # 所有的日志信息已由上述的 logger.log 完整记录到 .txt 文件中。
    pass

# --- 数据库日志缓冲区逻辑 (已停用) ---
_DB_LOG_BUFFER = []
_FLUSH_LOCK = asyncio.Lock()

def trigger_log_flush():
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(flush_db_logs())
    except: pass

async def flush_db_logs():
    global _DB_LOG_BUFFER
    if not _DB_LOG_BUFFER or _FLUSH_LOCK.locked():
        return
    async with _FLUSH_LOCK:
        batch = _DB_LOG_BUFFER[:]
        _DB_LOG_BUFFER = []
        try:
            from database import db
            from models import SystemLog
            async with db.session_scope(force_new=True):
                objs = [SystemLog(**item) for item in batch]
                db.session.add_all(objs)
                await db.session.commit()
        except:
            if len(_DB_LOG_BUFFER) < 500:
                _DB_LOG_BUFFER = batch + _DB_LOG_BUFFER

def setup_logger(name: str, log_file: str = None, level=logging.INFO):
    return logging.getLogger(name)