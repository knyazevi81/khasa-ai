from pwdlib import PasswordHash


class BcryptPasswordHasher:
    """
    Адаптер для pwdlib. Использует `PasswordHash.recommended()` — это
    argon2id (primary) с возможностью верификации старых bcrypt-хэшей
    (backward-compatible если кто-то заводил юзеров на предыдущей версии).

    Имя класса оставлено для совместимости с импортами в коде.
    """

    def __init__(self) -> None:
        self._ph = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        return self._ph.hash(password)

    def verify(self, password: str, hashed: str | None) -> bool:
        if not hashed:
            return False
        try:
            return self._ph.verify(password, hashed)
        except Exception:
            return False
