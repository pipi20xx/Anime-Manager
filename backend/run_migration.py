import asyncio
from database import init_db
from logger import init_logging

async def main():
    print("正在执行数据库迁移...")
    init_logging()
    try:
        await init_db()
        print("数据库迁移执行成功！")
    except Exception as e:
        print(f"数据库迁移失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())