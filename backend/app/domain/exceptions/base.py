class AppException(Exception):
    code: int = 400
    message: str = "Application error"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.__class__.message
        super().__init__(self.message)


# ── Auth ──────────────────────────────────────────────────────────────────────

class InvalidCredentialsError(AppException):
    code = 401
    message = "Неверный email или пароль"


class TokenExpiredError(AppException):
    code = 401
    message = "Срок действия токена истёк"


class NotAuthenticatedError(AppException):
    code = 401
    message = "Требуется авторизация"


class ForbiddenError(AppException):
    code = 403
    message = "Недостаточно прав"


# ── User ──────────────────────────────────────────────────────────────────────

class UserAlreadyExistsError(AppException):
    code = 409
    message = "Пользователь с таким email уже зарегистрирован"


class UserNotFoundError(AppException):
    code = 404
    message = "Пользователь не найден"


class UserInactiveError(AppException):
    code = 403
    message = "Аккаунт ожидает одобрения администратором"


class EmailNotVerifiedError(AppException):
    code = 403
    message = "Email не подтверждён — введите код из письма"


# ── Email verification ────────────────────────────────────────────────────────

class VerificationCodeInvalidError(AppException):
    code = 400
    message = "Код подтверждения неверный или истёк"


class VerificationCodeCooldownError(AppException):
    code = 429
    message = "Слишком частая отправка кода — подождите немного"


class EmailAlreadyVerifiedError(AppException):
    code = 409
    message = "Email уже подтверждён"
