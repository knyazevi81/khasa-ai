import styles from "./TerminalLog.module.css";

export interface LogLine {
  color?: string;
  text: string;
}

interface Props {
  lines: LogLine[];
  cursor?: boolean;
}

/**
 * Терминальный «лог»: набор строк с цветными префиксами + опциональный
 * мигающий курсор в конце.
 */
export function TerminalLog({ lines, cursor }: Props) {
  return (
    <div className={styles.wrap}>
      {lines.map((l, i) => (
        <div key={i} className={styles.line} style={{ color: l.color || "var(--text)" }}>
          {l.text || "\u00A0"}
        </div>
      ))}
      {cursor && <span className={styles.cursor} />}
    </div>
  );
}

interface NoteProps {
  label?: string;
  accent?: string;
  children: React.ReactNode;
}

export function Note({ label = "// заметка", accent = "var(--yellow)", children }: NoteProps) {
  return (
    <div
      className={styles.note}
      style={{ borderLeftColor: accent }}
    >
      <div className={styles.label} style={{ color: accent }}>
        {label}
      </div>
      <div>{children}</div>
    </div>
  );
}
