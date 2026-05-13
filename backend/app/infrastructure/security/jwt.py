from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.domain.exceptions.base import InvalidCredentialsError
from app.domain.interface.token import AbstractTokenService
from app.domain.models.models import TokenPair, TokenPayload, TokenType
from app.infrastructure.config.config import Settings


class JoseTokenService(AbstractTokenService):
    """python-jose реализация AbstractTokenService."""

    def __init__(self, settings: Settings) -> None:
        self._secret = settings.JWT_SECRET_KEY.get_secret_value()
        self._algorithm = settings.JWT_ALGORITHM
        self._access_ttl = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        self._refresh_ttl = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    def create_pair(self, user_id: str) -> TokenPair:
        return TokenPair(
            access_token=self._encode(user_id, TokenType.ACCESS, self._access_ttl),
            refresh_token=self._encode(user_id, TokenType.REFRESH, self._refresh_ttl),
        )

    def decode_access(self, token: str) -> TokenPayload:
        return self._decode(token, expected_type=TokenType.ACCESS)

    def decode_refresh(self, token: str) -> TokenPayload:
        return self._decode(token, expected_type=TokenType.REFRESH)

    # ── private ──────────────────────────────────────────────────────────────

    def _encode(self, user_id: str, token_type: TokenType, ttl: timedelta) -> str:
        expire = datetime.now(timezone.utc) + ttl
        payload = {"sub": user_id, "type": token_type.value, "exp": expire}
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def _decode(self, token: str, expected_type: TokenType) -> TokenPayload:
        try:
            raw = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError as exc:
            raise InvalidCredentialsError() from exc

        payload = TokenPayload(
            sub=raw["sub"],
            type=TokenType(raw["type"]),
            exp=raw["exp"],
        )
        if payload.type != expected_type:
            raise InvalidCredentialsError()
        return payload
