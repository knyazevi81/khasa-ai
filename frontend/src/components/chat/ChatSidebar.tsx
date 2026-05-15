"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { Logomark } from "@/components/common/Logomark";
import { Avatar } from "@/components/common/Avatar";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type { ChatDTO } from "@/lib/chat-types";
import styles from "./ChatSidebar.module.css";

interface Props {
  /** Текущий чат — для подсветки активного пункта. */
  activeChatId?: string;
  /** Триггер для перезагрузки списка (например, при создании/удалении). */
  reloadKey?: number;
}

/**
 * Левый сайдбар чат-зоны: логотип, «новый», список чатов, профиль внизу
 * с выпадающим меню (настройки / выход).
 *
 * Спроектирован как **самостоятельный компонент** — не привязан к странице
 * списка чатов. Любая страница в `/chat/*` его рендерит.
 */
export function ChatSidebar({ activeChatId, reloadKey = 0 }: Props) {
  const router = useRouter();
  const params = useParams();
  const { user, logout } = useAuthStore();
  const [chats, setChats] = useState<ChatDTO[]>([]);
  const [creating, setCreating] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  // id чата для которого открыто контекстное меню действий (скрыть / удалить).
  // Только одно меню открыто одновременно — упрощает закрытие по outside-click.
  const [chatMenuOpenId, setChatMenuOpenId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Закрываем меню профиля по клику снаружи
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, []);

  // Закрываем chat-context-меню по клику снаружи. Используем capture-фазу
  // чтобы клики по другим item'ам тоже закрывали меню до их собственного хендлера.
  useEffect(() => {
    if (!chatMenuOpenId) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (target.closest(`[data-chat-menu="${chatMenuOpenId}"]`)) return;
      setChatMenuOpenId(null);
    }
    document.addEventListener("click", onDocClick, true);
    return () => document.removeEventListener("click", onDocClick, true);
  }, [chatMenuOpenId]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api.chats.list().then((r) => {
      if (!cancelled) setChats(r.chats);
    });
    return () => {
      cancelled = true;
    };
  }, [user, reloadKey, activeChatId]);

  async function handleNewChat() {
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

  return (
    <aside className={styles.sidebar}>
      {/* Логотип сверху */}
      <div className={styles.brand}>
        <Link href="/chat" className={styles.brandLink}>
          <Logomark size={20} caption={false} />
        </Link>
      </div>

      {/* Кнопка «новый чат» */}
      <button
        className={styles.newChat}
        onClick={handleNewChat}
        disabled={creating}
      >
        <span className={styles.plus}>+</span>
        <span>{creating ? "создаём…" : "новый чат"}</span>
      </button>

      {/* Список чатов */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <span>история</span>
          <span className={styles.count}>{chats.length}</span>
        </div>
        {chats.length === 0 ? (
          <div className={styles.empty}>пока пусто</div>
        ) : (
          <ul className={styles.list}>
            {chats.map((c) => {
              const isActive = c.id === activeChatId;
              const isMenuOpen = chatMenuOpenId === c.id;
              return (
                <li
                  key={c.id}
                  className={styles.itemWrap}
                  data-chat-menu={c.id}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setChatMenuOpenId(isMenuOpen ? null : c.id);
                  }}
                >
                  <Link
                    href={`/chat/${c.id}`}
                    className={`${styles.item} ${isActive ? styles.itemActive : ""}`}
                    title={c.title}
                  >
                    <span className={styles.itemTitle}>{c.title}</span>
                    {c.agent_mode && (
                      <span className={styles.itemAgent} title="агентный режим">
                        ◉
                      </span>
                    )}
                  </Link>
                  <button
                    className={styles.itemMenuBtn}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      setChatMenuOpenId(isMenuOpen ? null : c.id);
                    }}
                    title="действия"
                  >
                    ⋯
                  </button>
                  {isMenuOpen && (
                    <div
                      className={styles.chatMenu}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        className={styles.chatMenuItem}
                        onClick={async () => {
                          setChatMenuOpenId(null);
                          try {
                            await api.chats.hide(c.id);
                            setChats((prev) => prev.filter((x) => x.id !== c.id));
                            if (c.id === activeChatId) router.push("/chat");
                          } catch (e) {
                            alert(`Не удалось скрыть: ${e instanceof Error ? e.message : ""}`);
                          }
                        }}
                      >
                        <span className={styles.menuIcon}>◎</span>
                        <span>скрыть из истории</span>
                      </button>
                      <button
                        className={`${styles.chatMenuItem} ${styles.chatMenuDanger}`}
                        onClick={async () => {
                          setChatMenuOpenId(null);
                          if (
                            !confirm(
                              `Удалить чат «${c.title}» НАВСЕГДА?\n\nЭто также удалит все сообщения, артефакты и контейнер-песочницу. Восстановить нельзя.`,
                            )
                          )
                            return;
                          try {
                            await api.chats.delete(c.id);
                            setChats((prev) => prev.filter((x) => x.id !== c.id));
                            if (c.id === activeChatId) router.push("/chat");
                          } catch (e) {
                            alert(`Не удалось удалить: ${e instanceof Error ? e.message : ""}`);
                          }
                        }}
                      >
                        <span className={styles.menuIcon}>✕</span>
                        <span>удалить навсегда</span>
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Профиль внизу */}
      <div className={styles.profile} ref={menuRef}>
        {menuOpen && (
          <div className={styles.profileMenu}>
            <Link href="/settings" className={styles.menuItem}>
              <span className={styles.menuIcon}>⚙</span>
              <span>настройки</span>
            </Link>
            {user?.is_superuser && (
              <Link href="/admin" className={styles.menuItem}>
                <span className={styles.menuIcon}>※</span>
                <span>админ-панель</span>
              </Link>
            )}
            <div className={styles.menuRule} />
            <button
              className={`${styles.menuItem} ${styles.menuItemDanger}`}
              onClick={async () => {
                await logout();
                router.replace("/auth/login");
              }}
            >
              <span className={styles.menuIcon}>⏻</span>
              <span>выйти</span>
            </button>
          </div>
        )}

        <button
          className={styles.profileButton}
          onClick={() => setMenuOpen((v) => !v)}
        >
          <Avatar
            email={user?.email ?? "?"}
            size={28}
            borderColor={user?.is_superuser ? "var(--yellow)" : "var(--red)"}
          />
          <div className={styles.profileText}>
            <div className={styles.profileEmail}>
              {(user?.email ?? "").split("@")[0]}@khasa
            </div>
            <div className={styles.profileRole}>
              {user?.is_superuser ? "admin · pro" : "user · pro"}
            </div>
          </div>
          <span className={styles.profileDots}>⋯</span>
        </button>
      </div>
    </aside>
  );
}
