import { KHASA } from "@/styles/tokens";
import styles from "./WindowChrome.module.css";

interface Props {
  title?: string;
  right?: string;
}

/**
 * Терминальная «шапка окна» — три цветных кружка + заголовок.
 * Используется на auth/onboarding-экранах.
 */
export function WindowChrome({ title = "khasa", right }: Props) {
  return (
    <div className={styles.chrome}>
      <span className={styles.dot} style={{ background: KHASA.red }} />
      <span className={styles.dot} style={{ background: KHASA.yellow }} />
      <span className={styles.dot} style={{ background: KHASA.green }} />
      <span className={styles.title}>{title}</span>
      {right && <span className={styles.right}>{right}</span>}
    </div>
  );
}
