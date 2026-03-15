from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from database import get_session, db
from models import User, Session
from auth_utils import verify_password, create_access_token, decode_access_token, get_password_hash, login_limiter
from pydantic import BaseModel
from datetime import timedelta, datetime
from typing import Optional
import asyncio
import pyotp
import qrcode
import io
import base64
import logging
import uuid
import re

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)

class LoginRequest(BaseModel):
    username: str
    password: str
    otp_code: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    status: str = "success"

def parse_user_agent(user_agent: str) -> dict:
    """解析 User-Agent 字符串，提取浏览器和操作系统信息"""
    result = {
        "browser_name": "Unknown",
        "os_name": "Unknown",
        "device_name": "Unknown"
    }
    
    if not user_agent:
        return result
    
    ua = user_agent.lower()
    
    if "chrome" in ua and "edg" not in ua:
        match = re.search(r'chrome/(\d+\.\d+\.\d+\.\d+)', ua)
        result["browser_name"] = f"Chrome {match.group(1) if match else ''}"
    elif "firefox" in ua:
        match = re.search(r'firefox/(\d+\.\d+)', ua)
        result["browser_name"] = f"Firefox {match.group(1) if match else ''}"
    elif "safari" in ua and "chrome" not in ua:
        match = re.search(r'version/(\d+\.\d+)', ua)
        result["browser_name"] = f"Safari {match.group(1) if match else ''}"
    elif "edg" in ua:
        match = re.search(r'edg/(\d+\.\d+\.\d+\.\d+)', ua)
        result["browser_name"] = f"Edge {match.group(1) if match else ''}"
    
    if "windows" in ua:
        result["os_name"] = "Windows"
    elif "macintosh" in ua or "mac os x" in ua:
        result["os_name"] = "macOS"
    elif "linux" in ua:
        result["os_name"] = "Linux"
    elif "android" in ua:
        result["os_name"] = "Android"
    elif "iphone" in ua or "ipad" in ua:
        result["os_name"] = "iOS"
    
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        result["device_name"] = "Mobile"
    elif "tablet" in ua or "ipad" in ua:
        result["device_name"] = "Tablet"
    else:
        result["device_name"] = "Desktop"
    
    return result

async def create_session(user_id: int, token_id: str, request: Request, expires_at: datetime):
    """创建登录会话记录"""
    try:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        parsed_ua = parse_user_agent(user_agent)
        
        session = Session(
            user_id=user_id,
            token_id=token_id,
            ip_address=client_ip,
            user_agent=user_agent,
            device_name=parsed_ua["device_name"],
            browser_name=parsed_ua["browser_name"],
            os_name=parsed_ua["os_name"],
            expires_at=expires_at
        )
        
        async with db.session_scope() as db_session:
            db_session.add(session)
            await db_session.commit()
            await db_session.refresh(session)
            return session.id
    except Exception as e:
        logger.error(f"创建会话失败: {e}")
        return None

@router.post("/login", response_model=TokenResponse, summary="管理员登录")
async def login(req: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)):
    client_ip = request.client.host if request.client else "unknown"
    
    is_locked, remaining = login_limiter.is_locked(client_ip)
    if is_locked:
        raise HTTPException(status_code=429, detail=f"封锁中，请在 {remaining} 秒后再试")

    result = await session.execute(select(User).where(User.username == req.username))
    user = result.scalars().first()
    
    if not user or not verify_password(req.password, user.hashed_password):
        login_limiter.record_failure(client_ip)
        from logger import log_audit
        log_audit("AUTH", "登录失败", f"IP: {client_ip}, 用户: {req.username}", level="ERROR")
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    if user.is_otp_enabled:
        if not req.otp_code:
            pending_token, _ = create_access_token(data={"sub": user.username, "type": "2fa_pending"}, expires_delta=timedelta(minutes=5))
            return {
                "access_token": pending_token,
                "token_type": "bearer",
                "username": user.username,
                "status": "2fa_required"
            }
        totp = pyotp.TOTP(user.otp_secret)
        if not totp.verify(req.otp_code):
            login_limiter.record_failure(client_ip)
            raise HTTPException(status_code=401, detail="2FA 验证码错误")

    login_limiter.reset(client_ip)
    user.last_login = datetime.now()
    session.add(user)
    await session.commit()
    
    from config_manager import ConfigManager
    config = ConfigManager.get_config()
    jwt_never_expire = config.get("jwt_never_expire", False)
    
    access_token, token_id = create_access_token(
        data={"sub": user.username}, 
        password_hash=user.hashed_password,
        expires_delta=None if jwt_never_expire else None
    )
    
    expires_at = datetime.utcnow() + timedelta(minutes=24*60) if not jwt_never_expire else datetime.utcnow() + timedelta(days=365*10)
    await create_session(user.id, token_id, request, expires_at)
    
    from logger import log_audit
    log_audit("AUTH", "登录成功", f"IP: {client_ip}, 用户: {user.username}")
    
    return {"access_token": access_token, "token_type": "bearer", "username": user.username, "status": "success"}

@router.post("/password", summary="修改管理员密码")
async def change_password(req: PasswordChangeRequest, session: AsyncSession = Depends(get_session), token: str = Depends(oauth2_scheme)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload: raise HTTPException(status_code=401)
    username = payload.get("sub")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user or not verify_password(req.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="旧密码错误")
    
    user.hashed_password = get_password_hash(req.new_password)
    session.add(user)
    await session.commit()
    
    from logger import log_audit
    log_audit("AUTH", "修改密码", f"用户 {username} 修改了密码")
    return {"message": "成功"}

@router.get("/2fa/setup", summary="获取 2FA 设置信息")
async def setup_2fa(session: AsyncSession = Depends(get_session), token: str = Depends(oauth2_scheme)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload: raise HTTPException(status_code=401)
    username = payload.get("sub")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    
    secret = pyotp.random_base32()
    user.otp_secret = secret
    session.add(user)
    await session.commit()
    
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name="AnimeManager")
    img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return {"secret": secret, "qr_code": f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"}

@router.post("/2fa/enable", summary="正式开启 2FA")
async def enable_2fa(code: str, session: AsyncSession = Depends(get_session), token: str = Depends(oauth2_scheme)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload: raise HTTPException(status_code=401)
    username = payload.get("sub")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    
    if pyotp.TOTP(user.otp_secret).verify(code):
        user.is_otp_enabled = True
        session.add(user)
        await session.commit()
        return {"message": "成功"}
    raise HTTPException(status_code=400, detail="验证码无效")

@router.post("/2fa/disable", summary="关闭 2FA")
async def disable_2fa(session: AsyncSession = Depends(get_session), token: str = Depends(oauth2_scheme)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload: raise HTTPException(status_code=401)
    username = payload.get("sub")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    user.is_otp_enabled = False
    session.add(user)
    await session.commit()
    return {"message": "成功"}

@router.get("/status", summary="获取系统认证状态")
async def get_auth_status():
    return {"ui_auth_enabled": True}

@router.get("/me", summary="获取当前用户信息")
async def get_me(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload or payload.get("type") == "2fa_pending": raise HTTPException(status_code=401)
    username = payload.get("sub")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401)
        
    return {
        "username": user.username, 
        "is_otp_enabled": user.is_otp_enabled, 
        "last_login": user.last_login
    }

@router.get("/sessions", summary="获取当前用户的所有登录会话")
async def get_sessions(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload or payload.get("type") == "2fa_pending": raise HTTPException(status_code=401)
    username = payload.get("sub")
    current_token_id = payload.get("jti")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401)
    
    from models import Session as SessionModel
    from sqlmodel import select as sl
    from datetime import datetime
    
    sessions_result = await session.execute(
        sl(SessionModel).where(SessionModel.user_id == user.id).order_by(SessionModel.created_at.desc())
    )
    sessions = sessions_result.scalars().all()
    
    session_list = []
    for sess in sessions:
        expires_in_seconds = int((sess.expires_at - datetime.utcnow()).total_seconds())
        if expires_in_seconds < 0:
            expires_in_seconds = 0
        
        session_list.append({
            "id": sess.id,
            "token_id": sess.token_id,
            "ip_address": sess.ip_address,
            "user_agent": sess.user_agent,
            "device_name": sess.device_name,
            "browser_name": sess.browser_name,
            "os_name": sess.os_name,
            "is_current": sess.token_id == current_token_id,
            "expires_at": sess.expires_at.isoformat(),
            "expires_in": expires_in_seconds,
            "created_at": sess.created_at.isoformat(),
            "last_activity": sess.last_activity.isoformat()
        })
    
    return {"sessions": session_list}

@router.delete("/sessions/{session_id}", summary="踢出指定会话")
async def revoke_session(session_id: int, token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload or payload.get("type") == "2fa_pending": raise HTTPException(status_code=401)
    username = payload.get("sub")
    current_token_id = payload.get("jti")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401)
    
    from models import Session as SessionModel
    from sqlmodel import select as sl
    
    sessions_result = await session.execute(
        sl(SessionModel).where(SessionModel.id == session_id, SessionModel.user_id == user.id)
    )
    target_session = sessions_result.scalars().first()
    
    if not target_session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    if target_session.token_id == current_token_id:
        raise HTTPException(status_code=400, detail="不能踢出当前会话")
    
    await session.delete(target_session)
    await session.commit()
    
    from logger import log_audit
    log_audit("AUTH", "踢出会话", f"用户: {username}, 会话ID: {session_id}, IP: {target_session.ip_address}")
    
    return {"message": "会话已踢出"}

@router.delete("/sessions", summary="踢出除当前会话外的所有会话")
async def revoke_all_sessions(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)):
    if not token: raise HTTPException(status_code=401)
    payload = decode_access_token(token)
    if not payload or payload.get("type") == "2fa_pending": raise HTTPException(status_code=401)
    username = payload.get("sub")
    current_token_id = payload.get("jti")
    
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401)
    
    from models import Session as SessionModel
    from sqlmodel import select as sl
    
    sessions_result = await session.execute(
        sl(SessionModel).where(SessionModel.user_id == user.id, SessionModel.token_id != current_token_id)
    )
    sessions = sessions_result.scalars().all()
    
    for sess in sessions:
        await session.delete(sess)
    
    await session.commit()
    
    from logger import log_audit
    log_audit("AUTH", "批量踢出会话", f"用户: {username}, 踢出数量: {len(sessions)}")
    
    return {"message": f"已踢出 {len(sessions)} 个会话"}
