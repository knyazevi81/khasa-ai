from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from app.domain.exceptions.base import AppException, ForbiddenError
from app.domain.interface.llm import AbstractLLMRouter
from app.domain.models.chat import Chat, Message, MessageStatus
from app.domain.models.llm import (
    LLMMessage,
    LLMRequest,
    MessageRole,
    StreamEvent,
    StreamEventType,
)
from app.application.use_cases.llm_credentials import LLMCredentialService
from app.infrastructure.database.uow import UnitOfWork

logger_chat = logging.getLogger(__name__)


class ChatNotFoundError(AppException):
    code = 404
    message = "Чат не найден"


class MessageNotFoundError(AppException):
    code = 404
    message = "Сообщение не найдено"


class NoCredentialError(AppException):
    code = 400
    message = "Не выбран LLM-ключ для этого чата"


class ChatService:
    """
    Главный use case вокруг графа. Покрывает:
      • CRUD чатов;
      • добавление user-сообщения как нового узла в граф;
      • генерацию assistant-сообщения как стрима, который параллельно
        накатывается в БД;
      • регенерацию — новый assistant-узел с тем же parent (= ветка);
      • переключение активного листа (current_message_id).
    """

    def __init__(
        self,
        uow: UnitOfWork,
        llm_credentials: LLMCredentialService,
        router: AbstractLLMRouter,
        artifacts: "ArtifactService | None" = None,
    ) -> None:
        self.uow = uow
        self.llm_credentials = llm_credentials
        self.router = router
        # Поздний импорт чтобы избежать циклической зависимости
        if artifacts is None:
            from app.application.use_cases.artifacts import ArtifactService
            artifacts = ArtifactService(uow)
        self.artifacts = artifacts

    # ── CRUD чатов ───────────────────────────────────────────────────────────

    async def list_chats(self, user_id: uuid.UUID) -> list[Chat]:
        return await self.uow.chats.find_for_user(user_id)

    async def create_chat(
        self,
        *,
        user_id: uuid.UUID,
        title: str = "Новый чат",
        credential_id: uuid.UUID | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
    ) -> Chat:
        chat_id = uuid.uuid4()
        await self.uow.chats.add(
            id=chat_id,
            user_id=user_id,
            title=title,
            current_message_id=None,
            credential_id=credential_id,
            model=model,
            system_prompt=system_prompt,
        )
        chat = await self.uow.chats.get_by_id(chat_id)
        assert chat is not None
        return chat

    async def get_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> Chat:
        chat = await self.uow.chats.get_for_user(chat_id, user_id)
        if not chat:
            raise ChatNotFoundError()
        return chat

    async def delete_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> None:
        chat = await self.uow.chats.get_for_user(chat_id, user_id)
        if not chat:
            raise ChatNotFoundError()
        await self.uow.chats.delete_for_user(chat_id, user_id)

    async def set_current_message(
        self, *, chat_id: uuid.UUID, user_id: uuid.UUID, message_id: uuid.UUID
    ) -> Chat:
        chat = await self.get_chat(chat_id, user_id)
        msg = await self.uow.messages.get_by_id(message_id)
        if not msg or msg.chat_id != chat_id:
            raise MessageNotFoundError()
        await self.uow.chats.set_current_message(chat_id, message_id)
        chat = await self.uow.chats.get_by_id(chat_id)
        assert chat is not None
        return chat

    # ── Граф ─────────────────────────────────────────────────────────────────

    async def get_messages(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> list[Message]:
        chat = await self.get_chat(chat_id, user_id)
        return await self.uow.messages.find_for_chat(chat.id)

    async def add_user_message(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str,
        parent_id: uuid.UUID | None,
    ) -> Message:
        """
        Добавляет user-узел в граф. Родитель — либо явный (при форке/реплае),
        либо текущий лист чата.

        Если у чата ещё стоит дефолтное название "Новый чат" — заодно
        автоматически проставляем заголовок из первых ~50 символов сообщения.
        Это убирает «новый чат» из истории и делает её читаемой.
        """
        chat = await self.get_chat(chat_id, user_id)

        effective_parent = parent_id or chat.current_message_id

        if effective_parent:
            parent = await self.uow.messages.get_by_id(effective_parent)
            if not parent or parent.chat_id != chat_id:
                raise MessageNotFoundError()

        msg_id = uuid.uuid4()
        await self.uow.messages.add(
            id=msg_id,
            chat_id=chat_id,
            parent_id=effective_parent,
            role=MessageRole.USER.value,
            content=content,
            status=MessageStatus.READY.value,
        )
        await self.uow.chats.set_current_message(chat_id, msg_id)

        # Автотайтлинг
        if chat.title in ("Новый чат", "New chat", ""):
            new_title = _make_title(content)
            if new_title and new_title != chat.title:
                await self.uow.chats.update_fields(chat_id, title=new_title)

        msg = await self.uow.messages.get_by_id(msg_id)
        assert msg is not None
        return msg

    async def prepare_assistant_message(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        parent_id: uuid.UUID,
        branch_label: str | None = None,
    ) -> Message:
        """
        Создаёт пустой assistant-узел в статусе PENDING и помечает его как
        текущий лист. Контент будет накатываться отдельным методом
        `stream_assistant_response`.
        """
        chat = await self.get_chat(chat_id, user_id)
        parent = await self.uow.messages.get_by_id(parent_id)
        if not parent or parent.chat_id != chat_id:
            raise MessageNotFoundError()

        if not chat.credential_id:
            raise NoCredentialError()

        msg_id = uuid.uuid4()
        await self.uow.messages.add(
            id=msg_id,
            chat_id=chat_id,
            parent_id=parent_id,
            role=MessageRole.ASSISTANT.value,
            content="",
            branch_label=branch_label,
            status=MessageStatus.PENDING.value,
            provider=None,
            model=chat.model,
        )
        await self.uow.chats.set_current_message(chat_id, msg_id)

        msg = await self.uow.messages.get_by_id(msg_id)
        assert msg is not None
        return msg

    async def stream_assistant_response(
        self,
        *,
        chat: Chat,
        assistant_msg_id: uuid.UUID,
    ) -> AsyncIterator[StreamEvent]:
        """
        Запускает стрим к LLM и параллельно:
          • накатывает чанки в БД;
          • перекидывает события наверх (для WebSocket).
        Если у чата включён agent_mode — сначала просим LLM вернуть план в
        виде JSON-списка подзадач, сохраняем их в БД, потом запускаем
        основной стрим. План тоже стримится как обычный текст (фронт его не
        отрисовывает — он отрисовывает таблицу подзадач из API).
        """
        assert chat.credential_id is not None
        credential = await self.llm_credentials.get_for_user(
            chat.credential_id, chat.user_id
        )

        # Соберём контекст: путь от корня к родителю assistant-узла
        assistant = await self.uow.messages.get_by_id(assistant_msg_id)
        if not assistant:
            raise MessageNotFoundError()
        assert assistant.parent_id is not None

        # path_to_root возвращает [root..parent], это и есть «история диалога»
        path = await self.uow.messages.get_path_to_root(assistant.parent_id)
        history: list[LLMMessage] = []
        for m in path:
            if m.role in ("user", "assistant"):
                history.append(LLMMessage(role=MessageRole(m.role), content=m.content))

        # Базовый system_prompt
        base_system = chat.system_prompt

        # ── Artifact directive ────────────────────────────────────────────────
        # Учим модель использовать специальный fenced-блок для долгих
        # документов/кода/схем. На фронте такие блоки рендерятся в боковой
        # панели как «артефакты» с историей версий.
        artifact_directive = (
            "\n\nКогда отвечаешь длинным самостоятельным документом (код, статья, "
            "конспект, диаграмма, JSON-схема), оформляй его как АРТЕФАКТ. "
            "Артефакт = специальный fenced-блок:\n\n"
            "```khasa-artifact:KIND:SLUG:TITLE[:LANG]\n"
            "содержимое\n"
            "```\n\n"
            "KIND — один из: markdown, code, html, svg, mermaid, json.\n"
            "SLUG — короткий стабильный идентификатор (a-z, 0-9, дефис), "
            "вроде project-plan. ВАЖНО: если в этом диалоге ты уже создавал "
            "артефакт с таким slug — переиспользуй его, тогда получится новая "
            "версия того же документа, а не отдельный.\n"
            "TITLE — человекочитаемое название.\n"
            "LANG — для KIND=code: python, typescript, rust, ...\n\n"
            "Внутри артефакта НЕ используй другие ```khasa-artifact:``` блоки. "
            "Краткие пояснения пиши обычным текстом ВНЕ блока."
        )
        base_system = (base_system or "") + artifact_directive

        # ── Agent mode: planner step ─────────────────────────────────────────
        # Дешёвый трюк: добавляем в system инструкцию выдать сначала JSON-план,
        # потом продолжать обычным ответом. Парсим план из начала первого
        # сообщения и сохраняем подзадачи. Если LLM не вернёт JSON — ничего
        # не упадёт, просто не будет подзадач.
        if chat.agent_mode:
            agent_directive = (
                "\n\nКогда отвечаешь — сначала в первых строках выдай JSON-блок "
                "вида:\n"
                "```json\n"
                '{"subtasks": ["шаг 1", "шаг 2", "шаг 3"]}\n'
                "```\n"
                "Это список того, что ты собираешься сделать. Затем выполняй "
                "задачу и пиши обычный ответ. Шагов 2-6, кратко."
            )
            base_system = (base_system or "") + agent_directive

        request = LLMRequest(
            model=chat.model or credential.default_model or "claude-haiku-4-5",
            messages=history,
            system=base_system,
            temperature=None,
            max_tokens=None,
        )

        adapter = self.router.get(credential.provider.value)

        # Помечаем сообщение как стрим
        await self.uow.messages.update_fields(
            assistant_msg_id,
            status=MessageStatus.STREAMING.value,
            provider=credential.provider.value,
            model=request.model,
        )
        # Коммитим состояние сразу, чтобы фронт по запросу увидел статус
        await self.uow.session.commit()

        buffer: list[str] = []
        FLUSH_EVERY = 32   # символов
        last_flush = 0
        usage_in = 0
        usage_out = 0
        error: str | None = None

        # Для agent_mode — будем накапливать первые N символов чтобы выловить
        # JSON-блок с планом и создать подзадачи в БД на лету.
        accumulated_for_plan: list[str] = []
        plan_parsed = not chat.agent_mode  # если не агент — сразу True

        # Для парсинга артефактов — храним весь накопленный текст и список
        # уже эмитнутых (artifact_id, version_id) пар, чтобы не слать дубль.
        full_text_parts: list[str] = []
        emitted_versions: set[uuid.UUID] = set()
        last_artifact_scan_len = 0
        ARTIFACT_SCAN_EVERY = 200  # символов

        try:
            async for event in adapter.stream(credential, request):
                if event.type == StreamEventType.DELTA and event.text:
                    buffer.append(event.text)
                    full_text_parts.append(event.text)
                    if not plan_parsed:
                        accumulated_for_plan.append(event.text)
                        plan_parsed = await self._try_parse_plan(
                            "".join(accumulated_for_plan),
                            assistant_msg_id=assistant_msg_id,
                        )
                    total_len = sum(len(b) for b in buffer)
                    if total_len - last_flush >= FLUSH_EVERY:
                        chunk = "".join(buffer)
                        await self.uow.messages.append_content(assistant_msg_id, chunk)
                        await self.uow.session.commit()
                        buffer.clear()
                        last_flush = 0
                    else:
                        last_flush = total_len

                    # Раз в ARTIFACT_SCAN_EVERY символов парсим артефакты
                    full_len = sum(len(p) for p in full_text_parts)
                    if full_len - last_artifact_scan_len >= ARTIFACT_SCAN_EVERY:
                        last_artifact_scan_len = full_len
                        async for ev in self._scan_artifacts(
                            chat_id=chat.id,
                            message_id=assistant_msg_id,
                            accumulated="".join(full_text_parts),
                            emitted=emitted_versions,
                        ):
                            yield ev

                    yield event

                elif event.type == StreamEventType.ERROR:
                    error = event.error
                    yield event

                elif event.type == StreamEventType.DONE:
                    if event.usage:
                        usage_in = event.usage.input_tokens
                        usage_out = event.usage.output_tokens
                    yield event

                elif event.type == StreamEventType.START:
                    yield event

        except asyncio.CancelledError:
            # Юзер закрыл WebSocket — сохраняем то, что успели собрать
            if buffer:
                await self.uow.messages.append_content(assistant_msg_id, "".join(buffer))
            await self.uow.messages.update_fields(
                assistant_msg_id,
                status=MessageStatus.FAILED.value,
                error="Connection cancelled by client",
            )
            await self.uow.session.commit()
            raise

        # Окончательно дописываем хвост и проставляем статус
        if buffer:
            await self.uow.messages.append_content(assistant_msg_id, "".join(buffer))
        await self.uow.messages.update_fields(
            assistant_msg_id,
            status=MessageStatus.FAILED.value if error else MessageStatus.READY.value,
            input_tokens=usage_in,
            output_tokens=usage_out,
            error=error,
        )
        await self.uow.session.commit()

        # Финальный артефакт-скан: вдруг последний блок закрылся прямо перед DONE
        if not error and full_text_parts:
            async for ev in self._scan_artifacts(
                chat_id=chat.id,
                message_id=assistant_msg_id,
                accumulated="".join(full_text_parts),
                emitted=emitted_versions,
            ):
                yield ev

    async def _scan_artifacts(
        self,
        *,
        chat_id: uuid.UUID,
        message_id: uuid.UUID,
        accumulated: str,
        emitted: set[uuid.UUID],
    ) -> AsyncIterator[StreamEvent]:
        """
        Парсит закрытые артефакт-блоки и эмитит StreamEvent.ARTIFACT для каждой
        НОВОЙ версии (которую мы ещё не эмитили в этом стриме).
        """
        try:
            changed = await self.artifacts.upsert_from_stream(
                chat_id=chat_id,
                message_id=message_id,
                accumulated_text=accumulated,
            )
        except Exception as exc:
            # Парсинг артефакта не должен ронять весь стрим
            logger_chat.warning("artifact upsert failed: %s", exc)
            return

        for art in changed:
            if art.current_version_id and art.current_version_id not in emitted:
                emitted.add(art.current_version_id)
                await self.uow.session.commit()
                yield StreamEvent(
                    type=StreamEventType.ARTIFACT,
                    raw={
                        "artifact_id": str(art.id),
                        "version_id": str(art.current_version_id),
                        "slug": art.slug,
                        "kind": art.kind,
                        "title": art.title,
                        "language": art.language,
                    },
                )

    async def regenerate(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        from_assistant_message_id: uuid.UUID,
        branch_label: str | None = None,
    ) -> Message:
        """
        Создаёт новый assistant-узел с тем же parent, что у указанного —
        это и есть «альтернативная ветка ответа».
        """
        chat = await self.get_chat(chat_id, user_id)
        target = await self.uow.messages.get_by_id(from_assistant_message_id)
        if not target or target.chat_id != chat_id or target.role != "assistant":
            raise MessageNotFoundError()
        if target.parent_id is None:
            raise MessageNotFoundError("Целевое сообщение без родителя")

        return await self.prepare_assistant_message(
            chat_id=chat_id,
            user_id=user_id,
            parent_id=target.parent_id,
            branch_label=branch_label,
        )

    async def _try_parse_plan(
        self,
        accumulated: str,
        *,
        assistant_msg_id: uuid.UUID,
    ) -> bool:
        """
        Пытается выудить JSON-план из начала ответа агента.
        Возвращает True если план распарсен (или явно не будет найден),
        False — если стоит подождать ещё чанков.
        """
        # Ничего не пришло — ждём
        if len(accumulated) < 20:
            return False

        import json
        import re

        # Ищем JSON-блок в ```json ... ``` или просто {"subtasks": [...]}
        block_match = re.search(r"```json\s*(\{.+?\})\s*```", accumulated, re.DOTALL)
        if not block_match:
            # Не дождались закрывающего ```. Если уже накопилось много текста
            # без даже открывающего ``` — план просто пропустили.
            if len(accumulated) > 1500 and "```" not in accumulated:
                return True  # отказываемся ждать
            # Может, без блока — попробуем найти inline
            inline = re.search(r'(\{\s*"subtasks"\s*:\s*\[.+?\]\s*\})', accumulated, re.DOTALL)
            if not inline:
                return False
            block_match = inline

        try:
            data = json.loads(block_match.group(1))
        except json.JSONDecodeError:
            return False

        subtasks = data.get("subtasks") or []
        if not isinstance(subtasks, list):
            return True

        # Создаём подзадачи в БД
        for i, title in enumerate(subtasks):
            if not isinstance(title, str):
                continue
            await self.uow.agent_subtasks.add(
                id=uuid.uuid4(),
                message_id=assistant_msg_id,
                order_index=i,
                title=title.strip()[:200],
                status="pending",
            )
        await self.uow.session.commit()
        return True

    async def fork_from_message(
        self,
        *,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        from_message_id: uuid.UUID,
        new_content: str,
        branch_label: str | None = None,
    ) -> Message:
        """
        Edit-and-fork: создаёт новый user-узел с тем же parent_id, что у
        редактируемого сообщения. Это базовая операция для:
          • редактирования своего сообщения (создаём ветку с другим текстом);
          • форка от любого узла (юзер выбирает узел в графе и шлёт оттуда
            новый запрос).

        Сам редактируемый узел не меняется — мы лишь добавляем рядом с ним
        новую ветку. Активный лист (`current_message_id`) переходит на новый
        user-узел; следом за ним обычно идёт `prepare_assistant_message`.
        """
        chat = await self.get_chat(chat_id, user_id)
        target = await self.uow.messages.get_by_id(from_message_id)
        if not target or target.chat_id != chat_id:
            raise MessageNotFoundError()

        # parent нового узла = parent редактируемого. Если редактируем root —
        # parent_id будет None, и это всё ещё валидно (новый «корень» ветки).
        new_id = uuid.uuid4()
        await self.uow.messages.add(
            id=new_id,
            chat_id=chat_id,
            parent_id=target.parent_id,
            role=MessageRole.USER.value,
            content=new_content,
            branch_label=branch_label,
            status=MessageStatus.READY.value,
        )
        await self.uow.chats.set_current_message(chat_id, new_id)

        # Автотайтлинг (если чат всё ещё «Новый чат»)
        if chat.title in ("Новый чат", "New chat", ""):
            new_title = _make_title(new_content)
            if new_title and new_title != chat.title:
                await self.uow.chats.update_fields(chat_id, title=new_title)

        msg = await self.uow.messages.get_by_id(new_id)
        assert msg is not None
        return msg


def _make_title(content: str) -> str:
    """
    Подрезает первое сообщение юзера до короткого заголовка для истории чатов.
    Убирает блоки кода и аттачменты, чтобы они не лезли в название.
    """
    import re
    cleaned = re.sub(r"```[\s\S]*?```", " ", content)
    cleaned = re.sub(r"^📎.*$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    if len(cleaned) > 50:
        return cleaned[:48].rstrip() + "…"
    return cleaned
