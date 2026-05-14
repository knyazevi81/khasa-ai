"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { SystemPromptDTO } from "@/lib/chat-types";
import styles from "./prompts.module.css";

const ICON_OPTIONS = ["🤖", "🐍", "✏️", "🌍", "💼", "🎓", "🔍", "📊", "🎨", "⚙️"];

export default function PromptsPage() {
  const router = useRouter();
  const { user, initialized, bootstrap } = useAuthStore();
  const [prompts, setPrompts] = useState<SystemPromptDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<SystemPromptDTO | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [description, setDescription] = useState("");
  const [icon, setIcon] = useState<string>("🤖");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (initialized && !user) router.replace("/auth/login");
  }, [initialized, user, router]);

  async function reload() {
    const r = await api.prompts.list();
    setPrompts(r.prompts);
  }

  useEffect(() => {
    if (!user) return;
    reload().finally(() => setLoading(false));
  }, [user]);

  function openCreate() {
    setEditing(null);
    setTitle("");
    setContent("");
    setDescription("");
    setIcon("🤖");
    setError(null);
    setShowForm(true);
  }

  function openEdit(p: SystemPromptDTO) {
    setEditing(p);
    setTitle(p.title);
    setContent(p.content);
    setDescription(p.description ?? "");
    setIcon(p.icon ?? "🤖");
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
    if (!title.trim()) return setError("Введите название");
    if (!content.trim()) return setError("Введите текст промпта");
    setSubmitting(true);
    try {
      if (editing) {
        await api.prompts.update(editing.id, {
          title: title.trim(),
          content: content.trim(),
          description: description.trim() || null,
          icon: icon || null,
        });
      } else {
        await api.prompts.create({
          title: title.trim(),
          content: content.trim(),
          description: description.trim() || null,
          icon: icon || null,
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

  async function togglePinned(p: SystemPromptDTO) {
    await api.prompts.update(p.id, { is_pinned: !p.is_pinned });
    await reload();
  }

  async function remove(p: SystemPromptDTO) {
    if (!confirm(`Удалить «${p.title}»?`)) return;
    await api.prompts.delete(p.id);
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
          <span className={styles.title}>системные промпты</span>
          <span style={{ flex: 1 }} />
          <button className={styles.newBtn} onClick={openCreate}>
            + новый
          </button>
        </header>

        <div className={styles.scroll}>
          <div className={styles.container}>
            <p className={styles.subtitle}>
              Промпты задают «роль» ассистента в чате. При создании нового чата
              можно выбрать один из закреплённых.
            </p>

            {prompts.length === 0 ? (
              <div className={styles.empty}>
                <p>// библиотека пуста</p>
                <button className={styles.emptyCta} onClick={openCreate}>
                  + создать первый
                </button>
              </div>
            ) : (
              <ul className={styles.list}>
                {prompts.map((p) => (
                  <li key={p.id} className={styles.card}>
                    <div className={styles.cardHead}>
                      <span className={styles.cardIcon}>{p.icon ?? "🤖"}</span>
                      <span className={styles.cardTitle}>{p.title}</span>
                      {p.is_pinned && (
                        <span className={styles.pinned} title="закреплён">
                          ◉ закреплён
                        </span>
                      )}
                    </div>
                    {p.description && (
                      <div className={styles.cardDesc}>{p.description}</div>
                    )}
                    <pre className={styles.cardPreview}>{p.content}</pre>
                    <div className={styles.cardActions}>
                      <button
                        className={styles.smallBtn}
                        onClick={() => togglePinned(p)}
                      >
                        {p.is_pinned ? "открепить" : "закрепить"}
                      </button>
                      <button
                        className={styles.smallBtn}
                        onClick={() => openEdit(p)}
                      >
                        редактировать
                      </button>
                      <button
                        className={`${styles.smallBtn} ${styles.dangerBtn}`}
                        onClick={() => remove(p)}
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

      {/* Модалка создания/редактирования */}
      {showForm && (
        <div className={styles.scrim} onClick={closeForm}>
          <form
            className={styles.modal}
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSubmit}
          >
            <header className={styles.modalHead}>
              <span className={styles.modalTitle}>
                {editing ? "редактировать промпт" : "новый промпт"}
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
                <label className={styles.label}>иконка</label>
                <div className={styles.iconRow}>
                  {ICON_OPTIONS.map((i) => (
                    <button
                      key={i}
                      type="button"
                      className={`${styles.iconBtn} ${i === icon ? styles.iconBtnOn : ""}`}
                      onClick={() => setIcon(i)}
                    >
                      {i}
                    </button>
                  ))}
                </div>
              </div>

              <div className={styles.field}>
                <label className={styles.label}>название</label>
                <input
                  className={styles.input}
                  type="text"
                  placeholder="например: Помощник по Python"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={120}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label}>описание (опц.)</label>
                <input
                  className={styles.input}
                  type="text"
                  placeholder="короткое пояснение для библиотеки"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  maxLength={300}
                />
              </div>

              <div className={styles.field}>
                <label className={styles.label}>
                  текст промпта (system message)
                </label>
                <textarea
                  className={styles.textarea}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  rows={10}
                  placeholder="Ты — старший python-разработчик. Отвечай кратко, давай готовый код, объясняй только нетривиальные места…"
                />
                <div className={styles.charCounter}>
                  {content.length.toLocaleString("ru-RU")} симв.
                </div>
              </div>

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
                {submitting ? "сохраняем…" : editing ? "сохранить" : "создать"}
              </button>
            </footer>
          </form>
        </div>
      )}
    </div>
  );
}
