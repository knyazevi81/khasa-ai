"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { Logomark } from "@/components/common/Logomark";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import styles from "./welcome.module.css";

export default function ChatWelcome() {
  const router = useRouter();
  const { user, initialized, bootstrap } = useAuthStore();
  const [hasCredentials, setHasCredentials] = useState<boolean | null>(null);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (initialized && !user) router.replace("/auth/login");
  }, [initialized, user, router]);

  useEffect(() => {
    if (!user) return;
    api.llm.list().then((r) => setHasCredentials(r.total > 0));
  }, [user]);

  async function createChat() {
    if (!hasCredentials) {
      router.push("/settings");
      return;
    }
    setCreating(true);
    try {
      const creds = await api.llm.list();
      const first = creds.credentials.find((c) => c.is_active);
      if (!first) {
        router.push("/settings");
        return;
      }
      const chat = await api.chats.create({
        title: "Новый чат",
        credential_id: first.id,
        model: first.default_model ?? null,
      });
      router.push(`/chat/${chat.id}`);
    } finally {
      setCreating(false);
    }
  }

  if (!initialized || !user) {
    return <div className={styles.loading}>[runtime] загрузка…</div>;
  }

  return (
    <div className={styles.layout}>
      <ChatSidebar />

      <main className={styles.main}>
        <div className={styles.center}>
          <Logomark size={88} />
          <h1 className={styles.title}>
            С чего <span className={styles.accent}>начнём</span>?
          </h1>

          {hasCredentials === null ? (
            <p className={styles.hint}>// загрузка…</p>
          ) : hasCredentials ? (
            <>
              <p className={styles.hint}>
                выберите чат слева или создайте новый
              </p>
              <button
                className={styles.cta}
                onClick={createChat}
                disabled={creating}
              >
                <span className={styles.ctaPlus}>+</span>
                {creating ? "создаём…" : "новый чат"}
              </button>
            </>
          ) : (
            <>
              <p className={styles.hint}>
                сначала добавьте ключ LLM
                <br />
                <span className={styles.hintMuted}>
                  поддерживаются Claude, OpenAI и локальный Ollama
                </span>
              </p>
              <Link href="/settings" className={styles.cta}>
                <span className={styles.ctaPlus}>⚙</span>
                открыть настройки
              </Link>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
