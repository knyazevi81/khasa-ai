from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path
from typing import Any

import httpx

from app.infrastructure.skills.base import AbstractSkill, SkillContext


# ── bash ─────────────────────────────────────────────────────────────────────


class BashSkill(AbstractSkill):
    name = "bash"
    description = (
        "Выполнить shell-команду в песочнице чата. "
        "Возвращает stdout + stderr + exit code. "
        "Использовать для запуска python-скриптов, установки пакетов "
        "(`pip install ...`), git-операций, файловых операций сложнее "
        "чем read/write_file. Working directory — /workspace."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Команда (исполняется через sh -c)",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Таймаут в секундах (по умолчанию 60, максимум 300)",
                "default": 60,
            },
        },
        "required": ["command"],
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        command = (args.get("command") or "").strip()
        if not command:
            return "ERROR: empty command"
        timeout = min(int(args.get("timeout_seconds") or 60), 300)

        result = await ctx.sandbox.exec(
            ctx.container_id, command, timeout=timeout
        )
        chunks: list[str] = [f"$ {command}"]
        chunks.append(f"[exit {result.exit_code}]")
        if result.stdout:
            chunks.append("--- stdout ---")
            chunks.append(_truncate(result.stdout, 8000))
        if result.stderr:
            chunks.append("--- stderr ---")
            chunks.append(_truncate(result.stderr, 4000))
        return "\n".join(chunks)


# ── file operations ──────────────────────────────────────────────────────────


class ReadFileSkill(AbstractSkill):
    name = "read_file"
    description = (
        "Прочитать файл из workspace. Возвращает содержимое (текст) с "
        "номерами строк. Бинарные файлы вернут ошибку — для них используй bash."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Путь относительно /workspace (например, 'src/main.py')",
            },
        },
        "required": ["path"],
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        path = args.get("path") or ""
        safe = _safe_path(path)
        # cat -n внутри песочницы — всегда консистентно для модели
        result = await ctx.sandbox.exec(
            ctx.container_id,
            ["sh", "-c", f"cat -n {shlex.quote(safe)}"],
        )
        if result.exit_code != 0:
            return f"ERROR: {result.stderr or 'cannot read'}"
        return _truncate(result.stdout, 16000)


class WriteFileSkill(AbstractSkill):
    name = "write_file"
    description = (
        "Создать или ПЕРЕЗАПИСАТЬ файл в workspace. Возвращает количество "
        "записанных байт. Создаёт промежуточные директории."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Путь относительно /workspace"},
            "content": {"type": "string", "description": "Содержимое файла"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        path = args.get("path") or ""
        content = args.get("content", "")
        safe = _safe_path(path)

        # Через workspace на хосте (быстрее чем docker cp)
        host_path = os.path.join(ctx.sandbox.workspace_for(ctx.chat_id), safe)
        try:
            os.makedirs(os.path.dirname(host_path) or ".", exist_ok=True)
            with open(host_path, "w", encoding="utf-8") as f:
                f.write(content)
            # Файл создан от того, кто запустил backend (обычно root в
            # dev-контейнере) → внутри песочницы юзер 10001 не сможет его
            # ни прочитать, ни перезаписать. Чиним владельца + права.
            try:
                os.chown(host_path, 10001, 10001)
                # Если создавалась промежуточная директория — её тоже chown
                d = os.path.dirname(host_path)
                ws = ctx.sandbox.workspace_for(ctx.chat_id)
                while d and d.startswith(ws) and d != ws:
                    try:
                        os.chown(d, 10001, 10001)
                    except OSError:
                        pass
                    d = os.path.dirname(d)
            except (PermissionError, OSError):
                # На macOS Docker Desktop chown с хоста может не работать —
                # делаем chown внутри контейнера от root как fallback.
                try:
                    await ctx.sandbox.exec(
                        ctx.container_id,
                        ["chown", "10001:10001", safe],
                        user="root",
                    )
                except Exception:
                    pass

            return f"OK: wrote {len(content)} chars to {safe}"
        except OSError as exc:
            return f"ERROR: {exc}"


class EditFileSkill(AbstractSkill):
    name = "edit_file"
    description = (
        "Точечно поменять одну строку (или фрагмент) в файле. "
        "Найдёт `old_str` (должен встречаться ровно один раз) и заменит на `new_str`. "
        "Если old_str не найден или встречается несколько раз — вернёт ошибку."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_str": {"type": "string"},
            "new_str": {"type": "string"},
        },
        "required": ["path", "old_str", "new_str"],
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        path = args.get("path") or ""
        old = args.get("old_str") or ""
        new = args.get("new_str") or ""
        safe = _safe_path(path)
        host_path = os.path.join(ctx.sandbox.workspace_for(ctx.chat_id), safe)
        if not os.path.exists(host_path):
            return f"ERROR: {safe} does not exist"
        try:
            with open(host_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            return f"ERROR: {exc}"

        count = content.count(old)
        if count == 0:
            return "ERROR: old_str not found"
        if count > 1:
            return f"ERROR: old_str matches {count} places, must be unique"

        new_content = content.replace(old, new, 1)
        try:
            with open(host_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            # Чиним владельца на случай если файл был создан от root
            try:
                os.chown(host_path, 10001, 10001)
            except (PermissionError, OSError):
                try:
                    await ctx.sandbox.exec(
                        ctx.container_id,
                        ["chown", "10001:10001", safe],
                        user="root",
                    )
                except Exception:
                    pass
        except OSError as exc:
            return f"ERROR: {exc}"
        return f"OK: replaced 1 occurrence in {safe}"


class ListDirectorySkill(AbstractSkill):
    name = "list_directory"
    description = (
        "Показать содержимое директории внутри workspace (ls -la эквивалент)."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Путь относительно /workspace (пустое = корень)",
                "default": ".",
            },
        },
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        path = args.get("path") or "."
        safe = _safe_path(path)
        result = await ctx.sandbox.exec(
            ctx.container_id,
            ["sh", "-c", f"ls -la {shlex.quote(safe)}"],
        )
        if result.exit_code != 0:
            return f"ERROR: {result.stderr or 'cannot list'}"
        return _truncate(result.stdout, 4000)


# ── web ──────────────────────────────────────────────────────────────────────


class WebSearchSkill(AbstractSkill):
    name = "web_search"
    description = (
        "Поиск в интернете через DuckDuckGo HTML endpoint (без API-ключа). "
        "Возвращает топ-N результатов — заголовок, URL и короткий снипет."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        query = (args.get("query") or "").strip()
        if not query:
            return "ERROR: empty query"
        limit = min(int(args.get("limit") or 5), 10)
        # DuckDuckGo HTML — простой парсинг
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) khasa-agent/1.0",
                },
            ) as client:
                resp = await client.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query},
                )
                if resp.status_code != 200:
                    return f"ERROR: ddg returned {resp.status_code}"
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                results: list[str] = []
                for i, item in enumerate(soup.select(".result")[:limit]):
                    title = item.select_one(".result__title")
                    snippet = item.select_one(".result__snippet")
                    link = item.select_one(".result__a")
                    if not (title and link):
                        continue
                    url = link.get("href", "")
                    results.append(
                        f"[{i + 1}] {title.get_text(strip=True)}\n"
                        f"    {url}\n"
                        f"    {snippet.get_text(strip=True) if snippet else ''}"
                    )
                if not results:
                    return "no results"
                return "\n\n".join(results)
        except httpx.HTTPError as exc:
            return f"ERROR: {exc}"
        except ImportError:
            return "ERROR: beautifulsoup4 not installed in backend"


class WebFetchSkill(AbstractSkill):
    name = "web_fetch"
    description = (
        "Скачать страницу по URL и вернуть её текстовое содержимое "
        "(без HTML-разметки). Для просмотра содержимого статей, доков, "
        "блогов и т.п."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Полный URL (http/https)"},
        },
        "required": ["url"],
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        url = (args.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return "ERROR: url must start with http:// or https://"
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) khasa-agent/1.0",
                },
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return f"ERROR: HTTP {resp.status_code}"
                ctype = resp.headers.get("content-type", "")
                if "html" in ctype:
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(resp.text, "html.parser")
                        # Уберём шум
                        for tag in soup(["script", "style", "nav", "footer"]):
                            tag.decompose()
                        text = soup.get_text("\n", strip=True)
                        # Убираем пустые строки
                        lines = [l for l in text.splitlines() if l.strip()]
                        return _truncate("\n".join(lines), 12000)
                    except ImportError:
                        return _truncate(resp.text, 12000)
                if "json" in ctype:
                    return _truncate(resp.text, 12000)
                if ctype.startswith("text/"):
                    return _truncate(resp.text, 12000)
                return f"ERROR: unsupported content-type: {ctype}"
        except httpx.HTTPError as exc:
            return f"ERROR: {exc}"


# ── present_files: показать юзеру скачивание ─────────────────────────────────


class PresentFilesSkill(AbstractSkill):
    name = "present_files"
    description = (
        "Показать пользователю набор файлов из workspace как готовые к "
        "скачиванию. Используй когда закончил работу и хочешь отдать "
        "юзеру результаты (отчёт, код, архив). Пути — относительно /workspace."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Пути к файлам в workspace",
            },
            "caption": {
                "type": "string",
                "description": "Короткое описание (опц.)",
            },
        },
        "required": ["paths"],
    }

    async def execute(self, args: dict[str, Any], ctx: SkillContext) -> str:
        paths = args.get("paths") or []
        caption = (args.get("caption") or "").strip()
        if not paths:
            return "ERROR: empty paths — передай хотя бы один файл"

        # Проверим что файлы реально существуют
        workspace = ctx.sandbox.workspace_for(ctx.chat_id)
        valid: list[dict] = []
        missing: list[str] = []
        for p in paths:
            try:
                safe = _safe_path(p)
            except ValueError:
                missing.append(p)
                continue
            host_path = os.path.join(workspace, safe)
            if os.path.exists(host_path) and os.path.isfile(host_path):
                size = os.path.getsize(host_path)
                valid.append({"path": safe, "size": size})
            else:
                missing.append(safe)

        # Если ВООБЩЕ ни одного файла не нашли — это ошибка, не показываем
        # юзеру пустую «коробку с файлами». Модель должна понять что
        # пути неправильные и попробовать снова.
        if not valid:
            return (
                "ERROR: ни один файл не найден в /workspace. "
                f"Проверил пути: {', '.join(missing) or '(нет)'}. "
                "Подсказка: пути должны быть относительно /workspace без ведущего /. "
                "Используй list_directory чтобы посмотреть актуальные имена."
            )

        # Возвращаем специальную метку, по которой ChatService поймёт что
        # это «представление файлов» и отправит её в чат как блок.
        lines = ["__KHASA_PRESENT_FILES__", caption or ""]
        for v in valid:
            lines.append(f"{v['path']}\t{v['size']}")
        result = "\n".join(lines)
        if missing:
            result += "\n\nWARNING: not found: " + ", ".join(missing)
        return result


# ── helpers ──────────────────────────────────────────────────────────────────


def _safe_path(path: str) -> str:
    """
    Нормализует путь и не даёт уйти из /workspace. Возвращает путь
    относительно /workspace без ведущих /.

    Толерантно отрезает ведущий `/workspace/` если модель его случайно
    подставила — иначе путь становится абсолютным и `os.path.join` его
    не схлопывает. Это частая ошибка LLM (особенно у GPT-моделей).
    """
    p = path.strip()
    # Снимаем ведущий /workspace или workspace/
    if p.startswith("/workspace/"):
        p = p[len("/workspace/"):]
    elif p == "/workspace":
        p = "."
    p = p.lstrip("/")
    if not p:
        return "."
    norm = os.path.normpath(p)
    if norm.startswith(".."):
        raise ValueError(f"path escapes workspace: {path}")
    return norm


def _truncate(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[:n] + f"\n\n[... обрезано, всего {len(text)} символов]"


def register_builtin_skills(registry) -> None:
    """Регистрирует все встроенные скиллы в реестре."""
    registry.register(BashSkill())
    registry.register(ReadFileSkill())
    registry.register(WriteFileSkill())
    registry.register(EditFileSkill())
    registry.register(ListDirectorySkill())
    registry.register(WebSearchSkill())
    registry.register(WebFetchSkill())
    registry.register(PresentFilesSkill())
