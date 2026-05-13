"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Logomark } from "@/components/common/Logomark";
import { Button } from "@/components/common/Button";
import { useAuthStore } from "@/lib/auth-store";
import { api } from "@/lib/api";
import type { ChatDTO } from "@/lib/chat-types";
import styles from "./chat-list.module.css";

export default function ChatList() {
  const router = useRouter();
  const { user, initialized, bootstrap, logout } = useAuthStore();
  const [chats, setChats] = useState<ChatDTO[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [hasCredentials, setHasCredentials] = useState(false);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  useEffect(() => {
    if (initialized && !user) router.replace("/auth/login");
  }, [initialized, user, router]);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const [chatList, credList] = await Promise.all([
          api.chats.list(),
          api.llm.list(),
        ]);
        setChats(chatList.chats);
        setHasCredentials(credList.total > 0);
      } finally {
        setLoading(false);
      }
    })();
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
      const chat = await api.chats.create({
        title: "Новый чат",
        credential_id: first?.id ?? null,
        model: first?.default_model ?? null,
      });
      router.push(`/chat/${chat.id}`);
    } finally {
      setCreating(false);
    }
  }

  if (!initialized || !user || loading) {
    return <div className={styles.loading}>[runtime] загрузка...</div>;
  }

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <Logomark size={28} caption={false} />
        <span style={{ flex: 1 }} />
        <span className={styles.userEmail}>
          {user.email}
          {user.is_superuser && <span className={styles.adminBadge}> · admin</span>}
        </span>
        <Link href="/settings">
          <Button variant="ghost">настройки</Button>
        </Link>
        {user.is_superuser && (
          <Link href="/admin">
            <Button variant="ghost">админ</Button>
          </Link>
        )}
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
        <div className={styles.sidebar}>
          <div className={styles.sidebarHeader}>
            <span className={styles.sidebarTitle}>// чаты</span>
            <button
              className={styles.newButton}
              onClick={createChat}
              disabled={creating}
            >
              + новый
            </button>
          </div>
          {chats.length === 0 ? (
            <div className={styles.emptyList}>
              <p>пока пусто</p>
              <p className={styles.hint}>
                {hasCredentials
                  ? "создайте первый чат →"
                  : "сначала добавьте ключ LLM в настройках"}
              </p>
            </div>
          ) : (
            <ul className={styles.chatList}>
              {chats.map((c) => (
                <li key={c.id}>
                  <Link href={`/chat/${c.id}`} className={styles.chatItem}>
                    <span className={styles.chatTitle}>{c.title}</span>
                    {c.model && <span className={styles.chatModel}>{c.model}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className={styles.welcome}>
          <Logomark size={96} />
          <h1 className={styles.welcomeTitle}>
            С чего <span className={styles.accent}>начнём</span>?
          </h1>
          <p className={styles.welcomeText}>
            {hasCredentials
              ? "Выберите чат слева или создайте новый. Граф диалога — справа от сообщений, ветки переключаются кликом."
              : "Для начала добавьте API-ключ LLM в настройках. Поддерживаются Claude, OpenAI и локальный Ollama."}
          </p>
          {!hasCredentials && (
            <Link href="/settings">
              <Button variant="green">открыть настройки</Button>
            </Link>
          )}
        </div>
      </main>
    </div>
  );
}
