"""
Reset admin password.
Run from backend/ directory:  python reset_admin_password.py
"""
import asyncio
from app.database import engine
from app.core.security import hash_password
from sqlalchemy import text

ADMIN_EMAIL    = "admin@docai.com"
ADMIN_PASSWORD = "Admin@1234"

async def main():
    hashed = hash_password(ADMIN_PASSWORD)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("UPDATE users SET password_hash = :pw, role = 'admin' WHERE email = :email"),
            {"pw": hashed, "email": ADMIN_EMAIL}
        )
        if result.rowcount == 0:
            print(f"⚠  No user found with email: {ADMIN_EMAIL}")
        else:
            print(f"✅ Password reset for {ADMIN_EMAIL}")
            print(f"   New password: {ADMIN_PASSWORD}")

asyncio.run(main())
