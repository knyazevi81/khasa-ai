"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logomark } from "@/components/common/Logomark";
import { WindowChrome } from "@/components/common/WindowChrome";
import { TerminalLog, Note, type LogLine } from "@/components/common/TerminalLog";
import styles from "./AuthShell.module.css";

interface Props {
  /** Логические линии для левого терминального лога */
  logTitle?: string;
  logLines?: LogLine[];
  note?: React.ReactNode;
  /** Заголовок (jsx, чтобы можно было покрасить часть в жёлтый) */
  title: React.ReactNode;
  subtitle?: string;
  /** Контент формы справа */
  children: React.ReactNode;
  /** Показывать ли табы login/register сверху правой колонки */
  tabs?: "login" | "register" | null;
  /** Текст «шага» в правом верхнем углу окна */
  step?: string;
}

const DEFAULT_LINES: LogLine[] = [
  { color: "var(--dim)", text: "# session boot" },
  { color: "var(--muted)", text: "[runtime] ядро загружено" },
  { color: "var(--muted)", text: "[runtime] требуется аутентификация" },
  { color: "var(--muted)", text: "[runtime] ожидаю учётные данные..." },
];

/**
 * Общий каркас всех auth-экранов: window chrome + терминальный лог слева,
 * заголовок и форма справа.
 */
export function AuthShell({
  logTitle = "~/khasa/session.log",
  logLines = DEFAULT_LINES,
  note,
  title,
  subtitle,
  tabs,
  step,
  children,
}: Props) {
  const pathname = usePathname();

  return (
    <div className={styles.root}>
      <WindowChrome title="khasa — auth" right={step ?? "~/khasa"} />

      <aside className={styles.left}>
        <div style={{ marginBottom: 28 }}>
          <Logomark size={56} caption={false} />
        </div>

        <div className={styles.logPath}>{logTitle}</div>

        <div style={{ marginBottom: 24 }}>
          <TerminalLog lines={logLines} />
        </div>

        {note && <div style={{ marginBottom: 18 }}>{note}</div>}

        <div style={{ flex: 1 }} />

        <div className={styles.foot}>
          <span>v0.1.0 · 2026</span>
          <span>esc to cancel</span>
        </div>
      </aside>

      <main className={styles.right}>
        {tabs && (
          <div className={styles.tabs}>
            <Link
              href="/auth/login"
              className={`${styles.tab} ${
                tabs === "login" || pathname?.startsWith("/auth/login")
                  ? styles.active
                  : ""
              }`}
            >
              вход
            </Link>
            <Link
              href="/auth/register"
              className={`${styles.tab} ${
                tabs === "register" || pathname?.startsWith("/auth/register")
                  ? styles.active
                  : ""
              }`}
            >
              регистрация
            </Link>
          </div>
        )}

        <h1 className={styles.title}>{title}</h1>
        {subtitle && <p className={styles.subtitle}>{subtitle}</p>}

        {children}
      </main>
    </div>
  );
}

export { Note };
