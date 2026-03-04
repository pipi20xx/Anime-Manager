import asyncio
import sys
import os

# 确保可以导入项目模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db, init_db
from models import User
from auth_utils import get_password_hash
from sqlmodel import select

async def create_admin(username, password):
    await init_db()
    async with db.session_scope() as session:
        # 检查是否已存在
        result = await session.execute(select(User).where(User.username == username))
        existing_user = result.scalars().first()
        
        if existing_user:
            print(f"用户 {username} 已存在，正在更新密码...")
            existing_user.hashed_password = get_password_hash(password)
            session.add(existing_user)
        else:
            print(f"正在创建管理员用户: {username}")
            new_user = User(
                username=username,
                hashed_password=get_password_hash(password)
            )
            session.add(new_user)
        
        await session.commit()
        print("管理员用户初始化成功。")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python init_user.py <用户名> <密码>")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    asyncio.run(create_admin(username, password))
