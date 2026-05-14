from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedArtifact:
    """Распарсенный из стрима блок артефакта (готов к сохранению)."""
    kind: str
    slug: str
    title: str
    language: str | None
    content: str
    # Положение в полном тексте — для дедупликации повторных парсов
    start: int
    end: int


# Паттерны:
#   ```khasa-artifact:markdown:plan:Project Plan
#   ...content...
#   ```
#
# kind — обязательный; slug, title — обязательные; language — опциональный.
# Title и slug могут содержать пробелы/дефисы (slug — допустимы только
# [a-z0-9_-], title — что угодно кроме переноса строки).
_ARTIFACT_RE = re.compile(
    r"```khasa-artifact:"
    r"(?P<kind>[a-z]+):"
    r"(?P<slug>[a-zA-Z0-9_-]+):"
    r"(?P<title>[^\n:]+)"
    r"(?::(?P<language>[a-zA-Z0-9_+-]+))?"
    r"\s*\n"
    r"(?P<content>.*?)"
    r"```",
    re.DOTALL,
)


def extract_artifacts(full_text: str) -> list[ParsedArtifact]:
    """
    Извлекает все артефакт-блоки из полного текста ответа ассистента.
    Безопасно вызывать частично (на инкрементально-растущем тексте) — мы
    возвращаем только полностью закрытые блоки.
    """
    out: list[ParsedArtifact] = []
    for m in _ARTIFACT_RE.finditer(full_text):
        out.append(
            ParsedArtifact(
                kind=m.group("kind"),
                slug=m.group("slug"),
                title=m.group("title").strip(),
                language=m.group("language"),
                content=m.group("content"),
                start=m.start(),
                end=m.end(),
            )
        )
    return out


# Допустимые kind-ы — на стороне домена ArtifactKind, тут просто whitelist
_ALLOWED_KINDS = {"markdown", "code", "html", "svg", "mermaid", "json"}


def is_allowed_kind(kind: str) -> bool:
    return kind in _ALLOWED_KINDS
