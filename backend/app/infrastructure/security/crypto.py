from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.domain.exceptions.base import AppException


class SecretDecryptError(AppException):
    code = 500
    message = "Не удалось расшифровать секрет"


class SecretCipher:
    """
    Симметричное шифрование секретов на основе ключа из .env.

    Ключ из конфига берётся как произвольная строка любой длины — мы её
    хэшируем (SHA-256) и кодируем base64-urlsafe, чтобы получить валидный
    Fernet-ключ. Это даёт детерминированный 32-байтный ключ без требования
    задавать его в base64 в .env.

    Производительность нерелевантна — секрет шифруется/расшифровывается
    максимум раз в запросе. Криптостойкость задана Fernet (AES-128-CBC + HMAC).
    """

    def __init__(self, master_key: str) -> None:
        if not master_key:
            raise ValueError("SECRET_CIPHER_KEY must be set")
        digest = hashlib.sha256(master_key.encode("utf-8")).digest()
        fernet_key = base64.urlsafe_b64encode(digest)
        self._fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise SecretDecryptError() from exc
