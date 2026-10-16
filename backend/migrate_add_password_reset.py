"""
One-shot migration: add password_reset_token and password_reset_expires
columns to the users table.

Run from the backend/ directory:
    python migrate_add_password_reset.py
"""
import asyncio
from sqlalchemy import text
from app.database import engine


ALTER_STATEMENTS = [
    """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_reset_token VARCHAR(255);
    """,
    """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_reset_expires TIMESTAMP;
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_users_password_reset_token
    ON users (password_reset_token);
    """,
]


async def run():
    async with engine.begin() as conn:
        for stmt in ALTER_STATEMENTS:
            await conn.execute(text(stmt))
            print(f"Executed: {stmt.strip()[:70]}…")
    print("\nMigration complete.")


if __name__ == "__main__":
    asyncio.run(run())
