"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SystemPromptDTO } from "@/lib/chat-types";
import styles from "./PromptSelect.module.css";

interface Props {
  chatId: string;
  currentSystemPrompt: string | null;
  onChanged?: () => void;
}

/**
 * Селектор системного промпта для текущего чата.
 *
 * Поведение:
 *   • показывает иконку и название «активного» промпта (или ✎ если кастомный),
 *     или ○ если system_prompt пустой;
 *   • при клике — выпадашка со списком сохранённых промптов (пиннутые сверху),
 *     опцией «без промпта» и опцией «свой текст…» (открывает inline-textarea);
 *   • любой выбор → PATCH /chats/{id} { system_prompt }.
 */
export function PromptSelect({ chatId, currentSystemPrompt, onChanged }: Props) {
  const [open, setOpen] = useState(false);
  const [prompts, setPrompts] = useState<SystemPromptDTO[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [customMode, setCustomMode] = useState(false);
  const [customText, setCustomText] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!ref.current) return;
      if (!ref.current.contains(e.target as Node)) {
        setOpen(false);
        setCustomMode(false);
      }
    }
    document.addEventListener("click", onDoc);
    return () => document.removeEventListener("click", onDoc);
  }, []);

  useEffect(() => {
    setCustomText(currentSystemPrompt ?? "");
  }, [currentSystemPrompt]);

  async function ensureLoaded() {
    if (loaded) return;
    try {
      const r = await api.prompts.list();
      setPrompts(r.prompts);
    } catch {
      /* ничего */
    } finally {
      setLoaded(true);
    }
  }

  // Найти активный промпт (если system_prompt совпадает с одним из библиотечных)
  const activePrompt = prompts.find((p) => p.content === currentSystemPrompt);

  async function pick(promptContent: string | null) {
    try {
      await api.chats.update(chatId, { system_prompt: promptContent });
      onChanged?.();
    } finally {
      setOpen(false);
      setCustomMode(false);
    }
  }

  async function applyCustom() {
    const trimmed = customText.trim();
    await pick(trimmed || null);
  }

  // ── render trigger ──────────────────────────────────────────────────────
  let triggerIcon = "○";
  let triggerLabel = "роль";
  if (activePrompt) {
    triggerIcon = activePrompt.icon ?? "🤖";
    triggerLabel = activePrompt.title;
  } else if (currentSystemPrompt) {
    triggerIcon = "✎";
    triggerLabel = "свой";
  }

  return (
    <div ref={ref} className={styles.wrap}>
      <button
        className={`${styles.trigger} ${currentSystemPrompt ? styles.triggerOn : ""}`}
        onClick={() => {
          setOpen((v) => !v);
          ensureLoaded();
        }}
        title={currentSystemPrompt || "системный промпт не задан"}
      >
        <span className={styles.triggerIcon}>{triggerIcon}</span>
        <span className={styles.triggerLabel}>{triggerLabel}</span>
      </button>

      {open && (
        <div className={styles.menu}>
          {customMode ? (
            <div className={styles.customBox}>
              <div className={styles.customLabel}>// свой системный промпт</div>
              <textarea
                className={styles.customArea}
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                rows={6}
                placeholder="Ты — старший python-разработчик. Отвечай кратко…"
                autoFocus
              />
              <div className={styles.customActions}>
                <button
                  className={styles.smallBtn}
                  onClick={() => {
                    setCustomMode(false);
                    setCustomText(currentSystemPrompt ?? "");
                  }}
                >
                  назад
                </button>
                <button className={styles.primaryBtn} onClick={applyCustom}>
                  применить
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className={styles.menuHeader}>// системный промпт</div>

              <button
                className={`${styles.menuItem} ${!currentSystemPrompt ? styles.menuItemOn : ""}`}
                onClick={() => pick(null)}
              >
                <span className={styles.menuIcon}>○</span>
                <span>без промпта</span>
              </button>

              <button
                className={styles.menuItem}
                onClick={() => setCustomMode(true)}
              >
                <span className={styles.menuIcon}>✎</span>
                <span>свой текст…</span>
              </button>

              {prompts.length > 0 && (
                <>
                  <div className={styles.menuRule} />
                  {prompts.map((p) => (
                    <button
                      key={p.id}
                      className={`${styles.menuItem} ${p.content === currentSystemPrompt ? styles.menuItemOn : ""}`}
                      onClick={() => pick(p.content)}
                    >
                      <span className={styles.menuIcon}>{p.icon ?? "🤖"}</span>
                      <span className={styles.itemTitle}>{p.title}</span>
                      {p.is_pinned && (
                        <span className={styles.pinTag}>◉</span>
                      )}
                    </button>
                  ))}
                </>
              )}

              <div className={styles.menuRule} />
              <Link href="/settings/prompts" className={styles.menuFooter}>
                + управление библиотекой →
              </Link>
            </>
          )}
        </div>
      )}
    </div>
  );
}
