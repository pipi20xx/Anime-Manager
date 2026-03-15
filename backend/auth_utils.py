from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import jwt
import bcrypt
import os
import uuid

# 加密配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "anime_manager_secret_key_change_me_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 # 默认登录有效期 24 小时

def verify_password(plain_password: str, hashed_password: str):
    """校验明文密码与哈希值是否匹配"""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def get_password_hash(password: str):
    """对明文密码进行加密"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, password_hash: str = None, expires_delta: Optional[timedelta] = None) -> Tuple[str, str]:
    """创建 JWT 访问令牌，包含密码指纹使密码修改后旧token失效
    
    返回: (token, token_id)
    """
    to_encode = data.copy()
    token_id = str(uuid.uuid4())
    to_encode.update({"jti": token_id})
    
    if expires_delta is None:
        expire = datetime.utcnow() + timedelta(days=365*10)
    elif expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    if password_hash:
        to_encode.update({"pwd_fp": password_hash[:8]})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, token_id

def decode_access_token(token: str, password_hash: str = None) -> Optional[dict]:
    """解析并验证 JWT 令牌，可选验证密码指纹"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if password_hash and payload.get("pwd_fp"):
            if payload.get("pwd_fp") != password_hash[:8]:
                return None
        return payload
    except:
        return None

import time
from typing import Dict, Tuple

class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, lockout_minutes: int = 15):
        self.max_attempts = max_attempts
        self.lockout_duration = lockout_minutes * 60
        # 存储格式: { ip: (失败次数, 最后一次失败时间) }
        self.attempts: Dict[str, Tuple[int, float]] = {}

    def is_locked(self, ip: str) -> Tuple[bool, int]:
        """检查该 IP 是否处于封锁状态，返回 (是否锁定, 剩余秒数)"""
        if ip not in self.attempts:
            return False, 0
        
        count, last_time = self.attempts[ip]
        if count >= self.max_attempts:
            remaining = int((last_time + self.lockout_duration) - time.time())
            if remaining > 0:
                return True, remaining
            else:
                # 封锁期已过，重置
                del self.attempts[ip]
                return False, 0
        return False, 0

    def record_failure(self, ip: str):
        """记录一次失败尝试"""
        count, _ = self.attempts.get(ip, (0, 0.0))
        self.attempts[ip] = (count + 1, time.time())

    def reset(self, ip: str):
        """登录成功后重置该 IP 的记录"""
        if ip in self.attempts:
            del self.attempts[ip]

# 全局单例
login_limiter = LoginRateLimiter()

async def ensure_default_user():
    """启动时检查并初始化默认用户"""
    from database import db
    from models import User
    from sqlmodel import select
    from config_manager import ConfigManager
    import logging
    
    logger = logging.getLogger(__name__)
    
    async with db.session_scope() as session:
        try:
            # 检查是否已有用户
            result = await session.execute(select(User))
            if result.scalars().first():
                return
            
            # 读取现有配置中的 web_password
            config = ConfigManager.get_config()
            web_pwd = config.get("web_password")
            
            # 确定初始密码
            init_pwd = web_pwd if web_pwd else "admin123"
            
            logger.info(f"[Auth] 未检测到用户账号，正在初始化默认管理员: admin")
            
            admin_user = User(
                username="admin",
                hashed_password=get_password_hash(init_pwd)
            )
            session.add(admin_user)
            await session.commit()
            
            if web_pwd:
                logger.info("[Auth] 已成功从配置文件迁移旧版 web_password 到 admin 账号。")
            else:
                logger.warning("[Auth] 系统已初始化默认账号: admin / admin123，请尽快登录并修改密码！")
                
        except Exception as e:
            logger.error(f"[Auth] 自动初始化用户失败: {e}")
