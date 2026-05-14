"use client";

import { useEffect } from "react";
import type { MessageDTO } from "@/lib/chat-types";
import { GraphView } from "./GraphView";
import styles from "./GraphOverlay.module.css";

interface Props {
  open: boolean;
  onClose: () => void;
  messages: MessageDTO[];
  currentMessageId: string | null;
  onNodeClick?: (id: string) => void;
  onNodeContextMenu?: (e: React.MouseEvent, id: string) => void;
  branchCount: number;
}

/**
 * Граф диалога в попап-оверлее. Открывается из шапки чата (кнопка BranchIcon).
 * Закрывается по `Esc`, клику на оверлей или кнопке `×`.
 *
 * Когда закрыт — на кнопке-триггере висит счётчик веток (см. ChatHeaderActions).
 */
export function GraphOverlay({
  open,
  onClose,
  messages,
  currentMessageId,
  onNodeClick,
  onNodeContextMenu,
  branchCount,
}: Props) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className={styles.scrim} onClick={onClose}>
      <div className={styles.window} onClick={(e) => e.stopPropagation()}>
        <header className={styles.header}>
          <span className={styles.dot} style={{ background: "var(--yellow)" }} />
          <span className={styles.title}>граф диалога</span>
          <span className={styles.divider}>·</span>
          <span className={styles.subtitle}>
            {branchCount} {plural(branchCount, "ветка", "ветки", "веток")}
          </span>
          <span style={{ flex: 1 }} />
          <span className={styles.hint}>
            клик — переключить · правый клик — форк
          </span>
          <button className={styles.close} onClick={onClose} aria-label="закрыть">
            ×
          </button>
        </header>

        <div className={styles.canvas}>
          <GraphView
            messages={messages}
            currentMessageId={currentMessageId}
            onNodeClick={onNodeClick}
            onNodeContextMenu={onNodeContextMenu}
          />
        </div>

        <footer className={styles.legend}>
          <span className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: "var(--text)" }} />
            main
          </span>
          <span className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: "var(--yellow)" }} />
            ветка A
          </span>
          <span className={styles.legendItem}>
            <span className={styles.swatch} style={{ background: "var(--green)" }} />
            ветка B
          </span>
          <span style={{ flex: 1 }} />
          <span className={styles.legendItem}>
            <span className={styles.swatchSq} />
            вы
          </span>
          <span className={styles.legendItem}>
            <span className={styles.swatchCi} />
            khasa
          </span>
        </footer>
      </div>
    </div>
  );
}

function plural(n: number, one: string, few: string, many: string) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}
