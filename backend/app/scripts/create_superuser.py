"""
Создание (или повышение) суперюзера.

Использование:
    python -m app.scripts.create_superuser admin@khasa.local mySecretPass

Поведение:
  • если такого юзера нет — создаёт активного суперюзера с подтверждённым email;
  • если есть — выставляет is_superuser=True, is_active=True, is_email_verified=True.
"""
from __future__ import annotations

import asyncio
import sys
import uuid

from app.infrastructure.database.uow import UnitOfWorkFactory
from app.infrastructure.security.password import BcryptPasswordHasher


async def run(email: str, password: str) -> None:
    hasher = BcryptPasswordHasher()
    hashed = hasher.hash(password)

    async with UnitOfWorkFactory() as uow:
        existing = await uow.users.get_by_email(email)
        if existing:
            await uow.users.set_superuser(existing.id, True)
            await uow.users.activate(existing.id)
            await uow.users.mark_email_verified(existing.id)
            await uow.users.change_password(existing.id, hashed)
            print(f"✓ updated existing user {email} → superuser, active, verified")
            return

        user_id = uuid.uuid4()
        await uow.users.add(
            id=user_id,
            email=email,
            hashed_password=hashed,
            is_email_verified=True,
            is_active=True,
            is_superuser=True,
        )
        print(f"✓ created superuser {email} (id={user_id})")


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python -m app.scripts.create_superuser <email> <password>")
        sys.exit(1)
    email, password = sys.argv[1], sys.argv[2]
    asyncio.run(run(email, password))


if __name__ == "__main__":
    main()
