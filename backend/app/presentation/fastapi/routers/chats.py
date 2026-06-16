from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.application.use_cases.auth import AuthService
from app.application.use_cases.chat import ChatService
from app.domain.exceptions.base import AppException, NotAuthenticatedError
from app.domain.models.chat import Message
from app.domain.models.llm import StreamEventType
from app.domain.models.models import User
from app.infrastructure.database.dependencies import get_uow
from app.infrastructure.database.uow import UnitOfWork
from app.infrastructure.files.extractor import detect_kind, extract_text
from app.presentation.fastapi.dependencies import (
    get_auth_service,
    get_chat_service,
    get_current_user,
    get_llm_credential_service,
    get_llm_router,
)
from app.presentation.fastapi.schemas.chat import (
    ChatCreateRequest,
    ChatResponse,
    ChatUpdateRequest,
    ChatsListResponse,
    ForkRequest,
    MessageResponseDto,
    MessagesListResponse,
    RegenerateRequest,
    SendMessageRequest,
    SwitchBranchRequest,
)
from app.presentation.fastapi.schemas.schemas import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chats", tags=["chats"])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _to_chat_response(c) -> ChatResponse:
    return ChatResponse(
        id=c.id,
        title=c.title,
        current_message_id=c.current_message_id,
        credential_id=c.credential_id,
        model=c.model,
        system_prompt=c.system_prompt,
        agent_mode=getattr(c, "agent_mode", False),
    )


def _to_message_response(m: Message) -> MessageResponseDto:
    return MessageResponseDto(**m.model_dump())


# ── Chats CRUD ───────────────────────────────────────────────────────────────


@router.get("/", response_model=ChatsListResponse, summary="Мои чаты")
async def list_chats(
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatsListResponse:
    chats = await service.list_chats(current_user.id)
    return ChatsListResponse(
        chats=[_to_chat_response(c) for c in chats],
        total=len(chats),
    )


@router.post("/", response_model=ChatResponse, status_code=201)
async def create_chat(
    body: ChatCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    chat = await service.create_chat(
        user_id=current_user.id,
        title=body.title,
        credential_id=body.credential_id,
        model=body.model,
        system_prompt=body.system_prompt,
    )
    return _to_chat_response(chat)


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    chat = await service.get_chat(chat_id, current_user.id)
    return _to_chat_response(chat)


@router.patch("/{chat_id}", response_model=ChatResponse)
async def update_chat(
    chat_id: uuid.UUID,
    body: ChatUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    chat = await service.get_chat(chat_id, current_user.id)
    fields = body.model_dump(exclude_unset=True)
    if fields:
        await service.uow.chats.update_fields(chat_id, **fields)
    chat = await service.get_chat(chat_id, current_user.id)
    return _to_chat_response(chat)


@router.delete("/{chat_id}", response_model=MessageResponse)
async def delete_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponse:
    await service.delete_chat(chat_id, current_user.id)
    return MessageResponse(message="Чат удалён")


@router.post("/{chat_id}/hide", response_model=MessageResponse)
async def hide_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponse:
    await service.hide_chat(chat_id, current_user.id)
    return MessageResponse(message="Чат скрыт")


@router.post("/{chat_id}/unhide", response_model=MessageResponse)
async def unhide_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponse:
    await service.unhide_chat(chat_id, current_user.id)
    return MessageResponse(message="Чат восстановлен")


# ── Граф (все сообщения чата) ────────────────────────────────────────────────


@router.get("/{chat_id}/messages", response_model=MessagesListResponse)
async def list_messages(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessagesListResponse:
    chat = await service.get_chat(chat_id, current_user.id)
    msgs = await service.get_messages(chat_id, current_user.id)
    return MessagesListResponse(
        messages=[_to_message_response(m) for m in msgs],
        current_message_id=chat.current_message_id,
    )


@router.get("/{chat_id}/segments")
async def list_message_segments(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict:
    """
    Возвращает сегменты ассистент-сообщений (text-блоки и tool-call'ы)
    с общим order_idx, сгруппированные по message_id. Фронт мержит и
    рендерит "text → tool → text → tool → ..." по порядку.
    """
    await service.get_chat(chat_id, current_user.id)
    msgs = await service.get_messages(chat_id, current_user.id)
    msg_ids = [m.id for m in msgs]
    calls = await service.uow.tool_calls.find_for_messages(msg_ids)
    segments = await service.uow.text_segments.find_for_messages(msg_ids)

    grouped: dict[str, list[dict]] = {}
    for c in calls:
        grouped.setdefault(str(c.message_id), []).append({
            "kind": "tool_call",
            "order_idx": c.order_idx,
            "id": c.tool_use_id,
            "name": c.name,
            "input": c.input or {},
            "output": c.output,
            "status": c.status,
            "is_present_files": c.is_present_files,
        })
    for s in segments:
        grouped.setdefault(str(s.message_id), []).append({
            "kind": "text",
            "order_idx": s.order_idx,
            "id": str(s.id),
            "content": s.content,
        })

    # Сортируем каждую группу по order_idx
    for msg_id in grouped:
        grouped[msg_id].sort(key=lambda x: x["order_idx"])

    return {"segments": grouped}


@router.get("/{chat_id}/tool-calls")
async def list_tool_calls(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict:
    """
    Возвращает все сохранённые tool-calls этого чата сгруппированные по
    message_id. Используется фронтом при загрузке страницы чата, чтобы
    восстановить блоки tool-call'ов (которые при стриме шли через WS,
    но не попадают в обычный messages-endpoint).
    """
    await service.get_chat(chat_id, current_user.id)
    msgs = await service.get_messages(chat_id, current_user.id)
    msg_ids = [m.id for m in msgs]
    calls = await service.uow.tool_calls.find_for_messages(msg_ids)
    grouped: dict[str, list[dict]] = {}
    for c in calls:
        grouped.setdefault(str(c.message_id), []).append({
            "id": c.tool_use_id,
            "name": c.name,
            "input": c.input or {},
            "output": c.output,
            "status": c.status,
            "is_present_files": c.is_present_files,
            "order_idx": c.order_idx,
        })
    return {"tool_calls": grouped}


@router.post("/{chat_id}/switch-branch", response_model=ChatResponse)
async def switch_branch(
    chat_id: uuid.UUID,
    body: SwitchBranchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    chat = await service.set_current_message(
        chat_id=chat_id, user_id=current_user.id, message_id=body.message_id
    )
    return _to_chat_response(chat)


# ── Прикрепление файла к будущему user-сообщению ─────────────────────────────
# Простое решение: грузим файл, парсим, возвращаем извлечённый текст —
# фронт вставляет его в `content` следующего user-сообщения. Это держит
# граф простым (один узел = одно сообщение, attachments опциональны).


@router.post(
    "/parse-file",
    summary="Парсит .txt / .pdf и возвращает извлечённый текст",
)
async def parse_file(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
) -> dict:
    data = await file.read()
    kind = detect_kind(file.filename or "", file.content_type)
    text = extract_text(data, kind, filename=file.filename or "")
    return {
        "filename": file.filename,
        "kind": kind.value,
        "size_bytes": len(data),
        "extracted_text": text,
        "extracted_chars": len(text),
    }


# ── REST: добавить user-сообщение (без стрима) ───────────────────────────────


@router.post(
    "/{chat_id}/messages",
    response_model=MessageResponseDto,
    summary="Добавить user-сообщение в граф (без стрима ассистента)",
)
async def send_message(
    chat_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponseDto:
    msg = await service.add_user_message(
        chat_id=chat_id,
        user_id=current_user.id,
        content=body.content,
        parent_id=body.parent_id,
    )
    return _to_message_response(msg)


@router.get(
    "/{chat_id}/messages/{message_id}/subtasks",
    summary="Подзадачи агентного режима для сообщения",
)
async def list_subtasks(
    chat_id: uuid.UUID,
    message_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> dict:
    # Проверка владения через get_chat
    await service.get_chat(chat_id, current_user.id)
    subtasks = await service.uow.agent_subtasks.find_for_message(message_id)
    return {
        "subtasks": [
            {
                "id": str(s.id),
                "order_index": s.order_index,
                "title": s.title,
                "status": s.status,
            }
            for s in subtasks
        ]
    }


@router.post(
    "/{chat_id}/regenerate",
    response_model=MessageResponseDto,
    summary="Создать новую ветку ответа (новый assistant-узел на том же parent)",
)
async def regenerate(
    chat_id: uuid.UUID,
    body: RegenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponseDto:
    msg = await service.regenerate(
        chat_id=chat_id,
        user_id=current_user.id,
        from_assistant_message_id=body.from_assistant_message_id,
        branch_label=body.branch_label,
    )
    return _to_message_response(msg)


@router.post(
    "/{chat_id}/fork",
    response_model=MessageResponseDto,
    summary="Edit-and-fork: новый user-узел на том же parent, что у указанного",
)
async def fork_message(
    chat_id: uuid.UUID,
    body: ForkRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> MessageResponseDto:
    msg = await service.fork_from_message(
        chat_id=chat_id,
        user_id=current_user.id,
        from_message_id=body.from_message_id,
        new_content=body.new_content,
        branch_label=body.branch_label,
    )
    return _to_message_response(msg)


@router.get(
    "/{chat_id}/export",
    summary="Экспорт чата (активная ветка) в .md или .json",
)
async def export_chat(
    chat_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    format: str = "md",
):
    """
    Возвращает активную ветку чата (путь от корня до current_message_id).
    Формат:
      • md   — markdown с разделителями и метаинформацией;
      • json — структурированный объект {chat, messages[]}.
    """
    from fastapi import Response
    from datetime import datetime, timezone
    import json as _json

    chat = await service.get_chat(chat_id, current_user.id)

    if not chat.current_message_id:
        # Пустой чат — отдаём пустой документ
        if format == "json":
            return Response(
                content=_json.dumps(
                    {"chat": {"id": str(chat.id), "title": chat.title}, "messages": []},
                    ensure_ascii=False, indent=2,
                ),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{chat.title}.json"'},
            )
        return Response(
            content=f"# {chat.title}\n\n(пусто)\n",
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{chat.title}.md"'},
        )

    # path-to-root по активному листу
    path = await service.uow.messages.get_path_to_root(chat.current_message_id)
    base_name = _safe_filename(chat.title)

    if format == "json":
        payload = {
            "chat": {
                "id": str(chat.id),
                "title": chat.title,
                "model": chat.model,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            "messages": [
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "model": m.model,
                    "input_tokens": m.input_tokens,
                    "output_tokens": m.output_tokens,
                }
                for m in path
            ],
        }
        return Response(
            content=_json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers=_disposition_headers(base_name, "json"),
        )

    # markdown
    lines: list[str] = [f"# {chat.title}\n"]
    if chat.model:
        lines.append(f"_Model: `{chat.model}`_\n")
    lines.append(f"_Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n")
    lines.append("\n---\n\n")

    for m in path:
        role_label = {
            "user": "👤 **You**",
            "assistant": "🤖 **khasa**",
            "system": "⚙ **System**",
        }.get(m.role, m.role)
        lines.append(f"## {role_label}\n\n")
        lines.append(f"{m.content}\n\n")
        if m.role == "assistant" and (m.input_tokens or m.output_tokens):
            lines.append(
                f"<sub>tokens: in {m.input_tokens} · out {m.output_tokens}</sub>\n\n"
            )
        lines.append("---\n\n")

    return Response(
        content="".join(lines),
        media_type="text/markdown",
        headers=_disposition_headers(base_name, "md"),
    )


# ── WebSocket: стрим ассистента ──────────────────────────────────────────────
# Протокол (вход):
#   { "type": "send", "content": "...", "parent_id": null }
#   { "type": "regenerate", "from_assistant_message_id": "..." }
# Протокол (выход):
#   { "type": "user_message_created", "message": {...} }
#   { "type": "assistant_message_created", "message": {...} }
#   { "type": "delta", "message_id": "...", "text": "..." }
#   { "type": "done", "message_id": "...", "usage": {...} }
#   { "type": "error", "message_id"?: "...", "error": "..." }


@router.websocket("/{chat_id}/stream")
async def chat_stream(
    websocket: WebSocket,
    chat_id: uuid.UUID,
    token: Annotated[str | None, Query()] = None,
) -> None:
    """
    WebSocket для стриминга ответов LLM. Аутентификация через query-параметр
    `?token=<access_token>` (стандартный воркэраунд для WS — там нет
    Authorization-хедера).
    """
    if not token:
        await websocket.close(code=4401, reason="missing token")
        return

    # Создаём свой UoW и services вне FastAPI DI — DI здесь работает иначе
    from app.infrastructure.config.config import get_settings
    from app.infrastructure.database.engine import async_session_maker
    from app.infrastructure.email.service import EmailService
    from app.infrastructure.security.crypto import SecretCipher
    from app.infrastructure.security.jwt import JoseTokenService
    from app.infrastructure.security.password import BcryptPasswordHasher
    from app.application.use_cases.auth import AuthService as AuthServiceCls
    from app.application.use_cases.llm_credentials import LLMCredentialService
    from app.application.use_cases.chat import ChatService as ChatServiceCls

    settings = get_settings()

    async with async_session_maker() as session:
        async with UnitOfWork(session) as uow:
            try:
                auth = AuthServiceCls(
                    uow,
                    BcryptPasswordHasher(),
                    JoseTokenService(settings),
                    EmailService(settings),
                    settings,
                )
                user = await auth.get_current_user(token)
            except AppException as exc:
                await websocket.close(code=4401, reason=exc.message)
                return

            cipher = SecretCipher(settings.SECRET_CIPHER_KEY.get_secret_value())
            router_llm = get_llm_router()
            creds = LLMCredentialService(uow, cipher, router_llm)

            # Полный набор зависимостей — иначе агентный режим в WS не работает
            from app.application.use_cases.artifacts import ArtifactService
            from app.application.use_cases.mcp_servers import MCPService
            from app.application.use_cases.sandboxes import SandboxService
            from app.presentation.fastapi.dependencies import (
                get_sandbox_manager,
                get_skill_registry,
            )
            chat_service = ChatServiceCls(
                uow,
                creds,
                router_llm,
                artifacts=ArtifactService(uow),
                sandbox_service=SandboxService(uow, get_sandbox_manager()),
                mcp_service=MCPService(uow),
                skill_registry=get_skill_registry(),
            )

            await websocket.accept()

            try:
                # Проверка владения чатом — сразу
                try:
                    await chat_service.get_chat(chat_id, user.id)
                except AppException as exc:
                    await websocket.send_json({"type": "error", "error": exc.message})
                    await websocket.close()
                    return

                while True:
                    raw = await websocket.receive_text()
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        await websocket.send_json(
                            {"type": "error", "error": "invalid json"}
                        )
                        continue

                    try:
                        await _handle_ws_message(
                            websocket=websocket,
                            chat_service=chat_service,
                            chat_id=chat_id,
                            user_id=user.id,
                            payload=msg,
                        )
                    except AppException as exc:
                        # Доменная ошибка — отдаём текст наружу. Сокет может
                        # быть уже закрыт фронтом (юзер ушёл со страницы) —
                        # ловим RuntimeError, не падаем.
                        logger.info("ws AppException: %s", exc.message)
                        try:
                            await websocket.send_json(
                                {"type": "error", "error": exc.message}
                            )
                        except (RuntimeError, WebSocketDisconnect):
                            logger.debug("ws already closed, can't send error")
                    except Exception as exc:
                        # ВАЖНО: логируем ДО попытки отправить — на случай
                        # если сокет уже закрыт и send упадёт сам, тогда
                        # первичная ошибка теряется. logger.exception
                        # запишет полный traceback.
                        logger.exception(
                            "ws handler crashed: %s: %s",
                            type(exc).__name__,
                            exc,
                        )
                        try:
                            await websocket.send_json(
                                {"type": "error", "error": "internal error"}
                            )
                        except (RuntimeError, WebSocketDisconnect):
                            logger.debug("ws already closed, can't send error")

            except WebSocketDisconnect:
                logger.info("ws disconnect chat=%s user=%s", chat_id, user.id)


async def _handle_ws_message(
    *,
    websocket: WebSocket,
    chat_service,
    chat_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: dict,
) -> None:
    kind = payload.get("type")

    if kind == "send":
        content = (payload.get("content") or "").strip()
        if not content:
            await websocket.send_json({"type": "error", "error": "empty content"})
            return
        parent_id = payload.get("parent_id")
        parent_uuid = uuid.UUID(parent_id) if parent_id else None

        user_msg = await chat_service.add_user_message(
            chat_id=chat_id,
            user_id=user_id,
            content=content,
            parent_id=parent_uuid,
        )
        # Commit чтобы фронт мог сразу запросить /messages и увидел узел
        await chat_service.uow.session.commit()

        await websocket.send_json(
            {
                "type": "user_message_created",
                "message": _to_message_response(user_msg).model_dump(mode="json"),
            }
        )

        assistant_msg = await chat_service.prepare_assistant_message(
            chat_id=chat_id,
            user_id=user_id,
            parent_id=user_msg.id,
        )
        await chat_service.uow.session.commit()

        await websocket.send_json(
            {
                "type": "assistant_message_created",
                "message": _to_message_response(assistant_msg).model_dump(mode="json"),
            }
        )

        chat = await chat_service.get_chat(chat_id, user_id)
        await _pump_stream(websocket, chat_service, chat, assistant_msg.id)

    elif kind == "regenerate":
        from_id = payload.get("from_assistant_message_id")
        if not from_id:
            await websocket.send_json(
                {"type": "error", "error": "from_assistant_message_id required"}
            )
            return
        branch_label = payload.get("branch_label")

        assistant_msg = await chat_service.regenerate(
            chat_id=chat_id,
            user_id=user_id,
            from_assistant_message_id=uuid.UUID(from_id),
            branch_label=branch_label,
        )
        await chat_service.uow.session.commit()

        await websocket.send_json(
            {
                "type": "assistant_message_created",
                "message": _to_message_response(assistant_msg).model_dump(mode="json"),
            }
        )

        chat = await chat_service.get_chat(chat_id, user_id)
        await _pump_stream(websocket, chat_service, chat, assistant_msg.id)

    elif kind == "fork":
        # Edit-and-fork: новый user-узел с тем же parent, что у указанного
        # сообщения (свой message → редактирование, чужое → произвольный форк).
        # После создания user-узла сразу запускаем стрим assistant-ответа.
        from_id = payload.get("from_message_id")
        content = (payload.get("new_content") or "").strip()
        if not from_id or not content:
            await websocket.send_json(
                {"type": "error", "error": "from_message_id and new_content required"}
            )
            return
        branch_label = payload.get("branch_label")

        user_msg = await chat_service.fork_from_message(
            chat_id=chat_id,
            user_id=user_id,
            from_message_id=uuid.UUID(from_id),
            new_content=content,
            branch_label=branch_label,
        )
        await chat_service.uow.session.commit()

        await websocket.send_json(
            {
                "type": "user_message_created",
                "message": _to_message_response(user_msg).model_dump(mode="json"),
            }
        )

        assistant_msg = await chat_service.prepare_assistant_message(
            chat_id=chat_id,
            user_id=user_id,
            parent_id=user_msg.id,
        )
        await chat_service.uow.session.commit()

        await websocket.send_json(
            {
                "type": "assistant_message_created",
                "message": _to_message_response(assistant_msg).model_dump(mode="json"),
            }
        )

        chat = await chat_service.get_chat(chat_id, user_id)
        await _pump_stream(websocket, chat_service, chat, assistant_msg.id)

    else:
        await websocket.send_json({"type": "error", "error": f"unknown type: {kind}"})


async def _safe_send(websocket: WebSocket, payload: dict) -> bool:
    """
    Безопасная отправка JSON через WebSocket. Если сокет уже закрыт
    (юзер ушёл со страницы, обрыв сети) — возвращает False и не падает,
    давая вызывающему понять что дальше слать бессмысленно.
    """
    try:
        await websocket.send_json(payload)
        return True
    except (RuntimeError, WebSocketDisconnect):
        return False


async def _pump_stream(websocket, chat_service, chat, assistant_msg_id):
    async for event in chat_service.stream_assistant_response(
        chat=chat, assistant_msg_id=assistant_msg_id
    ):
        if event.type == StreamEventType.DELTA:
            ok = await _safe_send(
                websocket,
                {
                    "type": "delta",
                    "message_id": str(assistant_msg_id),
                    "text": event.text,
                    # segment_id / order_idx — для interleaved-рендера
                    **(event.raw or {}),
                },
            )
        elif event.type == StreamEventType.ARTIFACT:
            ok = await _safe_send(websocket, {"type": "artifact", "artifact": event.raw})
        elif event.type == StreamEventType.TOOL_USE:
            ok = await _safe_send(websocket, {"type": "tool_use", **(event.raw or {})})
        elif event.type == StreamEventType.TOOL_RESULT:
            ok = await _safe_send(websocket, {"type": "tool_result", **(event.raw or {})})
        elif event.type == StreamEventType.TRUNCATED:
            ok = await _safe_send(websocket, {"type": "truncated", **(event.raw or {})})
        elif event.type == StreamEventType.DONE:
            payload = {"type": "done", "message_id": str(assistant_msg_id)}
            if event.usage:
                payload["usage"] = event.usage.model_dump()
            ok = await _safe_send(websocket, payload)
        elif event.type == StreamEventType.ERROR:
            ok = await _safe_send(
                websocket,
                {
                    "type": "error",
                    "message_id": str(assistant_msg_id),
                    "error": event.error,
                },
            )
        else:
            ok = True  # START — служебное, фронту не нужно

        # Если сокет умер — генератор сам прервётся при следующей итерации
        # ChatService через CancelledError. Но мы можем выйти явно, чтобы не
        # ждать ещё одного цикла стрима.
        if not ok:
            return


# ── filename helpers (RFC 5987 для unicode-имён файлов) ──────────────────────


def _safe_filename(title: str) -> str:
    """
    Превращает заголовок чата в безопасное «базовое» имя файла.
    Сохраняет unicode-символы (они уйдут в filename* по RFC 5987), а из
    ASCII-fallback'а убирает всё кроме alnum/_-. — для совместимости
    со старыми браузерами и заголовком filename="..." (latin-1 only).
    """
    cleaned = title.strip() or "chat"
    # Заменим всё что точно сломает имя файла на _
    bad = '/\\:*?"<>|'
    out: list[str] = []
    for c in cleaned:
        if c in bad or ord(c) < 32:
            out.append("_")
        else:
            out.append(c)
    return "".join(out)[:80]


def _disposition_headers(name: str, ext: str) -> dict[str, str]:
    """
    Возвращает Content-Disposition с поддержкой unicode-имён.

    RFC 6266 + 5987: даём ascii-fallback в `filename=` (с заменой не-ASCII
    на `_`) и full UTF-8 в `filename*=` через percent-encoding. Современные
    браузеры (Chrome/FF/Safari) предпочитают filename*, IE11 — fallback.
    """
    from urllib.parse import quote

    full = f"{name}.{ext}"
    ascii_fallback = full.encode("ascii", "replace").decode("ascii").replace("?", "_")
    encoded = quote(full, safe="")
    disposition = (
        f'attachment; filename="{ascii_fallback}"; '
        f"filename*=UTF-8''{encoded}"
    )
    return {"Content-Disposition": disposition}
