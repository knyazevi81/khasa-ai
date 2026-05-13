"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Logomark } from "@/components/common/Logomark";
import { Button } from "@/components/common/Button";
import { GraphView } from "@/components/chat/GraphView";
import { SubtasksList } from "@/components/chat/SubtasksList";
import { useAuthStore } from "@/lib/auth-store";
import { useChatStore } from "@/lib/chat-store";
import { api } from "@/lib/api";
import type { MessageDTO, ChatDTO } from "@/lib/chat-types";
import styles from "./chat.module.css";

export default function ChatDetail() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const chatId = params.id;
  const { user, initialized, bootstrap, logout } = useAuthStore();
  const {
    chat,
    messages,
    currentMessageId,
    streaming,
    error,
    loadChat,
    connect,
    disconnect,
    sendMessage,
    regenerate,
    forkMessage,
    switchToBranch,
    reloadMessages,
  } = useChatStore();

  const [allChats, setAllChats] = useState<ChatDTO[]>([]);
  const [composer, setComposer] = useState("");
  const [attachment, setAttachment] = useState<{ filename: string; text: string } | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Редактирование user-сообщения (edit-and-fork)
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [agentMode, setAgentMode] = useState(false);

  // ── auth gate ────────────────────────────────────────────────────────────
  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (initialized && !user) router.replace("/auth/login");
  }, [initialized, user, router]);

  // ── load chat + connect ws ───────────────────────────────────────────────
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

  // Подтянем agent_mode из чата
  useEffect(() => {
    if (chat) setAgentMode(chat.agent_mode);
  }, [chat?.id, chat?.agent_mode]);

  async function toggleAgentMode() {
    if (!chat) return;
    const next = !agentMode;
    setAgentMode(next);
    try {
      await api.chats.update(chat.id, { agent_mode: next });
    } catch {
      setAgentMode(!next); // откатим при ошибке
    }
  }

  // ── load sidebar list ────────────────────────────────────────────────────
  useEffect(() => {
    if (!user) return;
    api.chats.list().then((r) => setAllChats(r.chats));
  }, [user, chat?.title]);

  // ── auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, currentMessageId]);

  // ── активная ветка: путь от корня к currentMessageId ─────────────────────
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

  // Альтернативные ветки: для каждого assistant-сообщения в активной ветке
  // ищем «братьев» по тому же parent_id
  function getSiblings(msg: MessageDTO): MessageDTO[] {
    if (msg.role !== "assistant" || !msg.parent_id) return [];
    return messages.filter(
      (m) => m.parent_id === msg.parent_id && m.role === "assistant",
    );
  }

  // То же для user-сообщений (edit-and-fork создаёт user-братьев)
  function getUserSiblings(msg: MessageDTO, all: MessageDTO[]): MessageDTO[] {
    if (msg.role !== "user") return [];
    return all.filter(
      (m) => m.parent_id === msg.parent_id && m.role === "user",
    );
  }

  function hasUserSiblings(msg: MessageDTO, all: MessageDTO[]): boolean {
    return getUserSiblings(msg, all).length > 1;
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
      content = `📎 ${attachment.filename}\n\n\`\`\`\n${attachment.text}\n\`\`\`\n\n${trimmed}`.trim();
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

  async function handleNodeContextMenu(e: React.MouseEvent, messageId: string) {
    // Произвольный форк от любого узла графа (правый клик).
    // Открываем prompt — это минималистичный UX для MVP.
    e.preventDefault();
    const text = prompt("Форк от этого узла. Введите новое сообщение:");
    if (text && text.trim()) {
      forkMessage(messageId, text.trim());
    }
  }

  if (!initialized || !user || !chat) {
    return <div className={styles.loading}>[runtime] загрузка...</div>;
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link href="/chat" className={styles.logoLink}>
          <Logomark size={24} caption={false} />
        </Link>
        <span className={styles.chatTitle}>{chat.title}</span>
        <span className={styles.metaSep}>·</span>
        <span className={styles.chatMeta}>
          {chat.model || "—"} · {messages.length} узлов
        </span>
        <span style={{ flex: 1 }} />

        <button
          className={`${styles.agentToggle} ${agentMode ? styles.agentToggleOn : ""}`}
          onClick={toggleAgentMode}
          title="Агентный режим: ассистент сначала декомпозирует задачу"
        >
          {agentMode ? "◉ агент" : "○ агент"}
        </button>

        <span className={styles.userEmail}>{user.email}</span>
        <Link href="/settings">
          <Button variant="ghost">настройки</Button>
        </Link>
        <Button
          variant="ghost"
          onClick={async () => {
            await logout();
            router.replace("/auth/login");
          }}
        >
          выйти
        </Button>
      </header>

      <main className={styles.main}>
        {/* ── sidebar: список чатов ────────────────────────────── */}
        <aside className={styles.sidebar}>
          <div className={styles.sidebarHeader}>
            <span className={styles.sidebarTitle}>// чаты</span>
            <Link href="/chat" className={styles.newLink}>+ новый</Link>
          </div>
          <ul className={styles.chatList}>
            {allChats.map((c) => (
              <li key={c.id}>
                <Link
                  href={`/chat/${c.id}`}
                  className={`${styles.chatItem} ${c.id === chatId ? styles.chatItemActive : ""}`}
                >
                  {c.title}
                </Link>
              </li>
            ))}
          </ul>
        </aside>

        {/* ── центральная колонка: сообщения активной ветки ───── */}
        <section className={styles.conversation}>
          <div className={styles.messages}>
            {activeBranch.length === 0 ? (
              <div className={styles.emptyConvo}>
                <p className={styles.emptyHint}>
                  // пустой чат · начните диалог снизу
                </p>
                {!chat.credential_id && (
                  <p className={styles.emptyHint}>
                    ⚠ ключ LLM не выбран — добавьте в{" "}
                    <Link href="/settings" className={styles.inlineLink}>
                      настройках
                    </Link>
                  </p>
                )}
              </div>
            ) : (
              activeBranch.map((m) => {
                const siblings = getSiblings(m);
                const hasAlternatives = siblings.length > 1;
                const isEditing = editingId === m.id;
                return (
                  <article
                    key={m.id}
                    className={`${styles.message} ${styles[`role_${m.role}`]}`}
                    data-status={m.status}
                  >
                    <div className={styles.messageHead}>
                      <span className={styles.messageRole}>
                        {m.role === "user"
                          ? "you"
                          : m.role === "assistant"
                            ? "khasa"
                            : "system"}
                      </span>
                      {m.model && (
                        <span className={styles.messageModel}>{m.model}</span>
                      )}
                      {m.status === "streaming" && (
                        <span className={styles.streamDot}>● стрим</span>
                      )}
                      {m.status === "failed" && (
                        <span className={styles.failedTag}>✕ ошибка</span>
                      )}
                    </div>

                    {isEditing ? (
                      <div className={styles.editBox}>
                        <textarea
                          className={styles.editTextarea}
                          value={editingContent}
                          onChange={(e) => setEditingContent(e.target.value)}
                          rows={Math.min(12, editingContent.split("\n").length + 1)}
                          autoFocus
                        />
                        <div className={styles.editActions}>
                          <button
                            className={styles.actionButton}
                            onClick={cancelEdit}
                          >
                            отмена
                          </button>
                          <button
                            className={`${styles.actionButton} ${styles.primaryButton}`}
                            onClick={confirmEdit}
                            disabled={!editingContent.trim() || streaming}
                          >
                            ↳ форк
                          </button>
                        </div>
                        <p className={styles.editHint}>
                          // создастся новая ветка с этим текстом, прежнее сообщение сохранится
                        </p>
                      </div>
                    ) : (
                      <div className={styles.messageContent}>
                        {m.content || (m.status === "streaming" ? "..." : "")}
                        {m.status === "streaming" && (
                          <span className={styles.caret} />
                        )}
                      </div>
                    )}

                    {m.error && (
                      <div className={styles.errorBox}>// {m.error}</div>
                    )}

                    {m.role === "assistant" && chat.agent_mode && (
                      <SubtasksList
                        chatId={chat.id}
                        messageId={m.id}
                        reloadKey={`${m.status}:${m.content.length}`}
                      />
                    )}

                    {!isEditing && (m.role === "assistant" && m.status === "ready") && (
                      <div className={styles.messageActions}>
                        <button
                          className={styles.actionButton}
                          onClick={() => regenerate(m.id)}
                          disabled={streaming}
                        >
                          ↻ регенерировать
                        </button>

                        {hasAlternatives && (
                          <div className={styles.branchSwitcher}>
                            <span className={styles.branchLabel}>
                              ветки ({siblings.length}):
                            </span>
                            {siblings.map((s, i) => (
                              <button
                                key={s.id}
                                className={`${styles.branchPill} ${s.id === m.id ? styles.branchPillActive : ""}`}
                                onClick={() => handleNodeClick(s.id)}
                              >
                                {String.fromCharCode(97 + i)}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {!isEditing && m.role === "user" && (
                      <div className={styles.messageActions}>
                        <button
                          className={styles.actionButton}
                          onClick={() => startEdit(m)}
                          disabled={streaming}
                        >
                          ✎ редактировать
                        </button>

                        {hasUserSiblings(m, messages) && (
                          <div className={styles.branchSwitcher}>
                            <span className={styles.branchLabel}>
                              версии:
                            </span>
                            {getUserSiblings(m, messages).map((s, i) => (
                              <button
                                key={s.id}
                                className={`${styles.branchPill} ${s.id === m.id ? styles.branchPillActive : ""}`}
                                onClick={() => handleNodeClick(s.id)}
                              >
                                {String.fromCharCode(97 + i)}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                );
              })
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* composer */}
          <div className={styles.composer}>
            {attachment && (
              <div className={styles.attachmentChip}>
                <span>📎 {attachment.filename}</span>
                <span className={styles.attachmentSize}>
                  · {attachment.text.length.toLocaleString("ru-RU")} симв.
                </span>
                <button
                  className={styles.attachmentRemove}
                  onClick={() => setAttachment(null)}
                >
                  ✕
                </button>
              </div>
            )}
            {uploadError && (
              <div className={styles.uploadError}>// {uploadError}</div>
            )}
            {error && (
              <div className={styles.uploadError}>// {error}</div>
            )}

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
                className={styles.fileButton}
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingFile}
                title=".txt или .pdf (текстовый)"
              >
                {uploadingFile ? "..." : "📎"}
              </button>

              <textarea
                className={styles.textarea}
                value={composer}
                onChange={(e) => setComposer(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  chat.credential_id
                    ? "напишите сообщение... (Enter — отправить, Shift+Enter — перенос)"
                    : "сначала добавьте ключ LLM в настройках"
                }
                disabled={!chat.credential_id || streaming}
                rows={3}
              />

              <button
                className={styles.sendButton}
                onClick={handleSend}
                disabled={
                  !chat.credential_id ||
                  streaming ||
                  (!composer.trim() && !attachment)
                }
              >
                {streaming ? "..." : "→"}
              </button>
            </div>
          </div>
        </section>

        {/* ── граф диалога справа ───────────────────────────────── */}
        <aside className={styles.graphPanel}>
          <GraphView
            messages={messages}
            currentMessageId={currentMessageId}
            onNodeClick={handleNodeClick}
            onNodeContextMenu={handleNodeContextMenu}
          />
        </aside>
      </main>
    </div>
  );
}
