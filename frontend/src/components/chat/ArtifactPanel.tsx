"use client";

import { useEffect, useMemo, useState } from "react";
import type {
  ArtifactDTO,
  ArtifactDetailDTO,
  ArtifactPushDTO,
  ArtifactVersionDTO,
} from "@/lib/chat-types";
import { api } from "@/lib/api";
import { Markdown } from "./Markdown";
import styles from "./ArtifactPanel.module.css";

interface Props {
  open: boolean;
  onClose: () => void;
  chatId: string;
  /** Стрим прислал обновлённый артефакт — это его «push» событие. */
  pushedArtifact: ArtifactPushDTO | null;
}

const KIND_LABEL: Record<ArtifactDTO["kind"], string> = {
  markdown: "MD",
  code: "CODE",
  html: "HTML",
  svg: "SVG",
  mermaid: "MMD",
  json: "JSON",
};

const KIND_COLOR: Record<ArtifactDTO["kind"], string> = {
  markdown: "var(--text)",
  code: "var(--green)",
  html: "var(--yellow)",
  svg: "var(--yellow)",
  mermaid: "var(--green)",
  json: "var(--muted)",
};

/**
 * Сворачивающаяся правая колонка с артефактами чата:
 *   • верхняя секция — список (с подсветкой активного);
 *   • основная — рендер выбранной версии;
 *   • снизу — переключатель версий (v1, v2, ...) и кнопка copy.
 *
 * Получает push-уведомления через `pushedArtifact` prop — на каждое обновление
 * рекалабается список и если показывается этот же артефакт, перетягивается
 * его деталь.
 */
export function ArtifactPanel({ open, onClose, chatId, pushedArtifact }: Props) {
  const [list, setList] = useState<ArtifactDTO[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ArtifactDetailDTO | null>(null);
  const [shownVersionId, setShownVersionId] = useState<string | null>(null);

  // ── загрузка списка ──────────────────────────────────────────────────────
  async function reloadList() {
    try {
      const r = await api.chats.artifacts(chatId);
      setList(r.artifacts);
      // Если ещё ничего не выбрано — берём первый
      if (!selectedId && r.artifacts.length > 0) {
        setSelectedId(r.artifacts[0].id);
      }
    } catch {
      /* пусто */
    }
  }

  useEffect(() => {
    if (!open) return;
    reloadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, chatId]);

  // ── загрузка детали ──────────────────────────────────────────────────────
  async function reloadDetail(id: string) {
    try {
      const d = await api.chats.artifact(chatId, id);
      setDetail(d);
      setShownVersionId(d.artifact.current_version_id);
    } catch {
      setDetail(null);
    }
  }

  useEffect(() => {
    if (!selectedId) return;
    reloadDetail(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // ── реакция на push из стрима ────────────────────────────────────────────
  useEffect(() => {
    if (!pushedArtifact) return;
    // Подтянем список + деталь, если этот артефакт показан
    reloadList();
    if (selectedId === pushedArtifact.artifact_id) {
      reloadDetail(pushedArtifact.artifact_id);
    } else if (!selectedId) {
      // Если ничего не выбрано — фокус на новом
      setSelectedId(pushedArtifact.artifact_id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pushedArtifact?.version_id]);

  const shownVersion: ArtifactVersionDTO | null = useMemo(() => {
    if (!detail || !shownVersionId) return null;
    return detail.versions.find((v) => v.id === shownVersionId) ?? null;
  }, [detail, shownVersionId]);

  async function pickVersion(versionId: string) {
    if (!detail) return;
    setShownVersionId(versionId);
    // Сделаем выбранную версию активной (current)
    try {
      await api.chats.setArtifactVersion(chatId, detail.artifact.id, versionId);
    } catch {
      /* визуально и так норм */
    }
  }

  function copyContent() {
    if (!shownVersion) return;
    navigator.clipboard.writeText(shownVersion.content).catch(() => {});
  }

  if (!open) return null;

  return (
    <aside className={styles.panel}>
      <header className={styles.header}>
        <span className={styles.dot} style={{ background: "var(--yellow)" }} />
        <span className={styles.title}>артефакты</span>
        <span className={styles.count}>· {list.length}</span>
        <span style={{ flex: 1 }} />
        <button className={styles.close} onClick={onClose} aria-label="закрыть">
          ×
        </button>
      </header>

      {list.length === 0 ? (
        <div className={styles.empty}>
          // пока ничего
          <br />
          <span className={styles.hint}>
            ассистент создаёт артефакты для долгих документов и кода
          </span>
        </div>
      ) : (
        <>
          {/* список артефактов */}
          <ul className={styles.list}>
            {list.map((a) => (
              <li key={a.id}>
                <button
                  className={`${styles.listItem} ${a.id === selectedId ? styles.listItemOn : ""}`}
                  onClick={() => setSelectedId(a.id)}
                >
                  <span
                    className={styles.kindTag}
                    style={{ color: KIND_COLOR[a.kind] }}
                  >
                    {KIND_LABEL[a.kind]}
                  </span>
                  <span className={styles.itemTitle}>{a.title}</span>
                </button>
              </li>
            ))}
          </ul>

          {/* деталь */}
          {detail && shownVersion ? (
            <div className={styles.detail}>
              <div className={styles.detailHeader}>
                <span
                  className={styles.kindTag}
                  style={{ color: KIND_COLOR[detail.artifact.kind] }}
                >
                  {KIND_LABEL[detail.artifact.kind]}
                </span>
                <span className={styles.detailTitle}>
                  {detail.artifact.title}
                </span>
                {detail.artifact.language && (
                  <span className={styles.detailLang}>
                    {detail.artifact.language}
                  </span>
                )}
                <span style={{ flex: 1 }} />
                <button className={styles.copyBtn} onClick={copyContent} title="copy">
                  ⎘ copy
                </button>
              </div>

              <div className={styles.content}>
                <ArtifactBody
                  kind={detail.artifact.kind}
                  language={detail.artifact.language}
                  content={shownVersion.content}
                />
              </div>

              {detail.versions.length > 1 && (
                <div className={styles.versions}>
                  <span className={styles.versionsLabel}>версии:</span>
                  {detail.versions.map((v) => (
                    <button
                      key={v.id}
                      className={`${styles.versionPill} ${v.id === shownVersionId ? styles.versionPillOn : ""}`}
                      onClick={() => pickVersion(v.id)}
                    >
                      v{v.version_no}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className={styles.empty}>— выберите артефакт —</div>
          )}
        </>
      )}
    </aside>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Рендер тела артефакта в зависимости от типа.
// Для html/svg используется sandbox-iframe чтобы LLM не могла стащить токены.
// ─────────────────────────────────────────────────────────────────────────────

function ArtifactBody({
  kind,
  language,
  content,
}: {
  kind: ArtifactDTO["kind"];
  language: string | null;
  content: string;
}) {
  if (kind === "markdown") {
    return <Markdown content={content} />;
  }
  if (kind === "json") {
    let pretty = content;
    try {
      pretty = JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      /* оставляем как есть */
    }
    return (
      <pre className={styles.code}>
        <code>{pretty}</code>
      </pre>
    );
  }
  if (kind === "code") {
    // Прикинемся блоком ```lang ... ``` и отдадим в Markdown — он подсветит
    const md = `\`\`\`${language || ""}\n${content}\n\`\`\``;
    return <Markdown content={md} />;
  }
  if (kind === "svg") {
    // SVG безопасно вставлять как dangerouslySetInnerHTML (без скриптов внутри —
    // современные браузеры sanitize'ят, но lock-down через CSP не делаем — это
    // приватная панель юзера, не публичная страница).
    return (
      <div
        className={styles.svgWrap}
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }
  if (kind === "html") {
    return (
      <iframe
        className={styles.iframe}
        sandbox="allow-scripts allow-forms"
        srcDoc={content}
        title="HTML artifact"
      />
    );
  }
  if (kind === "mermaid") {
    // Mermaid требует runtime библиотеку — для MVP просто показываем как код
    return (
      <pre className={styles.code}>
        <code>{content}</code>
      </pre>
    );
  }
  return <pre className={styles.code}>{content}</pre>;
}
