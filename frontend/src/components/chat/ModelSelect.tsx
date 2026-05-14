"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import styles from "./ModelSelect.module.css";

interface Props {
  chatId: string;
  credentialId: string | null;
  currentModel: string | null;
  onModelChange?: (model: string) => void;
}

/**
 * Компактный dropdown для выбора модели в шапке чата.
 * Модели подгружаются один раз — кэшируются в state. Если у юзера
 * сменился credential — список перечитается.
 */
export function ModelSelect({
  chatId,
  credentialId,
  currentModel,
  onModelChange,
}: Props) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, []);

  async function ensureLoaded() {
    if (models || loading || !credentialId) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.llm.models(credentialId);
      setModels(r.models);
      if (r.models.length === 0) setError("список моделей пуст");
    } catch (e) {
      setError(e instanceof Error ? e.message : "не удалось загрузить");
    } finally {
      setLoading(false);
    }
  }

  async function pick(m: string) {
    setOpen(false);
    try {
      await api.chats.update(chatId, { model: m });
      onModelChange?.(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : "не удалось сохранить");
    }
  }

  return (
    <div ref={ref} className={styles.wrap}>
      <button
        className={styles.trigger}
        disabled={!credentialId}
        onClick={() => {
          setOpen((v) => !v);
          ensureLoaded();
        }}
        title={!credentialId ? "сначала выберите ключ LLM" : "сменить модель"}
      >
        <span className={styles.label}>{currentModel || "модель"}</span>
        <span className={styles.chev}>▾</span>
      </button>

      {open && (
        <div className={styles.menu}>
          <div className={styles.menuHeader}>// доступные модели</div>
          {loading && <div className={styles.menuLoading}>загрузка…</div>}
          {error && <div className={styles.menuError}>// {error}</div>}
          {models && models.length > 0 && (
            <ul className={styles.menuList}>
              {models.map((m) => (
                <li key={m}>
                  <button
                    className={`${styles.menuItem} ${m === currentModel ? styles.menuItemOn : ""}`}
                    onClick={() => pick(m)}
                  >
                    {m === currentModel && (
                      <span className={styles.dot}>●</span>
                    )}
                    <span>{m}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
