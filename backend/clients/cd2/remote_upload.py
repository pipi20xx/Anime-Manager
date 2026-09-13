import hashlib
import logging
import os
import threading
import time
import uuid
from typing import Dict, Any, Optional

from logger import log_audit

logger = logging.getLogger(__name__)

# UploadFileInfo.Status 终态: Cancelled=2, Skipped=6, Finish=5, Error=9, FatalError=10
_TERMINAL_STATUS = {2, 5, 6, 9, 10}
_STATUS_TEXT = {
    0: "等待预处理", 1: "预处理中", 2: "已取消", 3: "传输中", 4: "暂停",
    5: "完成", 6: "已跳过", 7: "排队中", 8: "已忽略", 9: "错误", 10: "致命错误",
}

# CloudDriveFile.HashType: Unknown=0, Md5=1, Sha1=2, PikPakSha1=3
HASH_MD5, HASH_SHA1, HASH_PIKPAK = 1, 2, 3

_POLL_TIMEOUT = 25          # 浏览器长轮询等待时长（秒）
_RANGE_TIMEOUT = 300        # 等待浏览器回传分块的超时（秒）
_HASH_PROGRESS_INTERVAL = 16 * 1024 * 1024  # 哈希进度上报间隔（字节）


def _get_device_id() -> str:
    """持久化 device_id。协议要求跨重启复用，服务器借此替换通道并重放未完成请求。"""
    from .proto_loader import GEN_DIR
    path = os.path.join(GEN_DIR, "device_id")
    try:
        with open(path, "r") as f:
            device_id = f.read().strip()
            if device_id:
                return device_id
    except Exception:
        pass
    device_id = uuid.uuid4().hex
    try:
        os.makedirs(GEN_DIR, exist_ok=True)
        with open(path, "w") as f:
            f.write(device_id)
    except Exception:
        pass
    return device_id


def _pikpak_segment_size(size: int) -> int:
    """PikPakSha1 官方分段规则"""
    if size <= 128 * 1024 * 1024:
        return 256 * 1024
    if size <= 256 * 1024 * 1024:
        return 512 * 1024
    if size <= 512 * 1024 * 1024:
        return 1024 * 1024
    return 2048 * 1024


class _Session:
    def __init__(self, upload_id: str, file_path: str, size: int):
        self.upload_id = upload_id
        self.file_path = file_path
        self.size = size
        self.jobs: list = []              # 浏览器待取任务
        self.pending_reads: Dict[str, dict] = {}      # request_id -> 服务端 read 任务
        self.pending_hash_reads: Dict[str, dict] = {} # request_id -> 哈希取数等待器
        self.cond = threading.Condition()
        self.status: Optional[int] = None
        self.error = None
        self.terminal = False
        self.local = False  # 磁盘数据源模式：hash 请求在本地闭环处理，不入浏览器队列


class RemoteUploadManager:
    """
    CD2 Remote Upload 协议客户端（单例）。

    channel 全局一条长连接（daemon 线程），device_id 持久化跨重启复用。
    服务器推送的 read/hash 请求转为任务放入会话队列，由浏览器长轮询取走、
    按需切片回传（文件只在浏览器中，后端不整体缓冲）。
    """
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "RemoteUploadManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self):
        self._conn = None
        self._sessions: Dict[str, _Session] = {}
        self._sessions_lock = threading.Lock()
        self._channel_thread: Optional[threading.Thread] = None
        self._channel_stop = threading.Event()
        self._channel_wakeup = threading.Event()
        self._device_id = _get_device_id()
        # 会话注册前到达的通道消息缓冲（StartRemoteUpload 返回与注册间存在竞态窗口）
        self._orphan_replies: Dict[str, list] = {}

    def _register_session(self, session: _Session):
        """注册会话并回放注册前到达的通道消息"""
        with self._sessions_lock:
            self._sessions[session.upload_id] = session
            orphans = self._orphan_replies.pop(session.upload_id, [])
        for reply in orphans:
            logger.debug(f"回放孤儿通道消息: {session.upload_id[:8]}... ({reply.WhichOneof('request')})")
            self._dispatch(reply)

    # ---------- channel ----------
    def _ensure_channel(self, conn):
        if self._conn is conn and self._channel_thread and self._channel_thread.is_alive():
            # 通道可能因空闲转入待机，唤醒它立即重连
            self._channel_wakeup.set()
            return
        self._conn = conn
        self._channel_stop.clear()
        self._channel_wakeup.set()  # 唤醒旧线程（若挂起），使其检测到连接已更换后退出
        self._channel_thread = threading.Thread(
            target=self._channel_loop, name="CD2RemoteUploadChannel", daemon=True
        )
        self._channel_thread.start()
        self._channel_wakeup.clear()
        logger.info(f"[{conn.name}] RemoteUploadChannel 已启动 (device_id: {self._device_id[:8]}...)")

    def _has_active_sessions(self) -> bool:
        with self._sessions_lock:
            return any(not s.terminal for s in self._sessions.values())

    def _channel_loop(self):
        conn = self._conn
        while not self._channel_stop.is_set():
            if self._conn is not conn:
                # 连接已被更新（如配置变更重建客户端），旧通道线程退出
                return
            try:
                req = conn.pb2.RemoteUploadChannelRequest(device_id=self._device_id)
                stream = conn.stub.RemoteUploadChannel(req, metadata=conn.get_metadata())
                for reply in stream:
                    self._dispatch(reply)
            except Exception as e:
                if self._channel_stop.is_set():
                    break
                logger.warning(f"[{conn.name}] RemoteUploadChannel 断开: {e}")

            # 流已结束：仅在仍有活动会话时重连，否则转入待机，避免空闲期
            # 反复重连被服务端替换（channel replaced）造成告警刷屏
            if self._has_active_sessions():
                time.sleep(5)
                continue

            logger.info(f"[{conn.name}] 无活动上传会话，RemoteUploadChannel 转入待机")
            self._channel_wakeup.wait()
            self._channel_wakeup.clear()
            conn = self._conn

    def cancel(self, upload_id: str) -> Dict[str, Any]:
        conn = self._conn
        session = self._sessions.get(upload_id)
        req = conn.pb2.RemoteUploadControlRequest(upload_id=upload_id, cancel=conn.pb2.CancelRemoteUpload())
        conn.stub.RemoteUploadControl(req, metadata=conn.get_metadata(), timeout=30)
        if session:
            session.terminal = True
            with session.cond:
                session.cond.notify_all()
            self._sessions.pop(upload_id, None)
        return {"success": True, "message": "已取消"}

    # ---------- 本地磁盘数据源（供整理任务：本地文件 → 云端，后台同步执行） ----------
    def upload_local_file_sync(self, conn, local_path: str, cloud_file_path: str, stop_event: threading.Event = None) -> Dict[str, Any]:
        """
        将本地磁盘文件经 Remote Upload 协议上传到云端（流式分块，不整体缓冲）。
        与浏览器流程共用 channel 与会话机制，但数据直接从磁盘读取，
        read/hash 任务在本地闭环处理，不进入浏览器轮询队列。
        返回 {success, status_text, error}。
        """
        size = os.path.getsize(local_path)
        self._ensure_channel(conn)

        req = conn.pb2.StartRemoteUploadRequest(
            file_path=cloud_file_path,
            file_size=size,
            client_can_calculate_hashes=True,
        )
        started = conn.stub.StartRemoteUpload(req, metadata=conn.get_metadata(), timeout=60)
        upload_id = started.upload_id
        session = _Session(upload_id, cloud_file_path, size)
        session.local = True
        self._register_session(session)
        self._channel_wakeup.set()  # 会话已就绪，若通道恰在待机则立即恢复连接

        log_audit("CD2上传", "开始", f"远程上传(磁盘源): {cloud_file_path} ({size} 字节)")

        try:
            with open(local_path, "rb") as f:
                while not session.terminal:
                    if stop_event is not None and stop_event.is_set():
                        self.cancel(upload_id)
                        return {"success": False, "status_text": "已取消", "error": None}

                    job = self._next_job_local(session, timeout=10)
                    if job is None:
                        continue

                    if job["type"] == "read":
                        f.seek(job["offset"])
                        data = f.read(job["length"])
                        read_req = conn.pb2.RemoteReadDataUpload(
                            upload_id=upload_id,
                            offset=job["offset"],
                            length=len(data),
                            lazy_read=job["lazy_read"],
                            data=data,
                            is_last_chunk=(job["offset"] + len(data)) >= size,
                        )
                        resp = conn.stub.RemoteReadData(read_req, metadata=conn.get_metadata(), timeout=120)
                        if not resp.success:
                            raise RuntimeError(f"RemoteReadData 失败: {resp.error_message}")

                    elif job["type"] == "hash":
                        # 各哈希算法基于本地文件全量独立计算，
                        # 不依赖读取进度（哈希请求可能先于数据传输到达）
                        self._handle_hash_local(conn, session, local_path, job)
        except Exception as e:
            details = getattr(e, "details", None) or str(e)
            logger.error(f"磁盘源远程上传失败 {local_path}: {details}")
            try:
                self.cancel(upload_id)
            except Exception:
                pass
            return {"success": False, "status_text": "错误", "error": details}

        status_text = _STATUS_TEXT.get(session.status or -1, "未知")
        success = session.status == 5  # Finish
        with self._sessions_lock:
            self._sessions.pop(upload_id, None)
        if success:
            log_audit("CD2上传", "完成", f"远程上传完成: {cloud_file_path}")
        return {"success": success, "status_text": status_text, "error": session.error}

    def _handle_hash_local(self, conn, session: _Session, local_path: str, job: dict):
        """磁盘模式哈希：全文件独立计算并上报（与数据读取进度无关）"""
        hash_type = job.get("hash_type", 0)
        block_size = job.get("block_size", 0)
        size = session.size
        try:
            if hash_type == HASH_MD5:
                overall = hashlib.md5()
                block_hashes = []
                if block_size > 0:
                    with open(local_path, "rb") as bf:
                        while True:
                            chunk = bf.read(block_size)
                            if not chunk:
                                break
                            block_hashes.append(hashlib.md5(chunk).hexdigest())
                            overall.update(chunk)
                else:
                    with open(local_path, "rb") as bf:
                        for chunk in iter(lambda: bf.read(4 * 1024 * 1024), b""):
                            overall.update(chunk)
                self._report_hash_progress(conn, session, HASH_MD5, size,
                                           final_hex=overall.hexdigest(), block_hashes=block_hashes)
            elif hash_type == HASH_SHA1:
                sha1 = hashlib.sha1()
                with open(local_path, "rb") as bf:
                    for chunk in iter(lambda: bf.read(4 * 1024 * 1024), b""):
                        sha1.update(chunk)
                self._report_hash_progress(conn, session, HASH_SHA1, size, final_hex=sha1.hexdigest())
            elif hash_type == HASH_PIKPAK:
                segment_size = _pikpak_segment_size(size)
                digests = b""
                with open(local_path, "rb") as bf:
                    while True:
                        seg = bf.read(segment_size)
                        if not seg:
                            break
                        digests += hashlib.sha1(seg).digest()
                self._report_hash_progress(conn, session, HASH_PIKPAK, size,
                                           final_hex=hashlib.sha1(digests).hexdigest().upper())
            else:
                self._report_hash_progress(conn, session, hash_type, 0)
        except Exception as e:
            logger.error(f"磁盘源哈希计算失败: {e}")
            try:
                self._report_hash_progress(conn, session, hash_type, 0)
            except Exception:
                pass

    def _next_job_local(self, session: _Session, timeout: float) -> Optional[dict]:
        """磁盘模式：从会话队列取任务（无终态时阻塞等待）"""
        deadline = time.time() + timeout
        with session.cond:
            while True:
                if session.jobs:
                    return session.jobs.pop(0)
                if session.terminal:
                    return None
                remaining = deadline - time.time()
                if remaining <= 0:
                    return None
                session.cond.wait(remaining)

    def _dispatch(self, reply):
        session = self._sessions.get(reply.upload_id)
        if session is None:
            # 会话尚未注册（StartRemoteUpload 返回前服务器已推送请求）：暂存，注册时补入
            with self._sessions_lock:
                self._orphan_replies.setdefault(reply.upload_id, []).append(reply)
            return
        case = reply.WhichOneof("request")
        if case == "read_data":
            r = reply.read_data
            job = {
                "type": "read",
                "request_id": uuid.uuid4().hex,
                "offset": int(r.offset),
                "length": int(r.length),
                "lazy_read": bool(r.lazy_read),
            }
            session.pending_reads[job["request_id"]] = job
            self._push_job(session, job)
        elif case == "hash_data":
            h = reply.hash_data
            if session.local:
                # 磁盘数据源模式：hash 请求转成本地计算任务
                self._push_job(session, {"type": "hash", "hash_type": int(h.hash_type), "block_size": int(h.block_size or 0)})
            else:
                threading.Thread(
                    target=self._hash_worker, args=(session, int(h.hash_type), int(h.block_size or 0)),
                    name=f"CD2Hash-{reply.upload_id[:8]}", daemon=True,
                ).start()
        elif case == "status_changed":
            s = reply.status_changed
            session.status = int(s.status)
            session.error = s.error_message
            logger.info(f"远程上传 {reply.upload_id[:8]}... 状态: {_STATUS_TEXT.get(session.status, session.status)}")
            if session.status in _TERMINAL_STATUS:
                session.terminal = True
                with session.cond:
                    session.cond.notify_all()

    def _push_job(self, session: _Session, job: dict):
        with session.cond:
            session.jobs.append(job)
            session.cond.notify_all()

    # ---------- 会话操作 ----------
    def start(self, conn, path: str, file_name: str, size: int) -> Dict[str, Any]:
        conn = conn
        self._ensure_channel(conn)
        req = conn.pb2.StartRemoteUploadRequest(
            file_path=f"{path.rstrip('/')}/{file_name}",
            file_size=size,
            client_can_calculate_hashes=True,
        )
        started = conn.stub.StartRemoteUpload(req, metadata=conn.get_metadata(), timeout=60)
        upload_id = started.upload_id
        session = _Session(upload_id, req.file_path, size)
        self._register_session(session)
        self._channel_wakeup.set()  # 会话已就绪，若通道恰在待机则立即恢复连接
        log_audit("CD2上传", "开始", f"远程上传: {req.file_path} ({size} 字节)")
        return {"upload_id": upload_id, "file_path": req.file_path, "size": size}

    def next_request(self, upload_id: str, timeout: int = _POLL_TIMEOUT) -> Dict[str, Any]:
        """浏览器长轮询：取下一个任务；无任务且未终态则等待至超时"""
        session = self._sessions.get(upload_id)
        if session is None:
            return {"type": "error", "message": "上传会话不存在"}
        deadline = time.time() + timeout
        with session.cond:
            while True:
                if session.jobs:
                    return session.jobs.pop(0)
                if session.terminal:
                    self._sessions.pop(upload_id, None)
                    return {
                        "type": "done",
                        "status": session.status,
                        "status_text": _STATUS_TEXT.get(session.status or -1, "未知"),
                        "error": session.error,
                    }
                remaining = deadline - time.time()
                if remaining <= 0:
                    return {"type": "none"}
                session.cond.wait(remaining)

    def submit_data(self, upload_id: str, request_id: str, data: bytes) -> Dict[str, Any]:
        """浏览器回传分块：read 任务转发给服务器，hash_read 任务喂给哈希线程"""
        session = self._sessions.get(upload_id)
        if session is None:
            return {"success": False, "message": "上传会话不存在"}

        read_job = session.pending_reads.get(request_id)
        if read_job is not None:
            conn = self._conn
            is_last = (read_job["offset"] + len(data)) >= session.size
            req = conn.pb2.RemoteReadDataUpload(
                upload_id=upload_id,
                offset=read_job["offset"],
                length=len(data),
                lazy_read=read_job["lazy_read"],
                data=data,
                is_last_chunk=is_last,
            )
            resp = conn.stub.RemoteReadData(req, metadata=conn.get_metadata(), timeout=120)
            session.pending_reads.pop(request_id, None)
            if not resp.success:
                return {"success": False, "message": resp.error_message}
            return {"success": True, "bytes_received": int(resp.bytes_received)}

        waiter = session.pending_hash_reads.get(request_id)
        if waiter is not None:
            waiter["data"] = data
            waiter["event"].set()
            return {"success": True}

        return {"success": False, "message": "无效的 request_id"}

    def cancel(self, upload_id: str) -> Dict[str, Any]:
        conn = self._conn
        session = self._sessions.get(upload_id)
        req = conn.pb2.RemoteUploadControlRequest(upload_id=upload_id, cancel=conn.pb2.CancelRemoteUpload())
        conn.stub.RemoteUploadControl(req, metadata=conn.get_metadata(), timeout=30)
        if session:
            session.terminal = True
            with session.cond:
                session.cond.notify_all()
            self._sessions.pop(upload_id, None)
        return {"success": True, "message": "已取消"}

    # ---------- 哈希 ----------
    def _fetch_range(self, session: _Session, offset: int, length: int) -> bytes:
        """向浏览器请求任意范围的数据（用于哈希计算）"""
        rid = uuid.uuid4().hex
        waiter = {"event": threading.Event(), "data": None}
        session.pending_hash_reads[rid] = waiter
        self._push_job(session, {"type": "hash_read", "request_id": rid, "offset": offset, "length": length})
        if not waiter["event"].wait(timeout=_RANGE_TIMEOUT):
            session.pending_hash_reads.pop(rid, None)
            raise TimeoutError(f"等待浏览器回传数据超时: offset={offset}, length={length}")
        session.pending_hash_reads.pop(rid, None)
        data = waiter["data"]
        if data is None:
            raise RuntimeError("浏览器回传数据为空")
        return data

    def _report_hash_progress(self, conn, session: _Session, hash_type: int, hashed: int, final_hex: Optional[str] = None, block_hashes: Optional[list] = None):
        req = conn.pb2.RemoteHashProgressUpload(
            upload_id=session.upload_id,
            bytes_hashed=hashed,
            total_bytes=session.size,
            hash_type=hash_type,
        )
        if final_hex is not None:
            req.hash_value = final_hex
        if block_hashes:
            req.block_hashes.extend(block_hashes)
        conn.stub.RemoteHashProgress(req, metadata=conn.get_metadata(), timeout=60)

    def _hash_worker(self, session: _Session, hash_type: int, block_size: int):
        conn = self._conn
        try:
            size = session.size
            fetch = lambda off, ln: self._fetch_range(session, off, ln)

            if hash_type == HASH_MD5:
                overall = hashlib.md5()
                block_hashes = []
                hashed = 0
                last_report = time.time()
                if block_size > 0:
                    pos = 0
                    while pos < size:
                        chunk = fetch(pos, min(block_size, size - pos))
                        block_hashes.append(hashlib.md5(chunk).hexdigest())
                        overall.update(chunk)
                        pos += len(chunk)
                        hashed = pos
                        if time.time() - last_report >= 0.5:
                            self._report_hash_progress(conn, session, hash_type, hashed)
                            last_report = time.time()
                else:
                    pos = 0
                    while pos < size:
                        chunk = fetch(pos, min(4 * 1024 * 1024, size - pos))
                        overall.update(chunk)
                        pos += len(chunk)
                        hashed = pos
                        if time.time() - last_report >= 0.5:
                            self._report_hash_progress(conn, session, hash_type, hashed)
                            last_report = time.time()
                self._report_hash_progress(conn, session, hash_type, size, final_hex=overall.hexdigest(), block_hashes=block_hashes)

            elif hash_type == HASH_SHA1:
                sha1 = hashlib.sha1()
                pos = 0
                last_report = time.time()
                while pos < size:
                    chunk = fetch(pos, min(4 * 1024 * 1024, size - pos))
                    sha1.update(chunk)
                    pos += len(chunk)
                    hashed = pos
                    if time.time() - last_report >= 0.5:
                        self._report_hash_progress(conn, session, hash_type, hashed)
                        last_report = time.time()
                self._report_hash_progress(conn, session, hash_type, size, final_hex=sha1.hexdigest())

            elif hash_type == HASH_PIKPAK:
                segment_size = _pikpak_segment_size(size)
                digests = b""
                pos = 0
                hashed = 0
                last_report = time.time()
                while pos < size:
                    seg_len = min(segment_size, size - pos)
                    seg = fetch(pos, seg_len)
                    digests += hashlib.sha1(seg).digest()
                    pos += seg_len
                    hashed = pos
                    if time.time() - last_report >= 0.5:
                        self._report_hash_progress(conn, session, hash_type, hashed)
                        last_report = time.time()
                final = hashlib.sha1(digests).hexdigest().upper()
                self._report_hash_progress(conn, session, hash_type, size, final_hex=final)

            else:
                logger.warning(f"不支持的哈希类型: {hash_type}，发送空终态")

        except Exception as e:
            logger.error(f"远程上传哈希计算失败: {e}")
            try:
                # 取消时发送不带 hash_value 的终态进度
                self._report_hash_progress(conn, session, hash_type, 0)
            except Exception:
                pass
