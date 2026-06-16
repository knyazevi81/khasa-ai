from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import update as sa_update

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
from app.infrastructure.database.orm.models import (
    MessageTextSegments as MessageTextSegmentsORM,
)
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
        sandbox_service=None,
        mcp_service=None,
        skill_registry=None,
    ) -> None:
        self.uow = uow
        self.llm_credentials = llm_credentials
        self.router = router
        # Поздние импорты чтобы избежать циклических зависимостей
        if artifacts is None:
            from app.application.use_cases.artifacts import ArtifactService
            artifacts = ArtifactService(uow)
        self.artifacts = artifacts
        self.sandbox_service = sandbox_service
        self.mcp_service = mcp_service
        self.skill_registry = skill_registry

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
        """Жёсткое удаление — каскадом снесёт сообщения, артефакты, sandbox."""
        chat = await self.uow.chats.get_for_user(chat_id, user_id)
        if not chat:
            raise ChatNotFoundError()
        await self.uow.chats.delete_for_user(chat_id, user_id)

    async def hide_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> Chat:
        """Soft-hide: чат не показывается в истории, но не удаляется."""
        chat = await self.uow.chats.get_for_user(chat_id, user_id)
        if not chat:
            raise ChatNotFoundError()
        await self.uow.chats.update_fields(chat_id, is_hidden=True)
        return await self.get_chat(chat_id, user_id)

    async def unhide_chat(self, chat_id: uuid.UUID, user_id: uuid.UUID) -> Chat:
        chat = await self.uow.chats.get_for_user(chat_id, user_id)
        if not chat:
            raise ChatNotFoundError()
        await self.uow.chats.update_fields(chat_id, is_hidden=False)
        return await self.get_chat(chat_id, user_id)

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

    # Максимум итераций tool-use, чтобы агент не залип
    AGENT_MAX_TURNS = 8

    async def stream_assistant_response(
        self,
        *,
        chat: Chat,
        assistant_msg_id: uuid.UUID,
    ) -> AsyncIterator[StreamEvent]:
        """
        Главный метод стриминга. В обычном режиме — один LLM-вызов.
        В agent_mode — цикл tool-use: пока модель просит инструменты, мы их
        исполняем и возвращаем результат, до AGENT_MAX_TURNS итераций.
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

        path = await self.uow.messages.get_path_to_root(assistant.parent_id)
        history: list[LLMMessage] = []
        for m in path:
            if m.role in ("user", "assistant"):
                history.append(LLMMessage(role=MessageRole(m.role), content=m.content))

        # System prompt
        base_system = self._build_system_prompt(chat)

        # Tools (только в agent_mode + если есть sandbox/skills)
        tools = None
        if chat.agent_mode and self.skill_registry is not None:
            tool_defs = list(self.skill_registry.definitions())
            # Добавим MCP-tools юзера
            if self.mcp_service is not None:
                try:
                    mcp_bundles = await self.mcp_service.collect_tools_for_user(
                        chat.user_id
                    )
                    for server, mcp_tools in mcp_bundles:
                        for t in mcp_tools:
                            # Префиксируем имя: mcp__SERVERID__TOOL чтобы при
                            # tool_use мы знали с какого сервера дёрнуть
                            tool_defs.append(
                                _mcp_tool_def(server, t)
                            )
                except Exception as exc:
                    logger_chat.warning("mcp collect failed: %s", exc)

            tools = tool_defs

            # Заранее поднимаем sandbox чтобы tools работали
            if self.sandbox_service is not None:
                try:
                    await self.sandbox_service.get_or_create_for_chat(
                        chat.id, chat.user_id
                    )
                except Exception as exc:
                    logger_chat.warning("sandbox start failed: %s", exc)

        # Помечаем сообщение как стрим
        request_model = chat.model or credential.default_model or "claude-haiku-4-5"
        await self.uow.messages.update_fields(
            assistant_msg_id,
            status=MessageStatus.STREAMING.value,
            provider=credential.provider.value,
            model=request_model,
        )
        await self.uow.session.commit()

        adapter = self.router.get(credential.provider.value)
        max_turns = self.AGENT_MAX_TURNS if (chat.agent_mode and tools) else 1
        emitted_versions: set[uuid.UUID] = set()
        cumulative_usage_in = 0
        cumulative_usage_out = 0
        error: str | None = None
        # Если на ПОСЛЕДНЕЙ итерации модель всё ещё запросила tool_use, значит
        # она не закончила задачу — мы упёрлись в AGENT_MAX_TURNS. Юзеру
        # покажем кнопку «продолжить».
        hit_tool_use_limit = False

        # Глобальный счётчик order_idx — общий для text_segments и tool_calls.
        # При рендере фронт мержит их и сортирует по этому полю.
        # Передаём как dict чтобы _stream_single_pass мог мутировать (общий
        # state — text сегмент закрывается на каждом tool_use внутри турна).
        next_order_state = {"next": 0}

        try:
            for turn in range(max_turns):
                # Перед каждым LLM-вызовом создаём пустой text-сегмент.
                # Если в этом турне модель вызовет tools — _stream_single_pass
                # сама закроет этот сегмент и откроет новый после каждого tool_use.
                current_segment_id: uuid.UUID | None = None
                current_segment_order: int = 0
                if chat.agent_mode and tools:
                    current_segment_id = uuid.uuid4()
                    current_segment_order = next_order_state["next"]
                    next_order_state["next"] = current_segment_order + 1
                    await self.uow.text_segments.add(
                        id=current_segment_id,
                        message_id=assistant_msg_id,
                        order_idx=current_segment_order,
                        content="",
                    )
                    await self.uow.session.commit()

                result = await self._stream_single_pass(
                    adapter=adapter,
                    credential=credential,
                    request=LLMRequest(
                        model=request_model,
                        messages=history,
                        system=base_system,
                        tools=tools,
                    ),
                    chat=chat,
                    assistant_msg_id=assistant_msg_id,
                    emitted_versions=emitted_versions,
                    is_first_turn=(turn == 0),
                    segment_id=current_segment_id,
                    segment_order=current_segment_order,
                    next_order_state=next_order_state,
                )
                async for ev in result["events"]():
                    yield ev

                cumulative_usage_in += result["usage_in"]
                cumulative_usage_out += result["usage_out"]
                if result["error"]:
                    error = result["error"]
                    break

                if not result["tool_uses"]:
                    # Модель закончила без tool-use → выход
                    break

                # Есть tool_use'ы: добавляем в историю assistant-блок с этим
                # tool_use, исполняем, добавляем user-tool_result, продолжаем.
                assistant_blocks: list[dict] = []
                if result["text"]:
                    assistant_blocks.append({"type": "text", "text": result["text"]})
                for tu in result["tool_uses"]:
                    assistant_blocks.append({
                        "type": "tool_use",
                        "id": tu["id"],
                        "name": tu["name"],
                        "input": tu["input"],
                    })
                history.append(LLMMessage(
                    role=MessageRole.ASSISTANT, content=assistant_blocks
                ))

                # Исполняем все tool_uses (последовательно — большинству агентов
                # этого хватает, и проще логи разбирать)
                tool_results: list[dict] = []

                for tu in result["tool_uses"]:
                    # Создаём запись в БД с правильным order_idx.
                    # __order_idx__ был назначен в _stream_single_pass когда
                    # пришёл TOOL_USE event — он отражает реальный порядок
                    # появления tool_use'а среди других сегментов.
                    db_call_id = uuid.uuid4()
                    tool_order = tu.get("__order_idx__", next_order_state["next"])
                    if "__order_idx__" not in tu:
                        next_order_state["next"] = tool_order + 1
                    await self.uow.tool_calls.add(
                        id=db_call_id,
                        message_id=assistant_msg_id,
                        order_idx=tool_order,
                        tool_use_id=tu["id"],
                        name=tu["name"],
                        input=tu["input"] or {},
                        output=None,
                        status="running",
                        is_present_files=False,
                    )
                    await self.uow.session.commit()

                    yield StreamEvent(
                        type=StreamEventType.TOOL_USE,
                        raw={
                            "id": tu["id"],
                            "name": tu["name"],
                            "input": tu["input"],
                            "status": "running",
                            "order_idx": tool_order,
                        },
                    )
                    tool_output = await self._execute_tool(
                        chat=chat, tool_use=tu
                    )
                    is_present_files = tool_output.startswith("__KHASA_PRESENT_FILES__")

                    # Обновим запись результатом
                    await self.uow.tool_calls.update_fields(
                        db_call_id,
                        output=tool_output,
                        status="done",
                        is_present_files=is_present_files,
                    )
                    await self.uow.session.commit()

                    yield StreamEvent(
                        type=StreamEventType.TOOL_RESULT,
                        raw={
                            "id": tu["id"],
                            "name": tu["name"],
                            "output": tool_output,
                            "is_present_files": is_present_files,
                            "order_idx": tool_order,
                        },
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tu["id"],
                        "content": tool_output,
                    })

                # tool_result'ы прикладываем как user-message
                history.append(LLMMessage(role=MessageRole.USER, content=tool_results))

                # Маленький визуальный разделитель в основном сообщении
                await self.uow.messages.append_content(
                    assistant_msg_id, "\n\n"
                )
                await self.uow.session.commit()

                # Если это была последняя итерация — модель ещё не закончила
                if turn == max_turns - 1:
                    hit_tool_use_limit = True

        except asyncio.CancelledError:
            await self.uow.messages.update_fields(
                assistant_msg_id,
                status=MessageStatus.FAILED.value,
                error="Connection cancelled by client",
            )
            await self.uow.session.commit()
            raise

        # Финал
        await self.uow.messages.update_fields(
            assistant_msg_id,
            status=MessageStatus.FAILED.value if error else MessageStatus.READY.value,
            input_tokens=cumulative_usage_in,
            output_tokens=cumulative_usage_out,
            error=error,
        )
        await self.uow.session.commit()

        # Эмитим спец-событие truncated → фронт покажет кнопку «продолжить»
        if hit_tool_use_limit and not error:
            yield StreamEvent(
                type=StreamEventType.TRUNCATED,
                raw={
                    "reason": "tool_use_limit",
                    "max_turns": max_turns,
                    "message_id": str(assistant_msg_id),
                },
            )

    # ── одна LLM-итерация ────────────────────────────────────────────────────

    async def _stream_single_pass(
        self,
        *,
        adapter,
        credential,
        request: LLMRequest,
        chat: Chat,
        assistant_msg_id: uuid.UUID,
        emitted_versions: set[uuid.UUID],
        is_first_turn: bool,
        segment_id: uuid.UUID | None = None,
        segment_order: int = 0,
        next_order_state: dict | None = None,
    ) -> dict:
        """
        Один LLM-вызов. Возвращает dict с:
          • events() — async-генератор для прокидывания вверх
          • text — собранный текстовый ответ
          • tool_uses — список запрошенных инструментов
          • usage_in/usage_out
          • error
        """
        buffer: list[str] = []
        FLUSH_EVERY = 32
        last_flush = 0
        usage_in = 0
        usage_out = 0
        error: str | None = None

        accumulated_for_plan: list[str] = []
        plan_parsed = not (chat.agent_mode and is_first_turn)

        full_text_parts: list[str] = []
        last_artifact_scan_len = 0
        ARTIFACT_SCAN_EVERY = 200

        tool_uses: list[dict] = []
        events_queue: list[StreamEvent] = []

        async for event in adapter.stream(credential, request):
            if event.type == StreamEventType.DELTA and event.text:
                buffer.append(event.text)
                full_text_parts.append(event.text)
                if not plan_parsed:
                    accumulated_for_plan.append(event.text)
                    plan_parsed, plan_span = await self._try_parse_plan(
                        "".join(accumulated_for_plan),
                        assistant_msg_id=assistant_msg_id,
                    )
                    # Если план распарсен и есть span — вырезаем JSON-блок
                    # из видимого сегмента (мы записали его в БД до парсинга,
                    # теперь чистим UPDATE'ом).
                    if plan_parsed and plan_span and segment_id is not None:
                        plan_text = "".join(accumulated_for_plan)
                        before = plan_text[: plan_span[0]].rstrip()
                        after = plan_text[plan_span[1]:].lstrip()
                        cleaned = (before + ("\n\n" if before and after else "") + after).strip()
                        await self.uow.session.execute(
                            sa_update(MessageTextSegmentsORM)
                            .where(MessageTextSegmentsORM.id == segment_id)
                            .values(content=cleaned)
                        )
                        await self.uow.session.commit()
                        buffer.clear()
                        last_flush = 0
                        full_text_parts = [cleaned]
                        # Шлём фронту replace-event чтобы он переписал
                        # содержимое сегмента целиком (вместо append).
                        events_queue.append(StreamEvent(
                            type=StreamEventType.DELTA,
                            text="",
                            raw={
                                "segment_id": str(segment_id),
                                "order_idx": segment_order,
                                "replace": True,
                                "content": cleaned,
                            },
                        ))
                total_len = sum(len(b) for b in buffer)
                if total_len - last_flush >= FLUSH_EVERY:
                    chunk = "".join(buffer)
                    # Пишем в активный text-сегмент. Если сегмента нет —
                    # значит это не агент-режим, юзаем старый messages.content.
                    if segment_id is not None:
                        await self.uow.text_segments.append_content(
                            segment_id, chunk
                        )
                    else:
                        await self.uow.messages.append_content(
                            assistant_msg_id, chunk
                        )
                    await self.uow.session.commit()
                    buffer.clear()
                    last_flush = 0
                else:
                    last_flush = total_len

                full_len = sum(len(p) for p in full_text_parts)
                if full_len - last_artifact_scan_len >= ARTIFACT_SCAN_EVERY:
                    last_artifact_scan_len = full_len
                    async for ev in self._scan_artifacts(
                        chat_id=chat.id,
                        message_id=assistant_msg_id,
                        accumulated="".join(full_text_parts),
                        emitted=emitted_versions,
                    ):
                        events_queue.append(ev)

                # Прокидываем DELTA с информацией о сегменте — фронт по
                # segment_id + order_idx понимает куда дописывать.
                event_with_meta = StreamEvent(
                    type=event.type,
                    text=event.text,
                    raw={
                        "segment_id": str(segment_id) if segment_id else None,
                        "order_idx": segment_order,
                    },
                )
                events_queue.append(event_with_meta)

            elif event.type == StreamEventType.TOOL_USE:
                # Адаптер собрал tool_use полностью. Делаем разбиение сегмента:
                #   1. Допишем хвост буфера в текущий text-сегмент
                #   2. Создаём tool_call в БД с next_order
                #   3. Создаём НОВЫЙ text-сегмент для следующего текста (если будет)
                #   4. Эмитим tool_use событие с order_idx
                #
                # Это даёт настоящий interleaved-рендер: даже если модель в
                # одном LLM-ответе кладёт text → tool → tool → text → tool,
                # каждый блок получает свой order_idx по порядку появления.
                if buffer and segment_id is not None:
                    await self.uow.text_segments.append_content(
                        segment_id, "".join(buffer)
                    )
                    buffer.clear()
                    last_flush = 0
                if event.raw:
                    tool_uses.append(event.raw)
                    # Запишем tool_call в БД немедленно, до его исполнения,
                    # с правильным order_idx (между предыдущим текстом и
                    # следующим). next_order_state — общий счётчик из outer.
                    if next_order_state is not None and chat.agent_mode:
                        tool_order = next_order_state["next"]
                        next_order_state["next"] = tool_order + 1
                        event.raw["__order_idx__"] = tool_order

                        # Создаём новый text-сегмент для следующего текста.
                        # Если потом не будет текста — сегмент останется пустым
                        # и фронт его не отрисует.
                        new_seg_id = uuid.uuid4()
                        new_seg_order = next_order_state["next"]
                        next_order_state["next"] = new_seg_order + 1
                        await self.uow.text_segments.add(
                            id=new_seg_id,
                            message_id=assistant_msg_id,
                            order_idx=new_seg_order,
                            content="",
                        )
                        await self.uow.session.commit()
                        # Переключаем активный сегмент. Это работает потому что
                        # segment_id — локальная переменная функции, можно её
                        # переопределить для последующих DELTA внутри этого
                        # же turn'а.
                        segment_id = new_seg_id
                        segment_order = new_seg_order
                events_queue.append(event)

            elif event.type == StreamEventType.ERROR:
                error = event.error
                events_queue.append(event)

            elif event.type == StreamEventType.DONE:
                if event.usage:
                    usage_in = event.usage.input_tokens
                    usage_out = event.usage.output_tokens
                events_queue.append(event)

            elif event.type == StreamEventType.START:
                # START для UI неинтересен между турами — отправим только в 1-м
                if is_first_turn:
                    events_queue.append(event)

        # Доp- хвост буфера
        if buffer:
            if segment_id is not None:
                await self.uow.text_segments.append_content(
                    segment_id, "".join(buffer)
                )
            else:
                await self.uow.messages.append_content(
                    assistant_msg_id, "".join(buffer)
                )
            await self.uow.session.commit()

        # Финальный артефакт-скан
        if not error and full_text_parts:
            async for ev in self._scan_artifacts(
                chat_id=chat.id,
                message_id=assistant_msg_id,
                accumulated="".join(full_text_parts),
                emitted=emitted_versions,
            ):
                events_queue.append(ev)

        text_only = "".join(full_text_parts)

        async def replay():
            for e in events_queue:
                yield e

        return {
            "events": replay,
            "text": text_only,
            "tool_uses": tool_uses,
            "usage_in": usage_in,
            "usage_out": usage_out,
            "error": error,
        }

    # ── system prompt ────────────────────────────────────────────────────────

    def _build_system_prompt(self, chat: Chat) -> str:
        base = chat.system_prompt or ""

        artifact_directive = (
            "\n\nКогда отвечаешь длинным самостоятельным документом (код, статья, "
            "конспект, диаграмма, JSON-схема), оформляй его как АРТЕФАКТ. "
            "Артефакт = специальный fenced-блок:\n\n"
            "```khasa-artifact:KIND:SLUG:TITLE[:LANG]\n"
            "содержимое\n"
            "```\n\n"
            "KIND — один из: markdown, code, html, svg, mermaid, json.\n"
            "SLUG — короткий стабильный идентификатор (a-z, 0-9, дефис).\n"
            "Если в этом диалоге уже создавал артефакт с таким slug — "
            "переиспользуй его (получится новая версия).\n"
            "Внутри артефакта НЕ используй другие ```khasa-artifact:``` блоки. "
            "Краткие пояснения пиши обычным текстом ВНЕ блока."
        )
        base = base + artifact_directive

        if chat.agent_mode:
            agent_directive = (
                "\n\nУ тебя АГЕНТНЫЙ РЕЖИМ. Тебе доступен изолированный Linux-"
                "контейнер (рабочая директория /workspace) и набор инструментов:\n"
                "  • bash(command) — выполнить shell-команду\n"
                "  • read_file(path) / write_file(path, content) / edit_file\n"
                "  • list_directory(path)\n"
                "  • web_search(query) / web_fetch(url)\n"
                "  • present_files(paths, caption) — отдать готовые файлы юзеру\n"
                "  • (могут быть дополнительные tools от MCP-серверов юзера)\n\n"
                "Контейнер изолирован, ничего на хосте не сломаешь — пробуй "
                "вещи свободно. Внутри есть python3 (с requests, pandas, "
                "numpy, matplotlib, pillow), node/npm, git, curl, jq.\n\n"
                "ВАЖНЫЕ ПРАВИЛА ДЛЯ present_files:\n"
                "1. Вызывай его ОДИН РАЗ в конце задачи, со всеми финальными файлами.\n"
                "   НЕ дублируй вызовы — юзер увидит несколько пустых блоков.\n"
                "2. Пути ОТНОСИТЕЛЬНО /workspace, БЕЗ ведущего /. Например:\n"
                "   правильно: \"my-app/main.py\", \"build/app.zip\"\n"
                "   НЕправильно: \"/workspace/my-app/main.py\"\n"
                "3. Не создавай отдельную папку output/ — пользователь и так "
                "качает каждый файл по ссылке. Достаточно одного итогового zip.\n"
                "4. Если юзер просит «архив» — соберирай zip в /workspace и "
                "верни ОДИН путь к этому zip. Не нужно копировать его дважды.\n\n"
                "Когда сделал работу — собери результат в файлы в /workspace "
                "и вызови present_files(paths=[...]), чтобы юзер мог скачать. "
                "Не вставляй большие выводы команд в текст ответа — лучше "
                "сохрани в файл и сошлись на него.\n\n"
                "В НАЧАЛЕ ответа выдай JSON-план в блоке:\n"
                "```json\n"
                '{"subtasks": ["шаг 1", "шаг 2", "шаг 3"]}\n'
                "```\n"
                "Затем последовательно выполняй шаги через tools."
            )
            base = base + agent_directive

        return base

    # ── tool execution ───────────────────────────────────────────────────────

    async def _execute_tool(self, *, chat: Chat, tool_use: dict) -> str:
        """Резолвит вызов tool — либо встроенный skill, либо MCP."""
        name = tool_use.get("name") or ""
        args = tool_use.get("input") or {}

        # MCP-tools имеют префикс mcp__<server_id>__<tool_name>
        if name.startswith("mcp__") and self.mcp_service is not None:
            try:
                parts = name.split("__", 2)
                if len(parts) != 3:
                    return "ERROR: invalid MCP tool name"
                server_id_str = parts[1]
                real_name = parts[2]
                from sqlalchemy import select
                from app.infrastructure.database.orm.models import MCPServers
                result = await self.uow.session.execute(
                    select(MCPServers).filter_by(id=uuid.UUID(server_id_str))
                )
                server = result.scalar_one_or_none()
                if not server:
                    return f"ERROR: MCP server {server_id_str} not found"
                return await self.mcp_service.call_tool(
                    server=server, tool_name=real_name, arguments=args
                )
            except Exception as exc:
                return f"ERROR: MCP call failed: {exc}"

        # Встроенный skill
        if self.skill_registry is None or self.sandbox_service is None:
            return "ERROR: skills/sandbox not available on this backend"

        skill = self.skill_registry.get(name)
        if skill is None:
            return f"ERROR: unknown tool {name}"

        # Готовим контекст
        try:
            sandbox = await self.sandbox_service.get_or_create_for_chat(
                chat.id, chat.user_id
            )
            assert sandbox.container_id is not None
            from app.infrastructure.skills.base import SkillContext
            ctx = SkillContext(
                chat_id=chat.id,
                user_id=chat.user_id,
                container_id=sandbox.container_id,
                sandbox=self.sandbox_service.manager,
            )
            return await skill.execute(args, ctx)
        except Exception as exc:
            logger_chat.exception("tool execution failed")
            return f"ERROR: {type(exc).__name__}: {exc}"

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
    ) -> tuple[bool, tuple[int, int] | None]:
        """
        Пытается выудить JSON-план из начала ответа агента.
        Возвращает (parsed, span):
          parsed — True если стоит прекратить попытки парсинга (план найден
                   или явно не будет найден);
          span   — (start, end) позиций JSON-блока в accumulated, если он
                   был распарсен. Вызывающий может вырезать этот фрагмент
                   из видимого текста сегмента.
        """
        # Ничего не пришло — ждём
        if len(accumulated) < 20:
            return False, None

        import json
        import re

        # Ищем JSON-блок в ```json ... ``` или просто {"subtasks": [...]}
        block_match = re.search(r"```json\s*(\{.+?\})\s*```", accumulated, re.DOTALL)
        if not block_match:
            if len(accumulated) > 1500 and "```" not in accumulated:
                return True, None
            inline = re.search(r'(\{\s*"subtasks"\s*:\s*\[.+?\]\s*\})', accumulated, re.DOTALL)
            if not inline:
                return False, None
            block_match = inline

        try:
            data = json.loads(block_match.group(1))
        except json.JSONDecodeError:
            return False, None

        subtasks = data.get("subtasks") or []
        if not isinstance(subtasks, list):
            return True, None

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
        # Вернём span всего матча (с ```json ... ``` если был), чтобы
        # вырезать из видимого текста.
        return True, (block_match.start(), block_match.end())

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


def _mcp_tool_def(server, t: dict):
    """
    Превращает MCP-tool в нашу ToolDefinition. Имя префиксируется
    `mcp__<server_id>__<tool_name>` чтобы при tool_use мы знали с какого
    сервера дёргать его.
    """
    from app.domain.models.llm import ToolDefinition
    return ToolDefinition(
        name=f"mcp__{server.id}__{t['name']}",
        description=f"[{server.name}] {t.get('description', '')}",
        input_schema=t.get("input_schema") or {"type": "object"},
    )
