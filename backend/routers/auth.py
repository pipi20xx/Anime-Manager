from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from database import get_session, db
from models import User
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
        # ... (rest of the code)
        if not req.otp_code:
            pending_token = create_access_token(data={"sub": user.username, "type": "2fa_pending"}, expires_delta=timedelta(minutes=5))
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
    
    access_token = create_access_token(data={"sub": user.username})
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
    from config_manager import ConfigManager
    config = ConfigManager.get_config()
    
    # 优先读取用户手动设置的开关，默认开启
    ui_auth_enabled = config.get("ui_auth_enabled")
    if ui_auth_enabled is None:
        # 如果没设置过，且有 web_password，则默认为 True
        ui_auth_enabled = bool(config.get("web_password"))
    
    return {"ui_auth_enabled": ui_auth_enabled}

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
