from abc import ABC, abstractmethod


class AbstractEmailService(ABC):
    """
    Порт для отправки писем. Все шаблоны живут в инфраструктурном адаптере —
    домену не нужно знать ни HTML, ни SMTP-детали, только сигнатуры сценариев.
    """

    @abstractmethod
    async def send_verification_code(self, to: str, code: str, ttl_minutes: int) -> None: ...

    @abstractmethod
    async def send_registration_pending_approval(self, to: str) -> None: ...

    @abstractmethod
    async def send_account_activated(self, to: str) -> None: ...

    @abstractmethod
    async def send_password_changed(self, to: str) -> None: ...

    @abstractmethod
    async def send_custom(self, to: str | list[str], subject: str, message: str) -> None: ...
