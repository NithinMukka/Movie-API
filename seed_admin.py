"""
Create or promote an admin user.

Registration via the API always creates a 'customer' (so nobody can self-elevate),
so the first admin must be seeded here. Connects to the database configured in .env.

Examples:
    # create a brand-new admin
    python seed_admin.py --email you@example.com --password "strongpass" --name "You"

    # promote an already-registered user to admin (password/name left as-is)
    python seed_admin.py --email existing@example.com
"""
import argparse
import asyncio
import sys

# pyrefly: ignore [missing-import]
from sqlalchemy.future import select

import models
from database import SessionLocal, engine
from auth import hash_password

# asyncpg + asyncio on Windows is happiest on the selector event loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def seed_admin(email: str, password: str | None, name: str | None) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(models.User).filter(models.User.email == email))
        user = result.scalars().first()

        if user:
            user.role = "admin"
            if password:
                user.password_hash = hash_password(password)
            if name:
                user.name = name
            action = "promoted existing user to admin"
        else:
            if not password:
                print("Error: creating a new admin requires --password", file=sys.stderr)
                raise SystemExit(1)
            user = models.User(
                name=name or email.split("@")[0],
                email=email,
                password_hash=hash_password(password),
                role="admin",
            )
            db.add(user)
            action = "created new admin"

        await db.commit()
        await db.refresh(user)
        print(f"OK: {action}  (id={user.id}, email={user.email}, role={user.role})")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument("--email", required=True, help="Admin's email (login id)")
    parser.add_argument("--password", help="Required only when creating a new admin")
    parser.add_argument("--name", help="Display name (defaults to the email prefix)")
    args = parser.parse_args()
    asyncio.run(seed_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
