import { KHASA } from "@/styles/tokens";
import styles from "./Logomark.module.css";

interface Props {
  size?: number;
  caption?: boolean;
}

/**
 * Терминальный леттермарк khasa: три цветных квадратика + моноширинное «khasa».
 * Используется на auth-экранах и в шапках.
 */
export function Logomark({ size = 56, caption = true }: Props) {
  const dotSize = Math.round(size * 0.22);
  const dotGap = Math.round(size * 0.04);
  return (
    <div className={styles.wrap}>
      <div className={styles.row} style={{ gap: size * 0.18 }}>
        <div className={styles.dots} style={{ gap: dotGap }}>
          <span
            className={styles.dot}
            style={{ width: dotSize, height: dotSize, background: KHASA.red }}
          />
          <span
            className={styles.dot}
            style={{ width: dotSize, height: dotSize, background: KHASA.yellow }}
          />
          <span
            className={styles.dot}
            style={{ width: dotSize, height: dotSize, background: KHASA.green }}
          />
        </div>
        <div className={styles.text} style={{ fontSize: size }}>
          khasa
        </div>
      </div>
      {caption && (
        <div className={styles.caption} style={{ fontSize: size * 0.13 }}>
          // умный ассистент
        </div>
      )}
    </div>
  );
}

/** Маленькая версия для шапок. */
export function LogomarkSmall() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span style={{ width: 7, height: 7, background: KHASA.red }} />
        <span style={{ width: 7, height: 7, background: KHASA.yellow }} />
        <span style={{ width: 7, height: 7, background: KHASA.green }} />
      </div>
      <div
        style={{
          fontFamily: "var(--mono)",
          fontWeight: 700,
          fontSize: 18,
          color: "var(--text)",
          letterSpacing: "-0.04em",
        }}
      >
        khasa
      </div>
    </div>
  );
}
