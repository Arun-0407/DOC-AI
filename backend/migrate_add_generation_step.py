import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='documents' AND column_name='generation_step'"
        ))
        if result.fetchone():
            print("Column generation_step already exists — nothing to do.")
            return

        await db.execute(text(
            "ALTER TABLE documents ADD COLUMN generation_step VARCHAR(100) DEFAULT ''"
        ))
        await db.commit()
        print("Column generation_step added successfully.")


asyncio.run(main())
