from pwdlib import PasswordHash


class BcryptPasswordHasher:
    """
    Адаптер для pwdlib (bcrypt). Параметры подобраны для разумного времени
    хэширования (~250мс на современном CPU) без CPU-голодания event loop.
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
