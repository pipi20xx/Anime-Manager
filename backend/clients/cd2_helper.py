import os
import sys
import requests
import importlib
import pkg_resources
import hashlib
import logging
import bencodepy
from grpc_tools import protoc

logger = logging.getLogger(__name__)

OFFICIAL_PROTO_URL = "https://www.clouddrive2.com/api/clouddrive.proto"

def get_gen_dir():
    # 优先使用容器标准的 /app/data
    if os.path.exists("/app/data"):
        return "/app/data/cd2_gen"
    # 其次尝试相对于当前文件的路径
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "data", "cd2_gen")

GEN_DIR = get_gen_dir()
PROTO_FILE = os.path.join(GEN_DIR, "clouddrive.proto")
HASH_FILE = os.path.join(GEN_DIR, "clouddrive.proto.hash")

_LOADED_MODULES = None

def ensure_cd2_module():
    """
    确保 CD2 协议模块可用。支持持久化、Hash 校验和自动更新。
    """
    global _LOADED_MODULES, GEN_DIR, PROTO_FILE, HASH_FILE
    
    if _LOADED_MODULES:
        return _LOADED_MODULES

    logger.info(f"===> CD2 协议检查开始 (存储目录: {GEN_DIR})")

    if not os.path.exists(GEN_DIR):
        try:
            os.makedirs(GEN_DIR, exist_ok=True)
            logger.info(f"已创建 CD2 持久化目录: {GEN_DIR}")
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
            GEN_DIR = os.path.dirname(os.path.abspath(__file__))
            PROTO_FILE = os.path.join(GEN_DIR, "clouddrive.proto")
            HASH_FILE = os.path.join(GEN_DIR, "clouddrive.proto.hash")
            logger.warning(f"由于权限问题，CD2 协议将回退到非持久化目录: {GEN_DIR}")

    pb2_path = os.path.join(GEN_DIR, "clouddrive_pb2.py")
    pb2_grpc_path = os.path.join(GEN_DIR, "clouddrive_pb2_grpc.py")

    # 1. 尝试静默获取远程 Proto 以进行版本比对
    remote_proto_content = None
    remote_hash = None
    try:
        logger.info(f"正在尝试连接官网检查协议版本更新...")
        resp = requests.get(OFFICIAL_PROTO_URL, timeout=5)
        if resp.status_code == 200:
            remote_proto_content = resp.text
            remote_hash = hashlib.md5(remote_proto_content.encode('utf-8')).hexdigest()
            logger.info(f"远程协议获取成功，当前最新 Hash: {remote_hash}")
    except Exception as e:
        logger.warning(f"检查远程更新失败 (网络不通)，将依赖本地文件。")

    # 2. 读取本地 Hash
    local_hash = None
    if os.path.exists(HASH_FILE):
        try:
            with open(HASH_FILE, "r") as f:
                local_hash = f.read().strip()
            logger.info(f"本地缓存协议 Hash: {local_hash}")
        except:
            pass

    # 3. 决定是否需要下载或编译
    need_compile = False
    if not os.path.exists(pb2_path) or not os.path.exists(pb2_grpc_path):
        logger.info("未发现编译后的 Python 文件，准备开始初次构建。")
        need_compile = True
    elif remote_hash and local_hash and remote_hash != local_hash:
        logger.info(f"检测到协议版本更新，准备重新编译。")
        need_compile = True
    else:
        logger.info("CD2 协议版本一致且本地文件完整，跳过下载与编译过程。")

    if need_compile:
        # 如果已经拿到了远程内容，直接存
        if remote_proto_content:
            with open(PROTO_FILE, "w", encoding="utf-8") as f:
                f.write(remote_proto_content)
            if remote_hash:
                with open(HASH_FILE, "w") as f:
                    f.write(remote_hash)
            logger.info("已保存最新的协议内容到本地。")
        # 否则尝试正式下载函数
        elif not os.path.exists(PROTO_FILE):
            if not download_proto():
                logger.error("无法获取协议文件且本地不存在，初始化中止。")
                return None, None
        
        compile_proto()

    # 4. 加载生成的模块
    if GEN_DIR not in sys.path:
        sys.path.insert(0, GEN_DIR)
    
    try:
        for m in ['clouddrive_pb2', 'clouddrive_pb2_grpc']:
            if m in sys.modules: del sys.modules[m]
            
        import clouddrive_pb2
        import clouddrive_pb2_grpc
        _LOADED_MODULES = (clouddrive_pb2, clouddrive_pb2_grpc)
        logger.info("===> CD2 协议模块加载成功！✅")
        return _LOADED_MODULES
    except Exception as e:
        logger.error(f"导入 CD2 协议模块失败: {e}")
        return None, None

def download_proto():
    """专门负责下载的函数，包含详细日志"""
    try:
        logger.info(f"正在从官网下载 clouddrive.proto (URL: {OFFICIAL_PROTO_URL})...")
        resp = requests.get(OFFICIAL_PROTO_URL, timeout=15)
        resp.raise_for_status()
        with open(PROTO_FILE, "w", encoding="utf-8") as f:
            f.write(resp.text)
        h = hashlib.md5(resp.text.encode('utf-8')).hexdigest()
        with open(HASH_FILE, "w") as f:
            f.write(h)
        logger.info("协议文件下载成功。")
        return True
    except Exception as e:
        logger.error(f"下载协议文件失败: {e}")
        return False

def compile_proto():
    try:
        logger.info("正在执行 Protoc 编译...")
        try:
            proto_include = pkg_resources.resource_filename('grpc_tools', '_proto')
        except:
            import grpc_tools
            proto_include = os.path.join(os.path.dirname(grpc_tools.__file__), '_proto')

        cmd = [
            'protoc',
            f'-I{GEN_DIR}',
            f'-I{proto_include}',
            f'--python_out={GEN_DIR}',
            f'--grpc_python_out={GEN_DIR}',
            os.path.abspath(PROTO_FILE),
        ]
        
        exit_code = protoc.main(cmd)
        if exit_code != 0:
            logger.error(f"Protoc 编译失败，退出码: {exit_code}")
        else:
            logger.info("Protoc 编译成功。")
            
    except Exception as e:
        logger.error(f"编译 proto 过程中出现系统异常: {e}")

def torrent_to_magnet(torrent_content: bytes) -> str:
    try:
        metadata = bencodepy.decode(torrent_content)
        info = metadata[b'info']
        info_encoded = bencodepy.encode(info)
        digest = hashlib.sha1(info_encoded).hexdigest()
        return f"magnet:?xt=urn:btih:{digest}"
    except Exception as e:
        logger.error(f"种子转磁力链接失败: {e}")
        return ""