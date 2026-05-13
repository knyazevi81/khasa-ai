from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.uow import AbstractUnitOfWork
from app.infrastructure.database.engine import async_session_maker
from app.infrastructure.database.repositories.chat_extras import (
    SQLAgentSubtaskRepository,
    SQLAttachmentRepository,
)
from app.infrastructure.database.repositories.chats import SQLChatRepository
from app.infrastructure.database.repositories.llm_credentials import (
    SQLLLMCredentialRepository,
)
from app.infrastructure.database.repositories.messages import SQLMessageRepository
from app.infrastructure.database.repositories.users import SQLUserRepository
from app.infrastructure.database.repositories.verification_codes import (
    SQLVerificationCodeRepository,
)


class UnitOfWork(AbstractUnitOfWork):
    """
    Один UoW на запрос. Открывает репозитории, commit-ит на удачном выходе,
    rollback-ит на исключении.
    """

    users: SQLUserRepository
    verification_codes: SQLVerificationCodeRepository
    llm_credentials: SQLLLMCredentialRepository
    chats: SQLChatRepository
    messages: SQLMessageRepository
    attachments: SQLAttachmentRepository
    agent_subtasks: SQLAgentSubtaskRepository

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> "UnitOfWork":
        self.users = SQLUserRepository(self.session)
        self.verification_codes = SQLVerificationCodeRepository(self.session)
        self.llm_credentials = SQLLLMCredentialRepository(self.session)
        self.chats = SQLChatRepository(self.session)
        self.messages = SQLMessageRepository(self.session)
        self.attachments = SQLAttachmentRepository(self.session)
        self.agent_subtasks = SQLAgentSubtaskRepository(self.session)
        return self

    async def __aexit__(self, exc_type, *args) -> None:
        if exc_type:
            await self.rollback()
        else:
            await self.commit()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


class UnitOfWorkFactory:
    """Контекст-менеджер, который сам создаёт сессию (для скриптов / фоновых задач)."""

    async def __aenter__(self) -> UnitOfWork:
        self._session_ctx = async_session_maker()
        session = await self._session_ctx.__aenter__()
        self._uow = UnitOfWork(session)
        return await self._uow.__aenter__()

    async def __aexit__(self, *args) -> None:
        await self._uow.__aexit__(*args)
        await self._session_ctx.__aexit__(*args)
