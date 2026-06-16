"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ArtifactPanel } from "@/components/chat/ArtifactPanel";
import { GraphOverlay } from "@/components/chat/GraphOverlay";
import { Markdown } from "@/components/chat/Markdown";
import { ModelSelect } from "@/components/chat/ModelSelect";
import { PromptSelect } from "@/components/chat/PromptSelect";
import { SubtasksList } from "@/components/chat/SubtasksList";
import { ToolCallBlock } from "@/components/chat/ToolCallBlock";
import { BranchIcon } from "@/components/common/BranchIcon";
import { useAuthStore } from "@/lib/auth-store";
import { useChatStore } from "@/lib/chat-store";
import { api } from "@/lib/api";
import type { MessageDTO } from "@/lib/chat-types";
import styles from "./chat.module.css";

export default function ChatDetail() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const chatId = params.id;
  const { user, initialized, bootstrap } = useAuthStore();
  const {
    chat,
    messages,
    currentMessageId,
    streaming,
    error,
    lastArtifactPush,
    toolCallsByMessage,
    segmentsByMessage,
    truncatedMessages,
    loadChat,
    connect,
    disconnect,
    sendMessage,
    regenerate,
    forkMessage,
    switchToBranch,
    reloadMessages,
  } = useChatStore();

  const [composer, setComposer] = useState("");
  const [attachment, setAttachment] = useState<{
    filename: string;
    text: string;
  } | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [agentMode, setAgentMode] = useState(false);
  const [graphOpen, setGraphOpen] = useState(false);
  const [artifactsOpen, setArtifactsOpen] = useState(false);
  const [artifactsCount, setArtifactsCount] = useState(0);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);

  // ── auth gate ────────────────────────────────────────────────────────────
  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (initialized && !user) router.replace("/auth/login");
  }, [initialized, user, router]);

  // ── load + connect ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!user || !chatId) return;
    (async () => {
      try {
        await loadChat(chatId);
        connect(chatId);
      } catch {
        router.replace("/chat");
      }
    })();
    return () => {
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, chatId]);

  useEffect(() => {
    if (chat) setAgentMode(chat.agent_mode);
  }, [chat?.id, chat?.agent_mode]);

  // Загрузка количества артефактов при открытии чата
  useEffect(() => {
    if (!chatId) return;
    api.chats
      .artifacts(chatId)
      .then((r) => setArtifactsCount(r.total))
      .catch(() => setArtifactsCount(0));
  }, [chatId]);

  // Реакция на push артефакта из стрима: счётчик + первый раз авто-открываем
  useEffect(() => {
    if (!lastArtifactPush) return;
    api.chats
      .artifacts(chatId)
      .then((r) => {
        setArtifactsCount(r.total);
        if (!artifactsOpen && r.total === 1) {
          // первый артефакт в чате — раскроем сразу
          setArtifactsOpen(true);
        }
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastArtifactPush?.version_id]);

  // Auto-scroll: только если юзер уже стоит примерно у низа (sticky-bottom).
  // Если юзер сам отскроллил наверх — не трогаем, дадим ему читать.
  // `instant` вместо `smooth` — чтобы во время стрима не было трясёт.
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  // Отслеживаем позицию юзера
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    function onScroll() {
      if (!el) return;
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      // 80px — порог «у низа». Меньше → считаем что юзер хочет автоскролл
      stickToBottomRef.current = distanceFromBottom < 80;
    }
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!stickToBottomRef.current) return;
    // requestAnimationFrame чтобы скроллить ПОСЛЕ того как layout посчитан
    const id = requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "auto", block: "end" });
    });
    return () => cancelAnimationFrame(id);
  }, [messages, currentMessageId]);

  // Закрытие меню экспорта по клику вне его
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!exportMenuRef.current) return;
      if (!exportMenuRef.current.contains(e.target as Node)) {
        setExportMenuOpen(false);
      }
    }
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, []);

  // ── derived: активная ветка (путь от корня к current) ─────────────────────
  const activeBranch = useMemo<MessageDTO[]>(() => {
    if (!currentMessageId || messages.length === 0) return [];
    const byId = new Map(messages.map((m) => [m.id, m]));
    const path: MessageDTO[] = [];
    let id: string | null = currentMessageId;
    while (id) {
      const m = byId.get(id);
      if (!m) break;
      path.unshift(m);
      id = m.parent_id;
    }
    return path;
  }, [messages, currentMessageId]);

  function getSiblings(msg: MessageDTO): MessageDTO[] {
    if (!msg.parent_id) {
      return messages.filter((m) => m.parent_id === null && m.role === msg.role);
    }
    return messages.filter(
      (m) => m.parent_id === msg.parent_id && m.role === msg.role,
    );
  }

  // Считаем количество веток в чате (узлов с N>1 «братьями»)
  const branchCount = useMemo(() => {
    const parentCounts = new Map<string | null, number>();
    for (const m of messages) {
      parentCounts.set(m.parent_id, (parentCounts.get(m.parent_id) ?? 0) + 1);
    }
    let branches = 0;
    for (const c of parentCounts.values()) if (c > 1) branches += c - 1;
    return branches;
  }, [messages]);

  // ── actions ──────────────────────────────────────────────────────────────
  async function toggleAgentMode() {
    if (!chat) return;
    const next = !agentMode;
    setAgentMode(next);
    try {
      await api.chats.update(chat.id, { agent_mode: next });
    } catch {
      setAgentMode(!next);
    }
  }

  async function handleFileUpload(file: File) {
    setUploadError(null);
    setUploadingFile(true);
    try {
      const parsed = await api.files.parse(file);
      setAttachment({ filename: parsed.filename, text: parsed.extracted_text });
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "не удалось прочитать файл");
    } finally {
      setUploadingFile(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function handleSend() {
    const trimmed = composer.trim();
    if (!trimmed && !attachment) return;
    let content = trimmed;
    if (attachment) {
      content =
        `📎 ${attachment.filename}\n\n\`\`\`\n${attachment.text}\n\`\`\`\n\n${trimmed}`.trim();
    }
    sendMessage(content);
    setComposer("");
    setAttachment(null);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  async function handleNodeClick(messageId: string) {
    await switchToBranch(messageId);
    await reloadMessages();
  }

  async function handleNodeContextMenu(e: React.MouseEvent, messageId: string) {
    e.preventDefault();
    const text = prompt("Форк от этого узла. Введите новое сообщение:");
    if (text && text.trim()) {
      forkMessage(messageId, text.trim());
      setGraphOpen(false);
    }
  }

  function startEdit(msg: MessageDTO) {
    setEditingId(msg.id);
    setEditingContent(msg.content);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditingContent("");
  }

  function confirmEdit() {
    if (!editingId || !editingContent.trim()) return;
    forkMessage(editingId, editingContent.trim());
    setEditingId(null);
    setEditingContent("");
  }

  if (!initialized || !user || !chat) {
    return (
      <div className={styles.loading}>
        <span>[runtime] загрузка...</span>
      </div>
    );
  }

  return (
    <div className={styles.layout}>
      <ChatSidebar activeChatId={chatId} />

      <main className={styles.main}>
        {/* Topbar */}
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}>
            <span className={styles.title}>{chat.title}</span>
            <span className={styles.crumb}>·</span>
            <span className={styles.meta}>
              {messages.length} {wordNodes(messages.length)}
            </span>
            {streaming && (
              <>
                <span className={styles.crumb}>·</span>
                <span className={styles.metaLive}>
                  <span className={styles.liveDot} /> стрим
                </span>
              </>
            )}
          </div>

          <div className={styles.topbarRight}>
            <PromptSelect
              chatId={chat.id}
              currentSystemPrompt={chat.system_prompt}
              onChanged={() => loadChat(chatId)}
            />

            <ModelSelect
              chatId={chat.id}
              credentialId={chat.credential_id}
              currentModel={chat.model}
              onModelChange={async () => {
                await loadChat(chatId);
              }}
            />

            <button
              className={`${styles.iconBtn} ${agentMode ? styles.iconBtnOn : ""}`}
              onClick={toggleAgentMode}
              title="Агентный режим: ассистент сначала декомпозирует задачу"
            >
              {agentMode ? "◉" : "○"}
              <span className={styles.iconBtnLabel}>агент</span>
            </button>

            <button
              className={`${styles.iconBtn} ${artifactsOpen ? styles.iconBtnOn : ""}`}
              onClick={() => setArtifactsOpen((v) => !v)}
              title="Артефакты"
            >
              ◫
              <span className={styles.iconBtnLabel}>арт</span>
              {artifactsCount > 0 && !artifactsOpen && (
                <span className={styles.branchBadge}>{artifactsCount}</span>
              )}
            </button>

            <button
              className={`${styles.iconBtn} ${graphOpen ? styles.iconBtnOn : ""}`}
              onClick={() => setGraphOpen((v) => !v)}
              title="Граф диалога"
            >
              <BranchIcon size={13} />
              {branchCount > 0 && !graphOpen && (
                <span className={styles.branchBadge}>{branchCount}</span>
              )}
            </button>

            <div ref={exportMenuRef} className={styles.exportWrap}>
              <button
                className={styles.iconBtn}
                onClick={() => setExportMenuOpen((v) => !v)}
                title="Экспорт чата"
              >
                ⋯
              </button>
              {exportMenuOpen && (
                <div className={styles.exportMenu}>
                  <button
                    className={styles.exportItem}
                    onClick={async () => {
                      setExportMenuOpen(false);
                      await downloadExport(chat.id, "md", chat.title);
                    }}
                  >
                    <span className={styles.exportTag}>MD</span>
                    <span>скачать как markdown</span>
                  </button>
                  <button
                    className={styles.exportItem}
                    onClick={async () => {
                      setExportMenuOpen(false);
                      await downloadExport(chat.id, "json", chat.title);
                    }}
                  >
                    <span className={styles.exportTag}>JSON</span>
                    <span>скачать как json</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Messages */}
        <div className={styles.scroll}>
          <div className={styles.messages} ref={scrollContainerRef}>
            {activeBranch.length === 0 ? (
              <div className={styles.emptyConvo}>
                <div className={styles.emptyTitle}>
                  С чего <span className={styles.emptyAccent}>начнём</span>?
                </div>
                <div className={styles.emptyHint}>
                  // новый чат · напишите запрос внизу
                </div>
                {!chat.credential_id && (
                  <div className={styles.emptyWarn}>
                    ⚠ ключ LLM не выбран — добавьте в{" "}
                    <button
                      className={styles.linkLike}
                      onClick={() => router.push("/settings")}
                    >
                      настройках
                    </button>
                  </div>
                )}
              </div>
            ) : (
              activeBranch.map((m) => {
                const siblings = getSiblings(m);
                const isEditing = editingId === m.id;
                return (
                  <MessageBlock
                    key={m.id}
                    msg={m}
                    siblings={siblings}
                    chatId={chat.id}
                    chatAgentMode={chat.agent_mode}
                    toolCalls={toolCallsByMessage[m.id] || []}
                    segments={segmentsByMessage[m.id] || []}
                    truncated={truncatedMessages.has(m.id)}
                    onContinue={() => sendMessage("продолжай", m.id)}
                    isEditing={isEditing}
                    editingContent={editingContent}
                    setEditingContent={setEditingContent}
                    streaming={streaming}
                    onStartEdit={() => startEdit(m)}
                    onCancelEdit={cancelEdit}
                    onConfirmEdit={confirmEdit}
                    onRegenerate={() => regenerate(m.id)}
                    onSwitchTo={(id) => handleNodeClick(id)}
                  />
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Composer */}
          <div className={styles.composerWrap}>
            <div className={styles.composer}>
              {attachment && (
                <div className={styles.attachmentChip}>
                  <span>📎 {attachment.filename}</span>
                  <span className={styles.chipSize}>
                    · {attachment.text.length.toLocaleString("ru-RU")} симв.
                  </span>
                  <button
                    className={styles.chipRemove}
                    onClick={() => setAttachment(null)}
                  >
                    ×
                  </button>
                </div>
              )}

              {uploadError && (
                <div className={styles.errBanner}>// {uploadError}</div>
              )}
              {error && <div className={styles.errBanner}>// {error}</div>}

              <div className={styles.composerRow}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.pdf,text/plain,application/pdf"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFileUpload(f);
                  }}
                />
                <button
                  className={styles.fileBtn}
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingFile}
                  title=".txt или .pdf (текстовый)"
                >
                  {uploadingFile ? "…" : "+"}
                </button>

                <textarea
                  className={styles.textarea}
                  value={composer}
                  onChange={(e) => setComposer(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    chat.credential_id
                      ? "напишите khasa…  ⏎ — отправить, ⇧⏎ — перенос"
                      : "сначала добавьте ключ LLM в настройках"
                  }
                  disabled={!chat.credential_id || streaming}
                  rows={1}
                />

                <button
                  className={styles.sendBtn}
                  onClick={handleSend}
                  disabled={
                    !chat.credential_id ||
                    streaming ||
                    (!composer.trim() && !attachment)
                  }
                  title="отправить (Enter)"
                >
                  {streaming ? "…" : "→"}
                </button>
              </div>

              <div className={styles.composerHint}>
                <span>txt · pdf до 10 MB</span>
                <span style={{ flex: 1 }} />
                <span>{composer.length} симв.</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      <GraphOverlay
        open={graphOpen}
        onClose={() => setGraphOpen(false)}
        messages={messages}
        currentMessageId={currentMessageId}
        onNodeClick={(id) => {
          handleNodeClick(id);
        }}
        onNodeContextMenu={handleNodeContextMenu}
        branchCount={branchCount}
      />

      <ArtifactPanel
        open={artifactsOpen}
        onClose={() => setArtifactsOpen(false)}
        chatId={chat.id}
        pushedArtifact={lastArtifactPush}
      />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Один блок сообщения. Стиль — минималистичный (как в khasa-dark.jsx):
// meta-строка моноширинным шрифтом + вертикальная цветная полоса слева +
// текст в Inter. Никаких рамок-карточек.
// ─────────────────────────────────────────────────────────────────────────────

interface MessageBlockProps {
  msg: MessageDTO;
  siblings: MessageDTO[];
  chatId: string;
  chatAgentMode: boolean;
  toolCalls: import("@/lib/chat-types").ToolCallDTO[];
  segments: import("@/lib/chat-types").MessageSegment[];
  truncated: boolean;
  onContinue: () => void;
  isEditing: boolean;
  editingContent: string;
  setEditingContent: (s: string) => void;
  streaming: boolean;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onConfirmEdit: () => void;
  onRegenerate: () => void;
  onSwitchTo: (id: string) => void;
}

function MessageBlock({
  msg,
  siblings,
  chatId,
  chatAgentMode,
  toolCalls,
  segments,
  truncated,
  onContinue,
  isEditing,
  editingContent,
  setEditingContent,
  streaming,
  onStartEdit,
  onCancelEdit,
  onConfirmEdit,
  onRegenerate,
  onSwitchTo,
}: MessageBlockProps) {
  const isUser = msg.role === "user";
  const isSystem = msg.role === "system";

  const roleColor = isUser ? "var(--red)" : isSystem ? "var(--muted)" : "var(--green)";
  const roleLabel = isUser ? "you" : isSystem ? "system" : "khasa";

  const hasAlternatives = siblings.length > 1;

  return (
    <article className={styles.msg}>
      {/* meta */}
      <div className={styles.msgMeta}>
        <span
          className={styles.msgDot}
          style={{ background: roleColor }}
        />
        <span
          className={styles.msgRole}
          style={{ color: roleColor, fontWeight: 700 }}
        >
          {roleLabel}
        </span>
        {msg.model && (
          <>
            <span className={styles.msgSep}>·</span>
            <span className={styles.msgModel}>{msg.model}</span>
          </>
        )}
        {msg.status === "streaming" && (
          <>
            <span className={styles.msgSep}>·</span>
            <span className={styles.msgStream}>стрим…</span>
          </>
        )}
        {msg.status === "failed" && (
          <>
            <span className={styles.msgSep}>·</span>
            <span className={styles.msgFailed}>✕ ошибка</span>
          </>
        )}
      </div>

      {/* body */}
      {isEditing ? (
        <div
          className={styles.msgBody}
          style={{ borderColor: "var(--yellow)" }}
        >
          <textarea
            className={styles.editArea}
            value={editingContent}
            onChange={(e) => setEditingContent(e.target.value)}
            rows={Math.min(14, editingContent.split("\n").length + 1)}
            autoFocus
          />
          <div className={styles.editActions}>
            <button className={styles.btnGhost} onClick={onCancelEdit}>
              отмена
            </button>
            <button
              className={styles.btnAccent}
              onClick={onConfirmEdit}
              disabled={!editingContent.trim() || streaming}
            >
              ↳ форк
            </button>
          </div>
          <div className={styles.editHint}>
            // создастся новая ветка с этим текстом · прежняя сохранится
          </div>
        </div>
      ) : segments.length > 0 ? (
        // Interleaved-рендер: text → tool → text → tool → ... в порядке появления.
        // Используется в агент-режиме где сегменты пишутся в БД во время стрима.
        <div className={styles.msgBody} style={{ borderColor: roleColor }}>
          {segments.map((seg, i) => {
            if (seg.kind === "text") {
              if (!seg.content) return null;
              const isLastText =
                msg.status === "streaming" &&
                i === segments.length - 1 &&
                seg.kind === "text";
              return (
                <div key={seg.id} style={{ whiteSpace: "normal" }}>
                  <Markdown content={seg.content} />
                  {isLastText && <span className={styles.caret} />}
                </div>
              );
            }
            // tool_call segment — рендерим тем же ToolCallBlock'ом
            return (
              <ToolCallBlock
                key={seg.id}
                call={{
                  id: seg.id,
                  name: seg.name,
                  input: seg.input,
                  output: seg.output ?? undefined,
                  status: seg.status,
                  is_present_files: seg.is_present_files,
                }}
                chatId={chatId}
              />
            );
          })}
        </div>
      ) : (
        <div
          className={styles.msgBody}
          style={{ borderColor: roleColor }}
        >
          {msg.role === "assistant" && msg.content ? (
            <div style={{ whiteSpace: "normal" }}>
              <Markdown content={msg.content} />
              {msg.status === "streaming" && <span className={styles.caret} />}
            </div>
          ) : (
            <>
              {msg.content || (msg.status === "streaming" ? "…" : "")}
              {msg.status === "streaming" && <span className={styles.caret} />}
            </>
          )}
        </div>
      )}

      {msg.error && <div className={styles.errInline}>// {msg.error}</div>}

      {/* subtasks panel for assistant in agent mode */}
      {!isEditing && msg.role === "assistant" && chatAgentMode && (
        <SubtasksList
          chatId={chatId}
          messageId={msg.id}
          reloadKey={`${msg.status}:${msg.content.length}`}
        />
      )}

      {/* tool calls «снизу единым блоком» — рендерим ТОЛЬКО для старых
          сообщений без segments (до миграции 0007). Новые сообщения
          рендерят tool-calls в составе segments выше. */}
      {!isEditing &&
        msg.role === "assistant" &&
        segments.length === 0 &&
        toolCalls.length > 0 && (
          <div className={styles.toolCalls}>
            {toolCalls.map((call) => (
              <ToolCallBlock key={call.id} call={call} chatId={chatId} />
            ))}
          </div>
        )}

      {/* Кнопка «продолжить» — если упёрлись в AGENT_MAX_TURNS */}
      {!isEditing &&
        msg.role === "assistant" &&
        truncated &&
        !streaming && (
          <div className={styles.truncatedBox}>
            <div className={styles.truncatedText}>
              // упёрлись в лимит итераций tool-use. Модель не закончила.
            </div>
            <button
              className={styles.continueBtn}
              onClick={onContinue}
              type="button"
            >
              продолжить →
            </button>
          </div>
        )}

      {/* actions */}
      {!isEditing && (
        <div className={styles.msgActions}>
          {msg.role === "assistant" && msg.status === "ready" && (
            <button
              className={styles.btnGhost}
              onClick={onRegenerate}
              disabled={streaming}
            >
              ↻ регенерировать
            </button>
          )}
          {isUser && (
            <button
              className={styles.btnGhost}
              onClick={onStartEdit}
              disabled={streaming}
            >
              ✎ редактировать
            </button>
          )}

          {hasAlternatives && (
            <div className={styles.branches}>
              <span className={styles.branchesLabel}>
                <BranchIcon size={10} color="var(--yellow)" />
                {siblings.length}{" "}
                {isUser
                  ? wordVersions(siblings.length)
                  : wordBranches(siblings.length)}
              </span>
              <div className={styles.branchPills}>
                {siblings.map((s, i) => (
                  <button
                    key={s.id}
                    className={`${styles.branchPill} ${s.id === msg.id ? styles.branchPillOn : ""}`}
                    onClick={() => onSwitchTo(s.id)}
                  >
                    {String.fromCharCode(97 + i)}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

// ── small ────────────────────────────────────────────────────────────────────

/**
 * Скачивает экспорт чата. Делаем через fetch+blob чтобы корректно отправить
 * Authorization header — `<a href download>` это не умеет.
 */
async function downloadExport(
  chatId: string,
  format: "md" | "json",
  chatTitle: string,
): Promise<void> {
  const { tokenStorage } = await import("@/lib/token-storage");
  const token = tokenStorage.access;
  const base = process.env.NEXT_PUBLIC_API_URL || "/api";
  try {
    const resp = await fetch(`${base}/v1/chats/${chatId}/export?format=${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) {
      alert(`Не удалось скачать (${resp.status})`);
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeTitle =
      chatTitle.replace(/[^\w\u0400-\u04FF\-_]+/g, "_").slice(0, 60) || "chat";
    a.download = `${safeTitle}.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert(`Ошибка: ${e instanceof Error ? e.message : String(e)}`);
  }
}

function wordNodes(n: number) {
  const m10 = n % 10;
  const m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return "узел";
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return "узла";
  return "узлов";
}

function wordBranches(n: number) {
  const m10 = n % 10;
  if (m10 === 1) return "ветка";
  if (m10 >= 2 && m10 <= 4) return "ветки";
  return "веток";
}

function wordVersions(n: number) {
  const m10 = n % 10;
  if (m10 === 1) return "версия";
  if (m10 >= 2 && m10 <= 4) return "версии";
  return "версий";
}
