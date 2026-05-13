from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.base import Repository

ORMModel = TypeVar("ORMModel")


class ModelBaseRepository(Repository, Generic[ORMModel]):
    """Базовый репозиторий — держит session и ORM-класс."""

    def __init__(self, session: AsyncSession, model: type[ORMModel]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, model_id):
        raise NotImplementedError

    async def find_one_or_none(self, **filter_by):
        raise NotImplementedError

    async def find_all(self, **filter_by):
        raise NotImplementedError

    async def add(self, **data) -> None:
        raise NotImplementedError
