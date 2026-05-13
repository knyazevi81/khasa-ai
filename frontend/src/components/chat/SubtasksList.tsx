"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import styles from "./SubtasksList.module.css";

interface Subtask {
  id: string;
  order_index: number;
  title: string;
  status: "pending" | "running" | "done" | "failed";
}

interface Props {
  chatId: string;
  messageId: string;
  /**
   * Триггер для перезагрузки. Передавайте `streaming` или статус сообщения —
   * чтобы как только стрим закончится, список перечитался.
   */
  reloadKey: string | number | boolean;
}

const STATUS_ICONS: Record<Subtask["status"], string> = {
  pending: "○",
  running: "◐",
  done: "●",
  failed: "✕",
};

/**
 * Лента подзадач агентного режима. Подгружается по REST (не по WS, чтобы не
 * усложнять протокол) с пуллом по `reloadKey`.
 */
export function SubtasksList({ chatId, messageId, reloadKey }: Props) {
  const [subtasks, setSubtasks] = useState<Subtask[]>([]);

  useEffect(() => {
    let cancelled = false;
    api.chats
      .subtasks(chatId, messageId)
      .then((r) => {
        if (!cancelled) setSubtasks(r.subtasks);
      })
      .catch(() => {
        /* пусто — не показываем секцию */
      });
    return () => {
      cancelled = true;
    };
  }, [chatId, messageId, reloadKey]);

  if (subtasks.length === 0) return null;

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>// план агента · {subtasks.length} шагов</div>
      <ol className={styles.list}>
        {subtasks.map((s) => (
          <li key={s.id} className={`${styles.item} ${styles[`status_${s.status}`]}`}>
            <span className={styles.icon}>{STATUS_ICONS[s.status]}</span>
            <span className={styles.title}>{s.title}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
