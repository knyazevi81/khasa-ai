from abc import ABC, abstractmethod
from typing import Generic, TypeVar

Model = TypeVar("Model")


class Repository(ABC, Generic[Model]):
    @abstractmethod
    async def get_by_id(self, model_id) -> Model | None:
        ...

    @abstractmethod
    async def find_one_or_none(self, **filter_by) -> Model | None:
        ...

    @abstractmethod
    async def find_all(self, **filter_by) -> list[Model]:
        ...

    @abstractmethod
    async def add(self, **data) -> None:
        ...
