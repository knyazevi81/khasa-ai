"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Logomark } from "@/components/common/Logomark";
import { Button } from "@/components/common/Button";
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
  anthropic: "ключ из console.anthropic.com (начинается с sk-ant-)",
  openai: "ключ из platform.openai.com (начинается с sk-)",
  ollama: "URL вашего Ollama-сервера (например, http://localhost:11434)",
};

const PROVIDER_MODEL_PLACEHOLDER: Record<Provider, string> = {
  anthropic: "claude-haiku-4-5",
  openai: "gpt-4o-mini",
  ollama: "llama3.2",
};

export default function SettingsPage() {
  const router = useRouter();
  const { user, initialized, bootstrap } = useAuthStore();
  const [creds, setCreds] = useState<LLMCredentialDTO[]>([]);
  const [loading, setLoading] = useState(true);

  // форма добавления
  const [provider, setProvider] = useState<Provider>("anthropic");
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [defaultModel, setDefaultModel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

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
    if (!label.trim()) {
      setFormError("Введите название");
      return;
    }
    if (provider !== "ollama" && !secret.trim()) {
      setFormError("Введите API-ключ");
      return;
    }
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
      setToast("Ключ добавлен");
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
      setToast("Ключ валиден ✓");
    } catch (e) {
      setToast(`Ключ не работает: ${e instanceof Error ? e.message : ""}`);
    }
  }

  async function remove(id: string) {
    if (!confirm("Удалить этот ключ?")) return;
    await api.llm.delete(id);
    await reload();
  }

  if (!initialized || !user || loading) {
    return <div className={styles.loading}>[runtime] загрузка...</div>;
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Link href="/chat" className={styles.logoLink}>
          <Logomark size={24} caption={false} />
        </Link>
        <span className={styles.title}>// настройки · ключи LLM</span>
        <span style={{ flex: 1 }} />
        <Link href="/chat">
          <Button variant="ghost">← к чатам</Button>
        </Link>
      </header>

      <main className={styles.main}>
        {toast && <div className={styles.toast}>{toast}</div>}

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>добавить ключ</h2>
          <p className={styles.sectionHint}>
            ключи хранятся в БД зашифрованными (Fernet). показываем только
            первые 4 и последние 4 символа.
          </p>

          <form onSubmit={handleAdd} className={styles.form}>
            <div className={styles.formRow}>
              <label className={styles.label}>
                провайдер
                <select
                  className={styles.select}
                  value={provider}
                  onChange={(e) => setProvider(e.target.value as Provider)}
                >
                  {Object.entries(PROVIDER_LABELS).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.label}>
                название
                <input
                  className={styles.input}
                  type="text"
                  placeholder="например: рабочий"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                />
              </label>
            </div>

            {provider !== "ollama" && (
              <label className={styles.label}>
                API-ключ
                <input
                  className={styles.input}
                  type="password"
                  placeholder={PROVIDER_HINTS[provider]}
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  autoComplete="off"
                />
              </label>
            )}

            <label className={styles.label}>
              {provider === "ollama" ? "URL сервера" : "base_url (опционально)"}
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
            </label>

            <label className={styles.label}>
              модель по умолчанию (опционально)
              <input
                className={styles.input}
                type="text"
                placeholder={PROVIDER_MODEL_PLACEHOLDER[provider]}
                value={defaultModel}
                onChange={(e) => setDefaultModel(e.target.value)}
              />
            </label>

            {formError && <div className={styles.errorBox}>// {formError}</div>}

            <div className={styles.formActions}>
              <Button variant="green" loading={submitting} type="submit">
                добавить ключ
              </Button>
            </div>
          </form>
        </section>

        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>ваши ключи · {creds.length}</h2>
          {creds.length === 0 ? (
            <p className={styles.empty}>пока нет ключей</p>
          ) : (
            <ul className={styles.credsList}>
              {creds.map((c) => (
                <li key={c.id} className={styles.credCard}>
                  <div className={styles.credHead}>
                    <span
                      className={styles.providerTag}
                      data-provider={c.provider}
                    >
                      {c.provider}
                    </span>
                    <span className={styles.credLabel}>{c.label}</span>
                    {!c.is_active && (
                      <span className={styles.disabledTag}>· выключен</span>
                    )}
                  </div>
                  <div className={styles.credMeta}>
                    <span>secret: <code>{c.secret_mask}</code></span>
                    {c.base_url && <span>url: <code>{c.base_url}</code></span>}
                    {c.default_model && <span>model: <code>{c.default_model}</code></span>}
                  </div>
                  <div className={styles.credActions}>
                    <button
                      className={styles.smallButton}
                      onClick={() => validate(c.id)}
                    >
                      проверить
                    </button>
                    <button
                      className={`${styles.smallButton} ${styles.dangerButton}`}
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
      </main>
    </div>
  );
}
