import hashlib
import os
import asyncio
import logging
import struct
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PureMD4:
    __slots__ = ('_buffer', '_count', '_h')
    
    S = [
        3, 7, 11, 19, 3, 7, 11, 19, 3, 7, 11, 19, 3, 7, 11, 19,
        3, 5, 9, 13, 3, 5, 9, 13, 3, 5, 9, 13, 3, 5, 9, 13,
        3, 9, 11, 15, 3, 9, 11, 15, 3, 9, 11, 15, 3, 9, 11, 15
    ]
    
    def __init__(self, data: bytes = b''):
        self._buffer = bytearray()
        self._count = 0
        self._h = [0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476]
        if data:
            self.update(data)

    @staticmethod
    def _left_rotate(x: int, n: int) -> int:
        return ((x << n) | (x >> (32 - n))) & 0xffffffff

    def _process_block(self, block: bytes):
        X = list(struct.unpack('<16I', block))
        A, B, C, D = self._h

        for i in range(16):
            k = i
            s = self.S[i]
            F = (B & C) | (~B & D)
            A = (A + F + X[k]) & 0xffffffff
            A = self._left_rotate(A, s)
            A, B, C, D = D, A, B, C

        for i in range(16):
            k = [0, 4, 8, 12, 1, 5, 9, 13, 2, 6, 10, 14, 3, 7, 11, 15][i]
            s = self.S[16 + i]
            G = (B & C) | (B & D) | (C & D)
            A = (A + G + X[k] + 0x5a827999) & 0xffffffff
            A = self._left_rotate(A, s)
            A, B, C, D = D, A, B, C

        for i in range(16):
            k = [0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15][i]
            s = self.S[32 + i]
            H = B ^ C ^ D
            A = (A + H + X[k] + 0x6ed9eba1) & 0xffffffff
            A = self._left_rotate(A, s)
            A, B, C, D = D, A, B, C

        self._h[0] = (self._h[0] + A) & 0xffffffff
        self._h[1] = (self._h[1] + B) & 0xffffffff
        self._h[2] = (self._h[2] + C) & 0xffffffff
        self._h[3] = (self._h[3] + D) & 0xffffffff

    def update(self, data: bytes):
        self._buffer.extend(data)
        self._count += len(data)
        while len(self._buffer) >= 64:
            self._process_block(bytes(self._buffer[:64]))
            del self._buffer[:64]

    def digest(self) -> bytes:
        msg = bytearray(self._buffer)
        msg.append(0x80)
        msg.extend(b'\x00' * ((55 - len(self._buffer)) % 64))
        msg.extend(struct.pack('<Q', self._count * 8))
        
        for i in range(0, len(msg), 64):
            self._process_block(msg[i:i+64])
        
        return struct.pack('<4I', *self._h)

    def hexdigest(self) -> str:
        return self.digest().hex()


def _get_md4():
    try:
        test = hashlib.new('md4', b'test')
        logger.info("[HashCalculator] 使用 OpenSSL MD4 加速")
        return lambda data: hashlib.new('md4', data)
    except ValueError:
        pass
    
    try:
        from Crypto.Hash import MD4
        logger.info("[HashCalculator] 使用 pycryptodome MD4 加速")
        def pycrypto_md4(data: bytes):
            h = MD4.new()
            h.update(data)
            return h
        return pycrypto_md4
    except ImportError:
        pass
    
    logger.info("[HashCalculator] OpenSSL/pycryptodome MD4 不可用，使用纯 Python 实现（较慢）")
    return PureMD4


_md4_hash = _get_md4()


@dataclass
class HashResult:
    sha1: str
    ed2k: str
    ed2k_link: str
    file_size: int
    file_path: str
    filename: str


class HashCalculator:
    ED2K_BLOCK_SIZE = 9728000
    
    @staticmethod
    def _calculate_ed2k_final(block_hashes: list) -> str:
        if len(block_hashes) == 0:
            return ""
        if len(block_hashes) == 1:
            return block_hashes[0].hex()
        return _md4_hash(b''.join(block_hashes)).hexdigest()
    
    @staticmethod
    def _build_ed2k_link(filename: str, file_size: int, ed2k_hash: str) -> str:
        return f"ed2k://|file|{filename}|{file_size}|{ed2k_hash}|/"
    
    @staticmethod
    def calculate_hashes_sync(file_path: str) -> Optional[HashResult]:
        if not os.path.exists(file_path):
            logger.warning(f"[HashCalculator] 文件不存在: {file_path}")
            return None
        
        if not os.path.isfile(file_path):
            logger.warning(f"[HashCalculator] 不是文件: {file_path}")
            return None
        
        try:
            file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path)
            logger.info(f"[HashCalculator] 开始计算: {filename} ({file_size / 1024 / 1024:.2f} MB)")
            
            sha1_hash = hashlib.sha1()
            ed2k_block_hashes = []
            
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(HashCalculator.ED2K_BLOCK_SIZE)
                    if not chunk:
                        break
                    
                    sha1_hash.update(chunk)
                    ed2k_block_hashes.append(_md4_hash(chunk).digest())
            
            sha1 = sha1_hash.hexdigest()
            ed2k = HashCalculator._calculate_ed2k_final(ed2k_block_hashes)
            ed2k_link = HashCalculator._build_ed2k_link(filename, file_size, ed2k)
            
            logger.info(f"[HashCalculator] 计算完成: {filename}")
            logger.info(f"[HashCalculator] SHA1: {sha1}")
            logger.info(f"[HashCalculator] ED2K: {ed2k_link}")
            
            return HashResult(
                sha1=sha1,
                ed2k=ed2k,
                ed2k_link=ed2k_link,
                file_size=file_size,
                file_path=file_path,
                filename=filename
            )
            
        except PermissionError:
            logger.error(f"[HashCalculator] 权限不足: {file_path}")
            return None
        except Exception as e:
            logger.error(f"[HashCalculator] 计算失败: {file_path} | 错误: {e}", exc_info=True)
            return None
    
    @staticmethod
    async def calculate_hashes(file_path: str) -> Optional[HashResult]:
        return await asyncio.to_thread(HashCalculator.calculate_hashes_sync, file_path)


def format_file_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"
