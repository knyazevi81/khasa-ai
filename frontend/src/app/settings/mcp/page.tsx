"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { MCPServerDTO } from "@/lib/chat-types";
import styles from "./mcp.module.css";

type Transport = "sse" | "http" | "stdio";

export default function MCPPage() {
  const router = useRouter();
  const { user, initialized, bootstrap } = useAuthStore();
  const [servers, setServers] = useState<MCPServerDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<MCPServerDTO | null>(null);

  // form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [transport, setTransport] = useState<Transport>("sse");
  const [url, setUrl] = useState("");
  const [commandText, setCommandText] = useState(""); // JSON для stdio
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validating, setValidating] = useState<string | null>(null);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (initialized && !user) router.replace("/auth/login");
  }, [initialized, user, router]);

  async function reload() {
    const r = await api.mcp.list();
    setServers(r.servers);
  }

  useEffect(() => {
    if (!user) return;
    reload().finally(() => setLoading(false));
  }, [user]);

  function openCreate() {
    setEditing(null);
    setName("");
    setDescription("");
    setTransport("sse");
    setUrl("");
    setCommandText("");
    setError(null);
    setShowForm(true);
  }

  function openEdit(s: MCPServerDTO) {
    setEditing(s);
    setName(s.name);
    setDescription(s.description ?? "");
    setTransport(s.transport);
    setUrl(s.url ?? "");
    setCommandText(s.command ? JSON.stringify(s.command, null, 2) : "");
    setError(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditing(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return setError("Введите название");
    if (transport !== "stdio" && !url.trim())
      return setError("Введите URL для sse/http транспорта");

    let command: Record<string, any> | null = null;
    if (transport === "stdio") {
      try {
        command = commandText.trim() ? JSON.parse(commandText) : null;
      } catch {
        return setError(
          "command — некорректный JSON. Пример: {\"command\":\"node\",\"args\":[\"server.js\"]}",
        );
      }
    }

    setSubmitting(true);
    try {
      if (editing) {
        await api.mcp.update(editing.id, {
          name: name.trim(),
          description: description.trim() || null,
          transport,
          url: transport !== "stdio" ? url.trim() : null,
          command: transport === "stdio" ? command : null,
        });
      } else {
        await api.mcp.create({
          name: name.trim(),
          description: description.trim() || null,
          transport,
          url: transport !== "stdio" ? url.trim() : null,
          command: transport === "stdio" ? command : null,
        });
      }
      await reload();
      closeForm();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setSubmitting(false);
    }
  }

  async function validate(s: MCPServerDTO) {
    setValidating(s.id);
    try {
      const r = await api.mcp.validate(s.id);
      alert(
        `Подключение OK. Получено ${r.tools.length} tool(s):\n\n` +
          r.tools.map((t) => `· ${t.name}`).join("\n"),
      );
      await reload();
    } catch (e) {
      alert("Ошибка: " + (e instanceof Error ? e.message : String(e)));
    } finally {
      setValidating(null);
    }
  }

  async function toggleEnabled(s: MCPServerDTO) {
    await api.mcp.update(s.id, { is_enabled: !s.is_enabled });
    await reload();
  }

  async function remove(s: MCPServerDTO) {
    if (!confirm(`Удалить «${s.name}»?`)) return;
    await api.mcp.delete(s.id);
    await reload();
  }

  if (!initialized || !user || loading) {
    return <div className={styles.loading}>[runtime] загрузка…</div>;
  }

  return (
    <div className={styles.layout}>
      <ChatSidebar />

      <main className={styles.main}>
        <header className={styles.topbar}>
          <Link href="/settings" className={styles.crumbsLink}>
            ← настройки
          </Link>
          <span className={styles.crumbs}>·</span>
          <span className={styles.title}>MCP-серверы</span>
          <span style={{ flex: 1 }} />
          <button className={styles.newBtn} onClick={openCreate}>
            + подключить
          </button>
        </header>

        <div className={styles.scroll}>
          <div className={styles.container}>
            <p className={styles.subtitle}>
              <strong>Model Context Protocol</strong> — открытый стандарт
              Anthropic для подключения сторонних инструментов к LLM. Тут можно
              прописать MCP-сервер (URL для sse/http или команду для stdio), и
              его tools станут доступны ассистенту в агентном режиме.
            </p>

            {servers.length === 0 ? (
              <div className={styles.empty}>
                <p>// серверы не подключены</p>
                <p className={styles.emptyHint}>
                  Готовые серверы: <code>filesystem</code>, <code>git</code>,
                  <code>postgres</code>, <code>brave-search</code> — см.{" "}
                  <a
                    href="https://github.com/modelcontextprotocol/servers"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    официальный список
                  </a>
                </p>
                <button className={styles.emptyCta} onClick={openCreate}>
                  + подключить первый
                </button>
              </div>
            ) : (
              <ul className={styles.list}>
                {servers.map((s) => (
                  <li key={s.id} className={styles.card}>
                    <div className={styles.cardHead}>
                      <span
                        className={styles.transportBadge}
                        style={{
                          color: s.transport === "stdio" ? "var(--yellow)" : "var(--green)",
                          borderColor:
                            s.transport === "stdio" ? "var(--yellow)" : "var(--green)",
                        }}
                      >
                        {s.transport}
                      </span>
                      <span className={styles.cardTitle}>{s.name}</span>
                      {!s.is_enabled && (
                        <span className={styles.disabledTag}>выключен</span>
                      )}
                    </div>
                    {s.description && (
                      <div className={styles.cardDesc}>{s.description}</div>
                    )}
                    <div className={styles.cardMeta}>
                      {s.url && (
                        <span>
                          url: <code>{s.url}</code>
                        </span>
                      )}
                      {s.command && (
                        <span>
                          command: <code>{JSON.stringify(s.command)}</code>
                        </span>
                      )}
                      {s.tools_cache?.tools && (
                        <span>
                          tools: <code>{s.tools_cache.tools.length}</code>
                        </span>
                      )}
                    </div>
                    <div className={styles.cardActions}>
                      <button
                        className={styles.smallBtn}
                        onClick={() => validate(s)}
                        disabled={validating === s.id}
                      >
                        {validating === s.id ? "проверка…" : "проверить + tools"}
                      </button>
                      <button
                        className={styles.smallBtn}
                        onClick={() => toggleEnabled(s)}
                      >
                        {s.is_enabled ? "выключить" : "включить"}
                      </button>
                      <button
                        className={styles.smallBtn}
                        onClick={() => openEdit(s)}
                      >
                        редактировать
                      </button>
                      <button
                        className={`${styles.smallBtn} ${styles.dangerBtn}`}
                        onClick={() => remove(s)}
                      >
                        удалить
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </main>

      {showForm && (
        <div className={styles.scrim} onClick={closeForm}>
          <form
            className={styles.modal}
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSubmit}
          >
            <header className={styles.modalHead}>
              <span className={styles.modalTitle}>
                {editing ? "редактировать MCP-сервер" : "новый MCP-сервер"}
              </span>
              <button
                type="button"
                className={styles.closeBtn}
                onClick={closeForm}
              >
                ×
              </button>
            </header>

            <div className={styles.modalBody}>
              <div className={styles.field}>
                <label className={styles.label}>название</label>
                <input
                  className={styles.input}
                  type="text"
                  placeholder="например: filesystem"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  maxLength={120}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label}>описание (опц.)</label>
                <input
                  className={styles.input}
                  type="text"
                  placeholder="что делает сервер"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={300}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label}>транспорт</label>
                <div className={styles.transportRow}>
                  {(["sse", "http", "stdio"] as Transport[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      className={`${styles.transportBtn} ${t === transport ? styles.transportBtnOn : ""}`}
                      onClick={() => setTransport(t)}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {transport !== "stdio" ? (
                <div className={styles.field}>
                  <label className={styles.label}>URL сервера</label>
                  <input
                    className={styles.input}
                    type="url"
                    placeholder="https://mcp.example.com/sse"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                </div>
              ) : (
                <div className={styles.field}>
                  <label className={styles.label}>command (JSON)</label>
                  <textarea
                    className={styles.textarea}
                    rows={6}
                    placeholder={'{"command": "node", "args": ["server.js"]}'}
                    value={commandText}
                    onChange={(e) => setCommandText(e.target.value)}
                  />
                  <div className={styles.hint}>
                    Для stdio backend должен иметь доступ к исполняемому файлу.
                  </div>
                </div>
              )}

              {error && <div className={styles.errBox}>// {error}</div>}
            </div>

            <footer className={styles.modalFoot}>
              <button
                type="button"
                className={styles.smallBtn}
                onClick={closeForm}
              >
                отмена
              </button>
              <button
                type="submit"
                className={styles.primaryBtn}
                disabled={submitting}
              >
                {submitting
                  ? "сохраняем…"
                  : editing
                    ? "сохранить"
                    : "подключить"}
              </button>
            </footer>
          </form>
        </div>
      )}
    </div>
  );
}
