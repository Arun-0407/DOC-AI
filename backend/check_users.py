"""
Diagnostic script — list all users and create an admin if none exist.
Run from backend/ directory:  python check_users.py
"""
import asyncio
from app.database import engine
from app.core.security import hash_password
from sqlalchemy import text

ADMIN_EMAIL    = "admin@docai.com"
ADMIN_PASSWORD = "Admin@1234"
ADMIN_NAME     = "Admin"

async def main():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT email, role, is_active FROM users ORDER BY created_at"))
        rows = result.fetchall()

    if not rows:
        print("⚠  No users found in database.")
    else:
        print(f"✅ Found {len(rows)} user(s):")
        for row in rows:
            print(f"   email={row[0]}  role={row[1]}  active={row[2]}")

    # Check if admin exists
    admin_exists = any(r[0] == ADMIN_EMAIL for r in rows)
    if not admin_exists:
        print(f"\n🔧 Creating admin user: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        hashed = hash_password(ADMIN_PASSWORD)
        async with engine.begin() as conn:
            await conn.execute(text(
                "INSERT INTO users (id, email, password_hash, full_name, role, is_active, created_at) "
                "VALUES (gen_random_uuid(), :email, :pw, :name, 'admin', true, now())"
            ), {"email": ADMIN_EMAIL, "pw": hashed, "name": ADMIN_NAME})
        print("✅ Admin user created successfully!")
        print(f"   Email:    {ADMIN_EMAIL}")
        print(f"   Password: {ADMIN_PASSWORD}")
    else:
        print(f"\n✅ Admin user {ADMIN_EMAIL} already exists.")

asyncio.run(main())
