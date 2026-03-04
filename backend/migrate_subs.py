import asyncio
from database import db
from sqlalchemy import text
from config_manager import ConfigManager

async def migrate():
    print("Starting migration...")
    async with db.session_scope() as session:
        try:
            print("Adding column: target_feeds to subscriptions")
            await session.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS target_feeds VARCHAR"))
            
            print("Adding column: target_feeds to subscription_templates")
            await session.execute(text("ALTER TABLE subscription_templates ADD COLUMN IF NOT EXISTS target_feeds VARCHAR"))
            
            await session.commit()
            print("Migration completed successfully.")
        except Exception as e:
            print(f"Migration failed (columns might already exist or other error): {e}")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(migrate())