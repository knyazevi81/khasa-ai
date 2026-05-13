# khasa

Умный ассистент с **графом диалога** и мульти-провайдерным подключением к LLM. Монорепо: backend (FastAPI / DDD) + frontend (Next.js 15 App Router).

## Что внутри

- **Auth + email-подтверждение + аппрув админа** (3-шаговая регистрация)
- **Админ-панель** — список pending, активация, деактивация юзеров
- **Мульти-провайдер LLM** — Anthropic, OpenAI, локальный Ollama; каждый юзер хранит свои ключи (зашифрованы Fernet в БД, наружу маска)
- **Граф диалога** — дерево сообщений (`parent_id`), регенерация = новый assistant-узел с тем же parent, переключение веток через `current_message_id`, SVG-визуализация графа
- **WebSocket-стриминг** — токены приходят чанками через `/api/v1/chats/{id}/stream?token=...`
- **Файлы** — `.txt` и `.pdf` с текстовым слоем (без OCR), извлечённый текст вставляется в user-сообщение

## Стек

| Слой        | Технологии |
|-------------|-----------|
| Backend     | Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic, pwdlib bcrypt, python-jose, aiosmtplib, pydantic-settings, uv |
| Frontend    | Next.js 15 App Router, TypeScript, CSS Modules |
| Хранилище   | PostgreSQL 16 |
| Прокси      | nginx (отдаёт билд Next.js standalone и проксирует /api на backend) |
| Email (dev) | MailHog (UI на :8025) |
| Email (prod)| SMTP-провайдер |

## Архитектура backend

DDD-слои:

```
backend/app/
├── domain/                 # ядро: модели, исключения, абстрактные репозитории и порты
├── application/use_cases/  # бизнес-логика: AuthService, UserService
├── infrastructure/         # адаптеры: SQLAlchemy, JWT, bcrypt, SMTP, конфиг, логирование
└── presentation/fastapi/   # HTTP-слой: роутеры, схемы, middleware, DI
```

Поток зависимостей строго наружу: presentation → application → domain, infrastructure → domain.

## Регистрационный flow

1. `POST /api/v1/auth/register` — создаётся юзер `is_active=False, is_email_verified=False`, генерируется 6-значный код, шлётся на почту.
2. `POST /api/v1/auth/verify-email` — юзер вводит код. Если корректен — `is_email_verified=True`. Аккаунт всё ещё неактивен.
3. Суперюзер видит юзера в `/api/v1/users/pending` и активирует через `PATCH /api/v1/users/{id}/activate`. Юзеру приходит письмо «доступ открыт».
4. После этого юзер может залогиниться.

## Запуск

```bash
cp .env.example .env
# заполнить переменные (можно оставить дефолты для dev)

# поднять всё
docker compose --profile dev up -d --build

# применить миграции (один раз)
docker compose exec backend alembic upgrade head

# создать первого суперюзера (один раз)
docker compose exec backend python -m app.scripts.create_superuser admin@khasa.local <пароль>
```

После старта:

| URL | Что |
|-----|-----|
| http://localhost          | Приложение (через nginx) |
| http://localhost/api/v1/docs | Swagger |
| http://localhost:8025     | MailHog (входящие письма) |

## Граф диалога

Каждое сообщение — узел дерева (`messages.parent_id` → родитель). У одного родителя может быть N детей — это **ветки**. У чата есть `current_message_id` (текущий «лист»); путь от корня до листа — активный диалог, который видит юзер и который уходит в LLM как контекст.

**Сценарии:**

- **Обычная отправка**: новый user-узел вешается на `current_message_id`, затем создаётся PENDING assistant-узел, токены стримятся через WebSocket.
- **Регенерация**: создаётся новый assistant-узел с тем же `parent_id`, что и у прежнего, — это **ветка**. На фронте под сообщением появляются «таблетки» `a / b / c` для переключения.
- **Switch branch**: `POST /chats/{id}/switch-branch` меняет `current_message_id` — фронт перерисовывает активную ветку.

Контекст для LLM собирается рекурсивным CTE (`get_path_to_root`), который проходит по `parent_id` от листа к корню.

## Multi-provider LLM

Юзер заводит ключи в `/settings`. Каждый ключ — `LLMCredential` (provider + label + secret + base_url + default_model). Секреты хранятся зашифрованными (Fernet, ключ — `SECRET_CIPHER_KEY` в `.env`); наружу выдаются только маски (`sk-a…1234`).

Адаптеры:

| Провайдер  | Endpoint                              | Стрим       |
|------------|---------------------------------------|-------------|
| anthropic  | `/v1/messages` (`x-api-key`)          | SSE         |
| openai     | `/v1/chat/completions` (`Bearer …`)   | SSE         |
| ollama     | `/api/chat` (без ключа, base_url)     | NDJSON      |

Все приводятся к единому `AbstractLLMService.stream(...)` → асинхронный итератор `StreamEvent`'ов (`START / DELTA / DONE / ERROR`).

## WebSocket-протокол

`ws://localhost/api/v1/chats/{id}/stream?token=<access_token>`

**Входящие:**
```json
{ "type": "send", "content": "...", "parent_id": null }
{ "type": "regenerate", "from_assistant_message_id": "..." }
```

**Исходящие:**
```json
{ "type": "user_message_created", "message": {...} }
{ "type": "assistant_message_created", "message": {...} }
{ "type": "delta", "message_id": "...", "text": "..." }
{ "type": "done", "message_id": "...", "usage": {"input_tokens":0,"output_tokens":0} }
{ "type": "error", "message_id": "...", "error": "..." }
```

## Файлы (.txt / .pdf)

`POST /api/v1/chats/parse-file` (multipart) → возвращает `{filename, kind, size_bytes, extracted_text, extracted_chars}`. Парсер: `pypdf` для текстового слоя PDF (без OCR), плейн-декод для txt. Лимиты: 10MB файл, 200K символов на выход. Скан без текстового слоя — 400.

## Структура репозитория

```
khasa/
├── docker-compose.yml      # один compose, два профиля (dev / prod)
├── .env.example
├── Makefile                # удобные команды
├── backend/                # FastAPI приложение
├── frontend/               # Next.js приложение
└── nginx/                  # конфиг прокси
```
