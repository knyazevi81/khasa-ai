"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { LLMCredentialDTO } from "@/lib/chat-types";
import styles from "./settings.module.css";

type Provider = "anthropic" | "openai" | "ollama";

const PROVIDER_LABELS: Record<Provider, string> = {
  anthropic: "Anthropic (Claude)",
  openai: "OpenAI (GPT)",
  ollama: "Ollama (локально)",
};

const PROVIDER_HINTS: Record<Provider, string> = {
  anthropic: "ключ из console.anthropic.com (sk-ant-…)",
  openai: "ключ из platform.openai.com (sk-…)",
  ollama: "URL Ollama-сервера (например, http://localhost:11434)",
};

const PROVIDER_MODEL_PLACEHOLDER: Record<Provider, string> = {
  anthropic: "claude-haiku-4-5",
  openai: "gpt-4o-mini",
  ollama: "llama3.2",
};

const PROVIDER_COLOR: Record<Provider, string> = {
  anthropic: "var(--yellow)",
  openai: "var(--green)",
  ollama: "var(--red)",
};

export default function SettingsPage() {
  const router = useRouter();
  const { user, initialized, bootstrap } = useAuthStore();
  const [creds, setCreds] = useState<LLMCredentialDTO[]>([]);
  const [loading, setLoading] = useState(true);

  const [provider, setProvider] = useState<Provider>("anthropic");
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [defaultModel, setDefaultModel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ kind: "ok" | "err"; text: string } | null>(null);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (initialized && !user) router.replace("/auth/login");
  }, [initialized, user, router]);

  async function reload() {
    const r = await api.llm.list();
    setCreds(r.credentials);
  }

  useEffect(() => {
    if (!user) return;
    reload().finally(() => setLoading(false));
  }, [user]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setToast(null);
    if (!label.trim()) return setFormError("Введите название");
    if (provider !== "ollama" && !secret.trim())
      return setFormError("Введите API-ключ");
    setSubmitting(true);
    try {
      await api.llm.create({
        provider,
        label: label.trim(),
        secret: secret.trim() || "—",
        base_url: baseUrl.trim() || null,
        default_model: defaultModel.trim() || null,
      });
      setLabel("");
      setSecret("");
      setBaseUrl("");
      setDefaultModel("");
      setToast({ kind: "ok", text: "Ключ добавлен" });
      await reload();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setSubmitting(false);
    }
  }

  async function validate(id: string) {
    setToast(null);
    try {
      await api.llm.validate(id);
      setToast({ kind: "ok", text: "Ключ валиден ✓" });
    } catch (e) {
      setToast({
        kind: "err",
        text: `Ключ не работает: ${e instanceof Error ? e.message : ""}`,
      });
    }
  }

  async function remove(id: string) {
    if (!confirm("Удалить этот ключ?")) return;
    await api.llm.delete(id);
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
          <span className={styles.title}>настройки</span>
          <span className={styles.tabActive}>· ключи LLM</span>
          <Link href="/settings/prompts" className={styles.tabLink}>
            · системные промпты
          </Link>
          <Link href="/settings/mcp" className={styles.tabLink}>
            · MCP-серверы
          </Link>
          <span style={{ flex: 1 }} />
          <span className={styles.email}>{user.email}</span>
        </header>

        <div className={styles.scroll}>
          <div className={styles.container}>
            {toast && (
              <div
                className={`${styles.toast} ${toast.kind === "err" ? styles.toastErr : ""}`}
              >
                <span className={styles.toastTag}>
                  [{toast.kind === "ok" ? "ok" : "err"}]
                </span>
                <span>{toast.text}</span>
                <button
                  className={styles.toastClose}
                  onClick={() => setToast(null)}
                >
                  ×
                </button>
              </div>
            )}

            {/* Form */}
            <section className={styles.section}>
              <h2 className={styles.h2}>добавить ключ</h2>
              <p className={styles.subtitle}>
                ключи хранятся зашифрованными (Fernet, secret из .env). наружу — маска
                из первых и последних 4 символов
              </p>

              <form onSubmit={handleAdd} className={styles.form}>
                <div className={styles.providerRow}>
                  {(["anthropic", "openai", "ollama"] as Provider[]).map((p) => (
                    <button
                      type="button"
                      key={p}
                      className={`${styles.providerCard} ${provider === p ? styles.providerCardOn : ""}`}
                      style={
                        provider === p
                          ? ({ "--accent": PROVIDER_COLOR[p] } as React.CSSProperties)
                          : undefined
                      }
                      onClick={() => setProvider(p)}
                    >
                      <span
                        className={styles.providerDot}
                        style={{ background: PROVIDER_COLOR[p] }}
                      />
                      {PROVIDER_LABELS[p]}
                    </button>
                  ))}
                </div>

                <div className={styles.field}>
                  <label className={styles.label}>название</label>
                  <input
                    className={styles.input}
                    type="text"
                    placeholder="например: рабочий"
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                  />
                </div>

                {provider !== "ollama" && (
                  <div className={styles.field}>
                    <label className={styles.label}>API-ключ</label>
                    <input
                      className={styles.input}
                      type="password"
                      placeholder={PROVIDER_HINTS[provider]}
                      value={secret}
                      onChange={(e) => setSecret(e.target.value)}
                      autoComplete="off"
                    />
                  </div>
                )}

                <div className={styles.fieldRow}>
                  <div className={styles.field}>
                    <label className={styles.label}>
                      {provider === "ollama" ? "URL сервера" : "base_url (опц.)"}
                    </label>
                    <input
                      className={styles.input}
                      type="text"
                      placeholder={
                        provider === "ollama"
                          ? "http://localhost:11434"
                          : "оставьте пустым для официального API"
                      }
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                    />
                  </div>

                  <div className={styles.field}>
                    <label className={styles.label}>
                      модель по умолчанию
                    </label>
                    <input
                      className={styles.input}
                      type="text"
                      placeholder={PROVIDER_MODEL_PLACEHOLDER[provider]}
                      value={defaultModel}
                      onChange={(e) => setDefaultModel(e.target.value)}
                    />
                  </div>
                </div>

                {formError && (
                  <div className={styles.err}>// {formError}</div>
                )}

                <div className={styles.formActions}>
                  <button
                    type="submit"
                    className={styles.submitBtn}
                    disabled={submitting}
                  >
                    {submitting ? "добавляем…" : "+ добавить ключ"}
                  </button>
                </div>
              </form>
            </section>

            {/* List */}
            <section className={styles.section}>
              <h2 className={styles.h2}>
                ваши ключи
                <span className={styles.h2Count}>· {creds.length}</span>
              </h2>

              {creds.length === 0 ? (
                <p className={styles.empty}>// пока нет ключей</p>
              ) : (
                <ul className={styles.credList}>
                  {creds.map((c) => (
                    <li key={c.id} className={styles.credCard}>
                      <div className={styles.credHead}>
                        <span
                          className={styles.providerTag}
                          style={{
                            color: PROVIDER_COLOR[c.provider],
                            borderColor: PROVIDER_COLOR[c.provider],
                          }}
                        >
                          {c.provider}
                        </span>
                        <span className={styles.credLabel}>{c.label}</span>
                        {!c.is_active && (
                          <span className={styles.disabled}>· выключен</span>
                        )}
                      </div>
                      <div className={styles.credMeta}>
                        <span>
                          secret: <code>{c.secret_mask}</code>
                        </span>
                        {c.base_url && (
                          <span>
                            url: <code>{c.base_url}</code>
                          </span>
                        )}
                        {c.default_model && (
                          <span>
                            model: <code>{c.default_model}</code>
                          </span>
                        )}
                      </div>
                      <div className={styles.credActions}>
                        <button
                          className={styles.smallBtn}
                          onClick={() => validate(c.id)}
                        >
                          проверить
                        </button>
                        <button
                          className={`${styles.smallBtn} ${styles.smallBtnDanger}`}
                          onClick={() => remove(c.id)}
                        >
                          удалить
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
